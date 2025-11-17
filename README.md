# TaskMind Async Telegram Task Tracker

Высокопроизводительный асинхронный бэкенд для обработки задач из естественного языка через Telegram.

## Стек
- FastAPI (ASGI)  
- Tortoise ORM + Aerich
- PostgreSQL (asyncpg)
- Dramatiq + Redis
- Aiogram (webhook)
- Pydantic v2
- OpenAI API для парсинга естественного языка

## Запуск (Dev)
1. Создать `.env` (см. `.env.example`).
2. Установить зависимости: `pip install -r requirements.txt`.
3. Инициализировать БД и миграции:
   - `aerich init -t app.core.db.TORTOISE_ORM`
   - `aerich init-db`
4. Запустить API: `uvicorn app.main:app --reload`.
5. Запустить Dramatiq workers: `dramatiq app.workers.actors`.

## Структура
```
app/
  core/        # конфиг, инициализация ORM
  models/      # Tortoise модели
  schemas/     # Pydantic модели (I/O)
  repositories/# CRUD слой
  services/    # бизнес-логика и внешние интеграции
  routers/     # FastAPI роутеры
  workers/     # Dramatiq actors
  utils/       # парсинг дат, summarization, prompt_manager
  prompts/     # AI промпты в виде шаблонов
test/          # интеграционные тесты
```

## AI Промпты
Все промпты хранятся в `app/prompts/` как текстовые файлы:
- `task_parser.txt` - парсинг естественного языка в задачи
- `chat_assistant.txt` - системный промпт для чат-бота  
- `welcome_message.txt` - приветственное сообщение

Использование:
```python
from app.utils.prompt_manager import prompt_manager

# Рендер с параметрами
prompt = prompt_manager.render("task_parser", 
                              current_date="2025-11-17", 
                              timezone="Europe/Moscow")
```

## Тестирование
```bash
# Все тесты
pytest

# Только быстрые (без API)
pytest -m "not requires_api_key"

# Интеграционные тесты с OpenAI
pytest -m requires_api_key
```

## Фичи
✅ AI парсинг текста задач через OpenAI  
✅ Система шаблонов промптов  
✅ Интеграционные тесты без моков  
🚧 Планировщик напоминаний  
🚧 Диалоговые сессии с резюме

## Лицензия
MIT
