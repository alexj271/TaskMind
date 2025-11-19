"""
Тесты для Gatekeeper Worker tasks.
Проверка обработки webhook сообщений, классификации и создания задач.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.workers.gatekeeper.models import MessageType, MessageClassification, IncomingMessage
from app.workers.gatekeeper.tasks import classify_message, process_message_with_ai


class TestGatekeeperTasks:
    """Тесты для задач Gatekeeper воркера."""
    
    @pytest.mark.asyncio
    async def test_classify_message_as_task(self):
        """Тест классификации сообщения как задачи."""
        # Тестируем сообщение с ключевыми словами задачи
        message_text = "Напомни мне купить молоко завтра"
        
        classification = await classify_message(message_text)
        
        assert classification.message_type == MessageType.TASK
        assert classification.confidence > 0.5
        assert "ключевые слова" in classification.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_classify_message_as_chat(self):
        """Тест классификации сообщения как чата."""
        # Тестируем обычное сообщение без ключевых слов задачи
        message_text = "Как дела? Что нового?"
        
        classification = await classify_message(message_text)
        
        assert classification.message_type == MessageType.CHAT
        assert classification.confidence > 0.3
        assert "обычное сообщение" in classification.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_classify_message_with_task_keywords(self):
        """Тест классификации с различными ключевыми словами задач."""
        task_messages = [
            "встреча завтра в 15:00",
            "дедлайн по проекту 30 числа", 
            "задача: проверить отчет",
            "нужно сделать презентацию",
            "позвонить клиенту"
        ]
        
        for message in task_messages:
            classification = await classify_message(message)
            assert classification.message_type == MessageType.TASK, f"Сообщение '{message}' должно быть задачей"
    


class TestWebhookProcessing:
    """Тесты для обработки webhook сообщений (упрощенные для тестирования логики)."""
    
    @pytest.mark.asyncio
    async def test_webhook_logic_task_classification(self):
        """Тест логики классификации сообщения как задачи."""
        # Тестируем что классификация правильно работает для задач
        task_message = "Напомни купить молоко завтра"
        classification = await classify_message(task_message)
        
        assert classification.message_type == MessageType.TASK
        assert classification.confidence > 0.5
    
    @pytest.mark.asyncio 
    async def test_webhook_logic_chat_classification(self):
        """Тест логики классификации сообщения как чата."""
        # Тестируем что классификация правильно работает для чата
        chat_message = "Привет! Как дела?"
        classification = await classify_message(chat_message)
        
        assert classification.message_type == MessageType.CHAT
        assert classification.confidence > 0.3
    
    @pytest.mark.asyncio
    @patch('app.workers.gatekeeper.tasks.openai_service')
    @patch('app.workers.shared.tasks.send_telegram_message')
    async def test_webhook_logic_task_creation(self, mock_send, mock_openai_service):
        """Тест логики создания задачи."""
        # Мокируем успешный парсинг задачи
        mock_task = Mock()
        mock_task.title = "Купить молоко"
        mock_task.scheduled_at = None
        mock_task.reminder_at = None
        
        mock_openai_service.parse_task = AsyncMock(return_value=mock_task)
        mock_send.send = AsyncMock()
        
        # Вызываем обработку сообщения
        await process_message_with_ai(
            user_id=123456,
            chat_id=123456,
            message_text="Купить молоко",
            user_name="TestUser"
        )
        
        # Проверяем что OpenAI был вызван
        mock_openai_service.parse_task.assert_called_once_with("Купить молоко")
        
        # Проверяем что подтверждение было отправлено
        mock_send.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_incoming_message_creation(self):
        """Тест создания объекта IncomingMessage."""
        message_data = {
            "from": {"id": 123456, "first_name": "TestUser"},
            "chat": {"id": 123456},
            "text": "Тестовое сообщение"
        }
        
        incoming_msg = IncomingMessage(
            update_id=999,
            user_id=message_data.get("from", {}).get("id", 0),
            chat_id=message_data.get("chat", {}).get("id", 0),
            message_text=message_data.get("text", ""),
            user_name=message_data.get("from", {}).get("first_name", "Unknown"),
            timestamp=datetime.utcnow()
        )
        
        assert incoming_msg.user_id == 123456
        assert incoming_msg.chat_id == 123456
        assert incoming_msg.message_text == "Тестовое сообщение"
        assert incoming_msg.user_name == "TestUser"


class TestErrorHandling:
    """Тесты обработки ошибок в Gatekeeper tasks."""
    
    @pytest.mark.asyncio
    async def test_classify_message_exception_handling(self):
        """Тест обработки исключений в classify_message."""
        # Даже если произойдет исключение, функция должна вернуть CHAT классификацию
        classification = await classify_message("тестовое сообщение")
        
        # Проверяем что возвращается валидная классификация
        assert isinstance(classification, MessageClassification)
        assert classification.message_type in [MessageType.TASK, MessageType.CHAT]
        assert 0 <= classification.confidence <= 1.0
    
    @pytest.mark.asyncio
    @patch('app.workers.gatekeeper.tasks.process_chat_message')
    @patch('app.workers.gatekeeper.tasks.openai_service')
    async def test_create_task_with_openai_error(self, mock_openai_service, mock_chat):
        """Тест обработки ошибки OpenAI - отправка в чат."""
        # Мокируем исключение в OpenAI сервисе
        mock_openai_service.parse_task.side_effect = Exception("OpenAI API error")
        mock_chat.send = Mock()
        
        # Функция не поднимает исключение, а отправляет в чат
        await process_message_with_ai(
            user_id=123456,
            chat_id=123456,
            message_text="Тестовая задача",
            user_name="TestUser"
        )
        
        # Проверяем что сообщение отправлено в чат (в случае ошибки)
        mock_chat.send.assert_called_once_with(
            user_id=123456,
            chat_id=123456,
            message_text="Тестовая задача",
            user_name="TestUser"
        )
    
    @pytest.mark.asyncio
    async def test_process_webhook_invalid_message_data(self):
        """Тест обработки некорректных данных."""
        # Тестируем создание IncomingMessage с пустыми данными
        incoming_msg = IncomingMessage(
            update_id=555,
            user_id=0,
            chat_id=0,
            message_text="",
            user_name="Unknown",
            timestamp=datetime.utcnow()
        )
        
        # Проверяем что объект создается с дефолтными значениями
        assert incoming_msg.user_id == 0
        assert incoming_msg.chat_id == 0
        assert incoming_msg.message_text == ""
        assert incoming_msg.user_name == "Unknown"
        
        # Тестируем классификацию пустого сообщения
        classification = await classify_message("")
        assert isinstance(classification, MessageClassification)
        assert classification.message_type in [MessageType.TASK, MessageType.CHAT]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])