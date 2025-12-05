"""
Главный файл для запуска Dramatiq воркеров.
Импортирует все воркеры для их регистрации в Dramatiq.
"""

# Сначала инициализируем Dramatiq с правильными настройками
from app.core.dramatiq_setup import init_dramatiq
print("Инициализация Dramatiq...")
broker = init_dramatiq()
print(f"Брокер инициализирован: {broker}")

# Импортируем все воркеры для их регистрации
import app.workers.gatekeeper.tasks
import app.workers.chat.tasks
import app.workers.shared.tasks

# Все воркеры теперь зарегистрированы в Dramatiq