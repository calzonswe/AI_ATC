from __future__ import annotations

from typing import List, Optional

from models import AtisData, MetarData


CLOUD_LABELS = {
    "FEW": "Few clouds",
    "SCT": "Scattered clouds",
    "BKN": "Broken ceiling",
    "OVC": "Overcast",
    "VV": "Vertical visibility",
}


def _build_cloud_text(clouds: List[dict]) -> str:
    if not clouds:
        return "Sky clear"
    parts = []
    for c in clouds:
        label = CLOUD_LABELS.get(c["code"], c["code"])
        parts.append(f"{label} at {c['alt_ft']} feet")
    return ". ".join(parts)


def _build_wind_text(dir_: int, speed_kt: int,
                     gust_kt: Optional[int] = None,
                     var_from: Optional[int] = None,
                     var_to: Optional[int] = None) -> str:
    if dir_ == 0 and speed_kt == 0:
        return "Wind calm"
    parts: List[str] = []
    if dir_ == 0:
        parts.append("Wind variable")
    else:
        parts.append(f"Wind {dir_:03d} degrees {speed_kt} knots")
    if gust_kt:
        parts.append(f"gusting {gust_kt} knots")
    if var_from is not None and var_to is not None:
        parts.append(f"variable between {var_from:03d} and {var_to:03d} degrees")
    return " ".join(parts)


def _build_visibility_text(visibility_m: int, cavok: bool) -> str:
    if cavok or visibility_m >= 9999:
        return "Visibility 10 kilometers or more"
    if visibility_m >= 5000:
        return f"Visibility {visibility_m // 1000} kilometers"
    return f"Visibility {visibility_m} meters"


def _build_weather_text(weather: List[str]) -> str:
    if not weather:
        return ""
    labels = []
    for w in weather:
        if w.startswith("-"):
            labels.append(f"Light {w[1:]}")
        elif w.startswith("+"):
            labels.append(f"Heavy {w[1:]}")
        else:
            labels.append(w)
    return "Weather: " + ". ".join(labels)


def build_atis_text(atis: AtisData) -> str:
    metar = atis.metar
    parts: List[str] = []

    parts.append(f"{atis.airport_icao} ATIS Information {atis.identifier}")

    if metar.time_zulu:
        parts.append(f"{metar.time_zulu}")

    parts.append(_build_wind_text(
        metar.wind_dir, metar.wind_speed_kt,
        metar.wind_gust_kt, metar.wind_variable_from, metar.wind_variable_to,
    ))

    parts.append(_build_visibility_text(metar.visibility_m, metar.cavok))

    weather_text = _build_weather_text(metar.weather)
    if weather_text:
        parts.append(weather_text)

    parts.append(_build_cloud_text(metar.clouds))

    if metar.temp_c is not None and metar.dewpoint_c is not None:
        parts.append(f"Temperature {metar.temp_c}, dewpoint {metar.dewpoint_c}")
    elif metar.temp_c is not None:
        parts.append(f"Temperature {metar.temp_c}")

    if metar.qnh_hpa:
        parts.append(f"QNH {metar.qnh_hpa}")

    if atis.runways_in_use:
        rwys = ", ".join(atis.runways_in_use)
        parts.append(f"Runways in use: {rwys}")

    if atis.approach_in_use:
        parts.append(f"Approach: {atis.approach_in_use}")

    if metar.trend:
        parts.append(metar.trend)

    for notice in atis.notices:
        parts.append(notice)

    parts.append(
        f"Advise controller on initial contact you have "
        f"Information {atis.identifier}"
    )

    return ". ".join(parts)
