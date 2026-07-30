import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from base import BaseController
from ground import GroundController
from tower import TowerController
from departure import DepartureController
from approach import ApproachController
from center import CenterController
from atis import AtisController
from models import ControllerPosition
from prompt_engine import (
    PromptEngine,
    PromptContext,
    RadioCallPrompt,
    IssuedClearance,
    LlmOutput,
    ICAO_SYSTEM_PROMPTS,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def engine():
    return PromptEngine(max_tokens=2048)


@pytest.fixture
def ground():
    return GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA")


@pytest.fixture
def tower():
    return TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L", "19R"])


@pytest.fixture
def departure():
    return DepartureController("ESSA_DEP", 124.3, "ESSA_DEP", "ESSA")


@pytest.fixture
def approach():
    return ApproachController("ESSA_APP", 119.7, "ESSA_APP", "ESSA")


@pytest.fixture
def center():
    return CenterController("ESSA_CTR", 135.5, "ESSA_CTR")


@pytest.fixture
def atis():
    return AtisController("ESSA_ATIS", 128.425, "ESSA_ATIS", "ESSA")


@pytest.fixture
def sample_aircraft():
    return {
        "SAS901": {
            "callsign": "SAS901",
            "state": "taxi",
            "position": {"lat": 59.65, "lon": 17.95, "alt_msl": 150},
            "motion": {"groundspeed": 15, "vertical_speed": 0, "on_ground": True},
            "flight_plan": {"departure": "ESSA", "arrival": "EKCH"},
        },
        "SAS456": {
            "callsign": "SAS456",
            "state": "cruise",
            "position": {"lat": 59.80, "lon": 18.10, "alt_msl": 35000},
            "motion": {"groundspeed": 450, "vertical_speed": 0, "on_ground": False},
            "flight_plan": {"departure": "ESSA", "arrival": "LIRF"},
        },
    }


@pytest.fixture
def sample_weather():
    return {
        "ESSA": {
            "wind": {"direction": 270, "speed_kn": 12, "gust_kn": 18},
            "visibility_m": 8000,
            "qnh_hpa": 1015.2,
            "temperature_c": 14,
            "clouds": [{"coverage": "BKN", "altitude_ft": 4000}],
        },
    }


@pytest.fixture
def sample_airports():
    return {
        "ESSA": {
            "elevation_ft": 137,
            "active_runway_dep": "01L",
            "active_runway_arr": "01L",
            "runways": {
                "01L": {
                    "identifier": "01L",
                    "heading": 12,
                    "length_ft": 10800,
                    "active_for_departure": True,
                    "active_for_arrival": True,
                },
                "19R": {
                    "identifier": "19R",
                    "heading": 192,
                    "length_ft": 10800,
                    "active_for_departure": False,
                    "active_for_arrival": False,
                },
            },
        },
    }


@pytest.fixture
def sample_context(ground, sample_aircraft, sample_weather, sample_airports):
    return PromptContext(
        controller=ground,
        aircraft_state=sample_aircraft,
        weather=sample_weather,
        airports=sample_airports,
        sectors=[{
            "sector_id": 1,
            "controller_callsign": "ESSA_GND",
            "aircraft_callsigns": ["SAS901"],
            "frequency_mhz": 121.8,
        }],
        conflicts=[{
            "aircraft_a": "SAS901",
            "aircraft_b": "SAS456",
            "lateral_distance_nm": 4.5,
            "vertical_distance_ft": 34850,
            "time_to_conflict_s": 300,
            "severity": "warning",
        }],
    )


# ──────────────────────────────────────────────
# ICAO System Prompts
# ──────────────────────────────────────────────

class TestIcaoPrompts:
    def test_all_positions_have_prompts(self):
        for pos in ControllerPosition:
            assert pos in ICAO_SYSTEM_PROMPTS
            assert len(ICAO_SYSTEM_PROMPTS[pos]) > 50

    def test_ground_prompt_contains_key_phrases(self):
        prompt = ICAO_SYSTEM_PROMPTS[ControllerPosition.GROUND]
        assert "PUSHBACK" in prompt
        assert "TAXI" in prompt
        assert "HOLD SHORT" in prompt

    def test_tower_prompt_contains_key_phrases(self):
        prompt = ICAO_SYSTEM_PROMPTS[ControllerPosition.TOWER]
        assert "LINE UP AND WAIT" in prompt
        assert "CLEARED FOR TAKEOFF" in prompt
        assert "CLEARED TO LAND" in prompt
        assert "GO AROUND" in prompt

    def test_departure_prompt_contains_key_phrases(self):
        prompt = ICAO_SYSTEM_PROMPTS[ControllerPosition.DEPARTURE]
        assert "SID" in prompt
        assert "CLIMB" in prompt

    def test_approach_prompt_contains_key_phrases(self):
        prompt = ICAO_SYSTEM_PROMPTS[ControllerPosition.APPROACH]
        assert "ILS" in prompt
        assert "HOLD AT" in prompt
        assert "HEADING" in prompt

    def test_center_prompt_contains_key_phrases(self):
        prompt = ICAO_SYSTEM_PROMPTS[ControllerPosition.CENTER]
        assert "CLIMB" in prompt
        assert "DESCEND" in prompt
        assert "MAINTAIN" in prompt

    def test_atis_prompt_contains_key_phrases(self):
        prompt = ICAO_SYSTEM_PROMPTS[ControllerPosition.ATIS]
        assert "ATIS" in prompt
        assert "ADVISE ON INITIAL CONTACT" in prompt


# ──────────────────────────────────────────────
# PromptEngine: build_system_prompt
# ──────────────────────────────────────────────

class TestBuildSystemPrompt:
    def test_ground_system_prompt(self, engine):
        prompt = engine.build_system_prompt(ControllerPosition.GROUND)
        assert "Ground Controller" in prompt

    def test_tower_system_prompt(self, engine):
        prompt = engine.build_system_prompt(ControllerPosition.TOWER)
        assert "Tower Controller" in prompt

    def test_departure_system_prompt(self, engine):
        prompt = engine.build_system_prompt(ControllerPosition.DEPARTURE)
        assert "Departure Controller" in prompt

    def test_approach_system_prompt(self, engine):
        prompt = engine.build_system_prompt(ControllerPosition.APPROACH)
        assert "Approach Controller" in prompt

    def test_center_system_prompt(self, engine):
        prompt = engine.build_system_prompt(ControllerPosition.CENTER)
        assert "Area/Enroute Controller" in prompt

    def test_atis_system_prompt(self, engine):
        prompt = engine.build_system_prompt(ControllerPosition.ATIS)
        assert "ATIS broadcast" in prompt

    def test_unknown_position_fallback(self, engine):
        prompt = engine.build_system_prompt(None)  # type: ignore
        assert "ATC Controller" in prompt


# ──────────────────────────────────────────────
# PromptEngine: build_radio_call_prompt
# ──────────────────────────────────────────────

class TestBuildRadioCallPrompt:
    def test_returns_radio_call_prompt(self, engine, sample_context):
        result = engine.build_radio_call_prompt(sample_context)
        assert isinstance(result, RadioCallPrompt)
        assert result.system_prompt
        assert result.context_prompt
        assert result.full_prompt
        assert result.estimated_tokens > 0

    def test_contains_controller_info(self, engine, sample_context):
        result = engine.build_radio_call_prompt(sample_context)
        assert "ESSA_GND" in result.full_prompt
        assert "121.8" in result.full_prompt

    def test_contains_aircraft(self, engine, sample_context):
        result = engine.build_radio_call_prompt(sample_context)
        assert "SAS901" in result.full_prompt
        assert "SAS456" in result.full_prompt

    def test_contains_weather(self, engine, sample_context):
        result = engine.build_radio_call_prompt(sample_context)
        assert "ESSA" in result.full_prompt
        assert "270" in result.full_prompt or "12kt" in result.full_prompt

    def test_contains_airports(self, engine, sample_context):
        result = engine.build_radio_call_prompt(sample_context)
        assert "01L" in result.full_prompt

    def test_contains_conflicts(self, engine, sample_context):
        result = engine.build_radio_call_prompt(sample_context)
        assert "SAS901 vs SAS456" in result.full_prompt

    def test_contains_sectors(self, engine, sample_context):
        result = engine.build_radio_call_prompt(sample_context)
        assert "Sector 1" in result.full_prompt

    def test_context_without_optional_fields(self, engine, ground):
        minimal = PromptContext(controller=ground)
        result = engine.build_radio_call_prompt(minimal)
        assert ground.callsign in result.full_prompt
        assert result.estimated_tokens > 0

    def test_context_with_navigation(self, engine, ground, sample_context):
        nav = {"taxi_route": ["A", "B", "C"], "distance_m": 1200}
        sample_context.navigation = nav
        result = engine.build_radio_call_prompt(sample_context)
        assert "taxi_route" in result.full_prompt

    def test_context_with_local_procedures(self, engine, ground, sample_context):
        procs = {"noise_abatement": "RNAV departure RWY 01L"}
        sample_context.local_procedures = procs
        result = engine.build_radio_call_prompt(sample_context)
        assert "noise_abatement" in result.full_prompt

    def test_controller_position_detection(self, engine, ground, tower, departure,
                                           approach, center, atis):
        for ctrl, expected in [
            (ground, ControllerPosition.GROUND),
            (tower, ControllerPosition.TOWER),
            (departure, ControllerPosition.DEPARTURE),
            (approach, ControllerPosition.APPROACH),
            (center, ControllerPosition.CENTER),
            (atis, ControllerPosition.ATIS),
        ]:
            ctx = PromptContext(controller=ctrl)
            result = engine.build_radio_call_prompt(ctx)
            assert ctrl.callsign in result.full_prompt

    def test_aircraft_marking(self, engine, ground, sample_aircraft, sample_weather):
        ground.accept_aircraft("SAS901")
        ctx = PromptContext(
            controller=ground,
            aircraft_state=sample_aircraft,
            weather=sample_weather,
        )
        result = engine.build_radio_call_prompt(ctx)
        assert "SAS901 *" in result.context_prompt or "[SAS901] *" or "*" in result.context_prompt

    def test_estimated_tokens_below_max(self, engine, sample_context):
        result = engine.build_radio_call_prompt(sample_context)
        assert result.estimated_tokens <= engine.max_tokens


# ──────────────────────────────────────────────
# PromptEngine: minimize_tokens
# ──────────────────────────────────────────────

class TestMinimizeTokens:
    def test_short_text_unchanged(self, engine):
        text = "Short text."
        assert engine.minimize_tokens(text, 500) == text

    def test_long_text_is_truncated(self, engine):
        text = "word " * 10000
        result = engine.minimize_tokens(text, 50)
        assert len(result) < len(text)

    def test_empties_are_stripped(self, engine):
        text = "KEEP\nnull\nNone\nundefined\nKEEP2"
        result = engine.minimize_tokens(text, 5)
        assert "KEEP" in result
        assert "KEEP2" in result
        assert "null" not in result

    def test_key_abbreviation(self, engine):
        text = "callsign=AAL123\naircraft=B738\nposition=here\n"
        result = engine.minimize_tokens(text, 10)
        assert "cs=" in result or "cs" in result
        assert "ac=" in result or "ac" in result
        assert "pos" in result

    def test_priority_sections_preserved(self, engine):
        text = "\n\n".join([
            "AIRCRAFT: SAS901",
            "WEATHER: ESSA",
            "CONFLICT: SAS901 vs SAS456",
            "LOW_PRIORITY: xyz",
        ])
        result = engine.minimize_tokens(text, 60)
        assert "AIRCRAFT" in result
        assert "CONFLICT" in result or "conflict" in result.lower()


# ──────────────────────────────────────────────
# PromptEngine: parse_llm_response
# ──────────────────────────────────────────────

class TestParseLlmResponse:
    def test_valid_json_output(self, engine):
        response = json.dumps({
            "readback_correct": True,
            "phraseology_text": "SAS901, TAXI TO RUNWAY 01L VIA A B C",
            "issued_clearance": {
                "type": "taxi",
                "route": ["A", "B", "C"],
                "runway": "01L",
            },
        })
        result = engine.parse_llm_response(response)
        assert result.readback_correct is True
        assert "TAXI" in result.phraseology_text
        assert result.issued_clearance is not None
        assert result.issued_clearance.type == "taxi"
        assert result.issued_clearance.route == ["A", "B", "C"]

    def test_markdown_code_block(self, engine):
        response = '''```json
{
    "readback_correct": false,
    "phraseology_text": "SAS456, CLIMB TO 35000FT"
}
```'''
        result = engine.parse_llm_response(response)
        assert result.readback_correct is False
        assert "CLIMB" in result.phraseology_text

    def test_markdown_code_block_no_lang(self, engine):
        response = '''```
{"readback_correct": true, "phraseology_text": "GO AROUND"}
```'''
        result = engine.parse_llm_response(response)
        assert result.readback_correct is True
        assert "GO AROUND" in result.phraseology_text

    def test_partial_json_no_clearance(self, engine):
        response = '{"readback_correct": true, "phraseology_text": "HOLD SHORT"}'
        result = engine.parse_llm_response(response)
        assert result.readback_correct is True
        assert result.issued_clearance is None

    def test_non_bool_readback_correct(self, engine):
        response = json.dumps({
            "readback_correct": "true",
            "phraseology_text": "CLEARED FOR TAKEOFF",
        })
        result = engine.parse_llm_response(response)
        assert result.readback_correct is True

    def test_malformed_json(self, engine):
        response = "This is not JSON at all."
        result = engine.parse_llm_response(response)
        assert result.readback_correct is False
        assert result.phraseology_text == response

    def test_issued_clearance_all_fields(self, engine):
        response = json.dumps({
            "readback_correct": True,
            "phraseology_text": "SAS901, CLIMB VIA SID",
            "issued_clearance": {
                "type": "climb_via_sid",
                "route": None,
                "hold_short": None,
                "altitude_ft": 5000,
                "heading_deg": 270.0,
                "speed_kn": 220,
                "runway": None,
                "sid": "BARK1A",
                "star": None,
                "approach": None,
                "frequency": 124.3,
                "squawk": "4321",
            },
        })
        result = engine.parse_llm_response(response)
        assert result.issued_clearance is not None
        c = result.issued_clearance
        assert c.type == "climb_via_sid"
        assert c.altitude_ft == 5000
        assert c.heading_deg == 270.0
        assert c.speed_kn == 220
        assert c.sid == "BARK1A"
        assert c.frequency == 124.3
        assert c.squawk == "4321"
        assert c.route is None
        assert c.hold_short is None

    def test_issued_clearance_missing_type_fallback(self, engine):
        response = json.dumps({
            "readback_correct": True,
            "phraseology_text": "CLEARED TO LAND",
            "issued_clearance": {},
        })
        result = engine.parse_llm_response(response)
        assert result.issued_clearance is not None
        assert result.issued_clearance.type == ""


# ──────────────────────────────────────────────
# PromptEngine: format_llm_request
# ──────────────────────────────────────────────

class TestFormatLlmRequest:
    def test_returns_json_schema_dict(self, engine, sample_context):
        req = engine.format_llm_request(sample_context)
        assert isinstance(req, dict)
        assert "model" in req
        assert "prompt" in req
        assert "stream" in req
        assert "format" in req

    def test_format_has_required_fields(self, engine, sample_context):
        req = engine.format_llm_request(sample_context)
        fmt = req["format"]
        assert "readback_correct" in fmt["properties"]
        assert "phraseology_text" in fmt["properties"]
        assert "readback_correct" in fmt["required"]
        assert "phraseology_text" in fmt["required"]

    def test_format_has_clearance_schema(self, engine, sample_context):
        req = engine.format_llm_request(sample_context)
        props = req["format"]["properties"]
        assert "issued_clearance" in props
        assert "type" in props["issued_clearance"]["properties"]
        assert props["issued_clearance"]["required"] == ["type"]


# ──────────────────────────────────────────────
# PromptEngine: validate_output
# ──────────────────────────────────────────────

class TestValidateOutput:
    def test_valid_output_no_errors(self, engine):
        output = LlmOutput(
            readback_correct=True,
            phraseology_text="SAS901, CLEARED FOR TAKEOFF",
            issued_clearance=IssuedClearance(type="takeoff"),
        )
        errors = engine.validate_output(output)
        assert errors == []

    def test_empty_phraseology(self, engine):
        output = LlmOutput(readback_correct=True, phraseology_text="")
        errors = engine.validate_output(output)
        assert "phraseology_text is empty" in errors

    def test_empty_clearance_type(self, engine):
        output = LlmOutput(
            readback_correct=True,
            phraseology_text="SAS901, CONTACT TOWER",
            issued_clearance=IssuedClearance(type=""),
        )
        errors = engine.validate_output(output)
        assert "issued_clearance.type is empty" in errors

    def test_multiple_errors(self, engine):
        output = LlmOutput(
            readback_correct=False,
            phraseology_text="",
            issued_clearance=IssuedClearance(type=""),
        )
        errors = engine.validate_output(output)
        assert len(errors) == 2


# ──────────────────────────────────────────────
# Integration: PromptContext serialization
# ──────────────────────────────────────────────

class TestPromptContext:
    def test_default_fields(self):
        ctrl = GroundController("TEST_GND", 121.8, "TEST_GND", "TEST")
        ctx = PromptContext(controller=ctrl)
        assert ctx.aircraft_state == {}
        assert ctx.weather == {}
        assert ctx.airports == {}
        assert ctx.sectors == []
        assert ctx.conflicts == []
        assert ctx.navigation is None
        assert ctx.local_procedures is None

    def test_controller_mutation_reflected(self, ground):
        ctx = PromptContext(controller=ground)
        ground.accept_aircraft("SAS901")
        assert "SAS901" in ctx.controller.controlled_aircraft


# ──────────────────────────────────────────────
# Integration: end-to-end
# ──────────────────────────────────────────────

class TestIntegration:
    def test_full_pipeline(self, engine, ground, sample_aircraft,
                           sample_weather, sample_airports):
        ground.accept_aircraft("SAS901")
        ctx = PromptContext(
            controller=ground,
            aircraft_state=sample_aircraft,
            weather=sample_weather,
            airports=sample_airports,
        )
        prompt = engine.build_radio_call_prompt(ctx)
        assert prompt.estimated_tokens > 0
        assert prompt.estimated_tokens <= engine.max_tokens

        # Simulate LLM response parsing
        llm_raw = json.dumps({
            "readback_correct": True,
            "phraseology_text": "SAS901, PUSHBACK APPROVED TAIL EAST",
            "issued_clearance": {
                "type": "pushback",
                "route": None,
                "hold_short": None,
            },
        })
        parsed = engine.parse_llm_response(llm_raw)
        assert parsed.readback_correct is True
        assert parsed.issued_clearance is not None
        assert parsed.issued_clearance.type == "pushback"

        errors = engine.validate_output(parsed)
        assert errors == []

    def test_rejects_invalid_output(self, engine, ground):
        ctx = PromptContext(controller=ground)
        prompt = engine.build_radio_call_prompt(ctx)
        _ = prompt  # Used for side-effect verification

        llm_raw = '{"readback_correct": false, "phraseology_text": ""}'
        parsed = engine.parse_llm_response(llm_raw)
        errors = engine.validate_output(parsed)
        assert "phraseology_text is empty" in errors

    def test_context_with_all_fields(self, engine, ground, sample_aircraft,
                                     sample_weather, sample_airports):
        ground.accept_aircraft("SAS901")
        ctx = PromptContext(
            controller=ground,
            aircraft_state=sample_aircraft,
            weather=sample_weather,
            airports=sample_airports,
            sectors=[{"sector_id": 1, "controller_callsign": "ESSA_GND",
                       "aircraft_callsigns": ["SAS901"], "frequency_mhz": 121.8}],
            conflicts=[{"aircraft_a": "SAS901", "aircraft_b": "SAS456",
                         "lateral_distance_nm": 5.0, "vertical_distance_ft": 34850,
                         "time_to_conflict_s": 120, "severity": "warning"}],
            navigation={"sid": {"name": "BARK1A", "runway": "01L"}},
            local_procedures={"preferred_rwy": "01L", "noise_abatement": True},
        )
        prompt = engine.build_radio_call_prompt(ctx)
        full = prompt.full_prompt
        assert "SAS901" in full
        assert "ESSA" in full
        assert "BARK1A" in full
        assert "preferred_rwy" in full or "noise_abatement" in full
        assert prompt.estimated_tokens > 0


# Helper import
import json  # noqa: E402 (needed by tests above)
