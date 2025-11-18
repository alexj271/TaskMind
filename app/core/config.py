from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Параметры базы данных
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5432)
    db_name: str = Field(default="taskmind")
    db_user: str = Field(default="user")
    db_password: str = Field(default="password")
    
    # Redis настройки для Dramatiq
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=1)  # Используем базу 1 для тестов
    redis_password: str | None = Field(default=None)
    redis_url: str = Field(default="redis://localhost:6379/0")
    
    # Остальные настройки
    telegram_bot_token: str = Field(default="TEST_TOKEN")
    openai_api_key: str | None = Field(default=None)
    openai_base_url: str | None = Field(default=None)
    gpt_model: str = Field(default="gpt-3.5-turbo")
    timezone: str = "UTC"
    
    @property
    def postgres_dsn(self) -> str:
        """Конструирует DSN для PostgreSQL из отдельных параметров"""
        return f"postgres://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
settings = Settings()