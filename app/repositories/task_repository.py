from app.models.task import Task
from typing import Optional, List
from datetime import datetime
import uuid

class TaskRepository:
    async def create(self, user_id: uuid.UUID, *, title: str, description: str | None, scheduled_at: datetime | None, reminder_at: datetime | None) -> Task:
        return await Task.create(user_id=user_id, title=title, description=description, scheduled_at=scheduled_at, reminder_at=reminder_at)

    async def get(self, task_id: uuid.UUID) -> Optional[Task]:
        return await Task.filter(id=task_id).first()

    async def list_for_user(self, user_id: uuid.UUID) -> List[Task]:
        return await Task.filter(user_id=user_id).all()

    async def delete(self, task_id: uuid.UUID) -> int:
        return await Task.filter(id=task_id).delete()

    async def update_reminder(self, task_id: uuid.UUID, reminder_at: datetime | None) -> int:
        return await Task.filter(id=task_id).update(reminder_at=reminder_at)
