#!/usr/bin/env python3
"""
Скрипт для запуска Agent Worker
Запускает многопользовательскую систему агентов с MCP интеграцией

Usage:
    python app/run_agent_worker.py
    
    или из любой директории:
    python /home/alex/project/vscode/TaskMind/app/run_agent_worker.py

Требования:
    - MCP сервер должен работать на http://0.0.0.0:8001/mcp
    - Redis должен быть доступен
    - OpenAI API ключ должен быть настроен в .env
"""

import asyncio
import logging
import sys
import os

# Добавляем корневую директорию в путь для импортов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging_config import setup_logging
from app.workers.agent.worker import worker_loop


def main():
    """Основная функция запуска Agent Worker"""
    # Настраиваем логирование
    setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("TaskMind Agent Worker Starting...")
    logger.info("=" * 50)
    
    try:
        # Проверяем зависимости
        from app.core.config import get_settings
        settings = get_settings()
        
        logger.info(f"Redis URL: {settings.redis_url}")
        logger.info(f"MCP Server URL: {settings.mcp_server_url}")
        logger.info("Запуск многопользовательской системы агентов...")
        
        # Запускаем основной цикл воркера
        asyncio.run(worker_loop())
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания (Ctrl+C)")
        logger.info("Завершение работы Agent Worker...")
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        logger.error("Проверьте, что все зависимости установлены")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Критическая ошибка в Agent Worker: {e}")
        logger.error("Подробности в логах выше")
        raise
    finally:
        logger.info("Agent Worker остановлен")


if __name__ == "__main__":
    main()