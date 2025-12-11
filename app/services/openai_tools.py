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

    async def chat_with_tools(self, messages: List[Dict[str, Any]], user_id: int, system_prompt: str = None, tools: List[Dict[str, Any]] = None) -> tuple[str, Optional[Dict[str, Any]]]:
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
                               
                return message_response.content or "", {
                    "function_name": function_name,
                    "arguments": function_args
                }
            
            # Если функция не вызвана, возвращаем только текстовый ответ
            return message_response.content or "", None
            
        except Exception as e:
            logger.exception("OpenAI API error in chat_with_tools")
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    async def chat_with_tools_mcp(self, messages: List[Dict[str, Any]], tools_schema: List[Dict[str, Any]], func_map: Dict[str, Any], user_id: int = None) -> tuple[str, List[Dict[str, Any]]]:
        """
        Чат с AI используя MCP pattern - выполняет функции внутри и передает результат обратно в AI.
        
        Args:
            messages: Список сообщений для отправки в OpenAI
            tools_schema: Схемы инструментов для OpenAI function calling
            func_map: Словарь функций {имя_функции: функция}
            user_id: ID пользователя для логирования
            
        Returns:
            tuple: (Финальный ответ AI пользователю, список выполненных функций с результатами)
        """
        
        try:
            # Форматируем схемы инструментов
            formatted_tools = [
                {
                    "type": "function", 
                    "function": tool
                }
                for tool in tools_schema
            ]
            
            executed_functions = []  # Список выполненных функций
            
            # Первый запрос к OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=formatted_tools,
                tool_choice="auto",
                max_tokens=800,
                temperature=0.3
            )
            
            message_response = response.choices[0].message
            
            # Если AI вызвал функцию - выполняем её
            if message_response.tool_calls:
                tool_call = message_response.tool_calls[0]
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"OpenAI MCP: вызов функции {function_name} с аргументами {function_args}")
                
                # Выполняем функцию
                if function_name in func_map:
                    try:
                        function_result = await func_map[function_name](**function_args)
                        logger.info(f"OpenAI MCP: результат функции {function_name}: {function_result}")
                        
                        # Сохраняем информацию о выполненной функции
                        executed_functions.append({
                            "function_name": function_name,
                            "arguments": function_args,
                            "result": function_result
                        })
                        
                    except Exception as func_error:
                        logger.exception(f"OpenAI MCP: ошибка выполнения функции {function_name}: {func_error}")
                        function_result = {"error": f"Ошибка выполнения функции: {str(func_error)}"}
                        
                        executed_functions.append({
                            "function_name": function_name,
                            "arguments": function_args,
                            "result": function_result
                        })
                else:
                    function_result = {"error": f"Функция {function_name} не найдена"}
                    executed_functions.append({
                        "function_name": function_name,
                        "arguments": function_args,
                        "result": function_result
                    })
                
                # Добавляем результат функции в историю сообщений
                updated_messages = messages.copy()
                updated_messages.append({
                    "role": "assistant",
                    "content": message_response.content,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function", 
                        "function": {
                            "name": function_name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                })
                updated_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps(function_result, ensure_ascii=False)
                })
                
                # Второй запрос к OpenAI с результатом функции
                final_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=updated_messages,
                    max_tokens=600,
                    temperature=0.3
                )
                
                return final_response.choices[0].message.content.strip(), executed_functions
            
            # Если функция не вызвана, возвращаем текстовый ответ
            return message_response.content or "Привет! Чем могу помочь?", executed_functions
            
        except Exception as e:
            logger.exception(f"OpenAI MCP error: {e}")
            raise RuntimeError(f"OpenAI MCP error: {str(e)}")

    async def chat_with_mcp_server(self, messages: List[Dict[str, Any]], tools_schema: List[Dict[str, Any]] = None, user_id: int = None) -> tuple[str, List[Dict[str, Any]]]:
        """
        Чат с AI используя OpenAI Responses API с MCP сервером.
        
        Args:
            messages: Список сообщений для отправки в OpenAI
            tools_schema: Схемы инструментов (игнорируется, получаем из MCP)
            user_id: ID пользователя для контекста
            
        Returns:
            tuple: (Финальный ответ AI пользователю, список выполненных функций с результатами)
        """
        
        try:
            from mcp.client.stdio import stdio_client
            from mcp import ClientSession, StdioServerParameters
            
            # 1. Подключаем MCP сервер по stdio
            server_params = StdioServerParameters(
                command="python",
                args=["-m", "app.mcp_server.server"],
                env=None
            )
            
            executed_functions = []  # Список выполненных функций
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # 2. Получаем инструменты MCP сервера
                    mcp_tools_response = await session.list_tools()
                    
                    # Преобразуем MCP tools в формат для Responses API
                    tools_list = []
                    for tool in mcp_tools_response.tools:
                        tools_list.append({
                            "type": "function",
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema
                        })
                    
                    # Формируем входной запрос пользователя из messages
                    user_input = ""
                    system_instructions = ""
                    
                    for message in messages:
                        if message.get("role") == "user":
                            user_input = message.get("content", "")
                        elif message.get("role") == "system":
                            system_instructions = message.get("content", "")
                    
                    if not user_input:
                        return "Не удалось найти запрос пользователя", []
                    
                    # 3. Используем OpenAI Responses API с instructions
                    logger.info(f"Отправляем запрос в Responses API:")
                    logger.info(f"  Модель: {self.model}")
                    logger.info(f"  Инструменты: {len(tools_list)} шт.")
                    logger.info(f"  Пользовательский ввод: {user_input}")
                    
                    response = await self.client.responses.create(
                        model=self.model,
                        input=user_input,
                        instructions=system_instructions + "\n\nКРИТИЧЕСКИ ВАЖНО: ТЫ ДОЛЖЕН ВЫЗВАТЬ ФУНКЦИЮ create_task НЕМЕДЛЕННО! НЕ спрашивай подтверждения, НЕ уточняй детали! Когда пользователь говорит 'Создай задачу', ты МГНОВЕННО вызываешь create_task с предоставленной информацией. Используй разумные значения по умолчанию для недостающих параметров.",
                        tools=tools_list,
                        tool_choice="required",  # Принудительно требуем использование функций
                        max_output_tokens=800,
                        temperature=0.3
                    )
                    
                    logger.info(f"Получен ответ от Responses API:")
                    logger.info(f"  Количество элементов output: {len(response.output)}")
                    for i, item in enumerate(response.output):
                        content = getattr(item, 'content', None)
                        name = getattr(item, 'name', None)
                        display_content = content if content else (name if name else 'неизвестно')
                        if display_content and len(str(display_content)) > 100:
                            display_content = str(display_content)[:100] + "..."
                        logger.info(f"  Элемент {i}: тип={item.type}, содержание={display_content}")
                    
                    # 4. Обрабатываем выходные данные Responses API
                    final_text_response = ""
                    
                    for item in response.output:
                        if item.type == "text":
                            final_text_response += item.content
                        elif item.type == "message":
                            # Обрабатываем message с возможными tool_calls
                            logger.info(f"Найден message с {len(item.content)} элементами содержимого")
                            for i, content_item in enumerate(item.content):
                                logger.info(f"  Элемент содержимого {i}: тип={type(content_item)}, атрибуты={dir(content_item)}")
                                if hasattr(content_item, 'text'):
                                    logger.info(f"  Добавляем текст: {content_item.text[:100]}...")
                                    final_text_response += content_item.text
                                elif hasattr(content_item, 'tool_calls'):
                                    # Обрабатываем вызовы функций в message
                                    for tool_call in content_item.tool_calls:
                                        function_name = tool_call.function.name
                                        function_args = json.loads(tool_call.function.arguments)
                                        
                                        logger.info(f"OpenAI Responses API: вызов {function_name} из message с аргументами {function_args}")
                                        
                                        # Выполняем функцию (перенесем код ниже)
                                        try:
                                            # Добавляем user_id в аргументы для функций, которые его требуют
                                            if function_name in ["create_task", "search_tasks", "get_user_tasks", "update_task_status", "link_task_to_event"]:
                                                if user_id:
                                                    function_args["user_id"] = user_id
                                            
                                            # Специальная обработка для функций событий
                                            if function_name in ["create_event", "get_events", "search_events"]:
                                                if user_id:
                                                    function_args["creator_user_id"] = user_id
                                            
                                            # Вызываем MCP tool
                                            tool_result = await session.call_tool(
                                                name=function_name,
                                                arguments=function_args
                                            )
                                            
                                            # Преобразуем результат MCP в наш формат
                                            if tool_result.content:
                                                try:
                                                    # Пытаемся распарсить JSON из первого элемента content
                                                    if hasattr(tool_result.content[0], 'text'):
                                                        function_result = json.loads(tool_result.content[0].text)
                                                    else:
                                                        function_result = {"result": str(tool_result.content[0])}
                                                except (json.JSONDecodeError, IndexError, AttributeError):
                                                    function_result = {"result": str(tool_result.content)}
                                            else:
                                                function_result = {"success": True}
                                            
                                            logger.info(f"OpenAI Responses API: результат {function_name}: {function_result}")
                                            
                                            executed_functions.append({
                                                "function_name": function_name,
                                                "arguments": function_args,
                                                "result": function_result
                                            })
                                            
                                            # Добавляем результат в финальный ответ если он есть
                                            if function_result.get("success"):
                                                if function_name == "create_task":
                                                    task_title = function_result.get("title", "новая задача")
                                                    final_text_response += f"\n✅ Создал задачу: {task_title}"
                                                elif function_name == "create_event":
                                                    event_title = function_result.get("title", "новое событие")
                                                    final_text_response += f"\n✅ Создал событие: {event_title}"
                                        
                                        except Exception as func_error:
                                            logger.exception(f"OpenAI Responses API: ошибка выполнения {function_name}: {func_error}")
                                            function_result = {"error": f"Ошибка выполнения функции: {str(func_error)}"}
                                            
                                            executed_functions.append({
                                                "function_name": function_name,
                                                "arguments": function_args,
                                                "result": function_result
                                            })
                                            
                                            final_text_response += f"\n❌ Ошибка при выполнении {function_name}"
                        elif item.type == "function_call":  # Прямой вызов функции
                            function_name = item.name
                            # Парсим аргументы как JSON, если это строка
                            if isinstance(item.arguments, str):
                                function_args = json.loads(item.arguments)
                            else:
                                function_args = item.arguments
                            
                            logger.info(f"OpenAI Responses API: вызов {function_name} с аргументами {function_args}")
                            
                            try:
                                # Добавляем user_id в аргументы для функций, которые его требуют
                                if function_name in ["create_task", "search_tasks", "get_user_tasks", "update_task_status", "link_task_to_event"]:
                                    if user_id:
                                        function_args["user_id"] = user_id
                                
                                # Специальная обработка для функций событий
                                if function_name in ["create_event", "get_events", "search_events"]:
                                    if user_id:
                                        function_args["creator_user_id"] = user_id
                                
                                # Вызываем MCP tool
                                tool_result = await session.call_tool(
                                    name=function_name,
                                    arguments=function_args
                                )
                                
                                # Преобразуем результат MCP в наш формат
                                if tool_result.content:
                                    try:
                                        # Пытаемся распарсить JSON из первого элемента content
                                        if hasattr(tool_result.content[0], 'text'):
                                            function_result = json.loads(tool_result.content[0].text)
                                        else:
                                            function_result = {"result": str(tool_result.content[0])}
                                    except (json.JSONDecodeError, IndexError, AttributeError):
                                        function_result = {"result": str(tool_result.content)}
                                else:
                                    function_result = {"success": True}
                                
                                logger.info(f"OpenAI Responses API: результат {function_name}: {function_result}")
                                
                                executed_functions.append({
                                    "function_name": function_name,
                                    "arguments": function_args,
                                    "result": function_result
                                })
                                
                                # Добавляем результат в финальный ответ если он есть
                                if function_result.get("success"):
                                    if function_name == "create_task":
                                        task_title = function_result.get("title", "новая задача")
                                        final_text_response += f"\n✅ Создал задачу: {task_title}"
                                    elif function_name == "create_event":
                                        event_title = function_result.get("title", "новое событие")
                                        final_text_response += f"\n✅ Создал событие: {event_title}"
                                
                            except Exception as func_error:
                                logger.exception(f"OpenAI Responses API: ошибка выполнения {function_name}: {func_error}")
                                function_result = {"error": f"Ошибка выполнения функции: {str(func_error)}"}
                                
                                executed_functions.append({
                                    "function_name": function_name,
                                    "arguments": function_args,
                                    "result": function_result
                                })
                                
                                final_text_response += f"\n❌ Ошибка при выполнении {function_name}"
                    
                    # Если нет финального ответа, создаем базовый
                    if not final_text_response.strip():
                        final_text_response = "Привет! Чем могу помочь?"
                    
                    return final_text_response.strip(), executed_functions
            
        except Exception as e:
            logger.exception(f"OpenAI Responses API error: {e}")
            raise RuntimeError(f"OpenAI Responses API error: {str(e)}")

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
            
            # Логируем сырой ответ для отладки
            logger.info(f"OpenAI raw response - content: {repr(message.content)}")
            if message.tool_calls:
                logger.info(f"OpenAI tool calls count: {len(message.tool_calls)}")
            
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
                            # Парсим аргументы с лучшей обработкой ошибок
                            try:
                                arguments = json.loads(tool_call.function.arguments)
                                logger.info(f"OpenAI tool call {function_name}: {arguments}")
                            except json.JSONDecodeError as json_error:
                                logger.error(f"Невалидный JSON от OpenAI для функции {function_name}")
                                logger.error(f"Сырые аргументы: {repr(tool_call.function.arguments)}")
                                logger.error(f"JSON ошибка: {json_error}")
                                # Пытаемся создать базовые аргументы для функции
                                arguments = {}
                            
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
                            logger.error(f"Аргументы функции: {tool_call.function.arguments}")
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


async def parse_task(text: str, timezone: str = "Europe/Moscow") -> ParsedTask:
    """Парсинг текста задачи через AI"""
    service = get_openai_service()
    return await service.parse_task(text, timezone)