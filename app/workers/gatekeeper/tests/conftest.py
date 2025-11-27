import pytest
import asyncio
import os
import sys
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

@pytest.fixture(scope="session", autouse=True)
async def tortoise_test_setup():
    """Настройка Tortoise ORM для тестов."""
    from tortoise import Tortoise
    
    # Используем SQLite в памяти для тестов
    TORTOISE_ORM_TEST = {
        "connections": {"default": "sqlite://:memory:"},
        "apps": {
            "models": {
                "models": [
                    "app.models.user",
                    "app.models.task",
                    "app.models.dialog_session",
                    "app.models.city",
                    "aerich.models",
                ],
                "default_connection": "default",
            }
        },
    }
    
    await Tortoise.init(config=TORTOISE_ORM_TEST)
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()