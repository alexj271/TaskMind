"""
Redis клиент для работы с флагами и состоянием пользователей.
"""
import redis.asyncio as redis
from app.core.config import get_settings

# Redis клиент для работы с флагами
redis_client = None

async def get_redis_client():
    """Получить Redis клиент для работы с флагами"""
    global redis_client
    if redis_client is None:
        settings = get_settings()
        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True
        )
    return redis_client

async def set_timezone_setup_flag(user_id: int):
    """Установить флаг ожидания установки таймзоны для пользователя"""
    client = await get_redis_client()
    key = f"timezone_setup:{user_id}"
    await client.setex(key, 3600, "1")  # Флаг живет 1 час

async def get_timezone_setup_flag(user_id: int) -> bool:
    """Проверить, установлен ли флаг ожидания установки таймзоны"""
    client = await get_redis_client()
    key = f"timezone_setup:{user_id}"
    value = await client.get(key)
    return value is not None

async def clear_timezone_setup_flag(user_id: int):
    """Снять флаг ожидания установки таймзоны"""
    client = await get_redis_client()
    key = f"timezone_setup:{user_id}"
    await client.delete(key)