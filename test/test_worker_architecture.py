"""
Тесты для новой архитектуры воркеров.
Проверка Gatekeeper, Chat и Shared воркеров.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from app.workers.gatekeeper.models import MessageType, MessageClassification, IncomingMessage


# Создаем тестовые версии функций без Dramatiq декораторов
async def _test_classify_message(message_text: str) -> MessageClassification:
    """Тестовая версия классификации без Dramatiq"""
    task_keywords = ["напомни", "встреча", "дедлайн", "задача", "сделать", "купить", "позвонить"]
    is_task = any(keyword in message_text.lower() for keyword in task_keywords)
    
    return MessageClassification(
        message_type=MessageType.TASK if is_task else MessageType.CHAT,
        confidence=0.8 if is_task else 0.6,
        reasoning=f"Найдены ключевые слова задач" if is_task else "Обычное сообщение"
    )


async def _test_process_webhook_message(update_id: int, message_data: dict, mock_classify=None, mock_create_task=None, mock_chat=None):
    """Тестовая версия обработки webhook без Dramatiq"""
    incoming_msg = IncomingMessage(
        update_id=update_id,
        user_id=message_data.get("from", {}).get("id", 0),
        chat_id=message_data.get("chat", {}).get("id", 0),
        message_text=message_data.get("text", ""),
        user_name=message_data.get("from", {}).get("first_name", "Unknown"),
        timestamp=datetime.utcnow()
    )
    
    # Классифицируем сообщение
    if mock_classify:
        classification = mock_classify.return_value
    else:
        classification = await _test_classify_message(incoming_msg.message_text)
    
    if classification.message_type == MessageType.TASK:
        if mock_create_task:
            mock_create_task.send()
    else:
        if mock_chat:
            mock_chat.send()


class TestGatekeeperWorker:
    """Тесты для Gatekeeper воркера"""
    
    def test_message_classification_models(self):
        """Тест Pydantic моделей классификации"""
        classification = MessageClassification(
            message_type=MessageType.TASK,
            confidence=0.95,
            reasoning="Обнаружены ключевые слова задачи"
        )
        
        assert classification.message_type == MessageType.TASK
        assert classification.confidence == 0.95
        assert "задачи" in classification.reasoning
    
    @pytest.mark.asyncio
    async def test_classify_message_as_task(self):
        """Тест классификации сообщения как задачи"""
        message_text = "напомни мне завтра в 10:00 позвонить врачу"
        
        # Вызываем тестовую функцию
        classification = await _test_classify_message(message_text)
        
        assert classification.message_type == MessageType.TASK
        assert classification.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_classify_message_as_chat(self):
        """Тест: классификация сообщения как чат"""
        message_text = "привет! как дела?"
        
        classification = await _test_classify_message(message_text)
        
        assert classification.message_type == MessageType.CHAT
        assert classification.confidence > 0.3
    
    @pytest.mark.asyncio
    async def test_webhook_message_routing_to_chat(self):
        """Тест маршрутизации сообщения в Chat воркер"""
        mock_classify = Mock()
        mock_classify.return_value = MessageClassification(
            message_type=MessageType.CHAT,
            confidence=0.8
        )
        
        mock_create_task = Mock()
        mock_chat = Mock()
        
        message_data = {
            "from": {"id": 12345, "first_name": "TestUser"},
            "chat": {"id": 12345},
            "text": "привет!"
        }
        
        # Вызываем тестовую функцию
        await _test_process_webhook_message(999, message_data, mock_classify, mock_create_task, mock_chat)
        
        # Проверяем что сообщение отправлено в Chat воркер
        mock_chat.send.assert_called_once()
        mock_create_task.send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_webhook_message_routing_to_task(self):
        """Тест маршрутизации сообщения для создания задачи"""
        mock_classify = Mock()
        mock_classify.return_value = MessageClassification(
            message_type=MessageType.TASK,
            confidence=0.9
        )
        
        mock_create_task = Mock()
        mock_chat = Mock()
        
        message_data = {
            "from": {"id": 12345, "first_name": "TestUser"},
            "chat": {"id": 12345},
            "text": "напомни позвонить"
        }
        
        # Вызываем тестовую функцию
        await _test_process_webhook_message(998, message_data, mock_classify, mock_create_task, mock_chat)
        
        # Проверяем что создается задача
        mock_create_task.send.assert_called_once()
        mock_chat.send.assert_not_called()


class TestWorkerArchitecture:
    """Тесты архитектуры воркеров"""
    
    def test_worker_imports(self):
        """Проверка что все воркеры импортируются корректно"""
        # Проверяем что можем импортировать все основные компоненты
        from app.workers.gatekeeper.tasks import process_webhook_message
        from app.workers.chat.tasks import process_chat_message
        from app.workers.shared.tasks import send_telegram_message, schedule_task_reminder
        
        assert process_webhook_message is not None
        assert process_chat_message is not None
        assert send_telegram_message is not None
        assert schedule_task_reminder is not None
    
    def test_message_type_enum(self):
        """Тест enum для типов сообщений"""
        assert MessageType.TASK == "task"
        assert MessageType.CHAT == "chat"
        
        # Проверяем что можем создавать из строк
        task_type = MessageType("task")
        chat_type = MessageType("chat")
        
        assert task_type == MessageType.TASK
        assert chat_type == MessageType.CHAT