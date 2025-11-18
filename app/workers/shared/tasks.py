"""
Shared tasks - общие задачи для всех воркеров.
Отправка сообщений в Telegram, планирование напоминаний.
"""
import dramatiq
import logging
from app.core.dramatiq_setup import redis_broker

logger = logging.getLogger(__name__)


@dramatiq.actor(broker=redis_broker, max_retries=1)
def schedule_task_reminder(user_id: int, chat_id: int, task_title: str, deadline_timestamp: int):
    """
    Отправляет напоминание о задаче пользователю.
    
    Args:
        user_id: ID пользователя Telegram
        chat_id: ID чата для отправки сообщения
        task_title: Название задачи
        deadline_timestamp: Timestamp дедлайна
    """
    try:
        logger.info(f"Shared: отправляем напоминание пользователю {user_id} о задаче '{task_title}'")
        
        # TODO: Реализовать отправку сообщения через Telegram Bot API
        reminder_text = f"⏰ Напоминание: у вас дедлайн по задаче '{task_title}'"
        send_telegram_message.send(chat_id=chat_id, text=reminder_text)
        
        logger.info(f"Shared: напоминание о задаче '{task_title}' отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"Shared: ошибка отправки напоминания пользователю {user_id}: {str(e)}")
        # Не поднимаем исключение, чтобы не делать retry для напоминаний


@dramatiq.actor(broker=redis_broker, max_retries=3)
def send_telegram_message(chat_id: int, text: str):
    """
    Отправляет сообщение в Telegram через Bot API.
    
    Args:
        chat_id: ID чата для отправки
        text: Текст сообщения
    """
    try:
        # TODO: Реализовать отправку через Telegram Bot API
        # Пока заглушка
        logger.info(f"Shared: отправка сообщения в чат {chat_id}: '{text[:50]}...'")
        
    except Exception as e:
        logger.error(f"Shared: ошибка отправки сообщения в чат {chat_id}: {str(e)}")
        raise