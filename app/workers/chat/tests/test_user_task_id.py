import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.workers.chat.tasks import TaskTools
from app.models.task import Task
from app.models.user import User


class TestUserTaskId:
    """Тесты для функциональности user_task_id"""
    
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
        """Мок задачи с user_task_id"""
        task = MagicMock(spec=Task)
        task.id = "550e8400-e29b-41d4-a716-446655440001"
        task.user_task_id = 1
        task.title = "Тестовая задача"
        task.description = "Описание задачи"
        task.created_at = datetime.now(timezone.utc)
        return task
    
    @pytest.mark.asyncio
    async def test_update_task_by_user_id_success(self, task_tools, mock_user, mock_task):
        """Тест успешного обновления задачи по user_task_id"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.get_by_user_task_id = AsyncMock(return_value=mock_task)
            mock_task_repo.update_by_user_task_id = AsyncMock(return_value=1)
            
            # Вызываем метод
            result = await task_tools.update_task_by_user_id(
                user_task_id=1,
                title="Обновленная задача"
            )
            
            # Проверяем результат
            assert result["success"] is True
            assert result["user_task_id"] == 1
            assert "task_id" in result
            
            # Проверяем что методы были вызваны правильно
            mock_task_repo.get_by_user_task_id.assert_called_once_with(mock_user.id, 1)
            mock_task_repo.update_by_user_task_id.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_update_task_by_user_id_not_found(self, task_tools, mock_user):
        """Тест обновления несуществующей задачи"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.get_by_user_task_id = AsyncMock(return_value=None)
            
            # Вызываем метод
            result = await task_tools.update_task_by_user_id(
                user_task_id=999,
                title="Новый заголовок"
            )
            
            # Проверяем результат
            assert "error" in result
            assert "Задача #999 не найдена" in result["error"]
    
    @pytest.mark.asyncio
    async def test_delete_task_by_user_id_success(self, task_tools, mock_user, mock_task):
        """Тест успешного удаления задачи по user_task_id"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.get_by_user_task_id = AsyncMock(return_value=mock_task)
            mock_task_repo.delete_by_user_task_id = AsyncMock(return_value=1)
            
            # Вызываем метод
            result = await task_tools.delete_task_by_user_id(user_task_id=1)
            
            # Проверяем результат
            assert result["success"] is True
            assert result["user_task_id"] == 1
            assert result["deleted"] is True
            
            # Проверяем что методы были вызваны правильно
            mock_task_repo.get_by_user_task_id.assert_called_once_with(mock_user.id, 1)
            mock_task_repo.delete_by_user_task_id.assert_called_once_with(mock_user.id, 1)
    
    @pytest.mark.asyncio
    async def test_delete_task_by_user_id_not_found(self, task_tools, mock_user):
        """Тест удаления несуществующей задачи"""
        with patch('app.workers.chat.tasks.user_repo') as mock_user_repo, \
             patch('app.workers.chat.tasks.task_repo') as mock_task_repo:
            
            # Настраиваем моки
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)
            mock_task_repo.get_by_user_task_id = AsyncMock(return_value=None)
            
            # Вызываем метод
            result = await task_tools.delete_task_by_user_id(user_task_id=999)
            
            # Проверяем результат
            assert "error" in result
            assert "Задача #999 не найдена" in result["error"]