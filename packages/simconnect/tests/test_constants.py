import sys
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from openatc.simconnect.constants import SIMVARS, REQUIRED_VARS


class TestConstants:
    def test_required_vars_are_subset_of_simvars(self):
        for var in REQUIRED_VARS:
            assert var in SIMVARS, f"{var} not in SIMVARS"

    def test_all_simvars_have_string_values(self):
        for key, val in SIMVARS.items():
            assert isinstance(key, str)
            assert isinstance(val, str)
            assert len(val) > 0

    def test_required_vars_not_empty(self):
        assert len(REQUIRED_VARS) > 0

    def test_required_vars_covers_telemetry_contract(self):
        required_contract_fields = {
            "LATITUDE", "LONGITUDE", "ALTITUDE_MSL", "ALTITUDE_AGL",
            "HEADING_TRUE", "HEADING_MAG", "AIRSPEED_INDICATED",
            "GROUND_SPEED", "ON_GROUND", "COM1_FREQ", "COM2_FREQ",
            "TRANSPONDER_CODE", "ATC_ID",
        }
        for field in required_contract_fields:
            assert field in REQUIRED_VARS, f"{field} missing from REQUIRED_VARS"
