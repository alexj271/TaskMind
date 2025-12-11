# TaskMind MCP Server

MCP (Model Context Protocol) сервер для TaskMind, обеспечивающий интеграцию с AI-ассистентами для управления задачами и событиями.

## Возможности

- ✅ Создание и управление задачами через существующие модели TaskMind
- ✅ Создание и управление событиями  
- ✅ Связывание задач с событиями
- ✅ Поиск и фильтрация задач и событий
- ✅ Обновление статуса задач
- ✅ Интеграция с базой данных TaskMind

## Структура

```
app/mcp_server/
├── __init__.py      # Экспорты модуля
├── server.py        # Основной MCP сервер  
├── models.py        # Pydantic модели для MCP
└── utils.py         # Утилиты и хранилище событий
```

## Использование

### Запуск сервера

#### Stdio режим (по умолчанию)
Для использования с MCP клиентами через stdin/stdout:
```bash
cd /home/alex/project/vscode/TaskMind
python -m app.mcp_server.server
```

#### HTTP сервер режим
Для запуска как HTTP сервер на порту 8001:
```bash
cd /home/alex/project/vscode/TaskMind
python -m app.mcp_server.server --http
```

HTTP сервер будет доступен по адресу: `http://localhost:8001`

### Доступные инструменты MCP

1. **create_task** - Создание задач
2. **create_event** - Создание событий
3. **get_events** - Получение списка событий
4. **search_tasks** - Поиск задач с фильтрами
5. **get_user_tasks** - Получение задач пользователя
6. **update_task_status** - Обновление статуса задачи
7. **link_task_to_event** - Связывание задач с событиями
8. **search_events** - Поиск событий

### Примеры использования

#### Создание события "Поход в горы"

```python
await create_event(
    title="Поход в горы Карпаты",
    description="Трехдневный поход с палатками",
    event_type="trip",
    start_date="2025-07-15T08:00:00",
    end_date="2025-07-17T18:00:00",
    location="Карпаты, Украина",
    participants=["Алексей", "Мария", "Игорь"]
)
```

#### Создание связанных задач

```python
# Создаем задачу подготовки
await create_task(
    user_id=12345,
    title="Купить палатку",
    description="Выбрать и купить 3-местную палатку",
    scheduled_at="2025-07-10T12:00:00",
    priority="high",
    event_id="event-uuid-here"
)

await create_task(
    user_id=12345, 
    title="Собрать рюкзак",
    description="Упаковать все необходимое для похода",
    scheduled_at="2025-07-14T20:00:00",
    event_id="event-uuid-here"
)
```

## Интеграция

MCP сервер использует:

- **Существующие модели**: `app/models/task.py`, `app/models/user.py`
- **Репозитории TaskMind**: `TaskRepository`, `UserRepository`
- **База данных**: PostgreSQL через Tortoise ORM
- **Временное хранилище**: События хранятся в памяти (планируется миграция в БД)

## Зависимости

- `fastmcp>=0.4.0` - MCP сервер
- Существующие зависимости TaskMind

## Логи

Логи сохраняются в файл `mcp_server.log` и выводятся в консоль с уровнем INFO.