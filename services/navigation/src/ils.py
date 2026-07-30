from __future__ import annotations

import math
from typing import Optional, Tuple

from geo import (
        angle_difference,
        destination_point,
        geodetic_distance,
        initial_bearing,
        normalize_heading,
    )
from models import ILSIntercept, LatLon


class ILSInterceptCalculator:
    GLIDESLOPE_DEG = 3.0
    LOCALIZER_WIDTH_DEG = 5.0
    INTERCEPT_ANGLE_MIN = 15.0
    INTERCEPT_ANGLE_MAX = 45.0
    INTERCEPT_ANGLE_IDEAL = 30.0

    def calculate_intercept(
        self,
        aircraft_lat: float,
        aircraft_lon: float,
        aircraft_alt_ft: float,
        aircraft_heading: float,
        runway_lat: float,
        runway_lon: float,
        runway_heading: float,
        ils_heading: Optional[float] = None,
    ) -> ILSIntercept:
        loc_hdg = normalize_heading(ils_heading if ils_heading is not None else runway_heading)
        intercept_angle = angle_difference(aircraft_heading, loc_hdg)

        distance_to_threshold = geodetic_distance(
            aircraft_lat, aircraft_lon, runway_lat, runway_lon
        )

        loc_bearing = initial_bearing(
            aircraft_lat, aircraft_lon, runway_lat, runway_lon
        )
        deviation = angle_difference(loc_bearing, loc_hdg)

        crosswind_dist_nm = distance_to_threshold * math.sin(math.radians(deviation))

        if intercept_angle < 1.0:
            intercept_angle = self.INTERCEPT_ANGLE_IDEAL

        intercept_dist_from_threshold = crosswind_dist_nm / math.sin(
            math.radians(intercept_angle)
        )
        intercept_dist = geodetic_distance(
            aircraft_lat, aircraft_lon, runway_lat, runway_lon
        )
        intercept_dist = min(intercept_dist, intercept_dist_from_threshold)

        glidepath_intercept_alt = self._calculate_glidepath_intercept(
            intercept_dist, runway_lat, runway_lon, runway_heading
        )

        rec_hdg = normalize_heading(
            loc_hdg + intercept_angle * (1 if self._is_left_of_course(
                aircraft_lat, aircraft_lon, runway_lat, runway_lon, loc_hdg
            ) else -1)
        )

        feasible = True
        reason = ""

        if intercept_angle < self.INTERCEPT_ANGLE_MIN:
            feasible = False
            reason = f"Intercept angle {intercept_angle:.1f}deg too shallow (min {self.INTERCEPT_ANGLE_MIN}deg)"

        if intercept_angle > self.INTERCEPT_ANGLE_MAX:
            feasible = False
            reason = f"Intercept angle {intercept_angle:.1f}deg too steep (max {self.INTERCEPT_ANGLE_MAX}deg)"

        if distance_to_threshold < 0.5:
            feasible = False
            reason = "Aircraft too close to runway threshold"

        return ILSIntercept(
            intercept_angle_deg=round(intercept_angle, 1),
            intercept_distance_nm=round(intercept_dist, 2),
            intercept_altitude_ft=round(glidepath_intercept_alt, 0),
            is_feasible=feasible,
            recommended_heading=round(rec_hdg, 1),
            distance_to_threshold_nm=round(distance_to_threshold, 2),
            reason=reason,
        )

    def calculate_glideslope_altitude(
        self, distance_from_threshold_nm: float
    ) -> float:
        dist_ft = distance_from_threshold_nm * 6076.12
        return dist_ft * math.tan(math.radians(self.GLIDESLOPE_DEG))

    def calculate_localizer_deviation(
        self,
        aircraft_lat: float,
        aircraft_lon: float,
        threshold_lat: float,
        threshold_lon: float,
        localizer_heading: float,
    ) -> Tuple[float, float]:
        bearing_to_threshold = initial_bearing(
            aircraft_lat, aircraft_lon, threshold_lat, threshold_lon
        )
        angular_deviation = angle_difference(bearing_to_threshold, localizer_heading)
        distance_nm = geodetic_distance(
            aircraft_lat, aircraft_lon, threshold_lat, threshold_lon
        )
        lateral_offset_nm = distance_nm * math.sin(math.radians(angular_deviation))
        return angular_deviation, lateral_offset_nm

    def calculate_glidepath_intercept(
        self,
        aircraft_alt_ft: float,
        aircraft_lat: float,
        aircraft_lon: float,
        runway_lat: float,
        runway_lon: float,
        runway_heading: float,
    ) -> float:
        distance_nm = geodetic_distance(
            aircraft_lat, aircraft_lon, runway_lat, runway_lon
        )
        required_alt = self.calculate_glideslope_altitude(distance_nm)
        return required_alt

    def is_on_glideslope(
        self,
        aircraft_alt_ft: float,
        distance_from_threshold_nm: float,
        tolerance_ft: float = 100.0,
    ) -> bool:
        expected_alt = self.calculate_glideslope_altitude(distance_from_threshold_nm)
        return abs(aircraft_alt_ft - expected_alt) <= tolerance_ft

    def _is_left_of_course(
        self,
        lat: float,
        lon: float,
        threshold_lat: float,
        threshold_lon: float,
        loc_heading: float,
    ) -> bool:
        bearing_to_threshold = initial_bearing(lat, lon, threshold_lat, threshold_lon)
        diff = (bearing_to_threshold - loc_heading + 360) % 360
        return diff < 180

    def _calculate_glidepath_intercept(
        self,
        intercept_distance_nm: float,
        threshold_lat: float,
        threshold_lon: float,
        runway_heading: float,
    ) -> float:
        distance_from_threshold = intercept_distance_nm
        intercept_alt = self.calculate_glideslope_altitude(distance_from_threshold)

        threshold_elevation_ft = 0
        intercept_alt += threshold_elevation_ft

        return intercept_alt
