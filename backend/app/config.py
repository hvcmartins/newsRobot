from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:////data/newsrobot.db"
    port: int = 8000
    cors_origins: str = "*"
    secret_key: str = "changeme"
    log_level: str = "info"
    debug: bool = False

    ai_enabled: bool = True
    ai_provider: str = "claude"
    ai_api_key: Optional[str] = None
    ai_model: str = "claude-haiku-4-5-20251001"
    ai_base_url: str = "http://localhost:11434"
    ai_relevance_threshold: float = 0.3

    max_article_age_days: int = 30  # skip articles published more than N days ago

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
