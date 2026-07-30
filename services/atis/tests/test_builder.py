import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from builder import build_atis_text
from metar import parse_metar
from models import AtisData


class TestAtisText:
    def _make_atis(self, metar_str: str, identifier: str = "Alpha",
                   runways=None, approach="", notices=None):
        metar = parse_metar(metar_str)
        return AtisData(
            airport_icao=metar.airport_icao,
            identifier=identifier,
            metar=metar,
            runways_in_use=runways or [],
            approach_in_use=approach,
            notices=notices or [],
        )

    def test_basic_atis(self):
        atis = self._make_atis(
            "ESSA 121820Z 20010KT 9999 FEW025 08/05 Q1015 NOSIG",
            "Alpha", ["01L/19R"],
        )
        text = build_atis_text(atis)
        assert "ESSA ATIS Information Alpha" in text
        assert "121820Z" in text
        assert "Wind 200 degrees 10 knots" in text
        assert "Visibility 10 kilometers or more" in text
        assert "Few clouds at 2500 feet" in text
        assert "Temperature 8, dewpoint 5" in text
        assert "QNH 1015" in text
        assert "Runways in use: 01L/19R" in text
        assert "NOSIG" in text
        assert "Advise controller on initial contact you have Information Alpha" in text

    def test_cavok(self):
        atis = self._make_atis(
            "ESSA 121900Z 18008KT CAVOK 12/07 Q1020 NOSIG",
            "Bravo", ["01L"],
        )
        text = build_atis_text(atis)
        assert "ESSA ATIS Information Bravo" in text
        assert "Visibility 10 kilometers or more" in text
        assert "Sky clear" in text

    def test_gusty_wind(self):
        atis = self._make_atis(
            "ESSB 121850Z 24015G25KT 8000 -RA BKN030 06/04 Q1003 TEMPO",
            "Charlie",
        )
        text = build_atis_text(atis)
        assert "Wind 240 degrees 15 knots" in text
        assert "gusting 25 knots" in text
        assert "Visibility 8 kilometers" in text
        assert "Light RA" in text
        assert "Broken ceiling at 3000 feet" in text
        assert "Temperature 6, dewpoint 4" in text

    def test_variable_wind(self):
        atis = self._make_atis(
            "ESSA 121900Z 20010KT 180V240 9999 FEW030 10/06 Q1018",
            "Delta",
        )
        text = build_atis_text(atis)
        assert "Wind 200 degrees 10 knots" in text
        assert "variable between 180 and 240 degrees" in text

    def test_calm_wind(self):
        atis = self._make_atis(
            "ESSA 121900Z 00000KT CAVOK 10/07 Q1018",
            "Echo",
        )
        text = build_atis_text(atis)
        assert "Wind calm" in text

    def test_negative_temperature(self):
        atis = self._make_atis(
            "ESSA 121800Z 09008KT 2000 -SN BKN010 M02/M04 Q1005",
            "Foxtrot",
        )
        text = build_atis_text(atis)
        assert "Temperature -2, dewpoint -4" in text
        assert "Visibility 2000 meters" in text
        assert "Light SN" in text

    def test_approach_in_use(self):
        atis = self._make_atis(
            "ESSA 121800Z 18010KT 9999 FEW030 10/07 Q1018",
            "Golf", ["01L"], "ILS 01L",
        )
        text = build_atis_text(atis)
        assert "Approach: ILS 01L" in text

    def test_with_notices(self):
        atis = self._make_atis(
            "ESSA 121800Z 18010KT 9999 FEW030 10/07 Q1018",
            "Hotel", ["01L"], notices=["WARNING: Taxiway Bravo closed"],
        )
        text = build_atis_text(atis)
        assert "WARNING: Taxiway Bravo closed" in text

    def test_missing_temp(self):
        atis = self._make_atis("ESSA 121800Z 18010KT 9999 FEW030 Q1018", "India")
        text = build_atis_text(atis)
        assert "Temperature" not in text
        assert "QNH 1018" in text

    def test_scattered_clouds_text(self):
        atis = self._make_atis(
            "ESSA 121800Z 18010KT 9999 SCT045 10/07 Q1018",
            "Kilo",
        )
        text = build_atis_text(atis)
        assert "Scattered clouds at 4500 feet" in text

    def test_overcast_text(self):
        atis = self._make_atis(
            "ESSA 121800Z 18010KT 9999 OVC120 10/07 Q1018",
            "Lima",
        )
        text = build_atis_text(atis)
        assert "Overcast at 12000 feet" in text
