import dramatiq
from app.services.telegram_service import TelegramService
from app.services.ai_parse_service import AIParseService
from app.services.task_service import TaskService
from app.repositories.task_repository import TaskRepository
import uuid

@dramatiq.actor
async def ai_parse_actor(user_id: str, text: str):
    ai = AIParseService()
    parsed = await ai.parse_task(text)
    svc = TaskService(TaskRepository())
    await svc.save_parsed(uuid.UUID(user_id), parsed)

@dramatiq.actor
async def send_telegram_actor(chat_id: int, message: str):
    tg = TelegramService()
    await tg.send_message(chat_id, message)

@dramatiq.actor
async def reminder_actor(task_id: str):
    # Placeholder for reminder scheduling logic
    pass
