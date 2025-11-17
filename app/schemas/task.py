from pydantic import BaseModel, Field
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
    id: uuid.UUID
    title: str
    description: Optional[str]
    scheduled_at: Optional[datetime]
    reminder_at: Optional[datetime]

    class Config:
        from_attributes = True
