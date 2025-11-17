from fastapi import APIRouter, Depends
from app.schemas.task import TaskCreate, TaskOut
from app.services.ai_parse_service import AIParseService
from app.services.task_service import TaskService
from app.repositories.task_repository import TaskRepository
import uuid

router = APIRouter()

async def get_task_service() -> TaskService:
    return TaskService(TaskRepository())

async def get_ai_service() -> AIParseService:
    return AIParseService()

@router.post("/parse", response_model=TaskOut)
async def parse_and_create_task(payload: TaskCreate, user_id: uuid.UUID, ai: AIParseService = Depends(get_ai_service), svc: TaskService = Depends(get_task_service)):
    parsed = await ai.parse_task(payload.text)
    task = await svc.save_parsed(user_id=user_id, parsed=parsed)
    return task
