"""
Telegram Bot API Client для отправки сообщений
"""
import httpx
import logging
from typing import Optional, Dict, Any
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TelegramClient:
    """Клиент для работы с Telegram Bot API"""
    
    def __init__(self, bot_token: str = None):
        settings = get_settings()
        self.bot_token = bot_token or settings.telegram_token
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.timeout = 30.0
        
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        """
        Отправляет сообщение в чат через Telegram Bot API
        
        Args:
            chat_id: ID чата для отправки
            text: Текст сообщения (до 4096 символов)
            parse_mode: Режим парсинга (HTML, Markdown, None)
            
        Returns:
            Dict с результатом API запроса
            
        Raises:
            httpx.HTTPError: При ошибке HTTP запроса
            Exception: При других ошибках API
        """
        if not text or not text.strip():
            raise ValueError("Текст сообщения не может быть пустым")
            
        # Обрезаем сообщение если слишком длинное
        if len(text) > 4096:
            text = text[:4093] + "..."
            logger.warning(f"Сообщение обрезано до 4096 символов для чата {chat_id}")
        
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        
        if parse_mode:
            payload["parse_mode"] = parse_mode
            
        url = f"{self.base_url}/sendMessage"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.debug(f"Отправка сообщения в чат {chat_id}: {text[:100]}...")
                
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                if not result.get("ok"):
                    error_description = result.get("description", "Unknown error")
                    raise Exception(f"Telegram API error: {error_description}")
                
                logger.info(f"Сообщение успешно отправлено в чат {chat_id}")
                return result
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP ошибка при отправке сообщения в чат {chat_id}: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Ошибка Telegram API при отправке в чат {chat_id}: {str(e)}")
                raise
    
    async def get_me(self) -> Dict[str, Any]:
        """
        Получает информацию о боте
        
        Returns:
            Dict с информацией о боте
        """
        url = f"{self.base_url}/getMe"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                
                result = response.json()
                
                if not result.get("ok"):
                    error_description = result.get("description", "Unknown error")
                    raise Exception(f"Telegram API error: {error_description}")
                
                return result
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP ошибка при получении информации о боте: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Ошибка Telegram API при получении информации о боте: {str(e)}")
                raise


# Глобальный экземпляр клиента
_telegram_client: Optional[TelegramClient] = None


def get_telegram_client() -> TelegramClient:
    """Получает глобальный экземпляр Telegram клиента"""
    global _telegram_client
    if _telegram_client is None:
        _telegram_client = TelegramClient()
    return _telegram_client


# Удобные функции для прямого использования
async def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
    """Отправляет сообщение через глобальный клиент"""
    client = get_telegram_client()
    return await client.send_message(chat_id, text, parse_mode)


async def get_bot_info() -> Dict[str, Any]:
    """Получает информацию о боте через глобальный клиент"""
    client = get_telegram_client()
    return await client.get_me()