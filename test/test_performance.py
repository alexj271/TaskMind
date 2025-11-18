"""
Тесты производительности API.
Нагрузочное тестирование критических эндпоинтов.
"""

import time
import asyncio
import pytest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
import httpx
from app.main import app

client = TestClient(app)


class TestAPIPerformance:
    """Тесты производительности API."""
    
    def test_docs_response_time(self):
        """Тест времени ответа документации."""
        start_time = time.time()
        response = client.get("/docs")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 1.0, f"Документация загружается слишком медленно: {response_time:.3f}s"
    
    def test_openapi_json_response_time(self):
        """Тест времени ответа OpenAPI схемы."""
        start_time = time.time()
        response = client.get("/openapi.json")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 0.5, f"OpenAPI JSON отвечает слишком медленно: {response_time:.3f}s"
    
    def test_webhook_validation_performance(self):
        """Тест производительности валидации webhook."""
        # Корректный payload для быстрой валидации
        valid_payload = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "date": 1640995200,
                "text": "test message",
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "first_name": "Test"
                },
                "chat": {
                    "id": 123456,
                    "type": "private"
                }
            }
        }
        
        start_time = time.time()
        response = client.post("/webhook/telegram", json=valid_payload)
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 0.1, f"Webhook валидация слишком медленная: {response_time:.3f}s"
    
    def test_concurrent_webhook_requests(self):
        """Тест обработки параллельных webhook запросов."""
        valid_payload = {
            "update_id": 124,
            "message": {
                "message_id": 2,
                "date": 1640995201,
                "text": "concurrent test",
                "from": {
                    "id": 123457,
                    "is_bot": False,
                    "first_name": "ConcurrentTest"
                },
                "chat": {
                    "id": 123457,
                    "type": "private"
                }
            }
        }
        
        def make_request():
            return client.post("/webhook/telegram", json=valid_payload)
        
        # Запускаем 5 параллельных запросов
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            responses = [future.result() for future in futures]
        end_time = time.time()
        
        # Все запросы должны быть успешными
        for response in responses:
            assert response.status_code == 200
        
        # Общее время не должно сильно превышать время одного запроса
        total_time = end_time - start_time
        assert total_time < 1.0, f"Параллельные запросы выполняются слишком медленно: {total_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_async_client_performance(self):
        """Тест производительности с асинхронным клиентом."""
        # Используем ASGITransport для тестирования FastAPI приложения
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
            
            # Тестируем несколько быстрых запросов
            tasks = []
            for i in range(10):
                task = async_client.get("/openapi.json")
                tasks.append(task)
            
            start_time = time.time()
            responses = await asyncio.gather(*tasks)
            end_time = time.time()
            
            # Все ответы должны быть успешными
            for response in responses:
                assert response.status_code == 200
            
            # 10 параллельных запросов должны выполняться быстро
            total_time = end_time - start_time
            assert total_time < 2.0, f"Асинхронные запросы слишком медленные: {total_time:.3f}s"
    
    def test_invalid_payload_performance(self):
        """Тест производительности валидации невалидных данных."""
        invalid_payloads = [
            {},  # Пустой payload
            {"invalid": "data"},  # Неправильная структура
            {"update_id": "not_a_number"},  # Неправильный тип
            {"update_id": 123, "message": {"invalid": "structure"}},  # Частично правильная структура
        ]
        
        for payload in invalid_payloads:
            start_time = time.time()
            response = client.post("/webhook/telegram", json=payload)
            end_time = time.time()
            
            # Ошибка валидации должна возвращаться быстро
            assert response.status_code == 422
            response_time = end_time - start_time
            assert response_time < 0.05, f"Валидация ошибки слишком медленная: {response_time:.3f}s для {payload}"
    
    def test_large_payload_handling(self):
        """Тест обработки больших payload."""
        # Создаем payload с длинным текстом
        large_text = "x" * 4000  # 4KB текста
        large_payload = {
            "update_id": 125,
            "message": {
                "message_id": 3,
                "date": 1640995202,
                "text": large_text,
                "from": {
                    "id": 123458,
                    "is_bot": False,
                    "first_name": "LargeTest"
                },
                "chat": {
                    "id": 123458,
                    "type": "private"
                }
            }
        }
        
        start_time = time.time()
        response = client.post("/webhook/telegram", json=large_payload)
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 0.2, f"Обработка большого payload слишком медленная: {response_time:.3f}s"


class TestMemoryUsage:
    """Тесты использования памяти (базовые)."""
    
    def test_multiple_requests_memory_stable(self):
        """Тест стабильности памяти при множественных запросах."""
        # Простой тест - делаем много запросов и проверяем что они все успешны
        # (признак того что нет серьезных утечек памяти)
        
        successful_requests = 0
        for i in range(50):
            response = client.get("/openapi.json")
            if response.status_code == 200:
                successful_requests += 1
        
        # Все запросы должны быть успешными
        assert successful_requests == 50, "Некоторые запросы завершились неудачно, возможна проблема с памятью"
    
    def test_webhook_requests_memory_stable(self):
        """Тест стабильности памяти при обработке webhook."""
        valid_payload = {
            "update_id": 126,
            "message": {
                "message_id": 4,
                "date": 1640995203,
                "text": "memory test",
                "from": {
                    "id": 123459,
                    "is_bot": False,
                    "first_name": "MemoryTest"
                },
                "chat": {
                    "id": 123459,
                    "type": "private"
                }
            }
        }
        
        successful_requests = 0
        for i in range(20):
            # Изменяем update_id для каждого запроса
            payload = valid_payload.copy()
            payload["update_id"] = 126 + i
            
            response = client.post("/webhook/telegram", json=payload)
            if response.status_code == 200:
                successful_requests += 1
        
        assert successful_requests == 20, "Некоторые webhook запросы завершились неудачно"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])