import pytest
import asyncio
import os
import sys
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Настройка для pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop():
    """Создает event loop для всей сессии тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Пометки для группировки тестов
def pytest_configure(config):
    """Регистрируем кастомные маркеры"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may be slow)"
    )
    config.addinivalue_line(
        "markers", "requires_api_key: marks tests that require real API keys"
    )
    config.addinivalue_line(
        "markers", "database: marks tests that use database"
    )


@pytest.fixture(scope="session")
def redis_test_setup():
    """Настройка Redis для тестов."""
    # Проверяем что Redis доступен для тестов
    import redis
    try:
        r = redis.Redis(host='localhost', port=6379, db=1)  # Используем БД 1 для тестов
        r.ping()
        r.flushdb()  # Очищаем тестовую БД
        yield r
        r.flushdb()  # Очищаем после тестов
    except redis.ConnectionError:
        pytest.skip("Redis не доступен для тестов")


@pytest.fixture
def client():
    """FastAPI test client."""
    from app.main import app
    with TestClient(app) as c:
        yield c