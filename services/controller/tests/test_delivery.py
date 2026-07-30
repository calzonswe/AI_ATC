import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from delivery import ClearanceDeliveryController
from factory import ControllerFactory
from models import (
    ControllerPosition,
    CraftClearance,
    DeliveryState,
    HoldingInstruction,
    MissedApproachProcedure,
)


@pytest.fixture
def delv():
    return ClearanceDeliveryController("ESSA_DEL", 121.95, "ESSA_DEL", "ESSA")


# ──────────────────────────────────────────────
# State and Dataclass Basics
# ──────────────────────────────────────────────

class TestDeliveryState:
    def test_delivery_state_values(self):
        assert DeliveryState.IDLE.value == "idle"
        assert DeliveryState.CLEARANCE_ISSUED.value == "clearance_issued"
        assert DeliveryState.READBACK_PENDING.value == "readback_pending"
        assert DeliveryState.READBACK_VERIFIED.value == "readback_verified"
        assert DeliveryState.RELEASED.value == "released"

    def test_controller_position(self):
        assert ControllerPosition.DELIVERY.value == "delivery"


class TestCraftClearanceDataclass:
    def test_create(self):
        c = CraftClearance(
            callsign="SAS901",
            destination="EKCH",
            sid_name="ARN1A",
            initial_altitude_ft=6000,
            departure_frequency_mhz=124.3,
            squawk="4321",
        )
        assert c.callsign == "SAS901"
        assert c.destination == "EKCH"
        assert c.sid_name == "ARN1A"
        assert c.initial_altitude_ft == 6000
        assert c.departure_frequency_mhz == 124.3
        assert c.squawk == "4321"

    def test_create_with_route_and_remarks(self):
        c = CraftClearance(
            callsign="SAS902",
            destination="ENGM",
            sid_name="NIL1B",
            initial_altitude_ft=8000,
            departure_frequency_mhz=124.3,
            squawk="5231",
            route="NIL1B NILUG P851",
            remarks="RELEASE: 15",
        )
        assert c.route == "NIL1B NILUG P851"
        assert c.remarks == "RELEASE: 15"


class TestHoldingInstructionDataclass:
    def test_create(self):
        h = HoldingInstruction(
            callsign="SAS901",
            fix="MAKUR",
            altitude_ft=5000,
        )
        assert h.callsign == "SAS901"
        assert h.fix == "MAKUR"
        assert h.altitude_ft == 5000
        assert h.leg_direction == "left"
        assert h.leg_length == "1 minute"

    def test_create_full(self):
        h = HoldingInstruction(
            callsign="SAS901",
            fix="MAKUR",
            altitude_ft=5000,
            leg_direction="right",
            inbound_heading=45.0,
            outbound_heading=225.0,
            leg_length="2 minutes",
            expected_approach_time="13:30",
        )
        assert h.leg_direction == "right"
        assert h.inbound_heading == 45.0
        assert h.outbound_heading == 225.0
        assert h.leg_length == "2 minutes"
        assert h.expected_approach_time == "13:30"


class TestMissedApproachProcedureDataclass:
    def test_create(self):
        m = MissedApproachProcedure(
            callsign="SAS901",
            missed_approach_point="RWY01L",
            climb_to_altitude_ft=3000,
            heading=25.0,
            contact_frequency_mhz=124.3,
            instructions="contact departure",
        )
        assert m.callsign == "SAS901"
        assert m.missed_approach_point == "RWY01L"
        assert m.climb_to_altitude_ft == 3000
        assert m.heading == 25.0
        assert m.contact_frequency_mhz == 124.3
        assert m.instructions == "contact departure"


# ──────────────────────────────────────────────
# CRAFT Clearance Issuance
# ──────────────────────────────────────────────

class TestCraftClearanceIssuance:
    def test_issue_clearance(self, delv):
        c = delv.issue_craft_clearance(
            "SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321",
        )
        assert isinstance(c, CraftClearance)
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.CLEARANCE_ISSUED
        assert delv.is_controlling("SAS901")

    def test_issue_clearance_stores_clearance(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        c = delv.get_craft_clearance("SAS901")
        assert c is not None
        assert c.destination == "EKCH"
        assert c.sid_name == "ARN1A"

    def test_issue_clearance_issues_command(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        cmds = delv.get_pending_commands()
        assert len(cmds) == 1
        cmd = cmds[0]
        assert cmd.command_type == "craft_clearance"
        assert cmd.target_callsign == "SAS901"

    def test_clearance_content_destination(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        cmds = delv.get_pending_commands()
        instr = cmds[0].data.get("instruction", "")
        assert "EKCH" in instr

    def test_clearance_content_sid(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        cmds = delv.get_pending_commands()
        instr = cmds[0].data.get("instruction", "")
        assert "ARN1A" in instr

    def test_clearance_content_altitude(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        cmds = delv.get_pending_commands()
        instr = cmds[0].data.get("instruction", "")
        assert "6000" in instr

    def test_clearance_content_frequency(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        cmds = delv.get_pending_commands()
        instr = cmds[0].data.get("instruction", "")
        assert "124.3" in instr

    def test_clearance_content_squawk(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        cmds = delv.get_pending_commands()
        instr = cmds[0].data.get("instruction", "")
        assert "4321" in instr

    def test_clearance_content_route(self, delv):
        delv.issue_craft_clearance(
            "SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321",
            route="ARN1A NILUG P851",
        )
        cmds = delv.get_pending_commands()
        instr = cmds[0].data.get("instruction", "")
        assert "ARN1A NILUG P851" in instr

    def test_clearance_content_remarks(self, delv):
        delv.issue_craft_clearance(
            "SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321",
            remarks="RELEASE: 15",
        )
        cmds = delv.get_pending_commands()
        instr = cmds[0].data.get("instruction", "")
        assert "RELEASE: 15" in instr

    def test_clearance_sets_clearance_state(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        cs = delv.get_clearance_state("SAS901")
        assert cs is not None
        assert cs.clearance_type == "craft_clearance"
        assert cs.issued_by == "ESSA_DEL"

    def test_multiple_aircraft_clearances(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.issue_craft_clearance("SAS902", "ENGM", "NIL1B", 8000, 124.3, "5231")
        assert delv.is_controlling("SAS901")
        assert delv.is_controlling("SAS902")
        c1 = delv.get_craft_clearance("SAS901")
        c2 = delv.get_craft_clearance("SAS902")
        assert c1.destination == "EKCH"
        assert c2.destination == "ENGM"

    def test_settle_for_clearance(self, delv):
        delv.issue_craft_clearance(
            "SAS901", "KLAX", "DAG9", 17000, 124.3, "6543",
            route="DAG9 DAG P52 HEC",
            remarks="CT-1234",
        )
        cmds = delv.get_pending_commands()
        instr = cmds[0].data.get("instruction", "")
        assert "SAS901" in instr
        assert "KLAX" in instr
        assert "DAG9" in instr
        assert "17000" in instr
        assert "124.3" in instr
        assert "6543" in instr
        assert "CT-1234" in instr


# ──────────────────────────────────────────────
# Readback Verification
# ──────────────────────────────────────────────

class TestReadbackVerification:
    def test_request_readback(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.READBACK_PENDING

    def test_request_readback_issues_command(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        cmds = delv.get_pending_commands()
        assert any("read back" in c.data.get("instruction", "") for c in cmds)

    def test_request_readback_only_from_clearance_issued(self, delv):
        delv.request_readback("SAS901")
        assert delv.get_aircraft_delivery_state("SAS901") is None

    def test_verify_correct_readback(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        result = delv.verify_readback(
            "SAS901",
            "Cleared to EKCH via ARN1A, climb to 6000, squawk 4321",
        )
        assert result is True

    def test_verify_correct_readback_changes_state(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        delv.verify_readback(
            "SAS901",
            "Cleared to EKCH via ARN1A, climb to 6000, squawk 4321",
        )
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.READBACK_VERIFIED

    def test_verify_correct_readback_issues_ok(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        delv.verify_readback(
            "SAS901",
            "Cleared to EKCH via ARN1A, climb to 6000, squawk 4321",
        )
        cmds = delv.get_pending_commands()
        assert any("readback correct" in c.data.get("instruction", "") for c in cmds)

    def test_verify_incorrect_readback(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        result = delv.verify_readback(
            "SAS901",
            "Cleared to ENGM via some route",
        )
        assert result is False

    def test_verify_incorrect_readback_stays_pending(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        delv.verify_readback("SAS901", "Cleared to ENGM via some route")
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.READBACK_PENDING

    def test_verify_incorrect_readback_issues_error(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        delv.verify_readback("SAS901", "Wrong readback")
        cmds = delv.get_pending_commands()
        assert any("readback incorrect" in c.data.get("instruction", "") for c in cmds)

    def test_verify_readback_not_pending(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        result = delv.verify_readback("SAS901", "Cleared to EKCH via ARN1A")
        assert result is False

    def test_verify_readback_no_clearance(self, delv):
        delv._aircraft_states["SAS901"] = DeliveryState.READBACK_PENDING
        result = delv.verify_readback("SAS901", "anything")
        assert result is False

    def test_readback_accepts_variations(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        result = delv.verify_readback(
            "SAS901",
            "Roger, cleared to EKCH airport via ARN1A departure, climb 6000 feet, squawk 4321",
        )
        assert result is True

    def test_is_readback_verified_true(self, delv):
        delv._aircraft_states["SAS901"] = DeliveryState.READBACK_VERIFIED
        assert delv.is_readback_verified("SAS901") is True

    def test_is_readback_verified_false(self, delv):
        assert delv.is_readback_verified("SAS901") is False
        delv._aircraft_states["SAS901"] = DeliveryState.CLEARANCE_ISSUED
        assert delv.is_readback_verified("SAS901") is False


# ──────────────────────────────────────────────
# Release to Ground
# ──────────────────────────────────────────────

class TestReleaseToGround:
    def test_release_to_ground(self, delv):
        delv._aircraft_states["SAS901"] = DeliveryState.READBACK_VERIFIED
        delv.accept_aircraft("SAS901")
        delv.release_to_ground("SAS901")
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.RELEASED

    def test_release_to_ground_issues_command(self, delv):
        delv._aircraft_states["SAS901"] = DeliveryState.READBACK_VERIFIED
        delv.accept_aircraft("SAS901")
        delv.release_to_ground("SAS901")
        cmds = delv.get_pending_commands()
        assert any("contact Ground" in c.data.get("instruction", "") for c in cmds)

    def test_release_to_ground_proposes_handoff(self, delv):
        delv._aircraft_states["SAS901"] = DeliveryState.READBACK_VERIFIED
        delv.accept_aircraft("SAS901")
        delv.release_to_ground("SAS901")
        handoffs = delv.get_pending_handoffs()
        assert len(handoffs) == 1
        assert handoffs[0].to_controller == "ESSA_GND"

    def test_release_to_ground_only_from_readback_verified(self, delv):
        delv.release_to_ground("SAS901")
        assert delv.get_aircraft_delivery_state("SAS901") is None
        delv._aircraft_states["SAS901"] = DeliveryState.CLEARANCE_ISSUED
        delv.release_to_ground("SAS901")
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.CLEARANCE_ISSUED

    def test_release_to_ground_multiple_aircraft(self, delv):
        delv._aircraft_states["SAS901"] = DeliveryState.READBACK_VERIFIED
        delv._aircraft_states["SAS902"] = DeliveryState.READBACK_VERIFIED
        delv.accept_aircraft("SAS901")
        delv.accept_aircraft("SAS902")
        delv.release_to_ground("SAS901")
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.RELEASED
        assert delv.get_aircraft_delivery_state("SAS902") == DeliveryState.READBACK_VERIFIED


# ──────────────────────────────────────────────
# Holding Instructions
# ──────────────────────────────────────────────

class TestHoldingInstructions:
    def test_issue_holding_instruction(self, delv):
        h = delv.issue_holding_instruction("SAS901", "MAKUR", 5000)
        assert isinstance(h, HoldingInstruction)
        assert h.fix == "MAKUR"
        assert h.altitude_ft == 5000

    def test_holding_instruction_issues_command(self, delv):
        delv.issue_holding_instruction("SAS901", "MAKUR", 5000)
        cmds = delv.get_pending_commands()
        assert any("hold at MAKUR" in c.data.get("instruction", "") for c in cmds)

    def test_holding_instruction_accepts_aircraft(self, delv):
        delv.issue_holding_instruction("SAS901", "MAKUR", 5000)
        assert delv.is_controlling("SAS901")

    def test_holding_instruction_right_hand(self, delv):
        delv.issue_holding_instruction(
            "SAS901", "MAKUR", 5000, leg_direction="right",
        )
        cmds = delv.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("right-hand" in ins for ins in instrs)

    def test_holding_instruction_with_inbound_heading(self, delv):
        delv.issue_holding_instruction(
            "SAS901", "MAKUR", 5000, inbound_heading=45.0,
        )
        cmds = delv.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("inbound heading 45" in ins for ins in instrs)

    def test_holding_instruction_with_eat(self, delv):
        delv.issue_holding_instruction(
            "SAS901", "MAKUR", 5000, expected_approach_time="13:30",
        )
        cmds = delv.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("13:30" in ins for ins in instrs)

    def test_holding_instruction_custom_leg_length(self, delv):
        delv.issue_holding_instruction(
            "SAS901", "MAKUR", 5000, leg_length="2 minutes",
        )
        cmds = delv.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("2 minutes" in ins for ins in instrs)

    def test_get_holding_instruction(self, delv):
        delv.issue_holding_instruction("SAS901", "MAKUR", 5000)
        h = delv.get_holding_instruction("SAS901")
        assert h is not None
        assert h.fix == "MAKUR"

    def test_holding_instruction_sets_clearance_state(self, delv):
        delv.issue_holding_instruction("SAS901", "MAKUR", 5000)
        cs = delv.get_clearance_state("SAS901")
        assert cs is not None
        assert cs.clearance_type == "holding"


# ──────────────────────────────────────────────
# Missed Approach Procedures
# ──────────────────────────────────────────────

class TestMissedApproach:
    def test_issue_missed_approach(self, delv):
        m = delv.issue_missed_approach("SAS901", climb_to_alt_ft=3000)
        assert isinstance(m, MissedApproachProcedure)
        assert m.climb_to_altitude_ft == 3000

    def test_missed_approach_issues_command(self, delv):
        delv.issue_missed_approach("SAS901")
        cmds = delv.get_pending_commands()
        assert any("missed approach" in c.data.get("instruction", "") for c in cmds)

    def test_missed_approach_with_point(self, delv):
        delv.issue_missed_approach("SAS901", missed_point="RWY01L")
        cmds = delv.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("RWY01L" in ins for ins in instrs)

    def test_missed_approach_with_climb_alt(self, delv):
        delv.issue_missed_approach("SAS901", climb_to_alt_ft=5000)
        cmds = delv.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("5000" in ins for ins in instrs)

    def test_missed_approach_with_heading(self, delv):
        delv.issue_missed_approach("SAS901", heading=25.0)
        cmds = delv.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("heading 25" in ins for ins in instrs)

    def test_missed_approach_with_contact_frequency(self, delv):
        delv.issue_missed_approach("SAS901", contact_frequency=124.3)
        cmds = delv.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("124.3" in ins for ins in instrs)

    def test_missed_approach_with_instructions(self, delv):
        delv.issue_missed_approach("SAS901", instructions="contact departure")
        cmds = delv.get_pending_commands()
        instrs = [c.data.get("instruction", "") for c in cmds]
        assert any("contact departure" in ins for ins in instrs)

    def test_get_missed_approach_procedure(self, delv):
        delv.issue_missed_approach("SAS901", climb_to_alt_ft=3000)
        m = delv.get_missed_approach_procedure("SAS901")
        assert m is not None
        assert m.climb_to_altitude_ft == 3000

    def test_cancel_missed_approach(self, delv):
        delv.issue_missed_approach("SAS901")
        delv.get_pending_commands()
        delv.cancel_missed_approach("SAS901")
        assert delv.get_missed_approach_procedure("SAS901") is None
        cmds = delv.get_pending_commands()
        assert any("missed approach cancelled" in c.data.get("instruction", "") for c in cmds)

    def test_cancel_nonexistent(self, delv):
        delv.cancel_missed_approach("SAS901")
        cmds = delv.get_pending_commands()
        assert any("missed approach cancelled" in c.data.get("instruction", "") for c in cmds)


# ──────────────────────────────────────────────
# Release Aircraft
# ──────────────────────────────────────────────

class TestReleaseAircraft:
    def test_release_aircraft_cleans_up(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.issue_holding_instruction("SAS901", "MAKUR", 5000)
        delv.issue_missed_approach("SAS901")
        assert delv.is_controlling("SAS901")
        delv.release_aircraft("SAS901")
        assert not delv.is_controlling("SAS901")
        assert delv.get_craft_clearance("SAS901") is None
        assert delv.get_holding_instruction("SAS901") is None
        assert delv.get_missed_approach_procedure("SAS901") is None
        assert delv.get_aircraft_delivery_state("SAS901") is None

    def test_release_aircraft_revokes_clearance(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.release_aircraft("SAS901")
        cs = delv.get_clearance_state("SAS901")
        assert cs is None or not cs.is_active

    def test_release_aircraft_not_controlling(self, delv):
        result = delv.release_aircraft("SAS901")
        assert result is False

    def test_release_aircraft_double_release(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.release_aircraft("SAS901")
        result = delv.release_aircraft("SAS901")
        assert result is False


# ──────────────────────────────────────────────
# Full Workflow Integration
# ──────────────────────────────────────────────

class TestFullClearanceWorkflow:
    def test_full_workflow(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.CLEARANCE_ISSUED
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.READBACK_PENDING
        delv.get_pending_commands()
        ok = delv.verify_readback(
            "SAS901",
            "Cleared to EKCH via ARN1A, climb to 6000, squawk 4321",
        )
        assert ok is True
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.READBACK_VERIFIED
        delv.get_pending_commands()
        delv.release_to_ground("SAS901")
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.RELEASED
        cmds = delv.get_pending_commands()
        assert any("contact Ground" in c.data.get("instruction", "") for c in cmds)
        handoffs = delv.get_pending_handoffs()
        assert len(handoffs) == 1

    def test_workflow_wrong_readback_then_correct(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        ok = delv.verify_readback("SAS901", "Wrong readback")
        assert ok is False
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.READBACK_PENDING
        delv.get_pending_commands()
        ok = delv.verify_readback(
            "SAS901",
            "Cleared to EKCH via ARN1A, climb to 6000, squawk 4321",
        )
        assert ok is True
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.READBACK_VERIFIED

    def test_workflow_multiple_aircraft(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.issue_craft_clearance("SAS902", "ENGM", "NIL1B", 8000, 124.3, "5231")
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        delv.verify_readback(
            "SAS901",
            "Cleared to EKCH via ARN1A, climb to 6000, squawk 4321",
        )
        delv.get_pending_commands()
        delv.release_to_ground("SAS901")
        delv.get_pending_commands()
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.RELEASED
        assert delv.get_aircraft_delivery_state("SAS902") == DeliveryState.CLEARANCE_ISSUED
        delv.request_readback("SAS902")
        delv.get_pending_commands()
        delv.verify_readback(
            "SAS902",
            "Cleared to ENGM via NIL1B, climb to 8000, squawk 5231",
        )
        assert delv.is_readback_verified("SAS902") is True

    def test_full_workflow_with_route_and_remarks(self, delv):
        delv.issue_craft_clearance(
            "SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321",
            route="ARN1A NILUG P851",
            remarks="RELEASE: 15",
        )
        delv.get_pending_commands()
        delv.request_readback("SAS901")
        delv.get_pending_commands()
        ok = delv.verify_readback(
            "SAS901",
            "Cleared to EKCH via ARN1A NILUG P851, climb to 6000, squawk 4321",
        )
        assert ok is True
        delv.get_pending_commands()
        delv.release_to_ground("SAS901")
        assert delv.get_aircraft_delivery_state("SAS901") == DeliveryState.RELEASED

    def test_workflow_holding_after_clearance(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.issue_holding_instruction("SAS901", "MAKUR", 5000, leg_direction="right")
        assert delv.get_holding_instruction("SAS901") is not None
        cmds = delv.get_pending_commands()
        assert any("MAKUR" in c.data.get("instruction", "") for c in cmds)

    def test_workflow_missed_approach_after_clearance(self, delv):
        delv.issue_craft_clearance("SAS901", "EKCH", "ARN1A", 6000, 124.3, "4321")
        delv.get_pending_commands()
        delv.issue_missed_approach("SAS901", climb_to_alt_ft=3000, heading=25.0)
        assert delv.get_missed_approach_procedure("SAS901") is not None
        cmds = delv.get_pending_commands()
        assert any("missed approach" in c.data.get("instruction", "") for c in cmds)


# ──────────────────────────────────────────────
# Factory Integration
# ──────────────────────────────────────────────

class TestDeliveryFactory:
    def test_factory_create_delivery(self):
        ctrl = ControllerFactory.create(
            ControllerPosition.DELIVERY,
            "KLAX_DEL", 121.95, "KLAX_DEL",
            airport_icao="KLAX",
        )
        assert isinstance(ctrl, ClearanceDeliveryController)
        assert ctrl.callsign == "KLAX_DEL"
        assert ctrl.frequency == 121.95
        assert ctrl.airport_icao == "KLAX"

    def test_factory_create_delivery_requires_airport(self):
        with pytest.raises(ValueError, match="airport_icao"):
            ControllerFactory.create(
                ControllerPosition.DELIVERY,
                "TEST_DEL", 121.95, "TEST_DEL",
            )

    def test_factory_create_all_airport_includes_delivery(self):
        controllers = ControllerFactory.create_all_for_airport("ESSA")
        assert ControllerPosition.DELIVERY in controllers
        ctrl = controllers[ControllerPosition.DELIVERY]
        assert isinstance(ctrl, ClearanceDeliveryController)
        assert ctrl.callsign == "ESSA_DEL"

    def test_factory_create_all_airport_custom_frequency(self):
        controllers = ControllerFactory.create_all_for_airport(
            "ESSA",
            frequencies={"delivery": 121.7},
        )
        ctrl = controllers[ControllerPosition.DELIVERY]
        assert ctrl.frequency == 121.7


# ──────────────────────────────────────────────
# Process Method
# ──────────────────────────────────────────────

class TestDeliveryProcess:
    def test_process_noop(self, delv):
        delv.process(1.0, {})
        assert len(delv.get_pending_commands()) == 0
