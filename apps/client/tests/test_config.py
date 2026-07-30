import os


class TestConfig:
    def test_defaults(self):
        from config import ClientSettings

        s = ClientSettings()
        assert s.ws_url == "ws://localhost:8000/ws/v1/telemetry"
        assert s.telemetry_rate_hz == 10.0
        assert s.callsign == "SAS123"
        assert s.use_mock is True

    def test_from_env(self):
        os.environ["WS_URL"] = "ws://test:9000/ws"
        os.environ["TELEMETRY_RATE_HZ"] = "20"
        os.environ["CALLSIGN"] = "UAL999"
        os.environ["USE_MOCK"] = "false"

        try:
            from config import ClientSettings

            s = ClientSettings()
            assert s.ws_url == "ws://test:9000/ws"
            assert s.telemetry_rate_hz == 20.0
            assert s.callsign == "UAL999"
            assert s.use_mock is False
        finally:
            for k in ["WS_URL", "TELEMETRY_RATE_HZ", "CALLSIGN", "USE_MOCK"]:
                os.environ.pop(k, None)
