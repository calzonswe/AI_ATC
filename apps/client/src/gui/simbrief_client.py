from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.request import urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

SIMBRIEF_API = "https://www.simbrief.com/api/xml.fetcher.php?userid={}&json=1"


@dataclass
class SimBriefFlightPlan:
    pilot_id: str = ""
    origin: str = ""
    destination: str = ""
    aircraft_type: str = ""
    cruise_altitude: str = ""
    route: str = ""
    waypoints: List[Dict[str, Any]] = field(default_factory=list)
    estimated_time: str = ""
    fuel: str = ""
    weights: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"Origin: {self.origin or 'N/A'}",
            f"Destination: {self.destination or 'N/A'}",
            f"Aircraft: {self.aircraft_type or 'N/A'}",
            f"Cruise: {self.cruise_altitude or 'N/A'}",
        ]
        if self.route:
            lines.append(f"Route: {self.route}")
        if self.waypoints:
            count = len(self.waypoints)
            first = self.waypoints[0].get("ident", "?")
            last = self.waypoints[-1].get("ident", "?")
            lines.append(f"Waypoints: {count} ({first} -> {last})")
        if self.estimated_time:
            lines.append(f"Est Time: {self.estimated_time}")
        return "\n".join(lines)


def fetch_flight_plan(pilot_id: str) -> SimBriefFlightPlan:
    url = SIMBRIEF_API.format(pilot_id.strip())
    logger.info("Fetching SimBrief flight plan for pilot %s", pilot_id)
    try:
        with urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, OSError) as exc:
        logger.error("SimBrief fetch failed: %s", exc)
        raise

    if not data or "fetch" not in data:
        raise ValueError("No flight plan data returned from SimBrief")

    general = data.get("general", {})
    origin = data.get("origin", {})
    destination = data.get("destination", {})
    aircraft = data.get("aircraft", {})
    navlog = data.get("navlog", []) or []

    def _safe(d: Any, key: str, default: str = "") -> str:
        if isinstance(d, dict):
            return str(d.get(key, default))
        return default

    waypoints = []
    for entry in navlog:
        wp = entry.get("fix", entry)
        waypoints.append({
            "ident": _safe(wp, "ident"),
            "type": _safe(wp, "type"),
            "lat": _safe(wp, "latitude"),
            "lon": _safe(wp, "longitude"),
            "alt": _safe(wp, "altitude"),
        })

    return SimBriefFlightPlan(
        pilot_id=pilot_id,
        origin=_safe(origin, "icao_code"),
        destination=_safe(destination, "icao_code"),
        aircraft_type=_safe(aircraft, "icao_code"),
        cruise_altitude=_safe(general, "cruise_altitude"),
        route=_safe(general, "route"),
        estimated_time=_safe(general, "flight_time"),
        fuel=_safe(general, "fuel_kg") or _safe(general, "total_fuel"),
        weights=_safe(general, "gross_weight"),
        waypoints=waypoints,
        raw=data,
    )
