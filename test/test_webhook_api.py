import pytest
import httpx
from fastapi.testclient import TestClient
from app.main import app


class TestWebhookAPI:
    """Тесты для API webhook эндпоинтов"""
    
    @pytest.fixture
    def client(self):
        """Фикстура для тестового клиента FastAPI"""
        return TestClient(app)
    
    def test_telegram_webhook_post(self, client):
        """Тест: POST запрос к /webhook/telegram"""
        # Пример payload от Telegram
        telegram_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 12345,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {
                    "id": 12345,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private"
                },
                "date": 1700000000,
                "text": "завтра встреча с клиентом в 10 утра"
            }
        }
        
        response = client.post("/webhook/telegram", json=telegram_update)
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
    
    def test_telegram_webhook_empty_payload(self, client):
        """Тест: POST запрос к /webhook/telegram с пустым payload"""
        response = client.post("/webhook/telegram", json={})
        
        # Теперь должен вернуть ошибку валидации
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    def test_telegram_webhook_invalid_json(self, client):
        """Тест: POST запрос к /webhook/telegram с невалидным JSON"""
        response = client.post(
            "/webhook/telegram", 
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_telegram_webhook_get_method_not_allowed(self, client):
        """Тест: GET запрос к /webhook/telegram должен вернуть 405"""
        response = client.get("/webhook/telegram")
        
        assert response.status_code == 405  # Method Not Allowed
    
    def test_webhook_root_endpoint_not_exists(self, client):
        """Тест: базовый /webhook эндпоинт не существует"""
        response = client.get("/webhook")
        
        assert response.status_code == 404  # Not Found
    
    def test_health_check_via_docs(self, client):
        """Тест: проверка что API документация доступна"""
        response = client.get("/docs")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_openapi_schema(self, client):
        """Тест: проверка OpenAPI схемы"""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        schema = response.json()
        
        # Проверяем что webhook эндпоинт есть в схеме
        assert "paths" in schema
        assert "/webhook/telegram" in schema["paths"]
        assert "post" in schema["paths"]["/webhook/telegram"]


class TestTasksAPI:
    """Тесты для API tasks эндпоинтов"""
    
    @pytest.fixture
    def client(self):
        """Фикстура для тестового клиента FastAPI"""
        return TestClient(app)
    
    def test_parse_task_endpoint(self, client):
        """Тест: POST запрос к /tasks/parse"""
        task_data = {
            "text": "завтра встреча с коллегой в 15:00"
        }
        
        # Этот тест требует user_id, который сейчас не реализован в API
        # Тестируем что эндпоинт существует и возвращает ошибку валидации
        response = client.post("/tasks/parse", json=task_data)
        
        # Ожидаем ошибку валидации из-за отсутствующего user_id
        assert response.status_code in [422, 400]  # Validation error or Bad Request


@pytest.mark.asyncio 
class TestAsyncAPI:
    """Асинхронные тесты API с httpx"""
    
    @pytest.mark.asyncio
    async def test_webhook_with_async_client(self):
        """Тест: асинхронный запрос к webhook"""
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            telegram_update = {
                "update_id": 987654321,
                "message": {
                    "message_id": 2,
                    "from": {"id": 54321, "is_bot": False, "first_name": "AsyncTest"},
                    "chat": {"id": 54321, "type": "private"},
                    "date": 1700000001,
                    "text": "купить продукты"
                }
            }
            
            response = await client.post("/webhook/telegram", json=telegram_update)
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_webhook_requests(self):
        """Тест: множественные одновременные запросы к webhook"""
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Создаем несколько одновременных запросов
            tasks = []
            for i in range(5):
                telegram_update = {
                    "update_id": 1000 + i,
                    "message": {
                        "message_id": i,
                        "from": {"id": 1000 + i, "is_bot": False, "first_name": f"User{i}"},
                        "chat": {"id": 1000 + i, "type": "private"},
                        "date": 1700000000 + i,
                        "text": f"задача номер {i}"
                    }
                }
                
                task = client.post("/webhook/telegram", json=telegram_update)
                tasks.append(task)
            
            # Выполняем все запросы одновременно
            import asyncio
            responses = await asyncio.gather(*tasks)
            
            # Проверяем что все запросы успешны
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"


class TestAPIErrorHandling:
    """Тесты обработки ошибок API"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_large_payload_handling(self, client):
        """Тест: обработка большого payload"""
        # Создаем большой payload (но не слишком большой для тестов)
        large_text = "текст задачи " * 1000  # ~13KB
        
        telegram_update = {
            "update_id": 999999999,
            "message": {
                "message_id": 999,
                "from": {"id": 99999, "is_bot": False, "first_name": "LargeTest"},
                "chat": {"id": 99999, "type": "private"},
                "date": 1700000999,
                "text": large_text
            }
        }
        
        response = client.post("/webhook/telegram", json=telegram_update)
        
        # Должен обработать даже большой payload
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_malformed_telegram_update(self, client):
        """Тест: некорректная структура Telegram update"""
        malformed_update = {
            "not_update_id": 123,
            "wrong_structure": "test"
        }
        
        response = client.post("/webhook/telegram", json=malformed_update)
        
        # Теперь должен вернуть ошибку валидации
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data