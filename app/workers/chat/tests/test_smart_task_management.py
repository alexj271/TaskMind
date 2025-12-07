import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.workers.chat.tasks import TaskTools
from app.models.task import Task
from app.models.user import User


class TestSmartTaskManagement:
    """Тесты для умного управления задачами через поиск с подтверждением"""
    
    @pytest_asyncio.fixture
    async def task_tools(self):
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
        """Мок задачи с расписанием"""
        task = MagicMock(spec=Task)
        task.id = "550e8400-e29b-41d4-a716-446655440001"
        task.user_task_id = 1
        task.title = "Купить хлеб"
        task.description = "В магазине на углу"
        task.scheduled_at = datetime(2025, 12, 8, 10, 0, tzinfo=timezone.utc)
        task.reminder_at = datetime(2025, 12, 8, 9, 30, tzinfo=timezone.utc)
        task.created_at = datetime.now(timezone.utc)
        task.similarity_distance = 0.2  # Высокое сходство
        return task

    # ===== Тесты для обновления задач =====
    
    @pytest.mark.asyncio
    async def test_find_task_for_update_success(self, task_tools, mock_user, mock_task):
        """Тест успешного поиска задачи для обновления"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.search_by_similarity = AsyncMock(return_value=[mock_task])
            
            # Вызываем метод
            result = await task_tools.find_task_for_update(
                query="хлеб",
                update_description="поменять описание"
            )
            
            # Проверяем результат
            assert result["action"] == "confirm_task_update"
            assert result["confirmation_required"] is True
            assert result["task_found"]["user_task_id"] == 1
            assert result["task_found"]["title"] == "Купить хлеб"
            assert result["confidence"] == "высокая"
            assert "Найдена задача #1" in result["message"]
            
            # Проверяем вызовы
            mock_task_repo.search_by_similarity.assert_called_once_with(mock_user.id, "хлеб", limit=5)
    
    @pytest.mark.asyncio
    async def test_find_task_for_update_no_results(self, task_tools, mock_user):
        """Тест когда задачи не найдены"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.search_by_similarity = AsyncMock(return_value=[])
            
            # Вызываем метод
            result = await task_tools.find_task_for_update("несуществующая задача")
            
            # Проверяем результат
            assert "error" in result
            assert "Задачи не найдены" in result["error"]
            assert "suggestion" in result
    
    @pytest.mark.asyncio
    async def test_confirm_and_update_task_success(self, task_tools, mock_user, mock_task):
        """Тест успешного подтверждения и обновления задачи"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.get_by_user_task_id = AsyncMock(return_value=mock_task)
            mock_task_repo.update_by_user_task_id = AsyncMock(return_value=1)
            
            # Вызываем метод
            result = await task_tools.confirm_and_update_task(
                task_id=str(mock_task.id),
                user_task_id=1,
                confirmed=True,
                title="Новый заголовок"
            )
            
            # Проверяем результат
            assert result["success"] is True
            assert result["action"] == "task_updated"
            assert "Задача #1 успешно обновлена!" in result["message"]
            
            # Проверяем что обновление было вызвано
            mock_task_repo.update_by_user_task_id.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_confirm_and_update_task_cancelled(self, task_tools):
        """Тест отмены обновления задачи"""
        result = await task_tools.confirm_and_update_task(
            task_id="some-id",
            user_task_id=1,
            confirmed=False
        )
        
        # Проверяем результат
        assert result["action"] == "cancelled"
        assert "отменено" in result["message"]

    # ===== Тесты для переноса задач =====
    
    @pytest.mark.asyncio
    async def test_find_task_for_reschedule_success(self, task_tools, mock_user, mock_task):
        """Тест успешного поиска задачи для переноса"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.search_by_similarity = AsyncMock(return_value=[mock_task])
            
            # Вызываем метод
            result = await task_tools.find_task_for_reschedule(
                query="хлеб",
                reschedule_description="перенести на завтра"
            )
            
            # Проверяем результат
            assert result["action"] == "confirm_task_reschedule"
            assert result["confirmation_required"] is True
            assert result["task_found"]["user_task_id"] == 1
            assert result["task_found"]["current_schedule"] == "запланировано на 08.12.2025 10:00"
            assert result["confidence"] == "высокая"
            assert "Переносим эту задачу?" in result["message"]
    
    @pytest.mark.asyncio
    async def test_find_task_for_reschedule_unscheduled_task(self, task_tools, mock_user):
        """Тест поиска незапланированной задачи для переноса"""
        # Создаем задачу без расписания
        unscheduled_task = MagicMock(spec=Task)
        unscheduled_task.id = "550e8400-e29b-41d4-a716-446655440002"
        unscheduled_task.user_task_id = 2
        unscheduled_task.title = "Прочитать книгу"
        unscheduled_task.description = "Художественная литература"
        unscheduled_task.scheduled_at = None
        unscheduled_task.reminder_at = None
        unscheduled_task.created_at = datetime.now(timezone.utc)
        unscheduled_task.similarity_distance = 0.25
        
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.search_by_similarity = AsyncMock(return_value=[unscheduled_task])
            
            # Вызываем метод
            result = await task_tools.find_task_for_reschedule("книга")
            
            # Проверяем результат
            assert result["task_found"]["current_schedule"] == "не запланировано"
    
    @pytest.mark.asyncio
    async def test_confirm_and_reschedule_task_success(self, task_tools, mock_user, mock_task):
        """Тест успешного подтверждения и переноса задачи"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.get_by_user_task_id = AsyncMock(return_value=mock_task)
            mock_task_repo.update_by_user_task_id = AsyncMock(return_value=1)
            
            new_date = "2025-12-09T14:00:00Z"
            
            # Вызываем метод
            result = await task_tools.confirm_and_reschedule_task(
                task_id=str(mock_task.id),
                user_task_id=1,
                confirmed=True,
                new_scheduled_at=new_date,
                keep_reminder=True
            )
            
            # Проверяем результат
            assert result["success"] is True
            assert result["action"] == "task_rescheduled"
            assert "успешно перенесена!" in result["message"]
            assert result["new_schedule"]["scheduled_at"] == new_date
            
            # Проверяем что обновление было вызвано
            mock_task_repo.update_by_user_task_id.assert_called_once()
            # Получаем параметры вызова
            call_args = mock_task_repo.update_by_user_task_id.call_args
            assert call_args[0][0] == mock_user.id  # user_id
            assert call_args[0][1] == 1  # user_task_id 
            # scheduled_at должен быть datetime объектом
            from datetime import datetime, timezone
            expected_dt = datetime(2025, 12, 9, 14, 0, tzinfo=timezone.utc)
            assert call_args[1]['scheduled_at'] == expected_dt
    
    @pytest.mark.asyncio
    async def test_confirm_and_reschedule_task_cancelled(self, task_tools):
        """Тест отмены переноса задачи"""
        result = await task_tools.confirm_and_reschedule_task(
            task_id="some-id",
            user_task_id=1,
            confirmed=False
        )
        
        # Проверяем результат
        assert result["action"] == "cancelled"
        assert "отменен" in result["message"]
    
    @pytest.mark.asyncio
    async def test_confirm_and_reschedule_task_no_new_time(self, task_tools, mock_user, mock_task):
        """Тест переноса задачи без указания нового времени"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.get_by_user_task_id = AsyncMock(return_value=mock_task)
            
            # Вызываем метод без указания нового времени
            result = await task_tools.confirm_and_reschedule_task(
                task_id=str(mock_task.id),
                user_task_id=1,
                confirmed=True
                # Не указываем new_scheduled_at и new_reminder_at
            )
            
            # Проверяем результат
            assert "error" in result
            assert "Не указано новое время для переноса" in result["error"]