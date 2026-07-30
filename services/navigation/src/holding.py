from __future__ import annotations

import math
from typing import List, Optional, Tuple

from geo import (
        angle_difference,
        destination_point,
        geodetic_distance,
        initial_bearing,
        normalize_heading,
    )
from models import (
    HoldEntrySolution,
    HoldEntryType,
    HoldingPattern,
    TurnDirection,
)


class HoldingPatternEngine:
    SECTOR_TEARDROP_DEG = 70.0
    SECTOR_PARALLEL_DEG = 110.0
    STANDARD_LEG_DURATION_S = 60.0
    STANDARD_SPEED_KN = 200.0
    HOLD_TOLERANCE_DEG = 5.0

    def calculate_pattern(
        self,
        fix_lat: float,
        fix_lon: float,
        inbound_heading: float,
        turn_direction: TurnDirection = TurnDirection.RIGHT,
        leg_duration_s: float = STANDARD_LEG_DURATION_S,
        speed_kn: float = STANDARD_SPEED_KN,
    ) -> HoldingPattern:
        inbound = normalize_heading(inbound_heading)
        if turn_direction == TurnDirection.RIGHT:
            outbound = normalize_heading(inbound + 180)
        else:
            outbound = normalize_heading(inbound - 180)

        leg_dist_nm = speed_kn * leg_duration_s / 3600.0

        return HoldingPattern(
            fix_lat=fix_lat,
            fix_lon=fix_lon,
            inbound_heading=inbound,
            turn_direction=turn_direction,
            leg_length_nm=leg_dist_nm,
            leg_duration_s=leg_duration_s,
            speed_kn=speed_kn,
            outbound_heading=outbound,
        )

    def determine_entry(
        self,
        aircraft_lat: float,
        aircraft_lon: float,
        aircraft_heading: float,
        holding_pattern: HoldingPattern,
    ) -> HoldEntrySolution:
        inbound = holding_pattern.inbound_heading
        outbound = holding_pattern.outbound_heading

        bearing_to_fix = normalize_heading(
            initial_bearing(aircraft_lat, aircraft_lon, holding_pattern.fix_lat, holding_pattern.fix_lon)
        )
        track_error = angle_difference(aircraft_heading, bearing_to_fix)

        course_to_fix = bearing_to_fix
        alpha = (course_to_fix - inbound + 360) % 360

        if alpha < self.SECTOR_TEARDROP_DEG:
            entry_type = HoldEntryType.TEARDROP
        elif alpha < (360 - self.SECTOR_TEARDROP_DEG):
            if alpha < 180:
                entry_type = HoldEntryType.PARALLEL
            else:
                entry_type = HoldEntryType.DIRECT
        else:
            entry_type = HoldEntryType.DIRECT

        entry = self._build_entry_solution(
            entry_type, holding_pattern, course_to_fix
        )
        return entry

    def _build_entry_solution(
        self,
        entry_type: HoldEntryType,
        pattern: HoldingPattern,
        course_to_fix: float,
    ) -> HoldEntrySolution:
        inbound = pattern.inbound_heading
        outbound = pattern.outbound_heading

        if entry_type == HoldEntryType.DIRECT:
            entry_hdg = normalize_heading(outbound)
            instr = [
                f"Fly direct to holding fix at {pattern.fix_lat:.4f}, {pattern.fix_lon:.4f}",
                f"Cross fix, turn {pattern.turn_direction.value} to outbound heading {outbound:.0f}°",
                f"Fly outbound for {pattern.leg_duration_s:.0f}s / {pattern.leg_length_nm:.1f}nm",
                f"Turn {pattern.turn_direction.value} to intercept inbound course {inbound:.0f}°",
            ]
            sector_angle = 0.0

        elif entry_type == HoldEntryType.TEARDROP:
            offset = 30.0
            if pattern.turn_direction == TurnDirection.RIGHT:
                entry_hdg = normalize_heading(inbound - offset)
            else:
                entry_hdg = normalize_heading(inbound + offset)

            instr = [
                f"Cross fix at heading {entry_hdg:.0f}° ({offset}° offset from inbound)",
                f"Fly outbound for {pattern.leg_duration_s * 1.5:.0f}s at {entry_hdg:.0f}°",
                f"Turn {pattern.turn_direction.value} 210° to intercept inbound course {inbound:.0f}°",
            ]
            sector_angle = self.SECTOR_TEARDROP_DEG

        else:
            entry_hdg = normalize_heading(inbound)
            if pattern.turn_direction == TurnDirection.RIGHT:
                offset_entry = normalize_heading(inbound + 180)
            else:
                offset_entry = normalize_heading(inbound - 180)

            instr = [
                f"Cross fix, fly outbound heading {offset_entry:.0f}° parallel to inbound",
                f"Fly for {pattern.leg_duration_s:.0f}s / {pattern.leg_length_nm:.1f}nm",
                f"Turn {('right' if pattern.turn_direction == TurnDirection.RIGHT else 'left')} "
                f"180° to re-intercept inbound course {inbound:.0f}°",
                f"Intercept inbound and return to fix",
            ]
            entry_hdg = offset_entry
            sector_angle = self.SECTOR_PARALLEL_DEG

        return HoldEntrySolution(
            entry_type=entry_type,
            inbound_heading=inbound,
            outbound_heading=outbound,
            outbound_leg_duration_s=pattern.leg_duration_s,
            outbound_distance_nm=pattern.leg_length_nm,
            turn_direction=pattern.turn_direction,
            entry_heading=entry_hdg,
            sector_angle_deg=sector_angle,
            instructions=instr,
        )

    def compute_hold_geometry(
        self,
        fix_lat: float,
        fix_lon: float,
        inbound_heading: float,
        leg_length_nm: float,
        turn_direction: TurnDirection = TurnDirection.RIGHT,
    ) -> List[Tuple[float, float]]:
        inbound = normalize_heading(inbound_heading)
        outbound = normalize_heading(
            inbound + (180 if turn_direction == TurnDirection.RIGHT else -180)
        )

        turn_radius_nm = self._turn_radius_nm(200.0, 25.0)

        fix_out = destination_point(fix_lat, fix_lon, outbound, leg_length_nm)
        out_end = destination_point(fix_out[0], fix_out[1], outbound, turn_radius_nm)
        out_to_in = destination_point(out_end[0], out_end[1], inbound, turn_radius_nm)

        return [
            (fix_lat, fix_lon),
            (fix_out[0], fix_out[1]),
            (out_end[0], out_end[1]),
            (out_to_in[0], out_to_in[1]),
            (fix_lat, fix_lon),
        ]

    def is_aircraft_in_holding_pattern(
        self,
        aircraft_lat: float,
        aircraft_lon: float,
        pattern: HoldingPattern,
        tolerance_nm: float = 5.0,
    ) -> bool:
        dist = geodetic_distance(
            aircraft_lat, aircraft_lon, pattern.fix_lat, pattern.fix_lon
        )
        return dist <= pattern.leg_length_nm + tolerance_nm

    @staticmethod
    def _turn_radius_nm(speed_kn: float, bank_deg: float = 25.0) -> float:
        speed_fps = speed_kn * 1.68781
        radius_ft = speed_fps ** 2 / (math.tan(math.radians(bank_deg)) * 32.174)
        return radius_ft / 6076.12
