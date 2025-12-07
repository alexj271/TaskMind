"""
Pydantic модели для Gatekeeper Worker.
Управление доступом через проверку таймзоны.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class IncomingMessage(BaseModel):
    """Входящее сообщение от Telegram"""
    update_id: int
    user_id: int
    chat_id: int
    message_text: str
    user_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GatekeeperResponse(BaseModel):
    """Ответ от Gatekeeper воркера"""
    action: Literal["timezone_set", "forwarded_to_chat", "timezone_required", "error"]
    message: str
    timezone: Optional[str] = None  # Установленная таймзона