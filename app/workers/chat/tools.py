"""
Определения инструментов (tools) для chat worker.
Схемы функций для OpenAI function calling.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository


logger = logging.getLogger(__name__)
user_repo = UserRepository()
task_repo = TaskRepository()


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
    },
    # Инструменты для работы с событиями через MCP
    {
        "name": "create_event",
        "description": "Создает новое событие (поездка, встреча, проект, личное мероприятие). Используй когда пользователь планирует событие, поездку, встречу или мероприятие.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Название события"},
                "description": {"type": "string", "description": "Описание события"},
                "event_type": {
                    "type": "string", 
                    "description": "Тип события",
                    "enum": ["trip", "meeting", "project", "personal", "work", "health", "education", "general"],
                    "default": "general"
                },
                "start_date": {"type": "string", "description": "Дата начала в ISO формате"},
                "end_date": {"type": "string", "description": "Дата окончания в ISO формате"},
                "location": {"type": "string", "description": "Место проведения"},
                "participants": {"type": "array", "items": {"type": "string"}, "description": "Список участников"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_events",
        "description": "Получает список событий пользователя с фильтрацией",
        "parameters": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "description": "Фильтр по типу события"},
                "limit": {"type": "integer", "description": "Максимум результатов", "default": 10}
            }
        }
    },
    {
        "name": "search_events",
        "description": "Ищет события по названию или описанию",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"},
                "event_type": {"type": "string", "description": "Фильтр по типу события"},
                "limit": {"type": "integer", "description": "Максимум результатов", "default": 10}
            },
            "required": ["query"]
        }
    },
    {
        "name": "link_task_to_event", 
        "description": "Связывает задачу с событием для организации подготовки",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID задачи или user_task_id"},
                "event_id": {"type": "string", "description": "ID события"}
            },
            "required": ["task_id", "event_id"]
        }
    }
]


class TaskTools:
    """Инструменты для работы с задачами, доступные AI агенту"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
    
    async def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        reminder_at: Optional[str] = None,
        priority: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создает новую задачу для пользователя"""
        try:
            # Получаем пользователя
            user = await user_repo.get_by_telegram(self.user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            # Парсим даты если они переданы
            scheduled_dt = None
            reminder_dt = None
            
            if scheduled_at:
                try:
                    scheduled_dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                except:
                    pass
                    
            if reminder_at:
                try:
                    reminder_dt = datetime.fromisoformat(reminder_at.replace('Z', '+00:00'))
                except:
                    pass
            
            # Создаем задачу
            task = await task_repo.create(
                user_id=user.id,
                title=title,
                description=description,
                scheduled_at=scheduled_dt,
                reminder_at=reminder_dt
            )
            
            logger.info(f"Создана задача '{title}' для пользователя {self.user_id}")
            
            return {
                "success": True,
                "task_id": str(task.id),
                "user_task_id": task.user_task_id,
                "title": task.title,
                "description": task.description,
                "created_at": task.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания задачи: {e}")
            return {"error": f"Ошибка создания задачи: {str(e)}"}
    
    async def search_tasks(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Ищет задачи по семантическому сходству"""
        try:
            # Получаем пользователя
            user = await user_repo.get_by_telegram(self.user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            # Выполняем поиск
            tasks = await task_repo.search_by_similarity(user.id, query, limit=limit)
            
            results = []
            for task in tasks:
                results.append({
                    "task_id": str(task.id),
                    "user_task_id": task.user_task_id,
                    "title": task.title,
                    "description": task.description,
                    "similarity_score": getattr(task, 'similarity_distance', 0.0),
                    "created_at": task.created_at.isoformat(),
                    "completed": getattr(task, 'completed', False)
                })
            
            logger.info(f"Найдено {len(results)} задач для запроса '{query}' пользователя {self.user_id}")
            
            return {
                "success": True,
                "results": results,
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Ошибка поиска задач: {e}")
            return {"error": f"Ошибка поиска: {str(e)}"}
    
    async def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        reminder_at: Optional[str] = None,
        completed: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Обновляет существующую задачу"""
        try:
            # Получаем задачу
            import uuid
            task_uuid = uuid.UUID(task_id)
            task = await task_repo.get(task_uuid)
            
            if not task:
                return {"error": "Задача не найдена"}
            
            # Проверяем права доступа
            user = await user_repo.get_by_telegram(self.user_id)
            if not user or task.user_id != user.id:
                return {"error": "Нет доступа к задаче"}
            
            # Обновляем поля
            updates = {}
            if title is not None:
                updates['title'] = title
            if description is not None:
                updates['description'] = description
            if completed is not None:
                updates['completed'] = completed
                
            # Парсим даты
            if scheduled_at:
                try:
                    updates['scheduled_at'] = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                except:
                    pass
                    
            if reminder_at:
                try:
                    updates['reminder_at'] = datetime.fromisoformat(reminder_at.replace('Z', '+00:00'))
                except:
                    pass
            
            # Применяем обновления
            for field, value in updates.items():
                setattr(task, field, value)
            
            await task.save()
            
            logger.info(f"Обновлена задача {task_id} для пользователя {self.user_id}")
            
            return {
                "success": True,
                "task_id": task_id,
                "updated_fields": list(updates.keys())
            }
            
        except Exception as e:
            logger.error(f"Ошибка обновления задачи: {e}")
            return {"error": f"Ошибка обновления: {str(e)}"}
    
    async def update_task_by_user_id(
        self,
        user_task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        reminder_at: Optional[str] = None,
        completed: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Обновляет задачу по user_task_id"""
        try:
            # Получаем пользователя
            user = await user_repo.get_by_telegram(self.user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            # Получаем задачу
            task = await task_repo.get_by_user_task_id(user.id, user_task_id)
            if not task:
                return {"error": f"Задача #{user_task_id} не найдена"}
            
            # Обновляем поля
            updates = {}
            if title is not None:
                updates['title'] = title
            if description is not None:
                updates['description'] = description
            if completed is not None:
                updates['completed'] = completed
                
            # Парсим даты
            if scheduled_at:
                try:
                    updates['scheduled_at'] = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                except:
                    pass
                    
            if reminder_at:
                try:
                    updates['reminder_at'] = datetime.fromisoformat(reminder_at.replace('Z', '+00:00'))
                except:
                    pass
            
            if updates:
                # Применяем обновления через репозиторий
                await task_repo.update_by_user_task_id(user.id, user_task_id, **updates)
                
                # Обновляем объект для возврата
                for field, value in updates.items():
                    setattr(task, field, value)
            
            logger.info(f"Обновлена задача #{user_task_id} для пользователя {self.user_id}")
            
            return {
                "success": True,
                "task_id": str(task.id),
                "user_task_id": task.user_task_id,
                "title": task.title,
                "description": task.description,
                "updated": True
            }
            
        except Exception as e:
            logger.error(f"Ошибка обновления задачи #{user_task_id}: {e}")
            return {"error": f"Ошибка обновления: {str(e)}"}
    
    async def delete_task_by_user_id(self, user_task_id: int) -> Dict[str, Any]:
        """Удаляет задачу по user_task_id"""
        try:
            # Получаем пользователя
            user = await user_repo.get_by_telegram(self.user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            # Проверяем существование задачи
            task = await task_repo.get_by_user_task_id(user.id, user_task_id)
            if not task:
                return {"error": f"Задача #{user_task_id} не найдена"}
            
            # Удаляем задачу
            deleted_count = await task_repo.delete_by_user_task_id(user.id, user_task_id)
            
            if deleted_count > 0:
                logger.info(f"Удалена задача #{user_task_id} для пользователя {self.user_id}")
                return {
                    "success": True,
                    "user_task_id": user_task_id,
                    "title": task.title,
                    "deleted": True
                }
            else:
                return {"error": "Не удалось удалить задачу"}
            
        except Exception as e:
            logger.error(f"Ошибка удаления задачи #{user_task_id}: {e}")
            return {"error": f"Ошибка удаления: {str(e)}"}
    
    async def find_task_for_update(
        self,
        query: str,
        update_description: str = ""
    ) -> Dict[str, Any]:
        """
        Находит задачу по семантическому поиску для последующего обновления.
        Возвращает найденную задачу для подтверждения пользователем.
        """
        try:
            # Получаем пользователя
            user = await user_repo.get_by_telegram(self.user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            # Выполняем семантический поиск задач
            tasks = await task_repo.search_by_similarity(user.id, query, limit=5)
            
            if not tasks:
                return {
                    "error": "Задачи не найдены",
                    "suggestion": f"Попробуйте уточнить запрос или создать новую задачу"
                }
            
            # Берем самую релевантную задачу (первую в результатах)
            best_match = tasks[0]
            similarity_score = getattr(best_match, 'similarity_distance', 0.0)
            
            # Если сходство слишком низкое (расстояние слишком большое), предупреждаем
            confidence = "высокая" if similarity_score < 0.3 else "средняя" if similarity_score < 0.6 else "низкая"
            
            logger.info(f"Найдена задача #{best_match.user_task_id} для обновления (confidence: {confidence})")
            
            return {
                "action": "confirm_task_update",
                "task_found": {
                    "task_id": str(best_match.id),
                    "user_task_id": best_match.user_task_id,
                    "title": best_match.title,
                    "description": best_match.description,
                    "scheduled_at": best_match.scheduled_at.isoformat() if best_match.scheduled_at else None,
                    "reminder_at": best_match.reminder_at.isoformat() if best_match.reminder_at else None,
                    "created_at": best_match.created_at.isoformat(),
                    "similarity_score": similarity_score
                },
                "update_intent": update_description,
                "confidence": confidence,
                "confirmation_required": True,
                "message": f"Найдена задача #{best_match.user_task_id}: '{best_match.title}'. Это та задача, которую нужно обновить?",
                "alternatives": [
                    {
                        "user_task_id": task.user_task_id,
                        "title": task.title,
                        "similarity_score": getattr(task, 'similarity_distance', 0.0)
                    } for task in tasks[1:3]  # Показываем 2 альтернативы
                ] if len(tasks) > 1 else []
            }
            
        except Exception as e:
            logger.error(f"Ошибка поиска задачи для обновления: {e}")
            return {"error": f"Ошибка поиска: {str(e)}"}
    
    async def confirm_and_update_task(
        self,
        task_id: str,
        user_task_id: int,
        confirmed: bool,
        title: Optional[str] = None,
        description: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        reminder_at: Optional[str] = None,
        completed: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Подтверждает и обновляет задачу после подтверждения пользователем.
        """
        try:
            if not confirmed:
                return {
                    "message": "Обновление задачи отменено. Уточните, какую задачу нужно обновить.",
                    "action": "cancelled"
                }
            
            # Обновляем задачу по user_task_id для надежности
            result = await self.update_task_by_user_id(
                user_task_id=user_task_id,
                title=title,
                description=description,
                scheduled_at=scheduled_at,
                reminder_at=reminder_at,
                completed=completed
            )
            
            if result.get("success"):
                logger.info(f"Успешно обновлена задача #{user_task_id} после подтверждения")
                return {
                    "success": True,
                    "message": f"Задача #{user_task_id} успешно обновлена!",
                    "updated_task": result,
                    "action": "task_updated"
                }
            else:
                return result  # Возвращаем ошибку из update_task_by_user_id
            
        except Exception as e:
            logger.error(f"Ошибка подтверждения и обновления задачи #{user_task_id}: {e}")
            return {"error": f"Ошибка обновления: {str(e)}"}
    
    async def find_task_for_reschedule(
        self,
        query: str,
        reschedule_description: str = ""
    ) -> Dict[str, Any]:
        """
        Находит задачу по семантическому поиску для последующего переноса.
        Специализированная версия для работы с датами и временем.
        """
        try:
            # Получаем пользователя
            user = await user_repo.get_by_telegram(self.user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            # Выполняем семантический поиск задач
            tasks = await task_repo.search_by_similarity(user.id, query, limit=5)
            
            if not tasks:
                return {
                    "error": "Задачи не найдены",
                    "suggestion": f"Попробуйте уточнить название задачи для переноса"
                }
            
            # Берем самую релевантную задачу
            best_match = tasks[0]
            similarity_score = getattr(best_match, 'similarity_distance', 0.0)
            
            # Определяем уровень уверенности
            confidence = "высокая" if similarity_score < 0.3 else "средняя" if similarity_score < 0.6 else "низкая"
            
            # Информация о текущем расписании
            current_schedule = "не запланировано"
            if best_match.scheduled_at:
                current_schedule = f"запланировано на {best_match.scheduled_at.strftime('%d.%m.%Y %H:%M')}"
            elif best_match.reminder_at:
                current_schedule = f"напоминание {best_match.reminder_at.strftime('%d.%m.%Y %H:%M')}"
            
            logger.info(f"Найдена задача #{best_match.user_task_id} для переноса (confidence: {confidence})")
            
            return {
                "action": "confirm_task_reschedule",
                "task_found": {
                    "task_id": str(best_match.id),
                    "user_task_id": best_match.user_task_id,
                    "title": best_match.title,
                    "description": best_match.description,
                    "scheduled_at": best_match.scheduled_at.isoformat() if best_match.scheduled_at else None,
                    "reminder_at": best_match.reminder_at.isoformat() if best_match.reminder_at else None,
                    "created_at": best_match.created_at.isoformat(),
                    "current_schedule": current_schedule,
                    "similarity_score": similarity_score
                },
                "reschedule_intent": reschedule_description,
                "confidence": confidence,
                "confirmation_required": True,
                "message": f"Найдена задача #{best_match.user_task_id}: '{best_match.title}' ({current_schedule}). Переносим эту задачу?",
                "alternatives": [
                    {
                        "user_task_id": task.user_task_id,
                        "title": task.title,
                        "current_schedule": "не запланировано" if not task.scheduled_at and not task.reminder_at 
                                          else f"запланировано на {task.scheduled_at.strftime('%d.%m.%Y')}"
                                          if task.scheduled_at else f"напоминание {task.reminder_at.strftime('%d.%m.%Y')}",
                        "similarity_score": getattr(task, 'similarity_distance', 0.0)
                    } for task in tasks[1:3]
                ] if len(tasks) > 1 else []
            }
            
        except Exception as e:
            logger.error(f"Ошибка поиска задачи для переноса: {e}")
            return {"error": f"Ошибка поиска: {str(e)}"}
    
    async def confirm_and_reschedule_task(
        self,
        task_id: str,
        user_task_id: int,
        confirmed: bool,
        new_scheduled_at: Optional[str] = None,
        new_reminder_at: Optional[str] = None,
        keep_reminder: bool = True
    ) -> Dict[str, Any]:
        """
        Подтверждает и переносит задачу на новое время/дату.
        Специализированный метод для работы с датами и напоминаниями.
        """
        try:
            if not confirmed:
                return {
                    "message": "Перенос задачи отменен. Уточните, какую задачу нужно перенести.",
                    "action": "cancelled"
                }
            
            # Получаем текущую задачу для информации
            user = await user_repo.get_by_telegram(self.user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            old_task = await task_repo.get_by_user_task_id(user.id, user_task_id)
            if not old_task:
                return {"error": f"Задача #{user_task_id} не найдена"}
            
            # Подготавливаем обновления для переноса
            updates = {}
            
            # Обновляем время выполнения
            if new_scheduled_at:
                updates['scheduled_at'] = new_scheduled_at
            
            # Обрабатываем напоминания
            if new_reminder_at:
                updates['reminder_at'] = new_reminder_at
            elif not keep_reminder and old_task.reminder_at:
                # Убираем напоминание, если не нужно его сохранять
                updates['reminder_at'] = None
            
            if not updates:
                return {"error": "Не указано новое время для переноса"}
            
            # Обновляем задачу
            result = await self.update_task_by_user_id(
                user_task_id=user_task_id,
                **updates
            )
            
            if result.get("success"):
                # Формируем сообщение о переносе
                schedule_info = []
                if new_scheduled_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(new_scheduled_at.replace('Z', '+00:00'))
                        schedule_info.append(f"выполнение на {dt.strftime('%d.%m.%Y %H:%M')}")
                    except:
                        schedule_info.append("новое время выполнения")
                
                if new_reminder_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(new_reminder_at.replace('Z', '+00:00'))
                        schedule_info.append(f"напоминание {dt.strftime('%d.%m.%Y %H:%M')}")
                    except:
                        schedule_info.append("новое напоминание")
                
                schedule_msg = " и ".join(schedule_info) if schedule_info else "новое время"
                
                logger.info(f"Успешно перенесена задача #{user_task_id} после подтверждения")
                return {
                    "success": True,
                    "message": f"Задача #{user_task_id} '{old_task.title}' успешно перенесена! Новое расписание: {schedule_msg}",
                    "rescheduled_task": result,
                    "action": "task_rescheduled",
                    "old_schedule": {
                        "scheduled_at": old_task.scheduled_at.isoformat() if old_task.scheduled_at else None,
                        "reminder_at": old_task.reminder_at.isoformat() if old_task.reminder_at else None
                    },
                    "new_schedule": {
                        "scheduled_at": new_scheduled_at,
                        "reminder_at": new_reminder_at
                    }
                }
            else:
                return result  # Возвращаем ошибку из update_task_by_user_id
            
        except Exception as e:
            logger.error(f"Ошибка подтверждения и переноса задачи #{user_task_id}: {e}")
            return {"error": f"Ошибка переноса: {str(e)}"}
    
    async def get_user_tasks(self, limit: int = 10, completed: Optional[bool] = None) -> Dict[str, Any]:
        """Получает список задач пользователя"""
        try:
            # Получаем пользователя
            user = await user_repo.get_by_telegram(self.user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            # Получаем задачи
            tasks = await task_repo.list_for_user(user.id)
            
            # Фильтруем по статусу если нужно
            if completed is not None:
                tasks = [t for t in tasks if getattr(t, 'completed', False) == completed]
            
            # Ограничиваем количество
            tasks = tasks[:limit]
            
            results = []
            for task in tasks:
                results.append({
                    "task_id": str(task.id),
                    "user_task_id": task.user_task_id,
                    "title": task.title,
                    "description": task.description,
                    "created_at": task.created_at.isoformat(),
                    "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
                    "completed": getattr(task, 'completed', False)
                })
            
            return {
                "success": True,
                "tasks": results,
                "total": len(results)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения задач: {e}")
            return {"error": f"Ошибка получения задач: {str(e)}"}