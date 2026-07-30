from pydantic_settings import BaseSettings


class WorldSettings(BaseSettings):
    world_tick_hz: float = 10.0
    conflict_detection_enabled: bool = True
    lateral_separation_nm: float = 5.0
    vertical_separation_ft: float = 1000.0
    terminal_lateral_separation_nm: float = 3.0
    trajectory_lookahead_s: float = 120.0
    redis_url: str = "redis://redis:6379/0"
    log_level: str = "info"

    model_config = {"env_prefix": "WORLD_", "env_file": ".env", "extra": "ignore"}


settings = WorldSettings()
