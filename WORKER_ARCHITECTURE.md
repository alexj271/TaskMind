# TaskMind - Архитектура Воркеров

## Обзор

TaskMind использует архитектуру на основе специализированных воркеров для обработки различных типов сообщений от Telegram.

## Структура Воркеров

```
app/workers/
├── gatekeeper/          # Первичная обработка всех сообщений
│   ├── __init__.py
│   ├── models.py        # Pydantic модели для классификации
│   ├── api.py          # REST API endpoints (будущее)
│   ├── tasks.py        # Dramatiq actors
│   ├── tests.py        # Тесты воркера (будущее)
│   └── prompts/        # AI промпты
│       ├── classify.md # Классификация сообщений
│       └── parse.md    # Парсинг задач
├── chat/               # Обработка разговорных сообщений
│   ├── __init__.py
│   ├── models.py       # Модели для чата (будущее)
│   ├── tasks.py        # Chat обработка
│   └── prompts/        # Chat промпты (будущее)
└── shared/             # Общие задачи
    └── tasks.py        # Telegram API, напоминания
```

## Поток Обработки Сообщений

```mermaid
graph TD
    A[Telegram Webhook] --> B[/webhook/telegram]
    B --> C[Gatekeeper Worker]
    C --> D{AI Классификация}
    D -->|task| E[Создание Задачи]
    D -->|chat| F[Chat Worker]
    E --> G[Сохранение в БД]
    E --> H[Планирование Напоминания]
    E --> I[Ответ в Telegram]
    F --> J[Генерация Ответа AI]
    F --> I
    H --> K[Shared: Напоминание]
    K --> I
```

## Воркеры

### 1. Gatekeeper Worker

**Назначение:** Первичная точка входа для всех Telegram сообщений

**Функции:**
- Логирование истории всех сообщений
- AI-классификация: задача vs обычный чат
- Маршрутизация в соответствующие воркеры
- Создание задач из структурированных сообщений

**Ключевые задачи:**
- `process_webhook_message` - главная точка входа
- `classify_message` - классификация с помощью AI
- `create_task_from_message` - создание задач

### 2. Chat Worker

**Назначение:** Обработка неструктурированных разговорных сообщений

**Функции:**
- Генерация естественных ответов
- Поддержание контекста диалога
- Обработка вопросов о функциональности

**Ключевые задачи:**
- `process_chat_message` - обработка чата

### 3. Shared Tasks

**Назначение:** Общие функции для всех воркеров

**Функции:**
- Отправка сообщений в Telegram
- Планирование и отправка напоминаний
- Общие утилиты

**Ключевые задачи:**
- `send_telegram_message` - отправка в Telegram
- `schedule_task_reminder` - напоминания

## Модели Данных

### MessageHistory
```python
class MessageHistory(Model):
    id = fields.UUIDField(pk=True)
    user_id = fields.BigIntField()
    chat_id = fields.BigIntField()
    message_text = fields.TextField()
    message_type = fields.CharEnumField(MessageType)
    timestamp = fields.DatetimeField(auto_now_add=True)
```

### Task
```python
class Task(Model):
    id = fields.UUIDField(pk=True)
    user_id = fields.BigIntField()
    title = fields.CharField(max_length=200)
    description = fields.TextField(null=True)
    scheduled_at = fields.DatetimeField(null=True)
    reminder_at = fields.DatetimeField(null=True)
    priority = fields.CharEnumField(Priority)
    created_at = fields.DatetimeField(auto_now_add=True)
```

## AI Промпты

### Классификация (gatekeeper/prompts/classify.md)
Определяет тип сообщения: задача или обычный чат

### Парсинг Задач (gatekeeper/prompts/parse.md)
Извлекает структурированную информацию из текста задачи

## Конфигурация

Воркеры используют общую конфигурацию Dramatiq:
- Redis как брокер сообщений
- AsyncIO middleware для async/await поддержки
- Retry политики для каждого типа задач

## Тестирование

Каждый воркер будет иметь:
- Юнит-тесты для моделей и бизнес-логики
- Интеграционные тесты для Dramatiq задах
- Тесты AI промптов с mock ответами

## Мониторинг

- Все воркеры логируют свою активность
- Метрики производительности через Dramatiq
- Отслеживание успешности классификации AI