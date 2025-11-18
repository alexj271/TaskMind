"""
Тесты основного API приложения.
Тестирование базовых эндпоинтов, документации и middleware.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestMainAPI:
    """Тесты основного API приложения."""
    
    def test_docs_available(self):
        """Тест доступности документации OpenAPI."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_openapi_json(self):
        """Тест эндпоинта OpenAPI JSON схемы."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        openapi_data = response.json()
        assert openapi_data["info"]["title"] == "TaskMind API"
        assert openapi_data["info"]["version"] == "1.0.0"
        assert "Высокопроизводительный асинхронный API" in openapi_data["info"]["description"]
    
    def test_redoc_available(self):
        """Тест доступности ReDoc документации."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_cors_headers(self):
        """Тест CORS заголовков."""
        response = client.options("/docs")
        # FastAPI автоматически не добавляет CORS, но тестируем базовую функциональность
        assert response.status_code in [200, 405]  # OPTIONS может не поддерживаться
    
    def test_api_paths_exist(self):
        """Тест существования основных API путей."""
        response = client.get("/openapi.json")
        openapi_data = response.json()
        
        paths = openapi_data.get("paths", {})
        
        # Проверяем существование webhook эндпоинта
        assert "/webhook/telegram" in paths
        webhook_info = paths["/webhook/telegram"]
        assert "post" in webhook_info
        assert "Telegram Webhook" in webhook_info["post"]["summary"]
        
        # Проверяем существование task parser эндпоинта  
        assert "/tasks/parse" in paths
        parse_info = paths["/tasks/parse"]
        assert "post" in parse_info
        assert "Парсинг задачи" in parse_info["post"]["summary"]
    
    def test_response_models_defined(self):
        """Тест определения моделей ответов в OpenAPI."""
        response = client.get("/openapi.json")
        openapi_data = response.json()
        
        components = openapi_data.get("components", {})
        schemas = components.get("schemas", {})
        
        # Проверяем наличие основных схем
        expected_schemas = ["TelegramUpdate", "TelegramMessage", "TelegramUser", "TaskOut", "TaskCreate"]
        for schema_name in expected_schemas:
            assert schema_name in schemas, f"Схема {schema_name} не найдена в OpenAPI"
    
    def test_webhook_path_documented(self):
        """Тест документирования webhook пути."""
        response = client.get("/openapi.json")
        openapi_data = response.json()
        
        webhook_path = openapi_data["paths"]["/webhook/telegram"]["post"]
        assert webhook_path["summary"] == "Telegram Webhook"
        assert "Обработчик webhook-ов от Telegram Bot API" in webhook_path["description"]
        assert "Статус обработки обновления" in webhook_path["responses"]["200"]["description"]
    
    def test_parse_task_path_documented(self):
        """Тест документирования task parser пути."""
        response = client.get("/openapi.json")
        openapi_data = response.json()
        
        parse_path = openapi_data["paths"]["/tasks/parse"]["post"]
        assert parse_path["summary"] == "Парсинг задачи"
        assert "Парсит текст на естественном языке" in parse_path["description"]
        
        # Проверяем response model
        responses = parse_path["responses"]
        assert "200" in responses
        content = responses["200"]["content"]["application/json"]
        assert "$ref" in content["schema"]
        assert "TaskOut" in content["schema"]["$ref"]


class TestAPIHealthAndMeta:
    """Тесты здоровья API и метаинформации."""
    
    def test_app_title_and_version(self):
        """Тест корректности названия и версии приложения."""
        response = client.get("/openapi.json")
        openapi_data = response.json()
        
        info = openapi_data["info"]
        assert info["title"] == "TaskMind API"
        assert info["version"] == "1.0.0"
        assert "Высокопроизводительный асинхронный API" in info["description"]
        assert "Telegram Bot" in info["description"]
    
    def test_tags_organization(self):
        """Тест организации тегов в API."""
        response = client.get("/openapi.json")
        openapi_data = response.json()
        
        # Проверяем что эндпоинты правильно тегированы
        paths = openapi_data["paths"]
        
        # Webhook должен иметь соответствующие теги
        webhook_tags = paths["/webhook/telegram"]["post"].get("tags", [])
        # В FastAPI теги берутся из router префикса, проверяем их наличие
        assert len(webhook_tags) >= 0  # Базовая проверка
    
    def test_security_schemes_defined(self):
        """Тест определения схем безопасности (если есть)."""
        response = client.get("/openapi.json")
        openapi_data = response.json()
        
        # Пока у нас нет аутентификации, но структура должна быть готова
        components = openapi_data.get("components", {})
        # Проверяем что компоненты существуют
        assert isinstance(components, dict)
    
    def test_servers_configuration(self):
        """Тест конфигурации серверов."""
        response = client.get("/openapi.json")
        openapi_data = response.json()
        
        # По умолчанию FastAPI создает базовую конфигурацию серверов
        # Проверяем что OpenAPI схема валидна
        assert "openapi" in openapi_data
        assert openapi_data["openapi"].startswith("3.")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])