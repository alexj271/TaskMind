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
        
        # 4. Подготавливаем инструменты для AI
        tools_prompt = prompt_manager.render("task_tools")
        
        # 5. Генерируем ответ с помощью AI
        messages = [
            {"role": "system", "content": system_prompt + "\n\n" + tools_prompt},
            {"role": "user", "content": f"Пользователь {user_name} написал: {message_text}"}
        ]
        
        # Определяем доступные функции для AI
        available_functions = {
            "create_task": task_tools.create_task,
            "search_tasks": task_tools.search_tasks,
            "update_task": task_tools.update_task,
            "get_user_tasks": task_tools.get_user_tasks
        }
        
        # Вызываем OpenAI с инструментами
        response = await openai_service.generate_response_with_tools(
            messages=messages,
            tools=available_functions,
            max_tokens=1000
        )
        
        response_text = response.get("content", "Извините, произошла ошибка при обработке запроса.")
        
        # 6. Обрабатываем вызовы функций если они были
        tasks_created = []
        tasks_updated = []
        
        if "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                function_name = tool_call.get("function", {}).get("name")
                if function_name == "create_task":
                    tasks_created.append(tool_call.get("result", {}))
                elif function_name == "update_task":
                    tasks_updated.append(tool_call.get("result", {}))
        
        # 7. Обновляем память диалога
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
        logger.error(f"Chat: ошибка обработки сообщения от пользователя {user_id}: {str(e)}")
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