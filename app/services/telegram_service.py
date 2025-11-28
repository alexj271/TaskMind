from aiogram import Bot
from app.core.config import get_settings

class TelegramService:
    def __init__(self):
        settings = get_settings()
        self.bot = Bot(token=settings.telegram_token)

    async def send_message(self, chat_id: int, text: str):
        await self.bot.send_message(chat_id=chat_id, text=text)
