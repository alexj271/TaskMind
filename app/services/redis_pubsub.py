"""
Redis Pub/Sub сервис для тестового режима.
Обеспечивает передачу сообщений между workers и GUI интерфейсом.
"""
import redis
import json
import logging
from typing import Dict, Any, Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class RedisPubSubService:
    """Сервис для работы с Redis Pub/Sub в тестовом режиме"""
    
    def __init__(self):
        settings = get_settings()
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True
        )
        self.test_channel_prefix = "taskMind:test:"
        
    def _get_test_channel(self, session_id: str) -> str:
        """Получает название канала для тестовой сессии"""
        return f"{self.test_channel_prefix}{session_id}"
    
    def _get_bot_response_channel(self, chat_id: int) -> str:
        """Получает название канала для ответов бота"""
        return f"{self.test_channel_prefix}bot_response:{chat_id}"
    
    async def publish_bot_message(self, chat_id: int, text: str, session_id: Optional[str] = None) -> bool:
        """
        Публикует сообщение от бота в Redis канал для перехвата в GUI
        
        Args:
            chat_id: ID чата
            text: Текст сообщения  
            session_id: ID тестовой сессии (опционально)
            
        Returns:
            bool: Успешность отправки
        """
        try:
            message_data = {
                "type": "bot_message",
                "chat_id": chat_id,
                "text": text,
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            }
            
            # Отправляем только в канал для конкретного чата (не дублируем в канал сессии)
            bot_channel = self._get_bot_response_channel(chat_id)
            result = self.redis_client.publish(bot_channel, json.dumps(message_data))
            
            logger.info(f"Redis PubSub: опубликовано сообщение в канал {bot_channel}, подписчиков: {result}")
            # Успех = сообщение опубликовано, даже если нет подписчиков
            return True
            
        except Exception as e:
            logger.error(f"Redis PubSub: ошибка публикации сообщения: {e}")
            return False
    
    async def publish_test_event(self, session_id: str, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Публикует тестовое событие в канал сессии
        
        Args:
            session_id: ID тестовой сессии
            event_type: Тип события (message_processed, error, etc.)
            data: Данные события
            
        Returns:
            bool: Успешность отправки
        """
        try:
            message_data = {
                "type": event_type,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                **data
            }
            
            channel = self._get_test_channel(session_id)
            result = self.redis_client.publish(channel, json.dumps(message_data))
            
            logger.info(f"Redis PubSub: опубликовано событие {event_type} в канал {channel}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Redis PubSub: ошибка публикации события: {e}")
            return False
    
    def subscribe_to_bot_responses(self, chat_id: int):
        """
        Создает подписчика на ответы бота для конкретного чата
        
        Args:
            chat_id: ID чата для подписки
            
        Returns:
            Redis PubSub объект
        """
        try:
            pubsub = self.redis_client.pubsub()
            channel = self._get_bot_response_channel(chat_id)
            pubsub.subscribe(channel)
            
            logger.info(f"Redis PubSub: создана подписка на канал {channel}")
            return pubsub
            
        except Exception as e:
            logger.error(f"Redis PubSub: ошибка создания подписки: {e}")
            return None
    
    def subscribe_to_session(self, session_id: str):
        """
        Создает подписчика на события тестовой сессии
        
        Args:
            session_id: ID тестовой сессии
            
        Returns:
            Redis PubSub объект
        """
        try:
            pubsub = self.redis_client.pubsub()
            channel = self._get_test_channel(session_id)
            pubsub.subscribe(channel)
            
            logger.info(f"Redis PubSub: создана подписка на сессию {session_id}")
            return pubsub
            
        except Exception as e:
            logger.error(f"Redis PubSub: ошибка создания подписки на сессию: {e}")
            return None
    
    async def set_test_mode_flag(self, chat_id: int, session_id: str, expires_in: int = 3600) -> bool:
        """
        Устанавливает флаг тестового режима для чата
        
        Args:
            chat_id: ID чата
            session_id: ID тестовой сессии  
            expires_in: Время жизни флага в секундах
            
        Returns:
            bool: Успешность установки
        """
        try:
            flag_key = f"taskMind:test_mode:{chat_id}"
            flag_data = {
                "session_id": session_id,
                "enabled": True,
                "created_at": datetime.now().isoformat()
            }
            
            result = self.redis_client.setex(
                flag_key, 
                expires_in, 
                json.dumps(flag_data)
            )
            
            logger.info(f"Redis: установлен флаг тестового режима для чата {chat_id}")
            return result
            
        except Exception as e:
            logger.error(f"Redis: ошибка установки флага тестового режима: {e}")
            return False
    
    async def get_test_mode_flag(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает флаг тестового режима для чата
        
        Args:
            chat_id: ID чата
            
        Returns:
            Dict с данными флага или None
        """
        try:
            flag_key = f"taskMind:test_mode:{chat_id}"
            flag_data = self.redis_client.get(flag_key)
            
            if flag_data:
                return json.loads(flag_data)
            return None
            
        except Exception as e:
            logger.error(f"Redis: ошибка получения флага тестового режима: {e}")
            return None
    
    async def clear_test_mode_flag(self, chat_id: int) -> bool:
        """
        Очищает флаг тестового режима для чата
        
        Args:
            chat_id: ID чата
            
        Returns:
            bool: Успешность очистки
        """
        try:
            flag_key = f"taskMind:test_mode:{chat_id}"
            result = self.redis_client.delete(flag_key)
            
            logger.info(f"Redis: очищен флаг тестового режима для чата {chat_id}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Redis: ошибка очистки флага тестового режима: {e}")
            return False


# Глобальный экземпляр сервиса
_pubsub_service: Optional[RedisPubSubService] = None


def get_pubsub_service() -> RedisPubSubService:
    """Получает глобальный экземпляр PubSub сервиса"""
    global _pubsub_service
    if _pubsub_service is None:
        _pubsub_service = RedisPubSubService()
    return _pubsub_service


from datetime import datetime