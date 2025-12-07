from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
import uuid

class TaskCreate(BaseModel):
    text: str = Field(description="Raw natural language task text")

class ParsedTask(BaseModel):
    title: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None

class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    user_task_id: int
    title: str
    description: Optional[str]
    scheduled_at: Optional[datetime]
    reminder_at: Optional[datetime]
