"""
Тесты для StateManager
"""
import pytest
import pytest_asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import redis.asyncio as aioredis

from app.workers.agent.state_manager import StateManager


@pytest_asyncio.fixture
async def redis_mock():
    """Мок Redis клиента"""
    mock = AsyncMock(spec=aioredis.Redis)
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    return mock


@pytest_asyncio.fixture
async def state_manager(redis_mock):
    """Создаёт StateManager для тестов"""
    manager = StateManager(user_id=12345, redis_client=redis_mock)
    return manager


class TestStateManagerInit:
    """Тесты инициализации"""
    
    @pytest.mark.asyncio
    async def test_init(self, state_manager):
        """Тест инициализации StateManager"""
        assert state_manager.user_id == 12345
        assert state_manager.redis_key == "agent:state:12345"
        assert "current_context" in state_manager.state
        assert "current_tasks" in state_manager.state
        assert "recent_actions" in state_manager.state
        assert "dialog_history" in state_manager.state


class TestRedisSync:
    """Тесты синхронизации с Redis"""
    
    @pytest.mark.asyncio
    async def test_load_from_redis_empty(self, state_manager, redis_mock):
        """Тест загрузки из пустого Redis"""
        redis_mock.get.return_value = None
        
        result = await state_manager.load_from_redis()
        
        assert result is False
        redis_mock.get.assert_called_once_with("agent:state:12345")
    
    @pytest.mark.asyncio
    async def test_load_from_redis_with_data(self, state_manager, redis_mock):
        """Тест загрузки существующего state из Redis"""
        test_state = {
            "user_id": 12345,
            "current_tasks": [{"task_id": "t_1", "status": "active"}],
            "metadata": {"total_interactions": 5}
        }
        redis_mock.get.return_value = json.dumps(test_state)
        
        result = await state_manager.load_from_redis()
        
        assert result is True
        assert state_manager.state["current_tasks"][0]["task_id"] == "t_1"
        assert state_manager.state["metadata"]["total_interactions"] == 5
    
    @pytest.mark.asyncio
    async def test_sync_to_redis(self, state_manager, redis_mock):
        """Тест сохранения в Redis"""
        state_manager.add_task("t_1", "active")
        
        result = await state_manager.sync_to_redis()
        
        assert result is True
        redis_mock.setex.assert_called_once()
        
        # Проверяем аргументы вызова
        call_args = redis_mock.setex.call_args
        assert call_args[0][0] == "agent:state:12345"  # key
        assert call_args[0][1] == 86400  # ttl
        
        # Проверяем, что данные можно десериализовать
        saved_data = json.loads(call_args[0][2])
        assert saved_data["current_tasks"][0]["task_id"] == "t_1"


class TestStateUpdates:
    """Тесты обновления полей state"""
    
    @pytest.mark.asyncio
    async def test_update_current_context(self, state_manager):
        """Тест обновления текущего контекста"""
        state_manager.update_current_context(
            intent="create_task",
            entities=["meeting", "tomorrow"]
        )
        
        assert state_manager.state["current_context"]["active_intent"] == "create_task"
        assert "meeting" in state_manager.state["current_context"]["mentioned_entities"]
        assert state_manager.state["current_context"]["last_interaction"] is not None
    
    @pytest.mark.asyncio
    async def test_add_task(self, state_manager):
        """Тест добавления задачи"""
        state_manager.add_task("t_1", "active", title="Test task")
        
        assert len(state_manager.state["current_tasks"]) == 1
        assert state_manager.state["current_tasks"][0]["task_id"] == "t_1"
        assert state_manager.state["current_tasks"][0]["status"] == "active"
        assert state_manager.state["current_tasks"][0]["title"] == "Test task"
    
    @pytest.mark.asyncio
    async def test_add_duplicate_task(self, state_manager):
        """Тест предотвращения дубликатов задач"""
        state_manager.add_task("t_1", "active")
        state_manager.add_task("t_1", "active")
        
        assert len(state_manager.state["current_tasks"]) == 1
    
    @pytest.mark.asyncio
    async def test_update_task_status(self, state_manager):
        """Тест обновления статуса задачи"""
        state_manager.add_task("t_1", "active")
        
        result = state_manager.update_task_status("t_1", "completed")
        
        assert result is True
        assert state_manager.state["current_tasks"][0]["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_remove_task(self, state_manager):
        """Тест удаления задачи"""
        state_manager.add_task("t_1", "active")
        state_manager.add_task("t_2", "active")
        
        result = state_manager.remove_task("t_1")
        
        assert result is True
        assert len(state_manager.state["current_tasks"]) == 1
        assert state_manager.state["current_tasks"][0]["task_id"] == "t_2"
    
    @pytest.mark.asyncio
    async def test_add_action(self, state_manager):
        """Тест добавления действия"""
        state_manager.add_action("task_created", "Создана задача", task_id="t_1")
        
        assert len(state_manager.state["recent_actions"]) == 1
        assert state_manager.state["recent_actions"][0]["type"] == "task_created"
        assert state_manager.state["recent_actions"][0]["task_id"] == "t_1"
    
    @pytest.mark.asyncio
    async def test_add_dialog_message(self, state_manager):
        """Тест добавления сообщения диалога"""
        state_manager.add_dialog_message("user", "Hello")
        state_manager.add_dialog_message("assistant", "Hi there!")
        
        assert len(state_manager.state["dialog_history"]) == 2
        assert state_manager.state["dialog_history"][0]["role"] == "user"
        assert state_manager.state["dialog_history"][1]["content"] == "Hi there!"


class TestStructuralOptimization:
    """Тесты структурной оптимизации"""
    
    @pytest.mark.asyncio
    async def test_remove_completed_tasks(self, state_manager):
        """Тест удаления завершённых задач"""
        state_manager.add_task("t_1", "active")
        state_manager.add_task("t_2", "completed")
        state_manager.add_task("t_3", "cancelled")
        state_manager.add_task("t_4", "active")
        
        stats = await state_manager.optimize_state()
        
        assert len(state_manager.state["current_tasks"]) == 2
        assert stats["tasks_removed"] == 2
        # Проверяем, что остались только активные
        for task in state_manager.state["current_tasks"]:
            assert task["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_trim_recent_actions(self, state_manager):
        """Тест обрезки списка действий"""
        # Добавляем действия напрямую в state, минуя add_action (который сам ограничивает)
        for i in range(15):
            action = {
                "type": "action",
                "description": f"Action {i}",
                "timestamp": datetime.now().isoformat()
            }
            state_manager.state["recent_actions"].append(action)
        
        assert len(state_manager.state["recent_actions"]) == 15
        
        stats = await state_manager.optimize_state()
        
        assert len(state_manager.state["recent_actions"]) == 10
        assert stats["actions_trimmed"] == 5
    
    @pytest.mark.asyncio
    async def test_limit_current_tasks(self, state_manager):
        """Тест ограничения количества задач"""
        # Добавляем больше задач чем лимит (MAX_CURRENT_TASKS = 20)
        for i in range(25):
            state_manager.add_task(f"t_{i}", "active")
        
        stats = await state_manager.optimize_state()
        
        assert len(state_manager.state["current_tasks"]) <= 20
        assert stats["tasks_removed"] >= 5


class TestSemanticCompression:
    """Тесты семантической компрессии"""
    
    @pytest.mark.asyncio
    async def test_needs_semantic_compression_by_length(self, state_manager):
        """Тест определения необходимости компрессии по длине"""
        # Добавляем много сообщений
        for i in range(35):
            state_manager.add_dialog_message("user", f"Message {i}")
        
        assert state_manager._needs_semantic_compression() is True
    
    @pytest.mark.asyncio
    async def test_needs_semantic_compression_by_tokens(self, state_manager):
        """Тест определения необходимости компрессии по токенам"""
        # Добавляем длинные сообщения
        long_message = "A" * 2000
        for i in range(5):
            state_manager.add_dialog_message("user", long_message)
        
        assert state_manager._needs_semantic_compression() is True
    
    @pytest.mark.asyncio
    async def test_semantic_compression_with_llm(self, state_manager):
        """Тест семантической компрессии с моком LLM"""
        # Добавляем историю диалога
        for i in range(20):
            state_manager.add_dialog_message("user", f"User message {i}")
            state_manager.add_dialog_message("assistant", f"Assistant response {i}")
        
        # Мокаем OpenAI клиент
        with patch('app.workers.agent.state_manager.AsyncOpenAI') as mock_openai:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps({
                "summary": "User discussed tasks and scheduling",
                "topics": ["tasks", "scheduling"],
                "user_preferences": {"prefers_morning": True}
            })
            
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            stats = await state_manager._semantic_compression()
            
            assert stats["semantic_compression"] == 1
            assert stats["dialog_compressed"] > 0
            assert state_manager.state["dialog_summary"] is not None
            assert len(state_manager.state["dialog_history"]) == 10  # Сокращено до 10


class TestRelevancePruning:
    """Тесты relevance pruning"""
    
    @pytest.mark.asyncio
    async def test_get_relevant_context_by_mention(self, state_manager):
        """Тест фильтрации по явному упоминанию"""
        state_manager.add_task("t_1", "active", title="Buy groceries")
        state_manager.add_task("t_2", "active", title="Call doctor")
        state_manager.add_task("t_3", "active", title="Meeting tomorrow")
        
        context = await state_manager.get_relevant_context("Show me task t_1")
        
        # Должна вернуться только задача t_1
        assert len(context["relevant_tasks"]) >= 1
        assert context["relevant_tasks"][0]["task_id"] == "t_1"
    
    @pytest.mark.asyncio
    async def test_get_relevant_context_by_recency(self, state_manager):
        """Тест фильтрации по недавним изменениям"""
        # Добавляем старую задачу
        state_manager.add_task("t_old", "active", title="Old task")
        state_manager.state["current_tasks"][0]["updated_at"] = (
            datetime.now() - timedelta(hours=5)
        ).isoformat()
        
        # Добавляем свежую задачу
        state_manager.add_task("t_new", "active", title="New task")
        
        context = await state_manager.get_relevant_context("What's new?")
        
        # Свежая задача должна быть в контексте
        task_ids = [t["task_id"] for t in context["relevant_tasks"]]
        assert "t_new" in task_ids
    
    @pytest.mark.asyncio
    async def test_get_relevant_context_limits_tasks(self, state_manager):
        """Тест ограничения количества задач в контексте"""
        # Добавляем много задач
        for i in range(10):
            state_manager.add_task(f"t_{i}", "active", title=f"Task {i}")
        
        context = await state_manager.get_relevant_context("Show all tasks")
        
        # Должно вернуться не более MAX_CONTEXT_TASKS (5)
        assert len(context["relevant_tasks"]) <= 5
    
    @pytest.mark.asyncio
    async def test_get_relevant_context_includes_summary(self, state_manager):
        """Тест включения summary в контекст"""
        state_manager.update_dialog_summary("User manages personal tasks")
        
        context = await state_manager.get_relevant_context("Help me")
        
        assert context["dialog_summary"] == "User manages personal tasks"


class TestStatistics:
    """Тесты статистики"""
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, state_manager):
        """Тест получения статистики"""
        state_manager.add_task("t_1", "active")
        state_manager.add_action("test", "Test action")
        state_manager.add_dialog_message("user", "Hello")
        
        stats = state_manager.get_statistics()
        
        assert stats["tasks_count"] == 1
        assert stats["actions_count"] == 1
        assert stats["dialog_messages"] == 1
        assert "metadata" in stats
