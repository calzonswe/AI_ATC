from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_dsn: str = "postgresql+asyncpg://atc_admin:atc_password_secret@postgres:5432/ai_atc"
    redis_url: str = "redis://redis:6379/0"
    qdrant_url: str = "http://qdrant:6333"
    ollama_url: str = "http://192.168.1.10:11434"
    ollama_model: str = "qwen3:30b"
    atc_api_token: str = ""
    log_level: str = "info"

    auth_jwt_secret: str = "change-me-to-a-random-secret-at-least-32-chars"
    auth_jwt_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 30
    auth_refresh_token_expire_days: int = 7
    auth_admin_username: str = "admin"
    auth_admin_password: str = "atc_admin_secret"

    cors_allow_origins: str = "http://localhost:3000,http://localhost:80"

    metrics_enabled: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
