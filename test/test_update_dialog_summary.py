"""
Тесты для update_dialog_summary в DialogRepository.
Тестируем логику обновления summary диалога.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.repositories.dialog_repository import DialogRepository
from app.models.dialog_session import DialogSession


@pytest.mark.database
@pytest.mark.asyncio
class TestUpdateDialogSummary:
    """Тесты для update_dialog_summary"""

    @patch('app.repositories.dialog_repository.generate_dialogue_summary')
    async def test_update_dialog_summary_with_previous_summary(self, mock_generate_summary):
        """Тест: обновление summary с предыдущим summary и сообщениями"""
        # Mock данные
        mock_session = Mock(spec=DialogSession)
        mock_session.summary = "Previous conversation summary"
        mock_session.last_messages = [
            {"role": "user", "content": "Hello", "timestamp": "2023-01-01"},
            {"role": "assistant", "content": "Hi there!", "timestamp": "2023-01-01"},
            {"role": "user", "content": "Create a task", "timestamp": "2023-01-01"},
            {"role": "assistant", "content": "Task created", "timestamp": "2023-01-01"}
        ]
        mock_session.save = AsyncMock()

        # Mock генерации summary
        mock_generate_summary.return_value = "Updated summary with new context"

        # Создаем репозиторий и вызываем метод
        repo = DialogRepository()
        await repo.update_dialog_summary(mock_session)

        # Проверки
        # Проверяем, что generate_dialogue_summary был вызван
        mock_generate_summary.assert_called_once()
        call_args = mock_generate_summary.call_args
        messages_arg = call_args[0][0]  # messages
        previous_summary_arg = call_args[0][1]  # previous_summary
        
        # Контекст должен содержать только последние сообщения (без previous summary)
        assert "Previous summary:" not in " ".join(messages_arg)
        assert "user: Hello" in messages_arg
        assert "assistant: Hi there!" in messages_arg
        assert "user: Create a task" in messages_arg
        assert "assistant: Task created" in messages_arg
        
        # previous_summary должен быть передан отдельно
        assert previous_summary_arg == "Previous conversation summary"

        # Проверяем, что summary обновлен
        assert mock_session.summary == "Updated summary with new context"
        
        # Проверяем, что last_messages оставлены только последние 2
        assert len(mock_session.last_messages) == 2
        assert mock_session.last_messages[0]["content"] == "Create a task"
        assert mock_session.last_messages[1]["content"] == "Task created"
        
        # Проверяем, что save был вызван
        mock_session.save.assert_called_once()

    @patch('app.repositories.dialog_repository.generate_dialogue_summary')
    async def test_update_dialog_summary_without_previous_summary(self, mock_generate_summary):
        """Тест: обновление summary без предыдущего summary"""
        # Mock данные
        mock_session = Mock(spec=DialogSession)
        mock_session.summary = None
        mock_session.last_messages = [
            {"role": "user", "content": "New message", "timestamp": "2023-01-01"}
        ]
        mock_session.save = AsyncMock()

        # Mock генерации summary
        mock_generate_summary.return_value = "New summary"

        # Создаем репозиторий и вызываем метод
        repo = DialogRepository()
        await repo.update_dialog_summary(mock_session)

        # Проверки
        mock_generate_summary.assert_called_once()
        call_args = mock_generate_summary.call_args
        messages_arg = call_args[0][0]
        previous_summary_arg = call_args[0][1]
        
        # Контекст должен содержать только сообщения (без previous summary)
        assert "Previous summary:" not in " ".join(messages_arg)
        assert "user: New message" in messages_arg
        
        # previous_summary должен быть пустым
        assert previous_summary_arg == ""

        assert mock_session.summary == "New summary"
        mock_session.save.assert_called_once()

    @patch('app.repositories.dialog_repository.generate_dialogue_summary')
    async def test_update_dialog_summary_empty_messages(self, mock_generate_summary):
        """Тест: обновление summary с пустыми сообщениями"""
        # Mock данные
        mock_session = Mock(spec=DialogSession)
        mock_session.summary = "Old summary"
        mock_session.last_messages = []
        mock_session.save = AsyncMock()

        # Mock генерации summary
        mock_generate_summary.return_value = "Summary from old context"

        # Создаем репозиторий и вызываем метод
        repo = DialogRepository()
        await repo.update_dialog_summary(mock_session)

        # Проверки
        mock_generate_summary.assert_called_once()
        call_args = mock_generate_summary.call_args
        messages_arg = call_args[0][0]
        previous_summary_arg = call_args[0][1]
        
        # Контекст должен быть пустым (нет сообщений)
        assert len(messages_arg) == 0
        
        # previous_summary должен быть передан
        assert previous_summary_arg == "Old summary"

        assert mock_session.summary == "Summary from old context"
        mock_session.save.assert_called_once()

    @patch('app.repositories.dialog_repository.generate_dialogue_summary')
    async def test_update_dialog_summary_few_messages(self, mock_generate_summary):
        """Тест: обновление summary с малым количеством сообщений (меньше 2)"""
        # Mock данные
        mock_session = Mock(spec=DialogSession)
        mock_session.summary = "Summary"
        mock_session.last_messages = [
            {"role": "user", "content": "Single message", "timestamp": "2023-01-01"}
        ]
        mock_session.save = AsyncMock()

        # Mock генерации summary
        mock_generate_summary.return_value = "Updated summary"

        # Создаем репозиторий и вызываем метод
        repo = DialogRepository()
        await repo.update_dialog_summary(mock_session)

        # Проверки
        mock_generate_summary.assert_called_once()
        call_args = mock_generate_summary.call_args
        messages_arg = call_args[0][0]
        previous_summary_arg = call_args[0][1]
        
        # Контекст должен содержать единственное сообщение
        assert "Previous summary:" not in " ".join(messages_arg)
        assert "user: Single message" in messages_arg
        
        # previous_summary должен быть передан
        assert previous_summary_arg == "Summary"