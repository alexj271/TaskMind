"""
Интеграция с Dramatiq для асинхронной обработки задач.
Настройка и подключение к очередям сообщений через Redis.
"""

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import CurrentMessage, Callbacks
from dramatiq.middleware.asyncio import AsyncIO
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Глобальная переменная для брокера
_redis_broker = None

def get_redis_broker():
    """Получить Redis брокер с ленивой инициализацией"""
    global _redis_broker
    if _redis_broker is None:
        # Сбрасываем настройки, чтобы они считались заново из переменных окружения
        from app.core.config import reset_settings, get_settings
        reset_settings()
        
        settings = get_settings()
        logger.info(f"REDIS_URL = {settings.redis_url}")
        logger.info(f"Создание Redis брокера с настройками: host={settings.redis_host}, port={settings.redis_port}, db={settings.redis_db}")
        _redis_broker = RedisBroker(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password if settings.redis_password else None
        )
        
        # Добавляем middleware
        _redis_broker.add_middleware(AsyncIO())
        _redis_broker.add_middleware(CurrentMessage())
        
        # Устанавливаем брокер как глобальный для Dramatiq
        dramatiq.set_broker(_redis_broker)
        
        logger.info(f"Dramatiq инициализирован с Redis брокером: {settings.redis_host}:{settings.redis_port}")
    
    return _redis_broker

# Функция для инициализации Dramatiq (вызывается после загрузки настроек)
def init_dramatiq():
    """Инициализирует Dramatiq с правильными настройками Redis"""
    broker = get_redis_broker()
    return broker

# Для обратной совместимости - свойство, которое инициализирует брокер при первом обращении
class _LazyBroker:
    _instance = None
    
    def __str__(self):
        return str(self._instance) if self._instance else "<uninitialized broker>"
    
    def __getattr__(self, name):
        if self._instance is None:
            self._instance = get_redis_broker()
        return getattr(self._instance, name)

redis_broker = _LazyBroker()

# Экспортируем функции
__all__ = ["redis_broker", "get_redis_broker", "init_dramatiq"]