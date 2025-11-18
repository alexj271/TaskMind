"""
Pydantic модели для Gatekeeper Worker.
Обработка входящих сообщений и классификация.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal
from enum import Enum


class MessageType(str, Enum):
    """Типы сообщений после классификации"""
    TASK = "task"
    CHAT = "chat"


class IncomingMessage(BaseModel):
    """Входящее сообщение от Telegram"""
    update_id: int
    user_id: int
    chat_id: int
    message_text: str
    user_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MessageClassification(BaseModel):
    """Результат классификации сообщения"""
    message_type: MessageType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None


class ParsedTaskData(BaseModel):
    """Данные распарсенной задачи"""
    title: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None
    priority: Optional[Literal["low", "medium", "high"]] = None


class GatekeeperResponse(BaseModel):
    """Ответ от Gatekeeper воркера"""
    action: Literal["task_created", "forwarded_to_chat", "error"]
    message: str
    task_id: Optional[str] = None  # UUID задачи, если создана