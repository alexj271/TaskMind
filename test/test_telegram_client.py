"""
Тест для Telegram Bot API клиента
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.services.telegram_client import TelegramClient, send_message


@pytest.mark.asyncio
async def test_telegram_client_send_message_success():
    """Тест успешной отправки сообщения"""
    
    # Мокаем httpx ответ
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "ok": True,
        "result": {
            "message_id": 123,
            "chat": {"id": 12345},
            "text": "Test message"
        }
    }
    mock_response.raise_for_status = AsyncMock()
    
    # Мокаем httpx клиент
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Создаем клиент и отправляем сообщение
        client = TelegramClient("test_token")
        result = await client.send_message(12345, "Test message")
        
        # Проверяем результат
        assert result["ok"] is True
        assert result["result"]["message_id"] == 123
        
        # Проверяем что был сделан правильный запрос
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.telegram.org/bottest_token/sendMessage"
        assert call_args[1]["json"]["chat_id"] == 12345
        assert call_args[1]["json"]["text"] == "Test message"


@pytest.mark.asyncio
async def test_telegram_client_send_message_too_long():
    """Тест обрезки слишком длинного сообщения"""
    
    # Мокаем httpx ответ
    mock_response = AsyncMock()
    mock_response.json.return_value = {"ok": True, "result": {}}
    mock_response.raise_for_status = AsyncMock()
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Создаем очень длинное сообщение (больше 4096 символов)
        long_message = "x" * 5000
        
        client = TelegramClient("test_token")
        await client.send_message(12345, long_message)
        
        # Проверяем что сообщение было обрезано
        call_args = mock_client.post.call_args
        sent_text = call_args[1]["json"]["text"]
        assert len(sent_text) == 4096
        assert sent_text.endswith("...")


@pytest.mark.asyncio
async def test_telegram_client_send_empty_message():
    """Тест отправки пустого сообщения"""
    
    client = TelegramClient("test_token")
    
    with pytest.raises(ValueError, match="Текст сообщения не может быть пустым"):
        await client.send_message(12345, "")
    
    with pytest.raises(ValueError, match="Текст сообщения не может быть пустым"):
        await client.send_message(12345, "   ")


@pytest.mark.asyncio
async def test_telegram_client_api_error():
    """Тест обработки ошибки Telegram API"""
    
    # Мокаем ответ с ошибкой
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "ok": False,
        "error_code": 400,
        "description": "Bad Request: chat not found"
    }
    mock_response.raise_for_status = AsyncMock()
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        client = TelegramClient("test_token")
        
        with pytest.raises(Exception, match="Telegram API error: Bad Request: chat not found"):
            await client.send_message(12345, "Test message")


@pytest.mark.asyncio
async def test_send_message_function():
    """Тест глобальной функции send_message"""
    
    mock_response = AsyncMock()
    mock_response.json.return_value = {"ok": True, "result": {}}
    mock_response.raise_for_status = AsyncMock()
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Тестируем глобальную функцию
        result = await send_message(12345, "Test message")
        
        assert result["ok"] is True
        mock_client.post.assert_called_once()