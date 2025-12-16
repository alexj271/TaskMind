import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import time
import redis.asyncio as aioredis
from openai import AsyncOpenAI
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from app.core.config import get_settings
from app.services.telegram_client import TelegramClient
from app.repositories.dialog_repository import DialogRepository
from app.repositories.user_repository import UserRepository
from app.utils.prompt_manager import TemplateManager, PromptManager, get_prompt
from .utils import MCPConfirmationFormatter
from .state_manager import StateManager
from .dialog_agent import DialogAgent
from .decision_engine import DecisionEngine


MAX_ACTIVE_AGENTS = 10
CHECK_INTERVAL = 0.3
AGENT_IDLE_TIMEOUT = 60

settings = get_settings()
logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url
)


class AgentSession:
    def __init__(self, user_id, redis):
        self.user_id = user_id
        self.redis = redis
        self.stream = f"agent:{user_id}:stream"
        self.last_active = time.time()
        self.running = True
        self.telegram_client = TelegramClient()
        self.mcp_tools = None
        
        # Шаблоны для сообщений MCP функций
        from pathlib import Path
        template_dir = Path(__file__).parent / "templates"
        template_manager = TemplateManager(template_dir=str(template_dir))
        self.confirmation_formatter = MCPConfirmationFormatter(template_manager)
        
        # StateManager для управления состоянием пользователя
        self.state_manager = StateManager(user_id=user_id, redis_client=redis)
        
        # DialogAgent для понимания языка и формирования ответов
        self.dialog_agent = DialogAgent(user_id=user_id)
        
        # DecisionEngine для выбора действий
        self.decision_engine = DecisionEngine(user_id=user_id)
        
        # Уникальный ID для отслеживания агента в логах
        import uuid
        self.agent_id = str(uuid.uuid4())[:8]

    async def run(self):
        logger.info(f"[AGENT {self.user_id}:{self.agent_id}] started")
        
        # Инициализируем БД для работы с репозиториями
        from app.core.db import init_db
        await init_db()
        
        # Загружаем state из Redis
        await self.state_manager.load_from_redis()
        logger.info(f"[AGENT {self.user_id}:{self.agent_id}] state loaded")
        
        try:
            async with streamablehttp_client(settings.mcp_server_url) as (read, write, get_session_id):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    self.mcp_tools = await self._get_mcp_tools(session)

                    while self.running:
                        # ждём новые сообщения
                        msgs = await self.redis.xread(
                            streams={self.stream: "$"},
                            block=1000  # ms
                        )

                        if not msgs:
                            # Проверяем флаг running после каждого цикла ожидания
                            if not self.running:
                                break
                            continue

                        _, entries = msgs[0]

                        for msg_id, data in entries:
                            self.last_active = time.time()
                            logger.info(f"[AGENT {self.user_id}:{self.agent_id}] received {msg_id} {data}")

                            # Проверяем тип сообщения
                            try:
                                message_json = json.loads(data.get('message', '{}'))
                            except (json.JSONDecodeError, AttributeError):
                                message_json = {}
                            
                            if 'callback_query' in message_json:
                                # Обрабатываем callback query
                                callback_data = message_json['callback_query'].get('data', '')
                                callback_id = message_json['callback_query'].get('id', '')
                                
                                # Отвечаем на callback query (убираем "часики")
                                if callback_id:
                                    asyncio.create_task(self._answer_callback_query(callback_id))
                                
                                # Проверяем, есть ли это MCP callback с Redis ключом
                                if callback_data.startswith('confirm_yes:') or callback_data.startswith('confirm_no:'):
                                    await self._handle_mcp_confirmation(callback_data, session)
                                else:
                                    # Простые callback без Redis (для совместимости)
                                    logger.info(f"[AGENT {self.user_id}:{self.agent_id}] simple callback: {callback_data}")
                                
                            else:
                                # Обрабатываем обычное текстовое сообщение
                                message_text = self._extract_message_text(data)
                                
                                # СХЕМА: User → Dialog Agent → Decision Engine → Tool → Response
                                response = await self._handle_user_message(session, message_text)
                                        
                                if response:
                                    # Отправляем ответ в Telegram
                                    await self._send_telegram_message(
                                        user_id=self.user_id,
                                        text=response
                                    )

                                logger.info(f"[AGENT {self.user_id}:{self.agent_id}] processed {msg_id} {response}")

                        # авто-выгрузка
                        if time.time() - self.last_active > AGENT_IDLE_TIMEOUT:
                            print(f"[AGENT {self.user_id}] auto stop (idle)")
                            break
        
        except asyncio.CancelledError:
            logger.info(f"[AGENT {self.user_id}:{self.agent_id}] cancelled by worker")
        except Exception as e:
            logger.error(f"[AGENT {self.user_id}:{self.agent_id}] error during execution: {e}")
        finally:
            # Сохраняем state в Redis перед остановкой
            await self.state_manager.sync_to_redis()
            logger.info(f"[AGENT {self.user_id}:{self.agent_id}] stopped, state saved")

    def _extract_message_text(self, data: dict) -> str:
        """Извлекает текст сообщения из данных Redis stream (только для обычных сообщений)"""
        try:
            # Парсим JSON из поля message
            message_json = json.loads(data.get('message', '{}'))
            
            # Возвращаем только текст обычного сообщения
            message_text = message_json.get('text', '')
        except (json.JSONDecodeError, AttributeError):
            message_text = str(data.get('message', ''))
        return message_text

    async def _send_telegram_message(self, user_id: int, text: str, **kwargs):
        """Отправляет сообщение в Telegram через TelegramClient"""
        try:
            result = await self.telegram_client.send_message(
                chat_id=user_id,
                text=text,
                **kwargs
            )
            
            if result.get("ok"):
                logger.info(f"[AGENT {user_id}] сообщение отправлено в Telegram")
                return True
            else:
                logger.error(f"[AGENT {user_id}] ошибка отправки в Telegram: {result.get('description', 'неизвестная ошибка')}")
                return False
                        
        except Exception as e:
            logger.error(f"[AGENT {user_id}] ошибка отправки сообщения: {e}")
            return False

    async def _answer_callback_query(self, callback_query_id: str, text: str = None):
        """Отвечает на callback query для убирания 'часиков' с inline кнопки"""
        try:
            result = await self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text=text
            )
            if result.get("ok"):
                logger.debug(f"[AGENT {self.user_id}] callback query answered: {callback_query_id}")
            else:
                logger.warning(f"[AGENT {self.user_id}] не удалось ответить на callback: {result}")
        except Exception as e:
            logger.error(f"[AGENT {self.user_id}] ошибка ответа на callback: {e}")

    async def _handle_mcp_confirmation(self, callback_data: str, session):
        """Обрабатывает подтверждение/отмену выполнения MCP функции"""
        try:
            # Парсим callback_data
            action, callback_key = callback_data.split(':', 1)
            
            # Получаем данные функции из Redis
            function_data_json = await self.redis.get(callback_key)
            if not function_data_json:
                await self._send_telegram_message(
                    user_id=self.user_id,
                    text="⚠️ Время ожидания подтверждения истекло или запрос не найден."
                )
                return
            
            function_data = json.loads(function_data_json)
            function_name = function_data["function_name"]
            arguments = function_data["arguments"]
            
            if action == "confirm_yes":
                # Выполняем функцию
                await self._send_telegram_message(
                    user_id=self.user_id,
                    text=f"⚡ Выполняется функция {function_name}..."
                )
                
                # Используем переданную сессию
                try:
                    # Вызываем MCP tool
                    tool_result = await session.call_tool(
                        name=function_name,
                        arguments=arguments
                    )
                    
                    # Обрабатываем результат
                    if tool_result.content:
                        try:
                            if hasattr(tool_result.content[0], 'text'):
                                result = json.loads(tool_result.content[0].text)
                            else:
                                result = {"result": str(tool_result.content[0])}
                        except (json.JSONDecodeError, IndexError, AttributeError):
                            result = {"result": str(tool_result.content)}
                    else:
                        result = {"success": True}
                    
                    # Отправляем результат в Telegram
                    if result.get("success"):
                        message = f"✅ Функция {function_name} выполнена успешно"
                        if "title" in result:
                            message += f": {result['title']}"
                    else:
                        message = f"❌ Ошибка выполнения {function_name}: {result.get('error', 'неизвестная ошибка')}"
                    
                    await self._send_telegram_message(
                        user_id=self.user_id,
                        text=message
                    )
                    
                except Exception as e:
                    await self._send_telegram_message(
                        user_id=self.user_id,
                        text=f"❌ Ошибка выполнения функции {function_name}: {str(e)}"
                    )
                    
            else:  # confirm_no
                # Отменяем выполнение
                await self._send_telegram_message(
                    user_id=self.user_id,
                    text=f"❌ Выполнение функции {function_name} отменено пользователем."
                )
            
            # Удаляем данные из Redis в любом случае
            await self.redis.delete(callback_key)
            
        except Exception as e:
            logger.exception(f"[AGENT {self.user_id}] ошибка обработки подтверждения MCP: {e}")

    async def _wait_for_user_response(self, timeout: int = 30):
        """Ожидает ответ пользователя в течение timeout секунд"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Проверяем новые сообщения в стриме
            msgs = await self.redis.xread(
                streams={self.stream: "$"},
                block=1000  # 1 секунда
            )
           
            if msgs:
                _, entries = msgs[0]
                for msg_id, data in entries:
                    message_text = self._extract_message_text(data)
                    logger.info(f"[AGENT {self.user_id}] получен ответ: {message_text}")
                    return message_text
        
        logger.warning(f"[AGENT {self.user_id}] таймаут ожидания ответа")
        return None

    async def _get_mcp_tools(self, session):
        """Получает список инструментов от MCP HTTP сервера"""
        try:
            # Получаем инструменты MCP сервера
            mcp_tools_response = await session.list_tools()
                    
            # Преобразуем MCP tools в формат для OpenAI
            tools_list = []
            for tool in mcp_tools_response.tools:
                tools_list.append({
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                })
                
            logger.info(f"[AGENT {self.user_id}:{self.agent_id}] успешно загружено {len(tools_list)} MCP инструментов")
            return tools_list                    
        except Exception as e:
            import traceback
            logger.error(f"[AGENT {self.user_id}] ошибка подключения к MCP серверу:")
            logger.error(f"[AGENT {self.user_id}] URL: {settings.mcp_server_url}")
            logger.error(f"[AGENT {self.user_id}] Ошибка: {e}")
            logger.error(f"[AGENT {self.user_id}] Traceback: {traceback.format_exc()}")
            return None

    async def _handle_user_message(self, mcp_session: object, message_text: str) -> str:
        """
        ПОЛНАЯ СХЕМА обработки сообщения пользователя:
        1. User → Dialog Agent (понимание намерения)
        2. Clarification check
        3. Intent Payload → Decision Engine (выбор действия)
        4. Tool Call → Tool Executor
        5. Tool Result → State Update
        6. Dialog Agent (человеческий ответ)
        """
        try:
            # === ШАГ 1: DIALOG AGENT - понимание намерения ===
            intent_result = await self.dialog_agent.understand_intent(message_text)
            
            logger.info(f"[AGENT {self.user_id}] Intent: {intent_result.get('intent')}")
            
            # === ШАГ 2: CLARIFICATION CHECK ===
            if intent_result.get("needs_clarification"):
                # Возвращаем уточняющий вопрос пользователю
                clarification_message = intent_result.get("clarification_question", "Уточните, пожалуйста, ваш запрос.")
                
                # Сохраняем в state что ждём уточнение
                self.state_manager.update_current_context(
                    intent="clarification_needed",
                    mentioned_entities=intent_result.get("entities", []),
                    clarification_question=clarification_message
                )
                await self.state_manager.sync_to_redis()
                
                return clarification_message
            
            # === ШАГ 3: DECISION ENGINE - выбор действия ===
            # Получаем релевантный контекст для Decision Engine
            relevant_context = await self.state_manager.get_relevant_context(
                user_message=message_text,
                intent=intent_result.get("intent")
            )
            
            # Получаем список доступных инструментов
            available_tools = [tool["name"] for tool in (self.mcp_tools or [])]
            
            decision_result = await self.decision_engine.choose_action_with_validation(
                intent_payload=intent_result,
                state_context=relevant_context,
                available_tools=available_tools
            )
            
            logger.info(f"[AGENT {self.user_id}] Decision: {decision_result.get('action_type')}")
            
            # === ШАГ 4-5: TOOL EXECUTION & STATE UPDATE ===
            if decision_result.get("action_type") == "tool_call":
                tool_name = decision_result.get("tool_name")
                tool_arguments = decision_result.get("tool_arguments", {})
                
                # Добавляем в recent_actions
                self.state_manager.add_action(
                    action_type="tool_call_initiated",
                    description=f"Вызов {tool_name}",
                    tool_name=tool_name,
                    arguments=tool_arguments
                )
                
                # Выполняем tool
                tool_result = await self._execute_tool(mcp_session, tool_name, tool_arguments)
                
                # Обновляем state на основе результата
                await self._update_state_from_tool_result(tool_name, tool_arguments, tool_result)
                
                # === ШАГ 5.1: STATE OPTIMIZATION ===
                # Оптимизируем state после обновления, но перед формированием ответа
                optimization_stats = await self.state_manager.optimize_state()
                logger.info(f"[AGENT {self.user_id}] State optimized after tool execution: {optimization_stats}")
                
                # Сохраняем state
                await self.state_manager.sync_to_redis()
                
                # === ШАГ 6: DIALOG AGENT - формирование ответа ===
                if tool_result.get("pending"):
                    # Ожидаем подтверждение - не отправляем дополнительное сообщение
                    return ""
                else:
                    # Формируем человеческий ответ на основе результата
                    response = await self.dialog_agent.format_response(
                        intent=intent_result.get("intent"),
                        tool_name=tool_name,
                        tool_result=tool_result
                    )
                    
                    # Сохраняем диалог
                    self.state_manager.add_dialog_message("user", message_text)
                    self.state_manager.add_dialog_message("assistant", response)
                    await self.state_manager.sync_to_redis()
                    
                    return response
            
            elif decision_result.get("action_type") == "noop":
                # Просто отвечаем без выполнения инструментов
                response = decision_result.get("message", "Понял вас, но действий не требуется.")
                
                # Сохраняем диалог
                self.state_manager.add_dialog_message("user", message_text)
                self.state_manager.add_dialog_message("assistant", response)
                await self.state_manager.sync_to_redis()
                
                return response
            
            else:
                return "Не удалось определить действие."
            
        except Exception as e:
            logger.exception(f"[AGENT {self.user_id}] ошибка обработки сообщения: {e}")
            return f"Произошла ошибка: {str(e)}"
    
    async def _execute_tool(self, mcp_session: object, tool_name: str, tool_arguments: dict) -> dict:
        """
        Tool Executor: Выполнение выбранного инструмента
        
        Returns:
            {
                "success": bool,
                "pending": bool (if confirmation needed),
                "result": any,
                "error": str (if failed)
            }
        """
        try:
            # Вызываем MCP функцию
            tool_result = await self._call_mcp_function(mcp_session, tool_name, tool_arguments)
            return tool_result
            
        except Exception as e:
            logger.error(f"[AGENT {self.user_id}] ошибка Tool Executor: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _update_state_from_tool_result(self, tool_name: str, tool_arguments: dict, tool_result: dict) -> None:
        """
        State Update: Обновление state на основе результата выполнения tool
        """
        try:
            # Добавляем action о результате
            if tool_result.get("success"):
                self.state_manager.add_action(
                    action_type="tool_call_success",
                    description=f"Успешно: {tool_name}",
                    tool_name=tool_name,
                    result=tool_result.get("result")
                )
                
                # Обновляем задачи если это было действие с задачей
                if tool_name == "create_task" and "task_id" in tool_result:
                    self.state_manager.add_task(
                        task_id=tool_result["task_id"],
                        status="active",
                        title=tool_arguments.get("title", "Новая задача")
                    )
                elif tool_name == "update_task_status":
                    self.state_manager.update_task_status(
                        task_id=tool_arguments.get("task_id"),
                        new_status=tool_arguments.get("status")
                    )
            else:
                self.state_manager.add_action(
                    action_type="tool_call_failed",
                    description=f"Ошибка: {tool_name}",
                    tool_name=tool_name,
                    error=tool_result.get("error")
                )
            
        except Exception as e:
            logger.error(f"[AGENT {self.user_id}] ошибка State Update: {e}")
    
    async def _call_mcp_function(self, session: object, function_name: str, arguments: dict):
        """Вызывает функцию на MCP HTTP сервере"""
        try:
            # Добавляем user_id в аргументы для функций которые его требуют
            if function_name in ["create_task", "search_tasks", "get_user_tasks", "update_task_status"]:
                arguments["user_id"] = int(self.user_id)

            # Генерируем уникальный ключ для сохранения в Redis
            import uuid
            callback_key = f"mcp_confirm:{self.user_id}:{uuid.uuid4().hex[:8]}"
            
            # Сохраняем данные функции в Redis на 5 минут
            function_data = {
                "function_name": function_name,
                "arguments": arguments,
                "user_id": self.user_id,
                "timestamp": time.time()
            }
            
            await self.redis.setex(
                callback_key, 
                300,  # 5 минут TTL
                json.dumps(function_data)
            )
            
            # Создаем inline клавиатуру с ключом Redis
            inline_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Да", "callback_data": f"confirm_yes:{callback_key}"},
                        {"text": "❌ Нет", "callback_data": f"confirm_no:{callback_key}"}
                    ]
                ]
            }

            # Генерируем человекочитаемое сообщение используя шаблоны
            confirmation_message = self.confirmation_formatter.format_mcp_confirmation_message(
                function_name, arguments, self.user_id, self.mcp_tools
            )

            result = await self.telegram_client.send_message(
                chat_id=self.user_id,
                text=confirmation_message,
                reply_markup=inline_keyboard,
                parse_mode="Markdown"
            )
            
            if not result.get("ok"):
                # Удаляем из Redis если не удалось отправить сообщение
                await self.redis.delete(callback_key)
                return {"success": False, "error": "Ошибка отправки сообщения подтверждения"}
            
            # Возвращаем успех - функция будет выполнена после подтверждения
            return {"success": True, "pending": True, "message": "Ожидается подтверждение пользователя"}
                    
        except Exception as e:
            logger.exception(f"[AGENT {self.user_id}] ошибка вызова MCP функции {function_name}: {e}")
            return {"success": False, "error": str(e)}


async def acquire_lock(redis, user_id):
    """Пытаемся получить эксклюзивный lock на агента."""
    return await redis.set(
        f"lock:{user_id}",
        "1",
        ex=AGENT_IDLE_TIMEOUT,
        nx=True
    )


async def release_lock(redis, user_id):
    await redis.delete(f"lock:{user_id}")


async def worker_loop():
    settings = get_settings()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    
    active_agents = {}  # user_id → AgentSession
    active_tasks = {}   # user_id → asyncio.Task
    
    while True:
        # очищаем мёртвых
        dead = [
            uid for uid, agent in active_agents.items()
            if time.time() - agent.last_active > AGENT_IDLE_TIMEOUT
        ]
        
        for uid in dead:
            logger.info(f"[WORKER] releasing idle agent {uid}")
            
            # Сначала проверяем, что агент действительно неактивен
            # Даём ещё одну секунду на обработку
            agent = active_agents.get(uid)
            if agent and (time.time() - agent.last_active < AGENT_IDLE_TIMEOUT - 5):
                continue  # Агент снова стал активным, пропускаем
            
            # Останавливаем агент
            if agent:
                agent.running = False
            
            # Отменяем задачу и ждем её завершения
            task = active_tasks.get(uid)
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            
            # Освобождаем ресурсы только после полной остановки
            await release_lock(redis, uid)
            active_agents.pop(uid, None)
            active_tasks.pop(uid, None)
        
        # если есть место — пытаемся взять новых агентов
        if len(active_agents) < MAX_ACTIVE_AGENTS:
            keys = await redis.keys("agent:*:stream")
            
            for key in keys:
                user_id = key.split(":")[1]
                
                # Проверяем что агент не существует и задача не запущена
                if user_id in active_agents or user_id in active_tasks:
                    continue
                
                # пытаемся получить lock на user_id
                if not await acquire_lock(redis, user_id):
                    continue
                
                # создаём агент
                agent = AgentSession(user_id, redis)
                task = asyncio.create_task(agent.run())
                
                active_agents[user_id] = agent
                active_tasks[user_id] = task
                
                if len(active_agents) >= MAX_ACTIVE_AGENTS:
                    break
        
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(worker_loop())
