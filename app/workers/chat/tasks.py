"""
Dramatiq задачи для Chat Worker.
Обработка разговорных сообщений и генерация ответов.
"""
import dramatiq
import logging
from typing import Optional

from app.core.dramatiq_setup import redis_broker
from app.services.openai_tools import OpenAIService
from app.core.db import init_db
from app.services.telegram_client import send_message as telegram_send_message

logger = logging.getLogger(__name__)

# Инициализируем OpenAI сервис
openai_service = OpenAIService()


@dramatiq.actor(broker=redis_broker, max_retries=2, min_backoff=2000, max_backoff=60000)
async def process_chat_message(user_id: int, chat_id: int, message_text: str, user_name: str):
    """
    Обрабатывает разговорное сообщение и генерирует ответ.
    
    Args:
        user_id: ID пользователя Telegram
        chat_id: ID чата
        message_text: Текст сообщения
        user_name: Имя пользователя
    """
    # Инициализируем Tortoise ORM для воркера
    await init_db()
    
    try:
        logger.info(f"Chat: обрабатываем сообщение от {user_name} (ID: {user_id})")
        
        # TODO: Получить историю диалога из БД
        # TODO: Сгенерировать ответ с помощью AI
        
        # Пока простой ответ
        response_text = f"Привет, {user_name}! Я получил твое сообщение: '{message_text}'. Это обычный чат, а не создание задачи."
        
        # Отправляем ответ в Telegram
        await telegram_send_message(chat_id, response_text)
        
        logger.info(f"Chat: ответ отправлен пользователю {user_name}")
        
    except Exception as e:
        logger.error(f"Chat: ошибка обработки сообщения от пользователя {user_id}: {str(e)}")
    finally:
        # Закрываем соединения после обработки
        from tortoise import Tortoise
        await Tortoise.close_connections()
        raise