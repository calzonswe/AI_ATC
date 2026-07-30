from __future__ import annotations

import math
from typing import Tuple

from geographiclib.geodesic import Geodesic

EARTH_RADIUS_NM = 3440.065  # NM
WGS84 = Geodesic.WGS84


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_NM * c


def geodetic_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    result = WGS84.Inverse(lat1, lon1, lat2, lon2)
    return result["s12"] / 1852.0


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    result = WGS84.Inverse(lat1, lon1, lat2, lon2)
    bearing = result["azi1"]
    return (bearing + 360) % 360


def final_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    result = WGS84.Inverse(lat1, lon1, lat2, lon2)
    bearing = result["azi2"]
    return (bearing + 360) % 360


def destination_point(
    lat: float, lon: float, bearing_deg: float, distance_nm: float
) -> Tuple[float, float]:
    distance_m = distance_nm * 1852.0
    result = WGS84.Direct(lat, lon, bearing_deg, distance_m)
    return result["lat2"], result["lon2"]


def cross_track_distance(
    point_lat: float,
    point_lon: float,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> float:
    bearing_ab = math.radians(initial_bearing(start_lat, start_lon, end_lat, end_lon))
    bearing_ap = math.radians(
        initial_bearing(start_lat, start_lon, point_lat, point_lon)
    )
    dist_ap_nm = haversine_distance(start_lat, start_lon, point_lat, point_lon)
    angular = bearing_ap - bearing_ab
    return dist_ap_nm * math.sin(angular)


def along_track_distance(
    point_lat: float,
    point_lon: float,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> float:
    bearing_ab = math.radians(initial_bearing(start_lat, start_lon, end_lat, end_lon))
    bearing_ap = math.radians(
        initial_bearing(start_lat, start_lon, point_lat, point_lon)
    )
    dist_ap_nm = haversine_distance(start_lat, start_lon, point_lat, point_lon)
    angular = bearing_ap - bearing_ab
    return dist_ap_nm * math.cos(angular)


def angle_difference(a_deg: float, b_deg: float) -> float:
    diff = (a_deg - b_deg + 180) % 360 - 180
    return abs(diff)


def normalize_heading(heading: float) -> float:
    return (heading + 360) % 360


def intercept_heading(
    current_lat: float,
    current_lon: float,
    target_lat: float,
    target_lon: float,
) -> float:
    return initial_bearing(current_lat, current_lon, target_lat, target_lon)


def parallel_offset_point(
    lat: float,
    lon: float,
    bearing_deg: float,
    distance_nm: float,
    side: str = "right",
) -> Tuple[float, float]:
    offset_bearing = (bearing_deg + 90) % 360 if side == "right" else (bearing_deg - 90) % 360
    return destination_point(lat, lon, offset_bearing, distance_nm)


def distance_to_go(
    lat1: float, lon1: float, heading_deg: float, lat2: float, lon2: float
) -> Tuple[float, float]:
    required_hdg = initial_bearing(lat1, lon1, lat2, lon2)
    dist = geodetic_distance(lat1, lon1, lat2, lon2)
    delta = angle_difference(heading_deg, required_hdg)
    return dist, delta
