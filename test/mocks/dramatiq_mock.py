"""
Мок-версия Dramatiq брокера для тестов.
Заменяет реальное подключение к Redis на заглушки.
"""

from unittest.mock import Mock


class MockDramatiqActor:
    """Мок-версия Dramatiq actor."""
    
    def __init__(self, func):
        self.func = func
        self.send = Mock()
        self.send_with_options = Mock()
    
    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


def mock_dramatiq_actor(*args, **kwargs):
    """Декоратор для мокирования Dramatiq actors в тестах."""
    def decorator(func):
        return MockDramatiqActor(func)
    return decorator