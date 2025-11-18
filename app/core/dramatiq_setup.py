"""
Интеграция с Dramatiq для асинхронной обработки задач.
Настройка и подключение к очередям сообщений через Redis.
"""

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import CurrentMessage, Callbacks
from dramatiq.middleware.asyncio import AsyncIO
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Создаем и настраиваем Redis брокер
redis_broker = RedisBroker(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    password=settings.redis_password if settings.redis_password else None
)

# Добавляем middleware для логирования и обработки ошибок
redis_broker.add_middleware(AsyncIO())  # Для поддержки async actors
redis_broker.add_middleware(CurrentMessage())
# Callbacks middleware добавляется автоматически, не добавляем дублирующий

# Устанавливаем брокер как глобальный
dramatiq.set_broker(redis_broker)

logger.info(f"Dramatiq инициализирован с Redis брокером: {settings.redis_host}:{settings.redis_port}")

# Экспортируем брокер для использования в других модулях
__all__ = ["redis_broker"]