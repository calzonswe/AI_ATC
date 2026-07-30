from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_dsn: str = "postgresql+asyncpg://atc_admin:atc_password_secret@postgres:5432/ai_atc"
    redis_url: str = "redis://redis:6379/0"
    ollama_url: str = "http://192.168.1.10:11434"
    ollama_model: str = "qwen3:30b"
    log_level: str = "info"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
