import json
from datetime import datetime, timedelta
import logging
import traceback
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.schemas.task import ParsedTask
from app.utils.prompt_manager import prompt_manager
from app.services.tools import TOOL_SCHEMAS


logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self, gpt_model: str = None):
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for AI services")
        
        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
            
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = gpt_model or settings.gpt_model_full

    async def chat(self, message: str) -> str:
        """Простой чат с OpenAI используя системный промпт"""
        try:
            # Загружаем системный промпт для чат-ассистента
            system_prompt = prompt_manager.render("chat_assistant")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    async def chat_with_tools(self, history_messages: List[Dict[str, Any]], user_id: int, system_prompt: str = None, tools: List[Dict[str, Any]] = None) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Чат с AI используя function calling.
        Возвращает tuple: (ответ, вызванная_функция_с_аргументами или None)
        """
        
        try:
            if tools is None:
                tools = TOOL_SCHEMAS
            else:
                # Добавляем только схемы указанных tools
                tools = [
                    {
                        "type": "function",
                        "function": tool
                    }
                    for tool in tools
                ]
        
            messages = [
                {"role": "system", "content": system_prompt},       
            ]

            messages = messages + history_messages

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",  # Оставляем auto, но с улучшенным промптом
                max_tokens=400,
                temperature=0.3  # Снижаем температуру для более точного следования инструкциям
            )
           
            message_response = response.choices[0].message
            
            # Проверяем был ли вызов функции
            if message_response.tool_calls:
                tool_call = message_response.tool_calls[0]
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Добавляем user_id если его нет в аргументах
                if 'user_id' not in function_args:
                    function_args['user_id'] = user_id
                
                return message_response.content or "", {
                    "function_name": function_name,
                    "arguments": function_args
                }
            
            # Если функция не вызвана, возвращаем только текстовый ответ
            return message_response.content or "", None
            
        except Exception as e:
            logger.exception("OpenAI API error in chat_with_tools")
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    async def parse_task(self, text: str, timezone: str = "Europe/Moscow") -> ParsedTask:
        """
        Парсит естественный язык в структурированную задачу.
        Пример: "завтра встреча с коллегой в 8 утра" -> ParsedTask с title, scheduled_at, etc.
        """
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Загружаем промпт из шаблона
        system_prompt = prompt_manager.render(
            "task_parser",
            current_date=current_date,
            timezone=timezone
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=200,
                temperature=0.1  # Низкая температура для более предсказуемых результатов
            )
            
            content = response.choices[0].message.content.strip()
            
            # Парсим JSON ответ
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: если JSON некорректный, создаем базовую задачу
                return ParsedTask(
                    title=text[:50],
                    description=None,
                    scheduled_at=None,
                    reminder_at=None
                )
            
            # Конвертируем строки в datetime объекты
            scheduled_at = None
            reminder_at = None
            
            if data.get("scheduled_at"):
                try:
                    scheduled_at = datetime.fromisoformat(data["scheduled_at"].replace("Z", "+00:00"))
                except ValueError:
                    pass
                    
            if data.get("reminder_at"):
                try:
                    reminder_at = datetime.fromisoformat(data["reminder_at"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            
            return ParsedTask(
                title=data.get("title", text[:50]),
                description=data.get("description"),
                scheduled_at=scheduled_at,
                reminder_at=reminder_at
            )
            
        except Exception as e:
            # В случае ошибки возвращаем базовую задачу
            return ParsedTask(
                title=text[:50],
                description=f"Ошибка парсинга: {str(e)}",
                scheduled_at=None,
                reminder_at=None
            )


# Глобальный экземпляр сервиса
_openai_service: Optional[OpenAIService] = None


def get_openai_service() -> OpenAIService:
    """Dependency injection для OpenAI сервиса"""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service


# Удобные функции для прямого использования
async def chat(message: str) -> str:
    """Простой чат с AI"""
    service = get_openai_service()
    return await service.chat(message)


async def chat_with_tools(message: str, user_id: int, tools: List[Dict[str, Any]] = None) -> tuple[str, Optional[Dict[str, Any]]]:
    """Чат с AI используя function calling"""
    service = get_openai_service()
    return await service.chat_with_tools(message, user_id, tools)


async def generate_response_with_tools(self, messages: List[Dict[str, Any]], tools: Dict[str, Any], max_tokens: int = 1000) -> Dict[str, Any]:
        """
        Генерирует ответ с поддержкой function calling.
        
        Args:
            messages: Список сообщений для отправки в OpenAI
            tools: Словарь доступных функций {name: callable}
            max_tokens: Максимальное количество токенов в ответе
            
        Returns:
            Словарь с ответом и результатами вызовов функций
        """
        try:
            # Создаем схемы инструментов для OpenAI
            tool_schemas = []
            for name, func in tools.items():
                if name == "create_task":
                    schema = {
                        "type": "function",
                        "function": {
                            "name": "create_task",
                            "description": "Создает новую задачу для пользователя",
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
                        }
                    }
                elif name == "search_tasks":
                    schema = {
                        "type": "function",
                        "function": {
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
                        }
                    }
                elif name == "update_task":
                    schema = {
                        "type": "function",
                        "function": {
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
                        }
                    }
                elif name == "get_user_tasks":
                    schema = {
                        "type": "function",
                        "function": {
                            "name": "get_user_tasks",
                            "description": "Получает список задач пользователя",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "limit": {"type": "integer", "description": "Максимум задач", "default": 10},
                                    "completed": {"type": "boolean", "description": "Фильтр по статусу"}
                                }
                            }
                        }
                    }
                
                tool_schemas.append(schema)
            
            # Вызываем OpenAI с инструментами
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
                tool_choice="auto",
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            message = response.choices[0].message
            result = {
                "content": message.content,
                "tool_calls": []
            }
            
            # Обрабатываем вызовы функций
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    
                    if function_name in tools:
                        try:
                            # Парсим аргументы
                            arguments = json.loads(tool_call.function.arguments)
                            
                            # Вызываем функцию
                            func_result = await tools[function_name](**arguments)
                            
                            result["tool_calls"].append({
                                "function": {
                                    "name": function_name,
                                    "arguments": arguments
                                },
                                "result": func_result
                            })
                            
                        except Exception as e:
                            logger.error(f"Ошибка вызова функции {function_name}: {e}")
                            result["tool_calls"].append({
                                "function": {
                                    "name": function_name,
                                    "arguments": {}
                                },
                                "result": {"error": str(e)}
                            })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка в generate_response_with_tools: {e}")
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    async def parse_task(self, text: str, timezone: str = "Europe/Moscow") -> ParsedTask:
        """
        Парсит естественный язык в структурированную задачу.
        Пример: "завтра встреча с коллегой в 8 утра" -> ParsedTask с title, scheduled_at, etc.
        """
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Загружаем промпт из шаблона
        system_prompt = prompt_manager.render(
            "task_parser",
            current_date=current_date,
            timezone=timezone
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=200,
                temperature=0.1  # Низкая температура для более предсказуемых результатов
            )
            
            content = response.choices[0].message.content.strip()
            
            # Парсим JSON ответ
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: если JSON некорректный, создаем базовую задачу
                return ParsedTask(
                    title=text[:50],
                    description=None,
                    scheduled_at=None,
                    reminder_at=None
                )
            
            # Конвертируем строки в datetime объекты
            scheduled_at = None
            reminder_at = None
            
            if data.get("scheduled_at"):
                try:
                    scheduled_at = datetime.fromisoformat(data["scheduled_at"].replace("Z", "+00:00"))
                except ValueError:
                    pass
                    
            if data.get("reminder_at"):
                try:
                    reminder_at = datetime.fromisoformat(data["reminder_at"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            
            return ParsedTask(
                title=data.get("title", text[:50]),
                description=data.get("description"),
                scheduled_at=scheduled_at,
                reminder_at=reminder_at
            )
            
        except Exception as e:
            # В случае ошибки возвращаем базовую задачу
            return ParsedTask(
                title=text[:50],
                description=f"Ошибка парсинга: {str(e)}",
                scheduled_at=None,
                reminder_at=None
            )