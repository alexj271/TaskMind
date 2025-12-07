"""
FastAPI роутер для тестирования системы через веб-интерфейс.
Предоставляет GUI для ручного тестирования чата и мониторинга результатов.
"""
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import asyncio

from app.workers.gatekeeper.tasks import process_webhook_message
from app.repositories.user_repository import UserRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.dialog_repository import DialogRepository
from app.core.db import init_db
from app.services.redis_pubsub import get_pubsub_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/testing", tags=["testing"])

# Настройка шаблонов
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Хранилище активных WebSocket соединений
active_connections: List[WebSocket] = []
# Хранилище результатов тестирования для каждой сессии
test_results: Dict[str, List[Dict[str, Any]]] = {}
# Хранилище сообщений от бота для отображения в GUI
bot_messages: Dict[str, List[Dict[str, Any]]] = {}  # session_id -> [message_data]


class ConnectionManager:
    """Управляет WebSocket соединениями для real-time обновлений"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Удаляем неактивные соединения
                self.active_connections.remove(connection)


manager = ConnectionManager()


async def handle_bot_message(chat_id: int, text: str):
    """Обработчик перехваченных сообщений от бота для отображения в GUI"""
    try:
        # Находим активные соединения для этого чата
        message_data = {
            "type": "bot_message", 
            "chat_id": chat_id,
            "text": text,
            "timestamp": datetime.now().isoformat()
        }
        
        # Отправляем во все активные WebSocket соединения
        await manager.broadcast(json.dumps(message_data))
        
        # Сохраняем в глобальном хранилище для истории
        session_key = f"chat_{chat_id}"
        if session_key not in bot_messages:
            bot_messages[session_key] = []
        bot_messages[session_key].append(message_data)
        
        # Ограничиваем историю
        if len(bot_messages[session_key]) > 100:
            bot_messages[session_key] = bot_messages[session_key][-100:]
        
        logger.info(f"Testing: перехвачено сообщение бота для чата {chat_id}: {text[:50]}...")
        
    except Exception as e:
        logger.error(f"Testing: ошибка обработки сообщения бота: {e}")


@router.get("/", response_class=HTMLResponse)
async def testing_interface(request: Request):
    """Главная страница тестирования"""
    logger.info("Тестирование: интерфейс запущен с Redis Pub/Sub поддержкой")
    return templates.TemplateResponse("testing.html", {"request": request})


async def redis_pubsub_listener(websocket: WebSocket, session_id: str, chat_id: int):
    """Прослушиватель Redis Pub/Sub сообщений от бота"""
    try:
        pubsub_service = get_pubsub_service()
        
        # Подписываемся на канал сессии
        pubsub_session = pubsub_service.subscribe_to_session(session_id)
        
        # Подписываемся на ответы бота для чата
        pubsub_bot = pubsub_service.subscribe_to_bot_responses(chat_id)
        
        if not pubsub_session or not pubsub_bot:
            logger.error(f"Redis PubSub: ошибка создания подписок")
            return
        
        logger.info(f"Redis PubSub: запущен прослушиватель для сессии {session_id}")
        
        while True:
            # Проверяем сообщения от обеих подписок
            session_message = pubsub_session.get_message(timeout=0.1)
            bot_message = pubsub_bot.get_message(timeout=0.1)
            
            if session_message and session_message['type'] == 'message':
                try:
                    data = json.loads(session_message['data'])
                    await websocket.send_text(json.dumps(data))
                    logger.info(f"Redis PubSub: передано сообщение сессии в WebSocket")
                except Exception as e:
                    logger.error(f"Redis PubSub: ошибка обработки сообщения сессии: {e}")
            
            if bot_message and bot_message['type'] == 'message':
                try:
                    data = json.loads(bot_message['data'])
                    await websocket.send_text(json.dumps(data))
                    logger.info(f"Redis PubSub: передано сообщение бота в WebSocket")
                except Exception as e:
                    logger.error(f"Redis PubSub: ошибка обработки сообщения бота: {e}")
            
            # Короткая пауза, чтобы не нагружать CPU
            await asyncio.sleep(0.1)
            
    except Exception as e:
        logger.error(f"Redis PubSub: ошибка в прослушивателе: {e}")
    finally:
        if 'pubsub_session' in locals():
            pubsub_session.close()
        if 'pubsub_bot' in locals():
            pubsub_bot.close()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Вебсокет endpoint для real-time коммуникации с интерфейсом"""
    await manager.connect(websocket)
    
    # Переменные для отслеживания Redis
    current_session_id = None
    current_chat_id = None
    pubsub_task = None
    
    try:
        while True:
            # Ждем сообщения от клиента
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data["type"] == "send_message":
                session_id = message_data.get("session_id", "default")
                chat_id = message_data.get("chat_id", message_data.get("user_id", 12345))
                
                # Перезапускаем Redis прослушиватель при смене сессии
                if current_session_id != session_id or current_chat_id != chat_id:
                    if pubsub_task:
                        pubsub_task.cancel()
                    
                    current_session_id = session_id
                    current_chat_id = chat_id
                    pubsub_task = asyncio.create_task(redis_pubsub_listener(websocket, session_id, chat_id))
                
                # Обрабатываем тестовое сообщение
                await handle_test_message(websocket, message_data)
            elif message_data["type"] == "get_test_results":
                # Отправляем результаты тестирования
                await send_test_results(websocket, message_data.get("session_id", "default"))
                
    except WebSocketDisconnect:
        if pubsub_task:
            pubsub_task.cancel()
        manager.disconnect(websocket)


async def handle_test_message(websocket: WebSocket, message_data: Dict[str, Any]):
    """Обрабатывает тестовое сообщение через систему воркеров"""
    try:
        # Извлекаем данные из сообщения
        user_id = message_data.get("user_id", 12345)
        chat_id = message_data.get("chat_id", user_id)
        message_text = message_data.get("message", "")
        user_name = message_data.get("user_name", "TestUser")
        session_id = message_data.get("session_id", "default")
        
        logger.info(f"Тестирование: обрабатываем сообщение от {user_name}: {message_text}")
        
        # Устанавливаем флаг тестового режима в Redis для данного чата
        pubsub_service = get_pubsub_service()
        await pubsub_service.set_test_mode_flag(chat_id, session_id)
        
        # Создаем webhook данные в формате Telegram
        webhook_data = {
            "update_id": int(datetime.now().timestamp()),
            "message": {
                "from": {
                    "id": user_id,
                    "first_name": user_name
                },
                "chat": {
                    "id": chat_id
                },
                "text": message_text
            }
        }
        
        # Инициализируем DB для тестирования
        await init_db()
        
        # Запускаем обработку через Dramatiq gatekeeper actor
        process_webhook_message.send(
            webhook_data["update_id"],
            webhook_data["message"]
        )
        
        # Собираем результаты
        await collect_test_results(websocket, session_id, user_id, message_text)
        
        # Отправляем подтверждение обработки
        await websocket.send_text(json.dumps({
            "type": "message_processed",
            "status": "success",
            "message": "Сообщение обработано (через Dramatiq + Redis Pub/Sub)"
        }))
        
    except Exception as e:
        logger.error(f"Testing: ошибка обработки сообщения: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Ошибка: {str(e)}"
        }))


async def collect_test_results(websocket: WebSocket, session_id: str, user_id: int, message_text: str):
    """Собирает результаты тестирования и отправляет их в интерфейс"""
    try:
        # Получаем информацию о пользователе
        user_repo = UserRepository()
        user = await user_repo.get_by_telegram(user_id)
        
        # Получаем задачи пользователя
        task_repo = TaskRepository()
        tasks = await task_repo.list_for_user(user.id) if user else []
        
        # Получаем диалоговую сессию
        dialog_repo = DialogRepository()
        dialog_session = await dialog_repo.get_or_create_for_user(user) if user else None
        
        # Формируем результаты
        results = {
            "type": "test_results",
            "timestamp": datetime.now().isoformat(),
            "input_message": message_text,
            "user_info": {
                "id": str(user.id) if user else None,
                "telegram_id": user.telegram_id if user else user_id,
                "username": user.username if user else "Unknown",
                "timezone": user.timezone if user else None,
                "created_at": user.created_at.isoformat() if user else None
            },
            "tasks": [
                {
                    "id": str(task.id),
                    "user_task_id": task.user_task_id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status.value,
                    "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat()
                }
                for task in tasks[-5:]  # Последние 5 задач
            ],
            "dialog_info": {
                "summary": dialog_session.summary if dialog_session else None,
                "last_messages": dialog_session.last_messages[-3:] if dialog_session else [],
                "updated_at": dialog_session.updated_at.isoformat() if dialog_session else None
            }
        }
        
        # Сохраняем результаты в глобальном хранилище
        if session_id not in test_results:
            test_results[session_id] = []
        test_results[session_id].append(results)
        
        # Ограничиваем количество сохраняемых результатов
        if len(test_results[session_id]) > 50:
            test_results[session_id] = test_results[session_id][-50:]
        
        # Отправляем результаты через WebSocket
        await websocket.send_text(json.dumps(results))
        
    except Exception as e:
        logger.error(f"Testing: ошибка сбора результатов: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Ошибка сбора результатов: {str(e)}"
        }))


async def send_test_results(websocket: WebSocket, session_id: str):
    """Отправляет накопленные результаты тестирования"""
    try:
        session_results = test_results.get(session_id, [])
        await websocket.send_text(json.dumps({
            "type": "all_test_results",
            "results": session_results
        }))
    except Exception as e:
        logger.error(f"Testing: ошибка отправки результатов: {str(e)}")


@router.get("/clear/{session_id}")
async def clear_test_results(session_id: str):
    """Очищает результаты тестирования для сессии"""
    if session_id in test_results:
        del test_results[session_id]
    return {"status": "cleared", "session_id": session_id}


@router.get("/results/{session_id}")
async def get_test_results_api(session_id: str):
    """API endpoint для получения результатов тестирования"""
    return {
        "session_id": session_id,
        "results": test_results.get(session_id, []),
        "count": len(test_results.get(session_id, []))
    }


@router.get("/disable-testing/{chat_id}")
async def disable_testing_endpoint(chat_id: int):
    """Отключает режим тестирования для конкретного чата"""
    pubsub_service = get_pubsub_service()
    success = await pubsub_service.clear_test_mode_flag(chat_id)
    
    message = f"Режим тестирования {'отключен' if success else 'не удалось отключить'} для чата {chat_id}"
    logger.info(f"Тестирование: {message}")
    
    return {"status": "disabled" if success else "error", "message": message}


@router.get("/bot-messages/{session_id}")
async def get_bot_messages(session_id: str):
    """Получает историю сообщений бота для сессии"""
    return {
        "session_id": session_id,
        "messages": bot_messages.get(session_id, []),
        "count": len(bot_messages.get(session_id, []))
    }