from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from app.workers.telegram_actors import process_webhook_message


logger = logging.getLogger(__name__)
router = APIRouter()


# Telegram Update модели
class TelegramUser(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None


class TelegramChat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TelegramMessage(BaseModel):
    message_id: int
    from_: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    # Можно добавить другие поля по необходимости


class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None
    # Можно добавить другие типы обновлений: edited_message, callback_query и т.д.


@router.post("/telegram", 
    summary="Telegram Webhook",
    description="Обработчик webhook-ов от Telegram Bot API. Принимает обновления и отправляет в очередь на обработку.",
    response_description="Статус обработки обновления"
)
async def telegram_webhook(update: TelegramUpdate):
    """
    Обработчик webhook от Telegram.
    Валидирует структуру update и отправляет в очередь на обработку.
    """
    try:
        logger.info(f"Получено обновление от Telegram: update_id={update.update_id}")
        
        if update.message:
            logger.info(f"Сообщение от пользователя {update.message.from_.id if update.message.from_ else 'неизвестен'}: {update.message.text or 'без текста'}")
            
            # Отправляем сообщение в Gatekeeper для классификации и обработки
            process_webhook_message.send(
                update_id=update.update_id,
                message_data=update.message.model_dump()
            )
            logger.info(f"Сообщение отправлено в очередь Dramatiq для обработки")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        return {"status": "error", "message": str(e)}
