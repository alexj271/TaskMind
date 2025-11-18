"""
Dramatiq actors для обработки Telegram сообщений.
Фоновая обработка сообщений от пользователей через очереди Redis.
"""

import dramatiq
import logging
from typing import Dict, Any
from app.core.dramatiq_setup import redis_broker
from app.services.openai_tools import OpenAIService
from app.core.config import settings

logger = logging.getLogger(__name__)

# Инициализируем OpenAI сервис
openai_service = OpenAIService()


@dramatiq.actor(broker=redis_broker, max_retries=3, min_backoff=1000, max_backoff=30000)
def process_telegram_message(update_id: int, message_data: Dict[str, Any]):
    """
    Обрабатывает сообщение от Telegram пользователя.
    
    Args:
        update_id: ID обновления от Telegram
        message_data: Данные сообщения в формате словаря
    """
    try:
        logger.info(f"Начинаем обработку сообщения update_id={update_id}")
        
        # Извлекаем основные данные
        message_text = message_data.get("text", "")
        user_id = None
        chat_id = message_data.get("chat", {}).get("id")
        
        if message_data.get("from_"):
            user_id = message_data["from_"]["id"]
            user_name = message_data["from_"].get("first_name", "Unknown")
        else:
            user_name = "Unknown"
        
        logger.info(f"Обрабатываем сообщение от {user_name} (ID: {user_id}): '{message_text[:100]}...'")
        
        # Если есть текст, пытаемся его распарсить
        if message_text.strip():
            # Отправляем в другой actor для парсинга задач
            parse_and_create_task.send(
                user_id=user_id,
                chat_id=chat_id,
                message_text=message_text,
                user_name=user_name
            )
        else:
            logger.info(f"Получено сообщение без текста от пользователя {user_id}")
            # TODO: отправить сообщение пользователю что бот понимает только текстовые сообщения
        
        logger.info(f"Сообщение update_id={update_id} успешно обработано")
        
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения update_id={update_id}: {str(e)}")
        raise  # Позволяем Dramatiq обработать retry логику


@dramatiq.actor(broker=redis_broker, max_retries=2, min_backoff=2000, max_backoff=60000)
def parse_and_create_task(user_id: int, chat_id: int, message_text: str, user_name: str):
    """
    Парсит текст сообщения и создает задачу с помощью AI.
    
    Args:
        user_id: ID пользователя Telegram
        chat_id: ID чата
        message_text: Текст сообщения для парсинга
        user_name: Имя пользователя
    """
    try:
        logger.info(f"Парсим задачу для пользователя {user_name} (ID: {user_id})")
        
        # Используем OpenAI для парсинга
        parsed_task = openai_service.parse_task(message_text)
        
        if parsed_task:
            logger.info(f"Задача успешно распарсена: {parsed_task.title}")
            
            # TODO: Сохранить задачу в базе данных
            # TODO: Отправить подтверждение пользователю в Telegram
            
            # Планируем напоминание если есть дедлайн
            if parsed_task.deadline:
                schedule_task_reminder.send_with_options(
                    args=(user_id, chat_id, parsed_task.title, parsed_task.deadline),
                    eta=parsed_task.deadline
                )
                logger.info(f"Запланировано напоминание о задаче '{parsed_task.title}' на {parsed_task.deadline}")
            
        else:
            logger.warning(f"Не удалось распарсить задачу из текста: '{message_text[:100]}...'")
            # TODO: отправить сообщение пользователю что не удалось понять задачу
        
    except Exception as e:
        logger.error(f"Ошибка парсинга задачи для пользователя {user_id}: {str(e)}")
        # TODO: отправить сообщение пользователю об ошибке
        raise


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
        logger.info(f"Отправляем напоминание пользователю {user_id} о задаче '{task_title}'")
        
        # TODO: Реализовать отправку сообщения через Telegram Bot API
        # reminder_text = f"⏰ Напоминание: у вас дедлайн по задаче '{task_title}'"
        # await send_telegram_message(chat_id, reminder_text)
        
        logger.info(f"Напоминание о задаче '{task_title}' отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания пользователю {user_id}: {str(e)}")
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
        logger.info(f"Отправка сообщения в чат {chat_id}: '{text[:50]}...'")
        
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения в чат {chat_id}: {str(e)}")
        raise