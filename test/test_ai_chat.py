import pytest
import asyncio
import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock

# Настройка для тестов с базой данных
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from app.services.openai_tools import chat, parse_task, get_openai_service
from app.schemas.task import ParsedTask
from app.models.task import Task
from app.models.user import User
from app.repositories.task_repository import TaskRepository
from app.services.task_service import TaskService
from tortoise import Tortoise


# event_loop фикстура теперь в conftest.py


@pytest.fixture(scope="session")
async def init_db():
    """Инициализация тестовой базы данных"""
    # Используем SQLite в памяти для тестов
    TORTOISE_ORM_TEST = {
        "connections": {"default": "sqlite://:memory:"},
        "apps": {
            "models": {
                "models": [
                    "app.models.user",
                    "app.models.task", 
                    "app.models.dialog_session"
                ],
                "default_connection": "default",
            }
        },
    }
    
    await Tortoise.init(config=TORTOISE_ORM_TEST)
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


@pytest.fixture
async def test_user():
    """Создает тестового пользователя"""
    # Инициализируем тестовую БД локально
    TORTOISE_ORM_TEST = {
        "connections": {"default": "sqlite://:memory:"},
        "apps": {
            "models": {
                "models": [
                    "app.models.user",
                    "app.models.task", 
                    "app.models.dialog_session"
                ],
                "default_connection": "default",
            }
        },
    }
    
    await Tortoise.init(config=TORTOISE_ORM_TEST)
    await Tortoise.generate_schemas()
    
    user = await User.create(telegram_id=12345)
    yield user
    
    await Tortoise.close_connections()


@pytest.mark.integration
class TestOpenAIIntegration:
    """
    Интеграционные тесты для реального взаимодействия с OpenAI API.
    Эти тесты требуют настоящий OPENAI_API_KEY в переменных окружения.
    """
    
    @pytest.mark.asyncio
    async def test_openai_service_requires_api_key(self):
        """Тест: сервис требует API key"""
        # Временно обнуляем ключ
        original_key = settings.openai_api_key
        settings.openai_api_key = None
        
        with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
            get_openai_service()
        
        # Восстанавливаем ключ
        settings.openai_api_key = original_key

    @pytest.mark.requires_api_key
    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "TEST_TOKEN",
        reason="Нужен реальный OPENAI_API_KEY для интеграционного теста"
    )
    @pytest.mark.asyncio
    async def test_real_chat(self):
        """Тест: реальный чат с OpenAI"""
        response = await chat("Привет! Как дела?")
        
        assert isinstance(response, str)
        assert len(response) > 0
        print(f"OpenAI ответ: {response}")

    @pytest.mark.requires_api_key
    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "TEST_TOKEN",
        reason="Нужен реальный OPENAI_API_KEY для интеграционного теста"
    )
    @pytest.mark.asyncio
    async def test_real_task_parsing(self):
        """Тест: реальный парсинг задач через OpenAI"""
        test_cases = [
            "завтра встреча с коллегой в 8 утра",
            "послезавтра звонок клиенту в 14:30",
            "в пятницу подать отчет до 17:00",
            "купить молоко",
            "встреча через час"
        ]
        
        for text in test_cases:
            print(f"\nТестируем: '{text}'")
            parsed = await parse_task(text)
            
            assert isinstance(parsed, ParsedTask)
            assert parsed.title is not None
            assert len(parsed.title) > 0
            
            print(f"  title: {parsed.title}")
            print(f"  description: {parsed.description}")
            print(f"  scheduled_at: {parsed.scheduled_at}")
            print(f"  reminder_at: {parsed.reminder_at}")

    @pytest.mark.requires_api_key
    @pytest.mark.database
    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "TEST_TOKEN",
        reason="Нужен реальный OPENAI_API_KEY для интеграционного теста"
    )
    @pytest.mark.asyncio
    async def test_full_task_creation_flow(self):
        """Тест: полный флоу создания задачи через AI + БД"""
        # Инициализируем тестовую БД
        TORTOISE_ORM_TEST = {
            "connections": {"default": "sqlite://:memory:"},
            "apps": {
                "models": {
                    "models": [
                        "app.models.user",
                        "app.models.task", 
                        "app.models.dialog_session"
                    ],
                    "default_connection": "default",
                }
            },
        }
        
        await Tortoise.init(config=TORTOISE_ORM_TEST)
        await Tortoise.generate_schemas()
        
        try:
            # Создаем тестового пользователя
            user = await User.create(telegram_id=12345)
            
            # Парсим задачу через AI
            text = "завтра встреча с коллегой в 9 утра"
            parsed_task = await parse_task(text)
            
            # Сохраняем в БД
            task_service = TaskService(TaskRepository())
            saved_task = await task_service.save_parsed(user.id, parsed_task)
            
            # Проверяем, что задача сохранена
            assert saved_task.id is not None
            assert saved_task.user_id == user.id
            assert saved_task.title == parsed_task.title
            
            # Проверяем, что задача есть в БД
            task_from_db = await Task.get(id=saved_task.id)
            assert task_from_db.title == parsed_task.title
            
            print(f"Сохранена задача: {task_from_db.title}")
            print(f"Время: {task_from_db.scheduled_at}")
            
        finally:
            await Tortoise.close_connections()

    @pytest.mark.asyncio
    async def test_fallback_parsing_without_api_key(self):
        """Тест: fallback парсинг без API ключа"""
        # Временно обнуляем ключ
        original_key = settings.openai_api_key
        settings.openai_api_key = None
        
        # Сбрасываем глобальный сервис
        import app.services.openai_tools
        app.services.openai_tools._openai_service = None
        
        try:
            # Этот тест должен пройти даже без ключа, используя fallback
            with pytest.raises(ValueError):
                await parse_task("тестовая задача")
        finally:
            # Восстанавливаем ключ
            settings.openai_api_key = original_key
            app.services.openai_tools._openai_service = None

    def test_parsed_task_schema_validation(self):
        """Тест: валидация схемы ParsedTask"""
        # Проверяем, что схема корректно работает с разными входными данными
        
        # Минимальная задача
        task1 = ParsedTask(title="Тест")
        assert task1.title == "Тест"
        assert task1.description is None
        assert task1.scheduled_at is None
        assert task1.reminder_at is None
        
        # Полная задача
        now = datetime.now()
        task2 = ParsedTask(
            title="Встреча",
            description="Важная встреча",
            scheduled_at=now,
            reminder_at=now
        )
        assert task2.title == "Встреча"
        assert task2.description == "Важная встреча"
        assert task2.scheduled_at == now
        assert task2.reminder_at == now


    @pytest.mark.requires_api_key
    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "TEST_TOKEN",
        reason="Нужен реальный OPENAI_API_KEY для интеграционного теста"
    )
    @pytest.mark.asyncio
    async def test_manual_openai_integration(self):
        """Ручной тест для отладки OpenAI интеграции"""
        print("🤖 Тестируем OpenAI интеграцию...")
        
        # Простой чат
        response = await chat("Скажи привет!")
        print(f"Чат: {response}")
        assert isinstance(response, str)
        assert len(response) > 0
        
        # Парсинг задачи
        parsed = await parse_task("завтра встреча с клиентом в 10 утра")
        print(f"Парсинг: {parsed}")
        assert isinstance(parsed, ParsedTask)
        assert parsed.title is not None
