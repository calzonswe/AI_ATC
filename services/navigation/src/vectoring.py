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
    FinalApproachVector,
    TurnDirection,
    VectorInstruction,
)


class VectoringEngine:
    BASE_LEG_OFFSET_NM = 4.0
    INTERCEPT_ANGLE_DEG = 30.0
    FINAL_APPROACH_FIX_DIST_NM = 10.0
    VECTOR_SPACING_NM = 3.0
    VECTOR_SPACING_TIME_S = 120.0

    def vector_to_localizer(
        self,
        aircraft_lat: float,
        aircraft_lon: float,
        aircraft_heading: float,
        aircraft_alt_ft: float,
        aircraft_speed_kn: float,
        runway_lat: float,
        runway_lon: float,
        runway_heading: float,
        ils_heading: Optional[float] = None,
    ) -> FinalApproachVector:
        loc_hdg = normalize_heading(ils_heading if ils_heading is not None else runway_heading)
        distance_to_runway = geodetic_distance(
            aircraft_lat, aircraft_lon, runway_lat, runway_lon
        )

        turn_dir = self._determine_intercept_turn(
            aircraft_lat, aircraft_lon, aircraft_heading, runway_lat, runway_lon, loc_hdg
        )

        intercept_hdg = normalize_heading(
            loc_hdg + self.INTERCEPT_ANGLE_DEG * (1 if turn_dir == "right" else -1)
        )

        intercept_dist = distance_to_runway * math.sin(math.radians(self.INTERCEPT_ANGLE_DEG))
        intercept_alt = int(aircraft_alt_ft)

        instructions = []
        instructions.append(VectorInstruction(
            heading_deg=round(intercept_hdg, 1),
            reason=f"Turn {turn_dir} to intercept localizer course {loc_hdg:.0f}°",
            distance_nm=round(intercept_dist, 2),
            altitude_ft=intercept_alt,
            speed_kn=int(aircraft_speed_kn),
            turn_direction=turn_dir,
        ))

        return FinalApproachVector(
            heading_to_intercept=round(intercept_hdg, 1),
            intercept_angle_deg=self.INTERCEPT_ANGLE_DEG,
            distance_to_runway_nm=round(distance_to_runway, 2),
            intercept_distance_nm=round(intercept_dist, 2),
            altitude_ft=intercept_alt,
            instructions=instructions,
        )

    def vector_to_base_leg(
        self,
        aircraft_lat: float,
        aircraft_lon: float,
        aircraft_heading: float,
        aircraft_alt_ft: float,
        runway_lat: float,
        runway_lon: float,
        runway_heading: float,
        side: str = "left",
    ) -> VectorInstruction:
        offset_side = "right" if side == "left" else "left"
        base_lat, base_lon = self._compute_base_leg_position(
            runway_lat, runway_lon, runway_heading, self.BASE_LEG_OFFSET_NM, offset_side
        )

        base_hdg = normalize_heading(
            initial_bearing(aircraft_lat, aircraft_lon, base_lat, base_lon)
        )
        dist_to_base = geodetic_distance(aircraft_lat, aircraft_lon, base_lat, base_lon)

        return VectorInstruction(
            heading_deg=round(base_hdg, 1),
            reason=f"Vector to base leg for runway {runway_heading:.0f}°",
            distance_nm=round(dist_to_base, 2),
            altitude_ft=int(aircraft_alt_ft),
            turn_direction=side,
        )

    def vector_for_spacing(
        self,
        lead_lat: float,
        lead_lon: float,
        lead_speed_kn: float,
        trail_lat: float,
        trail_lon: float,
        trail_speed_kn: float,
        desired_spacing_nm: float = 3.0,
        extend_heading: float = 0.0,
    ) -> Tuple[VectorInstruction, float]:
        current_spacing = geodetic_distance(lead_lat, lead_lon, trail_lat, trail_lon)
        spacing_error = desired_spacing_nm - current_spacing

        if spacing_error > 0 and trail_speed_kn > 0:
            extend_time_s = (spacing_error / trail_speed_kn) * 3600.0
        else:
            extend_time_s = 0.0

        return (
            VectorInstruction(
                heading_deg=round(extend_heading, 1),
                reason=f"Extend downwind for spacing ({spacing_error:+.1f}nm)",
                distance_nm=round(abs(spacing_error), 2),
                speed_kn=int(trail_speed_kn),
            ),
            extend_time_s,
        )

    def calculate_turn_to_final(
        self,
        aircraft_lat: float,
        aircraft_lon: float,
        aircraft_heading: float,
        aircraft_speed_kn: float,
        runway_lat: float,
        runway_lon: float,
        runway_heading: float,
    ) -> VectorInstruction:
        hdg_diff = angle_difference(aircraft_heading, runway_heading)
        turn_angle = 90.0 - (hdg_diff / 2)
        intercept_hdg = normalize_heading(runway_heading - turn_angle)
        dist_to_runway = geodetic_distance(aircraft_lat, aircraft_lon, runway_lat, runway_lon)

        return VectorInstruction(
            heading_deg=round(intercept_hdg, 1),
            reason=f"Turn to final approach runway heading {runway_heading:.0f}°",
            distance_nm=round(dist_to_runway, 2),
            speed_kn=int(aircraft_speed_kn),
        )

    def calculate_downwind_leg(
        self,
        runway_lat: float,
        runway_lon: float,
        runway_heading: float,
        offset_nm: float = 4.0,
    ) -> Tuple[float, float, float]:
        downwind_hdg = normalize_heading(runway_heading + 180)
        base_lat, base_lon = self._compute_base_leg_position(
            runway_lat, runway_lon, runway_heading, offset_nm, "right"
        )
        threshold_end_lat, threshold_end_lon = destination_point(
            runway_lat, runway_lon, runway_heading, -1.0
        )
        return downwind_hdg, base_lat, base_lon

    def _determine_intercept_turn(
        self,
        lat: float,
        lon: float,
        heading: float,
        rwy_lat: float,
        rwy_lon: float,
        loc_heading: float,
    ) -> str:
        bearing_to_threshold = initial_bearing(lat, lon, rwy_lat, rwy_lon)
        rel_pos = (bearing_to_threshold - loc_heading + 360) % 360
        return "right" if rel_pos < 180 else "left"

    def _compute_base_leg_position(
        self,
        rwy_lat: float,
        rwy_lon: float,
        rwy_heading: float,
        offset_nm: float,
        side: str = "right",
    ) -> Tuple[float, float]:
        perp_bearing = (rwy_heading + 90) % 360 if side == "right" else (rwy_heading - 90) % 360
        offset_lat, offset_lon = destination_point(rwy_lat, rwy_lon, perp_bearing, offset_nm)

        mid_lat = (rwy_lat + offset_lat) / 2
        mid_lon = (rwy_lon + offset_lon) / 2

        base_bearing = normalize_heading(rwy_heading + 180)
        base_lat, base_lon = destination_point(mid_lat, mid_lon, base_bearing, offset_nm)

        return base_lat, base_lon
