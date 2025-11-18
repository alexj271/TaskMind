"""
Дополнительные тесты для проверки специфических сценариев webhook API
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
import logging


class TestWebhookLogging:
    """Тесты логирования webhook"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_webhook_logs_message_processing(self, client, caplog):
        """Тест: webhook логирует обработку сообщений"""
        with caplog.at_level(logging.INFO):
            telegram_update = {
                "update_id": 555,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555, "is_bot": False, "first_name": "LogTest"},
                    "chat": {"id": 555, "type": "private"},
                    "date": 1700000000,
                    "text": "тестовое сообщение для логирования"
                }
            }
            
            response = client.post("/webhook/telegram", json=telegram_update)
            
            assert response.status_code == 200
            
            # Проверяем что лог содержит информацию об update_id
            log_messages = [record.message for record in caplog.records]
            assert any("Получено обновление от Telegram: update_id=555" in msg for msg in log_messages)
    
    def test_webhook_handles_message_without_from(self, client):
        """Тест: webhook обрабатывает сообщения без поля from"""
        telegram_update = {
            "update_id": 666,
            "message": {
                "message_id": 1,
                "chat": {"id": 666, "type": "channel"},
                "date": 1700000000,
                "text": "сообщение из канала без поля from"
            }
        }
        
        response = client.post("/webhook/telegram", json=telegram_update)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_webhook_handles_non_text_message(self, client):
        """Тест: webhook обрабатывает не-текстовые сообщения"""
        telegram_update = {
            "update_id": 777,
            "message": {
                "message_id": 1,
                "from": {"id": 777, "is_bot": False, "first_name": "PhotoTest"},
                "chat": {"id": 777, "type": "private"}, 
                "date": 1700000000,
                # Нет поля text - например, фото или стикер
                "photo": [{"file_id": "test_photo"}]
            }
        }
        
        response = client.post("/webhook/telegram", json=telegram_update)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestWebhookEdgeCases:
    """Тесты граничных случаев"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_webhook_with_minimal_valid_update(self, client):
        """Тест: минимально валидный update"""
        minimal_update = {
            "update_id": 999
            # Только update_id, без message
        }
        
        response = client.post("/webhook/telegram", json=minimal_update)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_webhook_with_very_long_text(self, client):
        """Тест: очень длинный текст сообщения"""
        very_long_text = "очень длинное сообщение " * 200  # ~5KB текста
        
        telegram_update = {
            "update_id": 1111,
            "message": {
                "message_id": 1,
                "from": {"id": 1111, "is_bot": False, "first_name": "LongText"},
                "chat": {"id": 1111, "type": "private"},
                "date": 1700000000,
                "text": very_long_text
            }
        }
        
        response = client.post("/webhook/telegram", json=telegram_update)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_webhook_with_unicode_text(self, client):
        """Тест: Unicode символы в тексте"""
        unicode_text = "задача с эмодзи 😀🎉 и символами ñáéíóú"
        
        telegram_update = {
            "update_id": 2222,
            "message": {
                "message_id": 1,
                "from": {"id": 2222, "is_bot": False, "first_name": "Unicode"},
                "chat": {"id": 2222, "type": "private"},
                "date": 1700000000,
                "text": unicode_text
            }
        }
        
        response = client.post("/webhook/telegram", json=telegram_update)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"