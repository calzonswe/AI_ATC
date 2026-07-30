import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from phonetic import next_code
from models import PHONETIC_CODES


class TestNextCode:
    def test_none_returns_alpha(self):
        assert next_code(None) == "Alpha"

    def test_alpha_returns_bravo(self):
        assert next_code("Alpha") == "Bravo"

    def test_bravo_returns_charlie(self):
        assert next_code("Bravo") == "Charlie"

    def test_zulu_returns_alpha(self):
        assert next_code("Zulu") == "Alpha"

    def test_all_codes_wrap_correctly(self):
        for i, code in enumerate(PHONETIC_CODES):
            expected = PHONETIC_CODES[(i + 1) % len(PHONETIC_CODES)]
            assert next_code(code) == expected

    def test_invalid_code_returns_alpha(self):
        assert next_code("Invalid") == "Alpha"

    def test_case_sensitive(self):
        assert next_code("alpha") == "Alpha"


class TestPhoneticCodes:
    def test_26_codes(self):
        assert len(PHONETIC_CODES) == 26

    def test_first_is_alpha(self):
        assert PHONETIC_CODES[0] == "Alpha"

    def test_last_is_zulu(self):
        assert PHONETIC_CODES[-1] == "Zulu"

    def test_all_distinct(self):
        assert len(set(PHONETIC_CODES)) == len(PHONETIC_CODES)

    def test_standard_icao_sequence(self):
        expected = [
            "Alpha", "Bravo", "Charlie", "Delta", "Echo",
            "Foxtrot", "Golf", "Hotel", "India", "Juliett",
            "Kilo", "Lima", "Mike", "November", "Oscar",
            "Papa", "Quebec", "Romeo", "Sierra", "Tango",
            "Uniform", "Victor", "Whiskey", "X-ray", "Yankee", "Zulu",
        ]
        assert PHONETIC_CODES == expected
