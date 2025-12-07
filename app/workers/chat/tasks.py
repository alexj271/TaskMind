"""
Dramatiq задачи для Chat Worker.
Интеллектуальная обработка сообщений с управлением задачами через AI.
"""
import dramatiq
import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.core.dramatiq_setup import redis_broker
from app.services.openai_tools import OpenAIService
from app.core.db import init_db
from app.services.telegram_client import send_message as telegram_send_message
from app.utils.prompt_manager import PromptManager
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.workers.chat.memory_service import DialogMemoryService
from app.workers.chat.models import ChatRequest, ChatResponse, DialogGoal, TaskAction
from app.workers.chat.tools import CHAT_TOOLS

logger = logging.getLogger(__name__)

# Инициализируем сервисы
openai_service = OpenAIService(gpt_model="gpt-5")
prompt_manager = PromptManager()
task_repo = TaskRepository()
user_repo = UserRepository()
memory_service = DialogMemoryService()


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


async def _process_chat_message_impl(user_id: int, chat_id: int, message_text: str, user_name: str):
    """
    Обрабатывает разговорное сообщение с помощью AI агента для управления задачами.
    
    Args:
        user_id: ID пользователя Telegram
        chat_id: ID чата
        message_text: Текст сообщения
        user_name: Имя пользователя
    """
    # Инициализируем Tortoise ORM для воркера
    await init_db()
    
    try:
        logger.info(f"Chat: обрабатываем сообщение от {user_name} (ID: {user_id}): '{message_text[:100]}...'")
        
        # 1. Получаем память диалога
        memory = await memory_service.get_or_create_memory(user_id)
        
        # Очищаем устаревшую память
        if memory_service.should_cleanup_memory(memory):
            memory_service.cleanup_memory(memory)
        
        # 2. Ищем релевантные задачи
        task_tools = TaskTools(user_id)
        relevant_tasks = ""
        
        try:
            search_result = await task_tools.search_tasks(message_text, limit=3)
            if search_result.get("success") and search_result.get("results"):
                relevant_tasks = "Найденные похожие задачи:\n"
                for task in search_result["results"]:
                    status = "✅" if task.get("completed") else "⏳"
                    relevant_tasks += f"{status} {task['title']}\n"
        except Exception as e:
            logger.warning(f"Ошибка поиска релевантных задач: {e}")
        
        # 3. Подготавливаем контекст для AI
        # Получаем форматированное резюме для промпта
        dialog_summary = memory_service.get_summary_for_prompt(memory)
        
        system_prompt = prompt_manager.render(
            "system_chat_agent",
            user_goal=memory.user_goal,
            dialog_context=dialog_summary,
            clarifications="\n".join(memory.clarifications) if memory.clarifications else "Нет",
            recent_actions=memory_service.get_recent_actions_summary(memory),
            relevant_tasks=relevant_tasks if relevant_tasks else "Релевантные задачи не найдены"
        )
        
        # 4. Генерируем ответ с помощью AI
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Пользователь {user_name} написал: {message_text}"}
        ]
        
        # Вызываем OpenAI с инструментами через chat_with_tools
        try:
            response_text, tool_call_result = await openai_service.chat_with_tools(
                history_messages=messages,
                user_id=user_id,
                system_prompt=system_prompt,
                tools=CHAT_TOOLS
            )
            
            # Логируем результат вызова инструментов
            if tool_call_result:
                logger.info(f"Chat: OpenAI вызвал функцию - {tool_call_result}")
            else:
                logger.info(f"Chat: OpenAI ответил без вызова функций")
            
            if not response_text:
                response_text = "Привет! Как дела?"
                
        except Exception as openai_error:
            logger.error(f"Chat: ошибка OpenAI с tools: {openai_error}")
            # Fallback: простой чат без инструментов
            try:
                simple_response = await openai_service.chat(message_text)
                response_text = simple_response
                tool_call_result = None
                logger.info(f"Chat: использован fallback режим для пользователя {user_id}")
            except Exception as fallback_error:
                logger.error(f"Chat: ошибка fallback OpenAI: {fallback_error}")
                response_text = "Извините, произошла ошибка при обращении к AI. Попробуйте еще раз."
                tool_call_result = None

        # 6. Обрабатываем вызов функции если он был
        tasks_created = []
        tasks_updated = []
        
        if tool_call_result:
            function_name = tool_call_result.get("function_name")
            function_args = tool_call_result.get("arguments", {})
            
            try:
                # Вызываем соответствующую функцию из TaskTools
                func_map = {
                    "create_task": task_tools.create_task,
                    "search_tasks": task_tools.search_tasks,
                    "update_task": task_tools.update_task,
                    "update_task_by_user_id": task_tools.update_task_by_user_id,
                    "delete_task_by_user_id": task_tools.delete_task_by_user_id,
                    "get_user_tasks": task_tools.get_user_tasks,
                    "find_task_for_update": task_tools.find_task_for_update,
                    "confirm_and_update_task": task_tools.confirm_and_update_task,
                    "find_task_for_reschedule": task_tools.find_task_for_reschedule,
                    "confirm_and_reschedule_task": task_tools.confirm_and_reschedule_task
                }
                
                if function_name in func_map:
                    result = await func_map[function_name](**function_args)
                    
                    # Отслеживаем созданные и обновленные задачи
                    if function_name == "create_task" and result.get("success"):
                        tasks_created.append(result)
                    elif function_name in ["update_task", "update_task_by_user_id", "confirm_and_update_task", "confirm_and_reschedule_task"] and result.get("success"):
                        tasks_updated.append(result)
                    
                logger.info(f"Chat: выполнена функция {function_name} с результатом: {result}")
                
            except Exception as func_error:
                logger.error(f"Chat: ошибка выполнения функции {function_name}: {func_error}")        # 7. Обновляем память диалога
        if tasks_created:
            for task in tasks_created:
                if task.get("success"):
                    memory_service.add_task_action(
                        memory,
                        TaskAction.CREATED,
                        task.get("task_id", ""),
                        task.get("title", ""),
                        f"Создана через чат"
                    )
        
        if tasks_updated:
            for task in tasks_updated:
                if task.get("success"):
                    memory_service.add_task_action(
                        memory,
                        TaskAction.UPDATED,
                        task.get("task_id", ""),
                        "Задача",
                        f"Обновлена через чат"
                    )
        
        # 8. Обновляем контекст диалога с помощью ИИ-резюмирования  
        await memory_service.update_context_with_ai_summary(memory, message_text, user_name)
        
        # Сохраняем обновленную память
        await memory_service.update_memory(user_id, memory)
        
        # 9. Отправляем ответ в Telegram
        await telegram_send_message(chat_id, response_text)
        
        logger.info(f"Chat: ответ отправлен пользователю {user_name}, создано задач: {len(tasks_created)}, обновлено: {len(tasks_updated)}")
        
    except Exception as e:
        logger.exception(f"Chat: ошибка обработки сообщения от пользователя {user_id}: {str(e)}")
        error_message = "Извините, произошла ошибка при обработке вашего сообщения. Попробуйте еще раз."
        await telegram_send_message(chat_id, error_message)
        
    finally:
        # Закрываем соединения после обработки
        from tortoise import Tortoise
        await Tortoise.close_connections()


@dramatiq.actor(max_retries=2, min_backoff=2000, max_backoff=60000)
async def process_chat_message(user_id: int, chat_id: int, message_text: str, user_name: str):
    """
    Dramatiq актор для обработки chat сообщений.
    """
    return await _process_chat_message_impl(user_id, chat_id, message_text, user_name)