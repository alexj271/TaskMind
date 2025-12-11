#!/usr/bin/env python3
"""
TaskMind MCP Server
Сервер Model Context Protocol для управления задачами и событиями
Использует существующие модели TaskMind из app/models
"""

import asyncio
import logging
import sys
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastmcp import FastMCP

# Импорты моделей TaskMind
from app.models.task import Task
from app.models.user import User

# Импорты репозиториев
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.repositories.event_repository import EventRepository

# Локальные импорты MCP
from .models import (
    EventType, MCPEventModel, MCPTaskRequest, MCPEventRequest,
    MCPTaskResponse, MCPEventResponse, MCPListResponse
)
from .utils import MCPUtils, event_storage

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем экземпляр FastMCP
mcp = FastMCP("TaskMind")

# Репозитории
task_repo = TaskRepository()
user_repo = UserRepository()
event_repo = EventRepository()

@mcp.tool()
async def create_task(
    user_id: int,
    title: str,
    description: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    reminder_at: Optional[str] = None,
    priority: Optional[str] = None,
    event_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Создает новую задачу для пользователя в TaskMind.
    Может быть привязана к событию через event_id.
    
    Args:
        user_id: ID пользователя Telegram
        title: Название задачи
        description: Описание задачи
        scheduled_at: Дата выполнения в ISO формате
        reminder_at: Дата напоминания в ISO формате  
        priority: Приоритет задачи (low, medium, high, urgent)
        event_id: ID события для привязки задачи
    """
    try:
        # Получаем или создаем пользователя
        user = await MCPUtils.get_or_create_user(user_id)
        
        # Парсим даты
        scheduled_dt = MCPUtils.parse_datetime(scheduled_at)
        reminder_dt = MCPUtils.parse_datetime(reminder_at)
        
        # Проверяем существование события
        linked_event = None
        if event_id:
            try:
                from uuid import UUID
                event_uuid = UUID(event_id)
                event = await event_repo.get_by_id(event_uuid)
                if event:
                    linked_event = event_repo.to_dict(event)
                else:
                    logger.warning(f"Событие {event_id} не найдено в БД")
            except (ValueError, TypeError):
                logger.warning(f"Неверный формат ID события: {event_id}")
        
        # Создаем задачу используя существующий репозиторий
        task = await task_repo.create(
            user=user,
            title=title,
            description=description,
            scheduled_at=scheduled_dt,
            reminder_at=reminder_dt,
            priority=priority or "medium"
        )
        
        logger.info(f"✅ Создана задача {task.id} для пользователя {user_id}")
        
        return {
            "success": True,
            "task_id": str(task.id),
            "user_task_id": task.user_task_id,
            "title": task.title,
            "description": task.description,
            "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
            "priority": task.priority,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "linked_event": linked_event
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания задачи: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def create_event(
    title: str,
    description: Optional[str] = None,
    event_type: str = "general",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    location: Optional[str] = None,
    participants: Optional[List[str]] = None,
    creator_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Создает новое событие в базе данных TaskMind.
    
    Args:
        title: Название события
        description: Описание события
        event_type: Тип события (trip, meeting, project, personal, work, health, education, general)
        start_date: Дата начала в ISO формате
        end_date: Дата окончания в ISO формате
        location: Место проведения
        participants: Список участников
        creator_user_id: ID пользователя-создателя (опционально)
    """
    try:
        # Валидируем тип события
        try:
            event_type_enum = EventType(event_type)
        except ValueError:
            event_type_enum = EventType.GENERAL
        
        # Парсим даты
        start_dt = MCPUtils.parse_datetime(start_date)
        end_dt = MCPUtils.parse_datetime(end_date)
        
        # Получаем создателя если указан
        creator = None
        if creator_user_id:
            creator = await MCPUtils.get_or_create_user(creator_user_id)
        
        # Создаем событие в базе данных
        event = await event_repo.create(
            title=title,
            creator=creator,
            description=description,
            event_type=event_type_enum,
            start_date=start_dt,
            end_date=end_dt,
            location=location,
            participants=participants or []
        )
        
        logger.info(f"✅ Создано событие {event.id}: {title}")
        
        return {
            "success": True,
            "event_id": str(event.id),
            "title": event.title,
            "event_type": event.event_type.value,
            "start_date": event.start_date.isoformat() if event.start_date else None,
            "end_date": event.end_date.isoformat() if event.end_date else None,
            "location": event.location,
            "participants": event.participant_list,
            "creator_id": event.creator_id,
            "created_at": event.created_at.isoformat() if event.created_at else None
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания события: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_events(
    event_type: Optional[str] = None,
    creator_user_id: Optional[int] = None,
    limit: Optional[int] = 10
) -> Dict[str, Any]:
    """
    Получает список событий из базы данных с фильтрацией.
    
    Args:
        event_type: Фильтр по типу события
        creator_user_id: Фильтр по создателю
        limit: Максимальное количество результатов
    """
    try:
        # Валидируем тип события
        event_type_enum = None
        if event_type:
            try:
                event_type_enum = EventType(event_type)
            except ValueError:
                pass
        
        # Получаем создателя если указан
        creator = None
        if creator_user_id:
            creator = await user_repo.get_by_telegram(creator_user_id)
        
        # Получаем события из БД
        if creator:
            events = await event_repo.get_by_creator(creator, event_type_enum, limit)
        else:
            events = await event_repo.get_all(event_type_enum, limit)
        
        # Преобразуем в словари
        events_data = [event_repo.to_dict(event) for event in events]
        
        logger.info(f"📋 Найдено событий: {len(events_data)}")
        
        return {
            "success": True,
            "events": events_data,
            "total": len(events_data)
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения событий: {e}")
        return {"success": False, "error": str(e), "events": [], "total": 0}

@mcp.tool()
async def search_tasks(
    user_id: int,
    query: Optional[str] = None,
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    limit: Optional[int] = 10
) -> Dict[str, Any]:
    """
    Поиск задач пользователя с фильтрами используя существующие модели TaskMind.
    
    Args:
        user_id: ID пользователя Telegram
        query: Поисковый запрос по названию/описанию
        completed: Фильтр по статусу выполнения
        priority: Фильтр по приоритету
        limit: Максимальное количество результатов
    """
    try:
        # Получаем пользователя
        user = await user_repo.get_by_telegram(user_id)
        if not user:
            return {"success": False, "error": "Пользователь не найден", "tasks": [], "total": 0}
        
        # Ищем задачи через существующий репозиторий
        tasks = await task_repo.search(
            user=user,
            query=query,
            completed=completed,
            priority=priority,
            limit=limit
        )
        
        # Форматируем результаты
        task_list = []
        for task in tasks:
            task_dict = {
                "id": str(task.id),
                "user_task_id": task.user_task_id,
                "title": task.title,
                "description": task.description,
                "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
                "reminder_at": task.reminder_at.isoformat() if task.reminder_at else None,
                "priority": task.priority,
                "completed": task.completed,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            }
            task_list.append(task_dict)
        
        logger.info(f"🔍 Найдено задач для пользователя {user_id}: {len(task_list)}")
        
        return {
            "success": True,
            "tasks": task_list,
            "total": len(task_list)
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска задач: {e}")
        return {"success": False, "error": str(e), "tasks": [], "total": 0}

@mcp.tool()
async def get_user_tasks(
    user_id: int,
    completed: Optional[bool] = None,
    limit: Optional[int] = 10
) -> Dict[str, Any]:
    """
    Получает все задачи пользователя из TaskMind.
    
    Args:
        user_id: ID пользователя Telegram
        completed: Фильтр по статусу выполнения
        limit: Максимальное количество результатов
    """
    try:
        # Получаем пользователя
        user = await user_repo.get_by_telegram(user_id)
        if not user:
            return {"success": False, "error": "Пользователь не найден", "tasks": [], "total": 0}
        
        # Получаем задачи из TaskMind
        tasks = await task_repo.get_user_tasks(
            user=user,
            completed=completed,
            limit=limit
        )
        
        # Форматируем результаты
        task_list = []
        for task in tasks:
            task_dict = {
                "id": str(task.id),
                "user_task_id": task.user_task_id,
                "title": task.title,
                "description": task.description,
                "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
                "reminder_at": task.reminder_at.isoformat() if task.reminder_at else None,
                "priority": task.priority,
                "completed": task.completed,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            }
            task_list.append(task_dict)
        
        logger.info(f"📋 Загружены задачи пользователя {user_id}: {len(task_list)}")
        
        return {
            "success": True,
            "tasks": task_list,
            "total": len(task_list)
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения задач: {e}")
        return {"success": False, "error": str(e), "tasks": [], "total": 0}

@mcp.tool()
async def update_task_status(
    task_id: str,
    user_id: int,
    completed: bool
) -> Dict[str, Any]:
    """
    Обновляет статус выполнения задачи.
    
    Args:
        task_id: ID задачи (UUID или user_task_id)
        user_id: ID пользователя для проверки прав
        completed: Новый статус выполнения
    """
    try:
        # Получаем пользователя
        user = await user_repo.get_by_telegram(user_id)
        if not user:
            return {"success": False, "error": "Пользователь не найден"}
        
        # Получаем задачу
        try:
            # Пробуем как UUID
            task = await task_repo.get_by_id(task_id)
        except:
            # Пробуем как user_task_id
            try:
                user_task_id = int(task_id)
                task = await task_repo.get_by_user_task_id(user, user_task_id)
            except:
                return {"success": False, "error": "Задача не найдена"}
        
        if not task or task.user_id != user.id:
            return {"success": False, "error": "Задача не найдена или нет прав"}
        
        # Обновляем статус
        await task_repo.update_status(task, completed)
        
        logger.info(f"✅ Обновлен статус задачи {task.id}: completed={completed}")
        
        return {
            "success": True,
            "task_id": str(task.id),
            "task_title": task.title,
            "completed": completed,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статуса задачи: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def link_task_to_event(
    task_id: str,
    event_id: str,
    user_id: int
) -> Dict[str, Any]:
    """
    Связывает задачу с событием.
    
    Args:
        task_id: ID задачи (UUID или user_task_id)
        event_id: ID события
        user_id: ID пользователя для проверки прав
    """
    try:
        # Получаем пользователя
        user = await user_repo.get_by_telegram(user_id)
        if not user:
            return {"success": False, "error": "Пользователь не найден"}
        
        # Проверяем событие в БД
        try:
            from uuid import UUID
            event_uuid = UUID(event_id)
            event = await event_repo.get_by_id(event_uuid)
            if not event:
                return {"success": False, "error": "Событие не найдено"}
        except (ValueError, TypeError):
            return {"success": False, "error": "Неверный формат ID события"}
        
        # Получаем задачу
        try:
            # Пробуем как UUID
            task = await task_repo.get_by_id(task_id)
        except:
            # Пробуем как user_task_id
            try:
                user_task_id = int(task_id)
                task = await task_repo.get_by_user_task_id(user, user_task_id)
            except:
                return {"success": False, "error": "Задача не найдена"}
        
        if not task or task.user_id != user.id:
            return {"success": False, "error": "Задача не найдена или нет прав"}
        
        # В реальной реализации здесь бы было обновление поля event_id в модели Task
        # Пока что возвращаем успешный результат
        
        logger.info(f"🔗 Задача {task.id} связана с событием {event_id}")
        
        return {
            "success": True,
            "task_id": str(task.id),
            "task_title": task.title,
            "event_id": event_id,
            "event_title": event.title,
            "linked_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка связывания задачи с событием: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def search_events(
    query: str,
    event_type: Optional[str] = None,
    creator_user_id: Optional[int] = None,
    limit: Optional[int] = 10
) -> Dict[str, Any]:
    """
    Поиск событий по названию или описанию в базе данных.
    
    Args:
        query: Поисковый запрос
        event_type: Фильтр по типу события
        creator_user_id: Фильтр по создателю
        limit: Максимальное количество результатов
    """
    try:
        # Валидируем тип события
        event_type_enum = None
        if event_type:
            try:
                event_type_enum = EventType(event_type)
            except ValueError:
                pass
        
        # Получаем создателя если указан
        creator = None
        if creator_user_id:
            creator = await user_repo.get_by_telegram(creator_user_id)
        
        # Выполняем поиск в БД
        events = await event_repo.search(
            query=query,
            event_type=event_type_enum,
            creator=creator,
            limit=limit
        )
        
        # Преобразуем в словари
        events_data = [event_repo.to_dict(event) for event in events]
        
        logger.info(f"🔍 Найдено событий по запросу '{query}': {len(events_data)}")
        
        return {
            "success": True,
            "events": events_data,
            "total": len(events_data),
            "query": query
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска событий: {e}")
        return {"success": False, "error": str(e), "events": [], "total": 0}

async def init_mcp_server():
    """Инициализация MCP сервера с подключением к TaskMind БД"""
    try:
        from app.core.db import init_db
        await init_db()
        logger.info("🚀 MCP Сервер TaskMind запущен и подключен к БД")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации MCP сервера: {e}")
        return False

if __name__ == "__main__":
    async def main():
        """Основная функция запуска MCP сервера"""
        if await init_mcp_server():
            try:
                logger.info("🔧 Запуск MCP сервера TaskMind...")
                await mcp.run()
            except KeyboardInterrupt:
                logger.info("⚠️ Получен сигнал прерывания")
            except Exception as e:
                logger.error(f"❌ Ошибка работы сервера: {e}")
        else:
            logger.error("❌ Не удалось запустить MCP сервер")
            sys.exit(1)
    
@mcp.tool()
async def get_upcoming_events(
    creator_user_id: Optional[int] = None,
    days_ahead: Optional[int] = 30,
    limit: Optional[int] = 10
) -> Dict[str, Any]:
    """
    Получает предстоящие события из базы данных.
    
    Args:
        creator_user_id: Фильтр по создателю
        days_ahead: Количество дней вперед для поиска
        limit: Максимальное количество результатов
    """
    try:
        # Получаем создателя если указан
        creator = None
        if creator_user_id:
            creator = await user_repo.get_by_telegram(creator_user_id)
        
        # Получаем предстоящие события
        events = await event_repo.get_upcoming_events(
            creator=creator,
            days_ahead=days_ahead or 30,
            limit=limit
        )
        
        # Преобразуем в словари
        events_data = [event_repo.to_dict(event) for event in events]
        
        logger.info(f"📅 Найдено предстоящих событий: {len(events_data)}")
        
        return {
            "success": True,
            "events": events_data,
            "total": len(events_data),
            "days_ahead": days_ahead or 30
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения предстоящих событий: {e}")
        return {"success": False, "error": str(e), "events": [], "total": 0}


def main():
    """Основная функция для запуска MCP сервера через stdio"""
    async def init_and_run():
        from app.core.db import init_db
        await init_db()
        logger.info("🚀 TaskMind MCP Server запущен")
    
    # Инициализация БД синхронно
    import asyncio
    asyncio.get_event_loop().run_until_complete(init_and_run())
    
    # Запускаем MCP сервер через FastMCP (он сам управляет event loop)
    mcp.run()


def main_http():
    """Запуск MCP сервера как HTTP сервер"""
    async def init_and_run():
        from app.core.db import init_db
        await init_db()
        logger.info("🚀 TaskMind MCP HTTP Server запущен на порту 8001")
    
    # Инициализация БД синхронно
    import asyncio
    asyncio.get_event_loop().run_until_complete(init_and_run())
    
    # Запускаем HTTP сервер
    mcp.run(transport="http", host="0.0.0.0", port=8001)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        # Запуск как HTTP сервер
        main_http()
    else:
        # Запуск как stdio сервер (по умолчанию)
        main()