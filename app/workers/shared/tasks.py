"""
Shared tasks - общие задачи для всех воркеров.
Отправка сообщений в Telegram, планирование напоминаний.
"""
import dramatiq
import logging
import asyncio
from app.core.dramatiq_setup import redis_broker
from app.services.telegram_client import send_message as telegram_send_message
from app.core.db import init_db

logger = logging.getLogger(__name__)


@dramatiq.actor(broker=redis_broker, max_retries=1)
async def schedule_task_reminder(user_id: int, chat_id: int, task_title: str, deadline_timestamp: int):
    """
    Отправляет напоминание о задаче пользователю.
    
    Args:
        user_id: ID пользователя Telegram
        chat_id: ID чата для отправки сообщения
        task_title: Название задачи
        deadline_timestamp: Timestamp дедлайна
    """
    # Инициализируем Tortoise ORM для воркера
    await init_db()
    
    try:
        logger.info(f"Shared: отправляем напоминание пользователю {user_id} о задаче '{task_title}'")
        
        # Отправляем сообщение через Telegram Bot API
        reminder_text = f"⏰ Напоминание: у вас дедлайн по задаче '{task_title}'"
        await telegram_send_message(chat_id, reminder_text)
        
        logger.info(f"Shared: напоминание о задаче '{task_title}' отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"Shared: ошибка отправки напоминания пользователю {user_id}: {str(e)}")
        # Не поднимаем исключение, чтобы не делать retry для напоминаний
    finally:
        # Закрываем соединения после обработки
        from tortoise import Tortoise
        await Tortoise.close_connections()