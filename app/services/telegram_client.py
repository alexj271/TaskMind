"""
Telegram Bot API Client для отправки сообщений
"""
import httpx
import logging
from typing import Optional, Dict, Any, List, Callable
from app.core.config import get_settings
from app.services.redis_pubsub import get_pubsub_service

logger = logging.getLogger(__name__)

# Глобальные переменные для тестирования
_testing_mode = False
_test_message_handlers = []


class TelegramClient:
    """Клиент для работы с Telegram Bot API"""
    
    def __init__(self, bot_token: str = None):
        settings = get_settings()
        self.bot_token = bot_token or settings.telegram_token
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.timeout = 30.0
        
    def enable_testing_mode(self):
        """Включает режим тестирования - сообщения не отправляются в Telegram API"""
        global _testing_mode
        _testing_mode = True
        logger.info("Telegram client: включен режим тестирования")
        
    def disable_testing_mode(self):
        """Отключает режим тестирования"""
        global _testing_mode
        _testing_mode = False
        logger.info("Telegram client: отключен режим тестирования")
        
    def add_test_message_handler(self, handler: Callable[[int, str], None]):
        """Добавляет обработчик сообщений для тестирования"""
        global _test_message_handlers
        _test_message_handlers.append(handler)
        
    def remove_test_message_handler(self, handler: Callable[[int, str], None]):
        """Удаляет обработчик сообщений для тестирования"""
        global _test_message_handlers
        try:
            _test_message_handlers.remove(handler)
        except ValueError:
            pass
        
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML", reply_markup: dict = None) -> Dict[str, Any]:
        """
        Отправляет сообщение в чат через Telegram Bot API или перехватывает в режиме тестирования
        
        Args:
            chat_id: ID чата для отправки
            text: Текст сообщения (до 4096 символов)
            parse_mode: Режим парсинга (HTML, Markdown, None)
            
        Returns:
            Dict с результатом API запроса или мок результат для тестирования
            
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
        
        # Проверяем флаг тестового режима в Redis для конкретного чата
        pubsub_service = get_pubsub_service()
        test_mode_flag = await pubsub_service.get_test_mode_flag(chat_id)
        
        if test_mode_flag:
            logger.info(f"Testing mode (Redis): перехвачено сообщение для чата {chat_id}: {text[:100]}...")
            
            # Отправляем сообщение через Redis Pub/Sub вместо Telegram API
            session_id = test_mode_flag.get("session_id")
            success = await pubsub_service.publish_bot_message(chat_id, text, session_id)
            
            if success:
                logger.info(f"Testing mode: сообщение отправлено через Redis Pub/Sub для сессии {session_id}")
            else:
                logger.error(f"Testing mode: ошибка отправки через Redis Pub/Sub")
            
            # Возвращаем мок успешного ответа
            return {
                "ok": True,
                "result": {
                    "message_id": 12345,
                    "date": 1704067200,
                    "chat": {"id": chat_id, "type": "private"},
                    "text": text,
                    "testing_mode": True,
                    "redis_pubsub": True
                }
            }
        
        # Обычный режим - отправляем в Telegram API
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
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

    async def answer_callback_query(self, callback_query_id: str, text: str = None, show_alert: bool = False) -> Dict[str, Any]:
        """
        Отвечает на callback query от inline клавиатуры
        
        Args:
            callback_query_id: ID callback query для ответа
            text: Опциональный текст уведомления (до 200 символов)
            show_alert: Показать как alert вместо уведомления
            
        Returns:
            Dict с результатом API запроса
        """
        payload = {
            "callback_query_id": callback_query_id
        }
        
        if text:
            payload["text"] = text[:200]  # Ограничение Telegram API
        if show_alert:
            payload["show_alert"] = show_alert
            
        url = f"{self.base_url}/answerCallbackQuery"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.debug(f"Отвечаем на callback query: {callback_query_id}")
                
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                if not result.get("ok"):
                    error_description = result.get("description", "Unknown error")
                    raise Exception(f"Telegram API error: {error_description}")
                
                logger.debug(f"Callback query успешно обработан: {callback_query_id}")
                return result
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP ошибка при ответе на callback query {callback_query_id}: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Ошибка Telegram API при ответе на callback query {callback_query_id}: {str(e)}")
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


# Функции для управления режимом тестирования
def enable_testing_mode():
    """Включает режим тестирования для всех Telegram сообщений"""
    client = get_telegram_client()
    client.enable_testing_mode()


def disable_testing_mode():
    """Отключает режим тестирования"""
    client = get_telegram_client()
    client.disable_testing_mode()


def add_test_message_handler(handler: Callable[[int, str], None]):
    """Добавляет обработчик для перехваченных сообщений в режиме тестирования"""
    client = get_telegram_client()
    client.add_test_message_handler(handler)


def remove_test_message_handler(handler: Callable[[int, str], None]):
    """Удаляет обработчик для перехваченных сообщений"""
    client = get_telegram_client()
    client.remove_test_message_handler(handler)