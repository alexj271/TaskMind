from app.repositories.task_repository import TaskRepository
from app.schemas.task import ParsedTask
import uuid
from datetime import datetime

class TaskService:
    def __init__(self, repo: TaskRepository):
        self.repo = repo

    async def save_parsed(self, user_id: uuid.UUID, parsed: ParsedTask):
        return await self.repo.create(
            user_id=user_id,
            title=parsed.title,
            description=parsed.description,
            scheduled_at=parsed.scheduled_at,
            reminder_at=parsed.reminder_at,
        )

    async def schedule_reminder(self, task_id: uuid.UUID, reminder_at: datetime | None):
        return await self.repo.update_reminder(task_id, reminder_at)
