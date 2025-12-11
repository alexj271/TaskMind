"""
Конфигурация логирования для TaskMind.
Настройка разделения INFO логов (stdout) и ERROR логов (stderr).
"""

import logging
import sys
from typing import Dict, Any


class InfoFilter(logging.Filter):
    """Фильтр для пропуска только INFO и DEBUG сообщений."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= logging.INFO


class ErrorFilter(logging.Filter):
    """Фильтр для пропуска только WARNING, ERROR и CRITICAL сообщений."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.WARNING


def setup_logging(log_level: str = "DEBUG") -> None:
    """
    Настройка логирования с разделением потоков только для app модулей.
    Не затрагиваем root logger, чтобы не конфликтовать с Dramatiq.
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    
    # Handler для INFO и DEBUG (stdout)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(InfoFilter())
    stdout_formatter = logging.Formatter(
        '[%(asctime)s] [PID %(process)d] [%(threadName)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    stdout_handler.setFormatter(stdout_formatter)
    
    # Handler для WARNING, ERROR, CRITICAL (stderr)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.addFilter(ErrorFilter())
    stderr_formatter = logging.Formatter(
        '[%(asctime)s] [PID %(process)d] [%(threadName)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    stderr_handler.setFormatter(stderr_formatter)
    
    # Настраиваем только loggers для наших модулей
    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    app_logger.addHandler(stdout_handler)
    app_logger.addHandler(stderr_handler)
    app_logger.setLevel(getattr(logging, log_level.upper()))
    app_logger.propagate = False  # Не передавать в root logger
    
    # Настройка уровней для различных библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Меньше шума от HTTP запросов
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    app_logger.info("Логирование настроено успешно для app модулей")


def setup_test_logging(log_level: str = "INFO") -> None:
    """
    Настройка логирования для тестов.
    В тестах используем propagate=True чтобы caplog мог ловить сообщения.
    """
    app_logger = logging.getLogger("app")
    app_logger.setLevel(getattr(logging, log_level.upper()))
    app_logger.propagate = True  # Важно для caplog в тестах
    
    # Настройка уровней для различных библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logging_config() -> Dict[str, Any]:
    """
    Возвращает конфигурацию логирования в формате dictConfig.
    Альтернативный способ настройки через словарь.
    """
    
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '[%(asctime)s] [PID %(process)d] [%(threadName)s] [%(name)s] [%(levelname)s] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S,%f'
            },
        },
        'filters': {
            'info_filter': {
                '()': InfoFilter,
            },
            'error_filter': {
                '()': ErrorFilter,
            },
        },
        'handlers': {
            'stdout': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filters': ['info_filter'],
                'stream': 'ext://sys.stdout',
            },
            'stderr': {
                'class': 'logging.StreamHandler',
                'level': 'WARNING',
                'formatter': 'detailed',
                'filters': ['error_filter'],
                'stream': 'ext://sys.stderr',
            },
        },
        'loggers': {
            'httpx': {
                'level': 'WARNING',
            },
            'httpcore': {
                'level': 'WARNING',
            },
            'urllib3': {
                'level': 'WARNING',
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['stdout', 'stderr'],
        },
    }