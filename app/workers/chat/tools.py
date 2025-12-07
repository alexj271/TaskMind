"""
Определения инструментов (tools) для chat worker.
Схемы функций для OpenAI function calling.
"""

from typing import List, Dict, Any

# Схемы инструментов для OpenAI function calling
CHAT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "create_task",
        "description": "Создает новую задачу для пользователя. Используй эту функцию когда пользователь просит что-то запомнить, записать, запланировать, назначить встречу или создать напоминание. Автоматически парси время из текста и устанавливай scheduled_at.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Название задачи"},
                "description": {"type": "string", "description": "Описание задачи"},
                "scheduled_at": {"type": "string", "description": "Дата выполнения в ISO формате"},
                "reminder_at": {"type": "string", "description": "Дата напоминания в ISO формате"},
                "priority": {"type": "string", "description": "Приоритет задачи"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "search_tasks",
        "description": "Ищет задачи по семантическому сходству",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"},
                "limit": {"type": "integer", "description": "Максимум результатов", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "update_task",
        "description": "Обновляет существующую задачу",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID задачи"},
                "title": {"type": "string", "description": "Новое название"},
                "description": {"type": "string", "description": "Новое описание"},
                "scheduled_at": {"type": "string", "description": "Новая дата выполнения"},
                "reminder_at": {"type": "string", "description": "Новая дата напоминания"},
                "completed": {"type": "boolean", "description": "Статус выполнения"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "update_task_by_user_id",
        "description": "Обновляет задачу по пользовательскому ID",
        "parameters": {
            "type": "object",
            "properties": {
                "user_task_id": {"type": "integer", "description": "Пользовательский ID задачи"},
                "title": {"type": "string", "description": "Новое название"},
                "description": {"type": "string", "description": "Новое описание"},
                "scheduled_at": {"type": "string", "description": "Новая дата выполнения"},
                "reminder_at": {"type": "string", "description": "Новая дата напоминания"},
                "completed": {"type": "boolean", "description": "Статус выполнения"}
            },
            "required": ["user_task_id"]
        }
    },
    {
        "name": "delete_task_by_user_id",
        "description": "Удаляет задачу по пользовательскому ID",
        "parameters": {
            "type": "object",
            "properties": {
                "user_task_id": {"type": "integer", "description": "Пользовательский ID задачи для удаления"}
            },
            "required": ["user_task_id"]
        }
    },
    {
        "name": "get_user_tasks",
        "description": "Получает список задач пользователя",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Максимум задач", "default": 10},
                "completed": {"type": "boolean", "description": "Фильтр по статусу"}
            }
        }
    },
    {
        "name": "find_task_for_update",
        "description": "Ищет задачу для обновления по описанию",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Описание задачи для поиска"},
                "update_description": {"type": "string", "description": "Описание планируемого обновления", "default": ""}
            },
            "required": ["query"]
        }
    },
    {
        "name": "confirm_and_update_task",
        "description": "Подтверждает и обновляет найденную задачу",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID задачи для обновления"},
                "user_task_id": {"type": "integer", "description": "Пользовательский ID задачи"},
                "confirmed": {"type": "boolean", "description": "Подтверждение обновления задачи"},
                "title": {"type": "string", "description": "Новое название задачи"},
                "description": {"type": "string", "description": "Новое описание задачи"},
                "scheduled_at": {"type": "string", "description": "Новая дата выполнения в ISO формате"},
                "reminder_at": {"type": "string", "description": "Новая дата напоминания в ISO формате"},
                "completed": {"type": "boolean", "description": "Статус выполнения задачи"}
            },
            "required": ["task_id", "user_task_id", "confirmed"]
        }
    },
    {
        "name": "find_task_for_reschedule",
        "description": "Ищет задачу для переноса по описанию",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Описание задачи для поиска"},
                "reschedule_description": {"type": "string", "description": "Описание планируемого переноса", "default": ""}
            },
            "required": ["query"]
        }
    },
    {
        "name": "confirm_and_reschedule_task",
        "description": "Подтверждает и переносит найденную задачу",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID задачи для переноса"},
                "user_task_id": {"type": "integer", "description": "Пользовательский ID задачи"},
                "confirmed": {"type": "boolean", "description": "Подтверждение переноса задачи"},
                "new_scheduled_at": {"type": "string", "description": "Новая дата выполнения в ISO формате"},
                "new_reminder_at": {"type": "string", "description": "Новая дата напоминания в ISO формате"},
                "keep_reminder": {"type": "boolean", "description": "Сохранить существующее напоминание", "default": True}
            },
            "required": ["task_id", "user_task_id", "confirmed"]
        }
    }
]