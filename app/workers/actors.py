"""
Главный файл для запуска Dramatiq воркеров.
Импортирует все воркеры для их регистрации в Dramatiq.
"""

# Импортируем все воркеры для их регистрации
from . import telegram_actors
from . import chat
from . import shared
from . import gatekeeper

# Все воркеры теперь зарегистрированы в Dramatiq