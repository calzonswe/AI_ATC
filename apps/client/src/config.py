from pydantic_settings import BaseSettings


class ClientSettings(BaseSettings):
    ws_url: str = "ws://localhost:8000/ws/v1/telemetry"
    ws_token: str = ""
    telemetry_rate_hz: float = 10.0
    callsign: str = "SAS123"
    use_mock: bool = True
    mock_airport_icao: str = "ESSA"

    simconnect_address: str = "localhost"
    connect_retry_delay_s: float = 5.0
    connect_max_retries: int = 0

    log_level: str = "info"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = ClientSettings()
