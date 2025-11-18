"""
Dramatiq задачи для Gatekeeper Worker.
Обработка входящих сообщений, классификация и маршрутизация.
"""
import dramatiq
import logging
from typing import Dict, Any
from datetime import datetime

from app.core.dramatiq_setup import redis_broker
from app.services.openai_tools import OpenAIService
from .models import IncomingMessage, MessageType, MessageClassification, ParsedTaskData
from ..chat.tasks import process_chat_message

logger = logging.getLogger(__name__)

# Инициализируем OpenAI сервис
openai_service = OpenAIService()


@dramatiq.actor(broker=redis_broker, max_retries=3, min_backoff=1000, max_backoff=30000)
async def process_webhook_message(update_id: int, message_data: Dict[str, Any]):
    """
    Главная точка входа для всех webhook сообщений.
    Логирует историю сообщений и запускает классификацию.
    
    Args:
        update_id: ID обновления от Telegram
        message_data: Данные сообщения в формате словаря
    """
    try:
        logger.info(f"Gatekeeper: обрабатываем сообщение update_id={update_id}")
        
        # Создаем объект входящего сообщения
        incoming_msg = IncomingMessage(
            update_id=update_id,
            user_id=message_data.get("from", {}).get("id", 0),
            chat_id=message_data.get("chat", {}).get("id", 0),
            message_text=message_data.get("text", ""),
            user_name=message_data.get("from", {}).get("first_name", "Unknown"),
            timestamp=datetime.utcnow()
        )
        
        # TODO: Сохранить в MessageHistory модель в БД
        logger.info(f"Gatekeeper: сохраняем историю сообщения от {incoming_msg.user_name}")
        
        # Классифицируем сообщение
        classification = await classify_message(incoming_msg.message_text)
        logger.info(f"Gatekeeper: классификация = {classification.message_type}, confidence = {classification.confidence}")
        
        if classification.message_type == MessageType.TASK:
            # Обрабатываем как задачу
            await create_task_from_message(
                user_id=incoming_msg.user_id,
                chat_id=incoming_msg.chat_id,
                message_text=incoming_msg.message_text,
                user_name=incoming_msg.user_name
            )
        else:
            # Отправляем в Chat Worker
            await process_chat_message.send(
                user_id=incoming_msg.user_id,
                chat_id=incoming_msg.chat_id,
                message_text=incoming_msg.message_text,
                user_name=incoming_msg.user_name
            )
            
        logger.info(f"Gatekeeper: сообщение update_id={update_id} успешно обработано")
        
    except Exception as e:
        logger.error(f"Gatekeeper: ошибка обработки сообщения update_id={update_id}: {str(e)}")
        raise


async def classify_message(message_text: str) -> MessageClassification:
    """
    Классифицирует сообщение с помощью AI.
    
    Args:
        message_text: Текст сообщения для классификации
        
    Returns:
        MessageClassification: Результат классификации
    """
    try:
        logger.info(f"Gatekeeper: классифицируем сообщение: '{message_text[:100]}...'")
        
        # TODO: Использовать специальный промпт для классификации
        # Пока используем простую эвристику
        task_keywords = ["напомни", "встреча", "дедлайн", "задача", "сделать", "купить", "позвонить"]
        
        is_task = any(keyword in message_text.lower() for keyword in task_keywords)
        
        classification = MessageClassification(
            message_type=MessageType.TASK if is_task else MessageType.CHAT,
            confidence=0.8 if is_task else 0.6,
            reasoning=f"Найдены ключевые слова задач" if is_task else "Обычное сообщение"
        )
        
        return classification
        
    except Exception as e:
        logger.error(f"Gatekeeper: ошибка классификации сообщения: {str(e)}")
        # В случае ошибки считаем обычным чатом
        return MessageClassification(
            message_type=MessageType.CHAT,
            confidence=0.3,
            reasoning="Ошибка классификации, по умолчанию чат"
        )


async def create_task_from_message(user_id: int, chat_id: int, message_text: str, user_name: str):
    """
    Создает задачу из классифицированного сообщения.
    
    Args:
        user_id: ID пользователя Telegram
        chat_id: ID чата
        message_text: Текст сообщения для парсинга
        user_name: Имя пользователя
    """
    try:
        logger.info(f"Gatekeeper: создаем задачу для пользователя {user_name} (ID: {user_id})")
        
        # Парсим задачу с помощью OpenAI
        parsed_task = await openai_service.parse_task(message_text)
        
        if parsed_task:
            logger.info(f"Gatekeeper: задача успешно распарсена: {parsed_task.title}")
            
            # TODO: Сохранить задачу в базе данных
            # TODO: Отправить подтверждение пользователю в Telegram
            
            # Планируем напоминание если есть запланированное время
            if parsed_task.scheduled_at:
                from ..shared.tasks import schedule_task_reminder
                scheduled_timestamp = int(parsed_task.scheduled_at.timestamp())
                schedule_task_reminder.send_with_options(
                    args=(user_id, chat_id, parsed_task.title, scheduled_timestamp),
                    eta=scheduled_timestamp
                )
                logger.info(f"Gatekeeper: запланировано напоминание о задаче '{parsed_task.title}' на {parsed_task.scheduled_at}")
            elif parsed_task.reminder_at:
                from ..shared.tasks import schedule_task_reminder
                reminder_timestamp = int(parsed_task.reminder_at.timestamp())
                schedule_task_reminder.send_with_options(
                    args=(user_id, chat_id, parsed_task.title, reminder_timestamp),
                    eta=reminder_timestamp
                )
                logger.info(f"Gatekeeper: запланировано напоминание о задаче '{parsed_task.title}' на {parsed_task.reminder_at}")
            
        else:
            logger.warning(f"Gatekeeper: не удалось распарсить задачу из текста: '{message_text[:100]}...'")
            # TODO: отправить сообщение пользователю что не удалось понять задачу
        
    except Exception as e:
        logger.error(f"Gatekeeper: ошибка создания задачи для пользователя {user_id}: {str(e)}")
        # TODO: отправить сообщение пользователю об ошибке
        raise