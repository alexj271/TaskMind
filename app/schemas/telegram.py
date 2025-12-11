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


class TelegramCallbackQuery(BaseModel):
    """Модель callback query от inline клавиатуры"""
    id: str
    from_: TelegramUser = Field(alias="from")
    message: Optional[TelegramMessage] = None
    inline_message_id: Optional[str] = None
    chat_instance: str
    data: Optional[str] = None
    game_short_name: Optional[str] = None


class TelegramUpdate(BaseModel):
    """Модель обновления от Telegram"""
    update_id: int
    message: Optional[TelegramMessage] = None
    edited_message: Optional[TelegramMessage] = None
    channel_post: Optional[TelegramMessage] = None
    edited_channel_post: Optional[TelegramMessage] = None
    callback_query: Optional[TelegramCallbackQuery] = None
    # Можно добавить другие типы обновлений по необходимости