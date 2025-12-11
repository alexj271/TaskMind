#!/usr/bin/env python3
"""
Тест для проверки отсутствия дублирования агентов
"""

import asyncio
import time
import redis.asyncio as aioredis
from app.core.config import get_settings


async def simulate_messages():
    """Симулируем отправку сообщений в Redis stream"""
    settings = get_settings()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    
    user_id = "test_user_123"
    stream = f"agent:{user_id}:stream"
    
    # Отправляем несколько сообщений с интервалом
    for i in range(3):
        message_data = {
            "message": f"Test message {i+1}",
            "timestamp": str(int(time.time()))
        }
        
        msg_id = await redis.xadd(stream, message_data)
        print(f"Sent message {i+1}: {msg_id}")
        
        # Ждем между сообщениями
        await asyncio.sleep(2)
    
    await redis.close()


if __name__ == "__main__":
    asyncio.run(simulate_messages())