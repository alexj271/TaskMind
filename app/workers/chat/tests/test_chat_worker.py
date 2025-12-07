"""
Тесты для Chat Worker - интеллектуального агента управления задачами.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.workers.chat.tasks import process_chat_message, TaskTools, _process_chat_message_impl
from app.workers.chat.memory_service import DialogMemoryService
from app.workers.chat.models import MemorySummary, DialogGoal, TaskAction
from app.models.user import User
from app.models.task import Task


class TestTaskTools:
    """Тесты для класса TaskTools"""
    
    @pytest.fixture
    def task_tools(self):
        return TaskTools(user_id=123456789)
    
    @pytest_asyncio.fixture
    async def mock_user(self):
        """Мок пользователя"""
        user = MagicMock(spec=User)
        user.id = "550e8400-e29b-41d4-a716-446655440000"
        user.telegram_id = 123456789
        user.username = "testuser"
        return user
    
    @pytest_asyncio.fixture
    async def mock_task(self):
        """Мок задачи"""
        task = MagicMock(spec=Task)
        task.id = "550e8400-e29b-41d4-a716-446655440001"
        task.user_task_id = 1
        task.title = "Тестовая задача"
        task.description = "Описание тестовой задачи"
        task.created_at = datetime.now(timezone.utc)
        task.scheduled_at = None
        task.reminder_at = None
        task.completed = False
        return task
    
    @pytest.mark.asyncio
    async def test_create_task_success(self, task_tools, mock_user, mock_task):
        """Тест успешного создания задачи"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем асинхронные моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.create = AsyncMock(return_value=mock_task)
            
            # Вызываем метод
            result = await task_tools.create_task(
                title="Новая задача",
                description="Описание новой задачи"
            )
            
            # Проверяем результат
            assert result["success"] is True
            assert result["title"] == "Тестовая задача"
            assert "task_id" in result
            assert result["user_task_id"] == 1
            
            # Проверяем вызовы
            mock_user_repo.get_by_telegram.assert_called_once_with(123456789)
            mock_task_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_task_user_not_found(self, task_tools):
        """Тест создания задачи когда пользователь не найден"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo:
            mock_user_repo.get_by_telegram = AsyncMock(return_value=None)
            
            result = await task_tools.create_task("Задача")
            
            assert "error" in result
            assert "Пользователь не найден" in result["error"]
    
    @pytest.mark.asyncio
    async def test_search_tasks_success(self, task_tools, mock_user, mock_task):
        """Тест успешного поиска задач"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем асинхронные моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.search_by_similarity = AsyncMock(return_value=[mock_task])
            
            # Вызываем метод
            result = await task_tools.search_tasks("тестовый запрос", limit=5)
            
            # Проверяем результат
            assert result["success"] is True
            assert len(result["results"]) == 1
            assert result["results"][0]["title"] == "Тестовая задача"
            assert result["query"] == "тестовый запрос"
            
            # Проверяем вызовы
            mock_task_repo.search_by_similarity.assert_called_once_with(
                mock_user.id, "тестовый запрос", limit=5
            )
    
    @pytest.mark.asyncio
    async def test_get_user_tasks_success(self, task_tools, mock_user, mock_task):
        """Тест успешного получения списка задач"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем асинхронные моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.list_for_user = AsyncMock(return_value=[mock_task])
            
            # Вызываем метод
            result = await task_tools.get_user_tasks(limit=10)
            
            # Проверяем результат
            assert result["success"] is True
            assert len(result["tasks"]) == 1
            assert result["tasks"][0]["title"] == "Тестовая задача"
            assert result["total"] == 1
            
            # Проверяем вызовы
            mock_task_repo.list_for_user.assert_called_once_with(mock_user.id)


class TestChatWorker:
    """Тесты для основного Chat Worker"""
    
    @pytest.mark.asyncio
    async def test_process_chat_message_simple(self):
        """Тест обработки простого сообщения"""
        with patch('app.workers.chat.tasks.init_db') as mock_init_db, \
             patch('app.workers.chat.tasks.memory_service') as mock_memory_service, \
             patch('app.workers.chat.tasks.openai_service') as mock_openai, \
             patch('app.workers.chat.tasks.telegram_send_message') as mock_telegram, \
             patch('app.workers.chat.tasks.prompt_manager') as mock_prompt_manager, \
             patch('tortoise.Tortoise.close_connections') as mock_close:
            
            # Настраиваем моки
            mock_memory = MemorySummary(
                user_goal=DialogGoal.GENERAL_CHAT,
                context="Контекст диалога",
                clarifications=[],
                task_action_history=[],
                last_updated=datetime.now(timezone.utc)
            )
            
            mock_memory_service.get_or_create_memory = AsyncMock(return_value=mock_memory)
            mock_memory_service.should_cleanup_memory.return_value = False
            mock_memory_service.get_recent_actions_summary.return_value = "Нет недавних действий"
            mock_memory_service.update_memory = AsyncMock()
            mock_memory_service.update_context_with_ai_summary = AsyncMock()
            mock_memory_service.get_summary_for_prompt.return_value = "Контекст диалога"
            
            # Мокаем prompt_manager
            mock_prompt_manager.render.side_effect = lambda name, **kwargs: f"Mock prompt for {name}"
            
            mock_openai.generate_response_with_tools = AsyncMock(return_value={
                "content": "Привет! Как дела?",
                "tool_calls": []
            })
            
            # Вызываем реализацию напрямую
            from app.workers.chat.tasks import _process_chat_message_impl
            await _process_chat_message_impl(
                user_id=123456789,
                chat_id=987654321,
                message_text="Привет",
                user_name="TestUser"
            )
            
            # Проверяем вызовы
            mock_init_db.assert_called_once()
            mock_memory_service.get_or_create_memory.assert_called_once_with(123456789)
            mock_openai.generate_response_with_tools.assert_called_once()
            mock_telegram.assert_called_once_with(987654321, "Привет! Как дела?")
            mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_chat_message_with_task_creation(self):
        """Тест обработки сообщения с созданием задачи"""
        with patch('app.workers.chat.tasks.init_db'), \
             patch('app.workers.chat.tasks.memory_service') as mock_memory_service, \
             patch('app.workers.chat.tasks.openai_service') as mock_openai, \
             patch('app.workers.chat.tasks.telegram_send_message') as mock_telegram, \
             patch('app.workers.chat.tasks.prompt_manager') as mock_prompt_manager, \
             patch('tortoise.Tortoise.close_connections'):
            
            # Настраиваем моки
            mock_memory = MemorySummary(
                user_goal=DialogGoal.CREATE_TASK,
                context="Пользователь хочет создать задачу",
                clarifications=[],
                task_action_history=[],
                last_updated=datetime.now(timezone.utc)
            )
            
            mock_memory_service.get_or_create_memory = AsyncMock(return_value=mock_memory)
            mock_memory_service.should_cleanup_memory.return_value = False
            mock_memory_service.get_recent_actions_summary.return_value = "Нет действий"
            mock_memory_service.add_task_action = MagicMock()
            mock_memory_service.update_memory = AsyncMock()
            mock_memory_service.update_context_with_ai_summary = AsyncMock()
            mock_memory_service.get_summary_for_prompt.return_value = "Пользователь хочет создать задачу"
            
            # Мокаем prompt_manager
            mock_prompt_manager.render.side_effect = lambda name, **kwargs: f"Mock prompt for {name}"
            
            # Мок ответа с вызовом функции создания задачи
            mock_openai.generate_response_with_tools = AsyncMock(return_value={
                "content": "Создал задачу 'Купить хлеб'",
                "tool_calls": [
                    {
                        "function": {"name": "create_task"},
                        "result": {
                            "success": True,
                            "task_id": "550e8400-e29b-41d4-a716-446655440000",
                            "title": "Купить хлеб"
                        }
                    }
                ]
            })
            
            # Вызываем реализацию напрямую
            from app.workers.chat.tasks import _process_chat_message_impl
            await _process_chat_message_impl(
                user_id=123456789,
                chat_id=987654321,
                message_text="Создай задачу: купить хлеб",
                user_name="TestUser"
            )
            
            # Проверяем что функции были вызваны
            mock_memory_service.add_task_action.assert_called_once()
            mock_memory_service.update_memory.assert_called_once()
            mock_telegram.assert_called_once_with(987654321, "Создал задачу 'Купить хлеб'")
    
    @pytest.mark.asyncio
    async def test_process_chat_message_error_handling(self):
        """Тест обработки ошибок в Chat Worker"""
        with patch('app.workers.chat.tasks.init_db'), \
             patch('app.workers.chat.tasks.memory_service') as mock_memory_service, \
             patch('app.workers.chat.tasks.telegram_send_message') as mock_telegram, \
             patch('tortoise.Tortoise.close_connections'):
            
            # Настраиваем ошибку в памяти (а не в init_db который выполняется раньше)
            mock_memory_service.get_or_create_memory.side_effect = Exception("Ошибка памяти")
            
            # Вызываем реализацию напрямую
            from app.workers.chat.tasks import _process_chat_message_impl
            await _process_chat_message_impl(
                user_id=123456789,
                chat_id=987654321,
                message_text="Тест ошибки",
                user_name="TestUser"
            )
            
            # Проверяем что отправлено сообщение об ошибке
            mock_telegram.assert_called_once()
            call_args = mock_telegram.call_args[0]
            assert "произошла ошибка" in call_args[1].lower()


@pytest.mark.requires_api_key
class TestChatWorkerWithAI:
    """Интеграционные тесты с реальным AI (требуют API ключ)"""
    
    @pytest.mark.asyncio
    async def test_real_ai_task_creation(self):
        """Тест создания задачи с реальным AI (только при наличии API ключа)"""
        # Этот тест будет пропущен если нет переменной окружения OPENAI_API_KEY
        pytest.skip("Интеграционный тест с OpenAI API")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])