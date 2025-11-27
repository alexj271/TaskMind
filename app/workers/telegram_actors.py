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
from app.core.logging_config import setup_logging
from app.workers.gatekeeper.tasks import _process_webhook_message_internal


# Настраиваем логирование при инициализации модуля
setup_logging()

logger = logging.getLogger(__name__)



@dramatiq.actor(broker=redis_broker, max_retries=3, min_backoff=1000, max_backoff=30000)
async def process_webhook_message(update_id: int, message_data: Dict[str, Any]):
    """
    Главная точка входа для всех webhook сообщений.
    Логирует историю сообщений и запускает классификацию.
    
    Args:
        update_id: ID обновления от Telegram
        message_data: Данные сообщения в формате словаря
    """
    await _process_webhook_message_internal(update_id, message_data)

    