"""
Telegram API модели для TaskMind.
Содержит Pydantic модели для работы с Telegram Bot API.
"""

from pydantic import BaseModel, Field
from typing import Optional


class TelegramUser(BaseModel):
    """Модель пользователя Telegram"""
    id: int
    is_bot: bool = False
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None


class TelegramChat(BaseModel):
    """Модель чата Telegram"""
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TelegramMessage(BaseModel):
    """Модель сообщения Telegram"""
    message_id: int
    from_: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    entities: Optional[list] = None
    # Можно добавить другие поля по необходимости


class TelegramUpdate(BaseModel):
    """Модель обновления от Telegram"""
    update_id: int
    message: Optional[TelegramMessage] = None
    # Можно добавить другие типы обновлений: edited_message, callback_query и т.д.