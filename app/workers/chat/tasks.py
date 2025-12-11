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
from app.repositories.event_repository import EventRepository
from app.workers.chat.memory_service import DialogMemoryService
from app.workers.chat.models import TaskAction
from app.workers.chat.tools import CHAT_TOOLS, TaskTools
from app.mcp_server import mcp, event_storage


logger = logging.getLogger(__name__)


# Инициализируем сервисы
openai_service = OpenAIService(gpt_model="gpt-4")
prompt_manager = PromptManager()
task_repo = TaskRepository()
user_repo = UserRepository()
event_repo = EventRepository()
memory_service = DialogMemoryService()


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
        
        # 2. Ищем релевантные задачи и события
        task_tools = TaskTools(user_id)
        relevant_tasks = ""
        relevant_events = ""
        
        try:
            # Поиск задач
            search_result = await task_tools.search_tasks(message_text, limit=3)
            if search_result.get("success") and search_result.get("results"):
                relevant_tasks = "Найденные похожие задачи:\n"
                for task in search_result["results"]:
                    status = "✅" if task.get("completed") else "⏳"
                    relevant_tasks += f"{status} {task['title']}\n"
                    
            # Поиск событий через MCP
            user = await user_repo.get_by_telegram(user_id)
            if user:
                events = await event_repo.search(message_text, limit=3)
                if events:
                    relevant_events = "Найденные похожие события:\n"
                    for event in events:
                        event_type_icon = {"trip": "🏔️", "meeting": "👥", "project": "📋", "personal": "👤", "work": "💼", "health": "🏥", "education": "📚", "general": "📅"}.get(event.event_type.value, "📅")
                        relevant_events += f"{event_type_icon} {event.title} ({event.event_type.value})\n"
                        
        except Exception as e:
            logger.warning(f"Ошибка поиска релевантного контекста: {e}")
        
        # 3. Подготавливаем контекст для AI
        # Получаем форматированное резюме для промпта
        dialog_summary = memory_service.get_summary_for_prompt(memory)
        
        system_prompt = prompt_manager.render(
            "system_chat_agent",
            user_goal=memory.user_goal,
            dialog_context=dialog_summary,
            clarifications="\n".join(memory.clarifications) if memory.clarifications else "Нет",
            recent_actions=memory_service.get_recent_actions_summary(memory),
            relevant_tasks=relevant_tasks if relevant_tasks else "Релевантные задачи не найдены",
            relevant_events=relevant_events if relevant_events else "Релевантные события не найдены"
        )
        
        # 4. Генерируем ответ с помощью AI
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Пользователь {user_name} написал: {message_text}"}
        ]
        
        # Вызываем OpenAI с инструментами через MCP сервер
        try:
            response_text, executed_functions = await openai_service.chat_with_mcp_server(
                messages=messages,
                tools_schema=CHAT_TOOLS,
                user_id=user_id
            )                
        except Exception as openai_error:
            logger.exception(f"Chat: ошибка OpenAI MCP Server: {openai_error}")
            response_text = "Извините, произошла ошибка при обращении к AI. Попробуйте еще раз."
            executed_functions = []

        # 6. Отслеживаем созданные и обновленные задачи/события для памяти диалога
        tasks_created = []
        tasks_updated = []
        events_created = []
        
        # Анализируем выполненные функции
        for func_exec in executed_functions:
            function_name = func_exec.get("function_name")
            result = func_exec.get("result", {})
            
            if function_name == "create_task" and result.get("success"):
                tasks_created.append(result)
                logger.info(f"Chat MCP: создана задача через функцию {function_name}")
            elif function_name == "create_event" and result.get("success"):
                events_created.append(result)
                logger.info(f"Chat MCP: создано событие через функцию {function_name}")
            elif function_name in ["update_task", "update_task_by_user_id", "confirm_and_update_task", "confirm_and_reschedule_task"] and result.get("success"):
                tasks_updated.append(result)
                logger.info(f"Chat MCP: обновлена задача через функцию {function_name}")
        
        # 7. Обновляем память диалога
        memory_service.add_message(memory, user_name, message_text)
        memory_service.add_message(memory, "AI", response_text[:200] + "..." if len(response_text) > 200 else response_text)

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
        
        if events_created:
            for event in events_created:
                if event.get("success"):
                    memory_service.add_task_action(
                        memory,
                        TaskAction.CREATED,
                        event.get("event_id", ""),
                        event.get("title", ""),
                        f"Событие создано через чат ({event.get('event_type', 'general')})"
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
        
        logger.info(f"Chat: ответ отправлен пользователю {user_name}, создано задач: {len(tasks_created)}, событий: {len(events_created)}, обновлено: {len(tasks_updated)}")
        
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