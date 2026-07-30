from __future__ import annotations

import math
from typing import Dict, List, Optional

from runtime.weather import CloudLayer, MetarData, WindData
from pubsub import EventBus, EventType


class WeatherManager:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._metars: Dict[str, MetarData] = {}
        self._event_bus = event_bus

    def set_metar(self, metar: MetarData) -> None:
        self._metars[metar.icao.upper()] = metar
        if self._event_bus:
            self._event_bus.publish(
                EventType.WEATHER_UPDATED,
                {
                    "icao": metar.icao,
                    "wind_direction": metar.wind.direction,
                    "wind_speed": metar.wind.speed_kn,
                    "qnh": metar.qnh_hpa,
                },
                source="WeatherManager",
            )

    def set_metar_from_dict(self, data: dict) -> None:
        wind_dict = data.get("wind", {})
        cloud_list = data.get("clouds", [])
        metar = MetarData(
            icao=data["icao"],
            time=data.get("time", 0.0),
            wind=WindData(
                direction=wind_dict.get("direction", 0.0),
                speed_kn=wind_dict.get("speed_kn", 0.0),
                gust_kn=wind_dict.get("gust_kn", 0.0),
                variation_from=wind_dict.get("variation_from"),
                variation_to=wind_dict.get("variation_to"),
            ),
            visibility_m=data.get("visibility_m", 10000.0),
            qnh_hpa=data.get("qnh_hpa", 1013.25),
            temperature_c=data.get("temperature_c", 15.0),
            dewpoint_c=data.get("dewpoint_c", 10.0),
            clouds=[
                CloudLayer(coverage=c["coverage"], altitude_ft=c["altitude_ft"])
                for c in cloud_list
            ],
        )
        self.set_metar(metar)

    def get(self, icao: str) -> Optional[MetarData]:
        return self._metars.get(icao.upper())

    def get_wind(self, icao: str) -> Optional[WindData]:
        metar = self.get(icao)
        return metar.wind if metar else None

    def get_qnh(self, icao: str) -> float:
        metar = self.get(icao)
        return metar.qnh_hpa if metar else 1013.25

    def calculate_runway_wind(
        self, icao: str, runway_heading: float
    ) -> tuple[float, float]:
        wind = self.get_wind(icao)
        if wind is None:
            return 0.0, 0.0
        angle_diff = math.radians(wind.direction - runway_heading)
        crosswind = abs(wind.speed_kn * math.sin(angle_diff))
        headwind = wind.speed_kn * math.cos(angle_diff)
        return crosswind, headwind

    def clear(self, icao: str) -> None:
        self._metars.pop(icao.upper(), None)

    def clear_all(self) -> None:
        self._metars.clear()

    @property
    def airport_count(self) -> int:
        return len(self._metars)
