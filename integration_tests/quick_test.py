#!/usr/bin/env python3
"""
Простой тест интеграционных тестов без Docker.
Используется для быстрой проверки функциональности.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from integration_tests.run_integration_tests import IntegrationTestRunner


async def quick_test():
    """Быстрый тест основных функций"""
    print("🧪 Запуск быстрого теста интеграционных функций")

    runner = IntegrationTestRunner()

    # Тестируем только мокаемую функциональность
    runner.mock_telegram_client()

    # Создаем тестовые сообщения
    test_messages = [
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 12345, "first_name": "TestUser"},
                "chat": {"id": 12345, "type": "private"},
                "date": 1638360000,
                "text": "Привет!"
            }
        }
    ]

    # Имитируем отправку сообщений
    for msg in test_messages:
        await runner.telegram_interceptor.mock_send_message(
            msg["message"]["chat"]["id"],
            f"Mock response to: {msg['message']['text']}"
        )

    # Проверяем, что сообщения перехвачены
    messages = runner.telegram_interceptor.get_all_messages()
    print(f"✅ Перехвачено {len(messages)} сообщений")

    for msg in messages:
        print(f"  📨 {msg['chat_id']}: {msg['text'][:50]}...")

    print("✅ Быстрый тест завершен успешно")


if __name__ == "__main__":
    asyncio.run(quick_test())