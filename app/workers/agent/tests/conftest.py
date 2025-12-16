import pytest
import pytest_asyncio
import asyncio
from tortoise import Tortoise


@pytest.fixture(scope="session")
def event_loop():
    """Создает event loop для всех тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def init_db():
    """Инициализирует тестовую БД перед каждым тестом"""
    # Используем in-memory SQLite для тестов
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": [
            "app.models.user",
            "app.models.task",
            "app.models.event",
            "app.models.dialog_session"
        ]}
    )
    await Tortoise.generate_schemas()
    
    yield
    
    # Закрываем соединения после теста
    await Tortoise.close_connections()
