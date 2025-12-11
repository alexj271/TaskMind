import asyncio
import json
import logging
import time
import redis.asyncio as aioredis
from openai import AsyncOpenAI
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from app.core.config import get_settings
from app.services.telegram_client import TelegramClient


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
        
        # Уникальный ID для отслеживания агента в логах
        import uuid
        self.agent_id = str(uuid.uuid4())[:8]

    async def run(self):
        logger.info(f"[AGENT {self.user_id}:{self.agent_id}] started")
        
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

                        # ---- логика обработки сообщения ----
                        message_text = self._extract_message_text(data)

                        # Используем OpenAI Responses API с MCP инструментами
                        response = await self._process_with_ai(session, message_text)
                                
                        # Отправляем ответ в Telegram
                        await self._send_telegram_message(
                            user_id=self.user_id,
                            text=response
                        )

                        logger.info(f"[AGENT {self.user_id}:{self.agent_id}] processed {msg_id} {response}")

                    # авто-выгрузка
                    # if time.time() - self.last_active > AGENT_IDLE_TIMEOUT:
                    #     print(f"[AGENT {self.user_id}] auto stop (idle)")
                    #     break
        
        except asyncio.CancelledError:
            logger.info(f"[AGENT {self.user_id}:{self.agent_id}] cancelled by worker")
        except Exception as e:
            logger.error(f"[AGENT {self.user_id}:{self.agent_id}] error during execution: {e}")
        finally:
            logger.info(f"[AGENT {self.user_id}:{self.agent_id}] stopped")

    def _extract_message_text(self, data: dict) -> str:
        """Извлекает текст сообщения из данных Redis stream"""
        try:
            # Парсим JSON из поля message
            message_json = json.loads(data.get('message', '{}'))
            message_text = message_json.get('text', '')
        except (json.JSONDecodeError, AttributeError):
            message_text = str(data.get('message', ''))
        return message_text

    async def _send_telegram_message(self, user_id: int, text: str):
        """Отправляет сообщение в Telegram через TelegramClient"""
        try:
            result = await self.telegram_client.send_message(
                chat_id=user_id,
                text=text
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

    async def _process_with_ai(self, session: object, message_text: str) -> str:
        """Обрабатывает сообщение с помощью OpenAI Responses API"""
        try:
            SYSTEM = """
                Ты - интеллектуальный помощник для управления задачами через Telegram бот.
                Используй доступные функции для выполнения запросов пользователя.
            """
            response = await client.responses.create(
                model="gpt-4.1-mini",
                input=message_text,
                instructions=SYSTEM,
                tools=self.mcp_tools,
                max_output_tokens=800,
                temperature=0.3
            )
            
            # Обрабатываем ответ
            result_text = ""            
            for item in response.output:
                logger.debug(f'Content: {item} Type: {item.type}')
                if item.type == "message":
                    result_text += " ".join([i.text for i in item.content])
                elif item.type == "function_call":
                    # Выполняем вызов MCP функции
                    arguments = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments

                    logger.debug(f'Function call: {item.name} Args: {arguments}')
                    func_result = await self._call_mcp_function(
                        session,
                        item.name, 
                        arguments
                    )
                    result_text += f"\n✅ Выполнено: {item.name}"
                    if func_result.get("success"):
                        if "title" in func_result:
                            result_text += f" - {func_result['title']}"
                    else:
                        result_text = f" - Ошибка: {func_result.get('error', 'неизвестная ошибка')}"
            
            return result_text if result_text.strip() else "Готово!"
            
        except Exception as e:
            logger.exception(f"[AGENT {self.user_id}] ошибка обработки AI: {e}")
            return f"Произошла ошибка при обработке запроса: {str(e)}"

    async def _call_mcp_function(self, session: object, function_name: str, arguments: dict):
        """Вызывает функцию на MCP HTTP сервере"""
        try:
            # Добавляем user_id в аргументы для функций которые его требуют
            if function_name in ["create_task", "search_tasks", "get_user_tasks", "update_task_status"]:
                arguments["user_id"] = int(self.user_id)

            await self._send_telegram_message(
                user_id=self.user_id,
                text=f"Будет выполнен запрос к функции {function_name}, вы подтверждаете? Да или нет."
            )
            user_response = await self._wait_for_user_response(timeout=60)

            if not user_response or user_response.lower() not in ["да", "yes", "подтверждаю"]:
                return {"success": False, "error": "Пользователь отменил выполнение функции."}
                    
            # Вызываем MCP tool
            tool_result = await session.call_tool(
                name=function_name,
                arguments=arguments
            )

            logger.debug(f"[AGENT {self.user_id}] MCP функция {function_name} выполнена: {tool_result}")
                    
            # Преобразуем результат MCP в наш формат
            if tool_result.content:
                try:
                    if hasattr(tool_result.content[0], 'text'):
                        function_result = json.loads(tool_result.content[0].text)
                    else:
                        function_result = {"result": str(tool_result.content[0])}
                except (json.JSONDecodeError, IndexError, AttributeError):
                    function_result = {"result": str(tool_result.content)}
            else:
                function_result = {"success": True}
                    
            return function_result
                    
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
