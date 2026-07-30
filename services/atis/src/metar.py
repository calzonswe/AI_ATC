from __future__ import annotations

import re
from typing import List, Optional

from models import MetarData


CLOUD_CODES = {"FEW", "SCT", "BKN", "OVC", "VV"}
TREND_KEYWORDS = {"NOSIG", "TEMPO", "BECMG", "INTER", "PROB30", "PROB40", "PROB50"}


def _try_int(val: str) -> Optional[int]:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _m_to_int(val: str) -> Optional[int]:
    if val.startswith("M"):
        num = _try_int(val[1:])
        return -num if num is not None else None
    return _try_int(val)


def _parse_wind(tokens: List[str], idx: int):
    raw = tokens[idx]
    m = re.match(r"^(\d{3}|VRB|///)(\d{2,3}|//)(G(\d{2,3}|//))?(KT|MPS|KMH|/)?$", raw)
    if not m:
        return None, idx
    dir_str = m.group(1)
    speed_str = m.group(2)
    gust_str = m.group(4)
    wind_dir = 0 if dir_str in ("VRB", "///") else _try_int(dir_str) or 0
    wind_speed = _try_int(speed_str) or 0
    wind_gust = _try_int(gust_str) if gust_str and gust_str not in ("//",) else None
    wind_var_from = None
    wind_var_to = None
    if idx + 1 < len(tokens):
        vm = re.match(r"^(\d{3})V(\d{3})$", tokens[idx + 1])
        if vm:
            wind_var_from = int(vm.group(1))
            wind_var_to = int(vm.group(2))
            return {
                "wind_dir": wind_dir,
                "wind_speed_kt": wind_speed,
                "wind_gust_kt": wind_gust,
                "wind_variable_from": wind_var_from,
                "wind_variable_to": wind_var_to,
            }, idx + 2
    return {
        "wind_dir": wind_dir,
        "wind_speed_kt": wind_speed,
        "wind_gust_kt": wind_gust,
        "wind_variable_from": None,
        "wind_variable_to": None,
    }, idx + 1


def _parse_visibility(token: str):
    if token == "CAVOK":
        return 9999, True
    if token == "9999":
        return 9999, False
    vis = _try_int(token)
    if vis is not None:
        return vis, False
    return 9999, False


def _parse_weather(tokens: List[str], idx: int):
    weather_pattern = re.compile(
        r"^([+-]?)(MI|BC|DR|BL|SH|TS|FZ|DZ|RA|SN|SG|PL|"
        r"GR|GS|UP|BR|FG|FU|DU|SA|HZ|VA|PY|"
        r"PO|SQ|FC|SS|DS|NS)+$"
    )
    weather: List[str] = []
    i = idx
    while i < len(tokens):
        if weather_pattern.match(tokens[i]):
            weather.append(tokens[i])
            i += 1
        else:
            break
    return weather, i


def _parse_clouds(tokens: List[str], idx: int):
    clouds: List[dict] = []
    i = idx
    while i < len(tokens):
        t = tokens[i]
        if t in ("NSC", "NCD", "SKC", "CLR"):
            break
        cm = re.match(r"^(FEW|SCT|BKN|OVC|VV)(\d{3})$", t)
        if cm:
            code = cm.group(1)
            alt_ft = int(cm.group(2)) * 100
            clouds.append({"code": code, "alt_ft": alt_ft})
            i += 1
        else:
            break
    return clouds, i


def _parse_temperature_dewpoint(token: str):
    m = re.match(r"^(M?\d{2})/(M?\d{2})$", token)
    if m:
        temp = _m_to_int(m.group(1))
        dew = _m_to_int(m.group(2))
        return temp, dew
    return None, None


def _parse_qnh(token: str):
    m = re.match(r"^Q(\d{4})$", token)
    if m:
        return int(m.group(1))
    am = re.match(r"^A(\d{4})$", token)
    if am:
        in_hg = int(am.group(1)) / 100
        return int(round(in_hg * 33.8639))
    return None


def parse_metar(metar_str: str) -> MetarData:
    raw = metar_str.strip()
    tokens = raw.split()
    if len(tokens) < 2:
        airport = tokens[0] if len(tokens) == 1 else ""
        return MetarData(airport_icao=airport, raw=raw)

    airport = tokens[0]
    time_zulu = tokens[1] if len(tokens) > 1 and tokens[1].endswith("Z") else ""

    data = {
        "airport_icao": airport,
        "time_zulu": time_zulu,
        "wind_dir": 0,
        "wind_speed_kt": 0,
        "wind_gust_kt": None,
        "wind_variable_from": None,
        "wind_variable_to": None,
        "visibility_m": 9999,
        "cavok": False,
        "weather": [],
        "clouds": [],
        "temp_c": None,
        "dewpoint_c": None,
        "qnh_hpa": None,
        "trend": "",
    }

    i = 2 if time_zulu else 1
    wind_done = False
    vis_done = False
    weather_done = False
    clouds_done = False
    temp_done = False
    qnh_done = False

    while i < len(tokens):
        t = tokens[i]

        if t.startswith("RMK"):
            break

        if t in TREND_KEYWORDS:
            data["trend"] = t
            i += 1
            continue

        if not wind_done and re.match(r"^(\d{3}|VRB|///)(\d{2,3}|//)", t):
            result, i = _parse_wind(tokens, i)
            if result:
                data.update(result)
                wind_done = True
            else:
                i += 1
            continue

        if not vis_done and (t == "CAVOK" or re.match(r"^\d{4}$", t)):
            vis, cavok = _parse_visibility(t)
            data["visibility_m"] = vis
            data["cavok"] = cavok
            vis_done = True
            i += 1
            continue

        if not weather_done and re.match(
            r"^[+-]?(MI|BC|DR|BL|SH|TS|FZ|DZ|RA|SN|SG|PL|"
            r"GR|GS|UP|BR|FG|FU|DU|SA|HZ|VA|PY|"
            r"PO|SQ|FC|SS|DS|NS)+$", t
        ):
            weather, i = _parse_weather(tokens, i)
            if weather:
                data["weather"] = weather
                weather_done = True
            else:
                i += 1
            continue

        if not clouds_done:
            if t in ("NSC", "NCD", "SKC", "CLR"):
                clouds_done = True
                i += 1
                continue
            cm = re.match(r"^(FEW|SCT|BKN|OVC|VV)(\d{3})$", t)
            if cm:
                clouds, i = _parse_clouds(tokens, i)
                if clouds:
                    data["clouds"] = clouds
                continue
            if not cm:
                clouds_done = True

        if not temp_done and re.match(r"^M?\d{2}/M?\d{2}$", t):
            temp, dew = _parse_temperature_dewpoint(t)
            data["temp_c"] = temp
            data["dewpoint_c"] = dew
            temp_done = True
            i += 1
            continue

        if not qnh_done and re.match(r"^[QA]\d{4}$", t):
            qnh = _parse_qnh(t)
            if qnh:
                data["qnh_hpa"] = qnh
                qnh_done = True
            i += 1
            continue

        i += 1

    return MetarData(raw=raw, **data)
