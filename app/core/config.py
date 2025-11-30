from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from urllib.parse import urlparse


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Параметры базы данных
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5432)
    db_name: str = Field(default="taskmind")
    db_user: str = Field(default="user")
    db_password: str = Field(default="password")
    
    # Redis настройки для Dramatiq
    redis_url: str = Field(default="redis://localhost:6379/0")
    
    # Остальные настройки
    telegram_token: str = Field(default="TEST_TOKEN")
    openai_api_key: str | None = Field(default=None)
    openai_base_url: str | None = Field(default=None)
    gpt_model_full: str = Field(default="gpt-5")
    gpt_model_fast: str = Field(default="gpt-4.1-nano")
    timezone: str = "UTC"
    
    @property
    def redis_host(self) -> str:
        """Извлекает host из REDIS_URL"""
        parsed = urlparse(self.redis_url)
        return parsed.hostname or "localhost"
    
    @property
    def redis_port(self) -> int:
        """Извлекает port из REDIS_URL"""
        parsed = urlparse(self.redis_url)
        return parsed.port or 6379
    
    @property
    def redis_db(self) -> int:
        """Извлекает database из REDIS_URL"""
        parsed = urlparse(self.redis_url)
        if parsed.path and parsed.path != '/':
            db_part = parsed.path.lstrip('/')
            if db_part.isdigit():
                return int(db_part)
        return 0
    
    @property
    def redis_password(self) -> Optional[str]:
        """Извлекает password из REDIS_URL"""
        parsed = urlparse(self.redis_url)
        return parsed.password
    
    @property
    def postgres_dsn(self) -> str:
        """Конструирует DSN для PostgreSQL из отдельных параметров"""
        return f"postgres://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = None

def get_settings() -> Settings:
    """Получить настройки приложения с ленивой инициализацией"""
    global settings
    if settings is None:
        settings = Settings()
    return settings

def reset_settings():
    """Сбросить кэшированные настройки (для тестирования)"""
    global settings
    settings = None


settings = get_settings()