from email.mime import message
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import redis.asyncio as aioredis
import logging

from app.workers.gatekeeper.tasks import process_webhook_message
from app.schemas.telegram import TelegramUpdate
from app.core.config import get_settings


logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
r = aioredis.from_url(settings.redis_url)


# Telegram Update модели теперь импортируются из app.schemas.telegram


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
            
            user_id = update.message.from_.id if update.message.from_ else None
            if user_id is None:
                raise HTTPException(status_code=400, detail="Отсутствует ID пользователя в сообщении")
            
            stream = f"agent:{user_id}:stream"
            await r.xadd(stream, {"msg": update.message.text or ""})

            # # Отправляем сообщение в Gatekeeper для классификации и обработки
            # process_webhook_message.send(
            #     update_id=update.update_id,
            #     message_data=update.message.model_dump()
            # )
            # logger.info(f"Сообщение отправлено в очередь Dramatiq для обработки")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        return {"status": "error", "message": str(e)}
