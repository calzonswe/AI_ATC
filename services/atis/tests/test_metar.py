import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from metar import parse_metar
from models import MetarData


class TestBasicMetar:
    def test_standard_metar(self):
        raw = "ESSA 121820Z 20010KT 9999 FEW025 SCT045 BKN080 08/05 Q1015 NOSIG"
        m = parse_metar(raw)
        assert m.airport_icao == "ESSA"
        assert m.time_zulu == "121820Z"
        assert m.wind_dir == 200
        assert m.wind_speed_kt == 10
        assert m.wind_gust_kt is None
        assert m.visibility_m == 9999
        assert m.cavok is False
        assert len(m.weather) == 0
        assert m.clouds == [
            {"code": "FEW", "alt_ft": 2500},
            {"code": "SCT", "alt_ft": 4500},
            {"code": "BKN", "alt_ft": 8000},
        ]
        assert m.temp_c == 8
        assert m.dewpoint_c == 5
        assert m.qnh_hpa == 1015
        assert m.trend == "NOSIG"
        assert m.raw == raw

    def test_gusty_wind(self):
        raw = "ESSB 121850Z 24015G25KT 8000 -RA BKN030 06/04 Q1003 TEMPO"
        m = parse_metar(raw)
        assert m.wind_dir == 240
        assert m.wind_speed_kt == 15
        assert m.wind_gust_kt == 25
        assert m.visibility_m == 8000
        assert m.weather == ["-RA"]
        assert m.clouds == [{"code": "BKN", "alt_ft": 3000}]
        assert m.temp_c == 6
        assert m.dewpoint_c == 4
        assert m.qnh_hpa == 1003
        assert m.trend == "TEMPO"

    def test_cavok(self):
        raw = "ESSA 121900Z 18008KT CAVOK 12/07 Q1020 NOSIG"
        m = parse_metar(raw)
        assert m.cavok is True
        assert m.visibility_m == 9999
        assert m.clouds == []
        assert m.temp_c == 12
        assert m.dewpoint_c == 7
        assert m.qnh_hpa == 1020

    def test_vrbl_wind(self):
        raw = "ESSA 121900Z VRB02KT 9999 NSC 15/09 Q1021"
        m = parse_metar(raw)
        assert m.wind_dir == 0
        assert m.wind_speed_kt == 2
        assert m.temp_c == 15
        assert m.dewpoint_c == 9

    def test_variable_wind_range(self):
        raw = "ESSA 121900Z 20010KT 180V240 9999 FEW030 10/06 Q1018"
        m = parse_metar(raw)
        assert m.wind_dir == 200
        assert m.wind_speed_kt == 10
        assert m.wind_variable_from == 180
        assert m.wind_variable_to == 240


class TestWeatherPhenomena:
    def test_moderate_rain(self):
        m = parse_metar("ESSA 121800Z 18010KT 5000 RA BKN020 08/06 Q1015")
        assert m.weather == ["RA"]

    def test_heavy_thunderstorm_rain(self):
        m = parse_metar("ESSA 121800Z 18010KT 3000 +TSRA BKN015CB 08/06 Q1015")
        assert "+TSRA" in m.weather

    def test_light_snow(self):
        m = parse_metar("ESSA 121800Z 09008KT 2000 -SN BKN010 M02/M04 Q1005")
        assert m.weather == ["-SN"]
        assert m.temp_c == -2
        assert m.dewpoint_c == -4


class TestClouds:
    def test_few_sct_bkn(self):
        m = parse_metar("ESSA 121800Z 18010KT 9999 FEW010 SCT025 BKN050 08/06 Q1015")
        assert len(m.clouds) == 3
        assert m.clouds[0] == {"code": "FEW", "alt_ft": 1000}
        assert m.clouds[1] == {"code": "SCT", "alt_ft": 2500}
        assert m.clouds[2] == {"code": "BKN", "alt_ft": 5000}

    def test_overcast(self):
        m = parse_metar("ESSA 121800Z 18010KT 9999 OVC120 08/06 Q1015")
        assert m.clouds == [{"code": "OVC", "alt_ft": 12000}]

    def test_nsc(self):
        m = parse_metar("ESSA 121800Z 18010KT 9999 NSC 08/06 Q1015")
        assert m.clouds == []

    def test_vertical_visibility(self):
        m = parse_metar("ESSA 121800Z 18010KT 0500 VV003 08/06 Q1015")
        assert m.clouds == [{"code": "VV", "alt_ft": 300}]


class TestQNH:
    def test_qnh_hpa(self):
        m = parse_metar("ESSA 121800Z 18010KT 9999 FEW030 10/07 Q1022")
        assert m.qnh_hpa == 1022

    def test_qnh_inhg(self):
        m = parse_metar("KJFK 121851Z 18010KT 10SM FEW030 10/07 A2992")
        assert m.qnh_hpa == 1013


class TestEdgeCases:
    def test_empty_string(self):
        m = parse_metar("")
        assert m.airport_icao == ""

    def test_calm_wind(self):
        m = parse_metar("ESSA 121800Z 00000KT CAVOK 10/07 Q1018")
        assert m.wind_dir == 0
        assert m.wind_speed_kt == 0

    def test_only_airport(self):
        m = parse_metar("ESSA")
        assert m.airport_icao == "ESSA"

    def test_raw_preserved(self):
        raw = "ESSA 121800Z 18010KT 9999 FEW030 10/07 Q1018"
        m = parse_metar(raw)
        assert m.raw == raw

    def test_missing_temp(self):
        m = parse_metar("ESSA 121800Z 18010KT 9999 FEW030 Q1018")
        assert m.temp_c is None
        assert m.dewpoint_c is None

    def test_no_trend(self):
        m = parse_metar("ESSA 121800Z 18010KT 9999 FEW030 10/07 Q1018")
        assert m.trend == ""

    def test_rmk_ignored(self):
        m = parse_metar("ESSA 121800Z 18010KT 9999 FEW030 10/07 Q1018 RMK AO2 SLP123")
        assert m.temp_c == 10
        assert m.dewpoint_c == 7
        assert m.qnh_hpa == 1018
