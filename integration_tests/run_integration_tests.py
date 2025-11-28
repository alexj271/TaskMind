#!/usr/bin/env python3
"""
Интеграционные тесты для TaskMind системы.
Запускает всю систему (API + воркеры), эмулирует Telegram вебхуки
и проверяет корректность обработки сообщений.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock

import httpx
import uvicorn
from fastapi import FastAPI
import redis.asyncio as redis

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app
from app.core.config import settings
from app.core.db import TORTOISE_ORM
from app.services.telegram_client import send_message as original_send_message
from app.workers.actors import *  # Импортируем все воркеры


class TelegramMessageInterceptor:
    """Перехватчик сообщений Telegram для тестирования"""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)

    def reset(self):
        """Очистить историю отправленных сообщений"""
        self.sent_messages.clear()

    async def mock_send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        """Мокаемая функция отправки сообщения"""
        message = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        self.sent_messages.append(message)
        self.logger.info(f"📨 Перехвачено сообщение в чат {chat_id}: {text[:100]}...")
        return {"ok": True, "result": {"message_id": len(self.sent_messages)}}

    def get_messages_for_chat(self, chat_id: int) -> List[Dict[str, Any]]:
        """Получить все сообщения для конкретного чата"""
        return [msg for msg in self.sent_messages if msg["chat_id"] == chat_id]

    def get_all_messages(self) -> List[Dict[str, Any]]:
        """Получить все отправленные сообщения"""
        return self.sent_messages.copy()


class IntegrationTestRunner:
    """Запускатель интеграционных тестов"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.telegram_interceptor = TelegramMessageInterceptor()
        self.api_server = None
        self.worker_tasks = []
        self.test_results = []

    async def setup_test_database(self):
        """Настройка тестовой базы данных SQLite"""
        self.logger.info("🗄️ Настройка тестовой базы данных (SQLite)")

        # Используем SQLite файл для Docker среды
        db_path = os.getenv("DB_PATH", "/tmp/test.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Модифицируем конфигурацию для использования SQLite
        test_tortoise_config = TORTOISE_ORM.copy()
        test_tortoise_config["connections"]["default"] = f"sqlite://{db_path}"

        # Инициализируем Tortoise с тестовой конфигурацией
        await Tortoise.init(config=test_tortoise_config)
        await Tortoise.generate_schemas(safe=True)  # safe=True для существующих таблиц

        self.logger.info(f"✅ Тестовая база данных настроена: {db_path}")

    async def start_api_server(self):
        """Запуск FastAPI сервера в фоне"""
        self.logger.info("🚀 Запуск FastAPI сервера")

        # В Docker среде API сервер запускается отдельно через docker-compose
        # Здесь мы просто проверяем его доступность
        await self.wait_for_api_server()
        self.logger.info("✅ FastAPI сервер доступен")

    async def wait_for_api_server(self, timeout: int = 30):
        """Ожидание запуска API сервера"""
        api_url = os.getenv("API_URL", "http://127.0.0.1:8001")

        for i in range(timeout):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{api_url}/docs", timeout=5.0)
                    if response.status_code == 200:
                        return
            except Exception:
                pass

            self.logger.info(f"⏳ Ожидание API сервера... ({i+1}/{timeout})")
            await asyncio.sleep(1)

        raise RuntimeError(f"API сервер не запустился в течение {timeout} секунд")

    async def start_workers(self):
        """Запуск Dramatiq воркеров в фоне"""
        self.logger.info("⚙️ Dramatiq воркеры должны быть запущены через docker-compose")

        # В Docker среде воркеры запускаются отдельно
        # Здесь мы просто проверяем их доступность через Redis
        await self.wait_for_workers()
        self.logger.info("✅ Dramatiq воркеры доступны")

    async def wait_for_workers(self, timeout: int = 10):
        """Ожидание запуска Dramatiq воркеров"""
        # Проверяем доступность Redis (индикатор того, что воркеры могут подключиться)
        import redis.asyncio as redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6382/1")

        for i in range(timeout):
            try:
                client = redis.from_url(redis_url)
                await client.ping()
                await client.aclose()
                return
            except Exception:
                pass

            self.logger.info(f"⏳ Ожидание воркеров... ({i+1}/{timeout})")
            await asyncio.sleep(1)

        raise RuntimeError(f"Воркеры не запустились в течение {timeout} секунд")

    def mock_telegram_client(self):
        """Мокаем Telegram клиент для перехвата сообщений"""
        self.logger.info("📡 Мокаем Telegram клиент")

        # Патчим функцию отправки сообщений
        patch.object(
            sys.modules['app.services.telegram_client'],
            'send_message',
            side_effect=self.telegram_interceptor.mock_send_message
        ).start()

        self.logger.info("✅ Telegram клиент замокан")

    async def send_test_webhook(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Отправка тестового вебхука"""
        api_url = os.getenv("API_URL", "http://127.0.0.1:8001")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{api_url}/webhook/telegram",
                    json=update_data,
                    timeout=30.0
                )
                return {
                    "status_code": response.status_code,
                    "response": response.json() if response.content else None,
                    "success": response.status_code == 200
                }
            except Exception as e:
                return {
                    "status_code": None,
                    "response": str(e),
                    "success": False
                }

    async def run_test_scenario(self, scenario_name: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Запуск тестового сценария"""
        self.logger.info(f"🧪 Запуск сценария: {scenario_name}")

        # Очищаем историю сообщений
        self.telegram_interceptor.reset()

        results = []
        start_time = time.time()

        for i, message_data in enumerate(messages):
            self.logger.info(f"📨 Отправка сообщения {i+1}/{len(messages)}")

            # Отправляем вебхук
            webhook_result = await self.send_test_webhook(message_data)

            # Ждем обработки (увеличиваем время для AI обработки)
            await asyncio.sleep(3)

            results.append({
                "message_index": i,
                "webhook_result": webhook_result,
                "sent_messages": self.telegram_interceptor.get_all_messages()
            })

        end_time = time.time()
        duration = end_time - start_time

        scenario_result = {
            "scenario_name": scenario_name,
            "duration": duration,
            "messages_count": len(messages),
            "results": results,
            "total_sent_messages": len(self.telegram_interceptor.get_all_messages()),
            "success": all(r["webhook_result"]["success"] for r in results)
        }

        self.test_results.append(scenario_result)
        self.logger.info(f"✅ Сценарий завершен: {scenario_name} ({duration:.2f}s)")
        return scenario_result

    def generate_report(self) -> Dict[str, Any]:
        """Генерация отчета о тестировании"""
        self.logger.info("📊 Генерация отчета")

        total_scenarios = len(self.test_results)
        successful_scenarios = sum(1 for r in self.test_results if r["success"])
        total_webhooks = sum(r["messages_count"] for r in self.test_results)
        total_messages_sent = sum(r["total_sent_messages"] for r in self.test_results)

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_scenarios": total_scenarios,
                "successful_scenarios": successful_scenarios,
                "failed_scenarios": total_scenarios - successful_scenarios,
                "success_rate": successful_scenarios / total_scenarios if total_scenarios > 0 else 0,
                "total_webhooks_sent": total_webhooks,
                "total_messages_sent": total_messages_sent
            },
            "scenarios": self.test_results,
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform,
                "test_database": "SQLite (Docker)",
                "environment": "Docker Compose"
            }
        }

        return report

    def save_report(self, report: Dict[str, Any], filename: str = None):
        """Сохранение отчета в файл"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"integration_test_report_{timestamp}.json"

        reports_dir = Path(__file__).parent / "reports"
        reports_dir.mkdir(exist_ok=True)

        report_path = reports_dir / filename

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.logger.info(f"💾 Отчет сохранен: {report_path}")
        return report_path

    async def run_integration_tests(self):
        """Основной метод запуска интеграционных тестов"""
        self.logger.info("🚀 Начало интеграционных тестов TaskMind")

        try:
            # Настройка тестовой среды
            await self.setup_test_database()
            self.mock_telegram_client()

            # Запуск сервисов
            await self.start_api_server()
            await self.start_workers()

            # Даем сервисам время на запуск
            await asyncio.sleep(2)

            # Определение тестовых сценариев
            test_scenarios = [
                {
                    "name": "timezone_setup",
                    "messages": [
                        {
                            "update_id": 1,
                            "message": {
                                "message_id": 1,
                                "from": {"id": 12345, "first_name": "TestUser"},
                                "chat": {"id": 12345, "type": "private"},
                                "date": int(time.time()),
                                "text": "Я из Москвы"
                            }
                        }
                    ]
                },
                {
                    "name": "task_creation",
                    "messages": [
                        {
                            "update_id": 2,
                            "message": {
                                "message_id": 2,
                                "from": {"id": 12345, "first_name": "TestUser"},
                                "chat": {"id": 12345, "type": "private"},
                                "date": int(time.time()),
                                "text": "Создай задачу: встреча завтра в 10 утра"
                            }
                        }
                    ]
                },
                {
                    "name": "chat_message",
                    "messages": [
                        {
                            "update_id": 3,
                            "message": {
                                "message_id": 3,
                                "from": {"id": 12345, "first_name": "TestUser"},
                                "chat": {"id": 12345, "type": "private"},
                                "date": int(time.time()),
                                "text": "Привет, как дела?"
                            }
                        }
                    ]
                }
            ]

            # Запуск тестовых сценариев
            for scenario in test_scenarios:
                await self.run_test_scenario(scenario["name"], scenario["messages"])

            # Генерация и сохранение отчета
            report = self.generate_report()
            report_path = self.save_report(report)

            # Вывод результатов
            self.print_summary(report)

            self.logger.info("✅ Интеграционные тесты завершены")
            return report_path

        except Exception as e:
            self.logger.error(f"❌ Ошибка в интеграционных тестах: {e}")
            raise
        finally:
            # Остановка сервисов
            await self.cleanup()

    def print_summary(self, report: Dict[str, Any]):
        """Вывод краткой сводки результатов"""
        summary = report["summary"]
        print("\n" + "="*60)
        print("📊 РЕЗУЛЬТАТЫ ИНТЕГРАЦИОННЫХ ТЕСТОВ")
        print("="*60)
        print(f"Всего сценариев: {summary['total_scenarios']}")
        print(f"Успешных: {summary['successful_scenarios']}")
        print(f"Проваленных: {summary['failed_scenarios']}")
        print(".1f")
        print(f"Отправлено вебхуков: {summary['total_webhooks_sent']}")
        print(f"Отправлено сообщений: {summary['total_messages_sent']}")
        print("="*60)

    async def cleanup(self):
        """Очистка ресурсов"""
        self.logger.info("🧹 Очистка ресурсов")

        # В Docker среде сервисы управляются docker-compose,
        # поэтому не останавливаем их здесь

        # Закрытие соединений с базой данных
        await Tortoise.close_connections()

        self.logger.info("✅ Очистка завершена")


async def main():
    """Главная функция"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Запуск интеграционных тестов
    runner = IntegrationTestRunner()
    report_path = await runner.run_integration_tests()

    print(f"\n📄 Подробный отчет сохранен: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())