from app.models.user import User
from typing import Optional

class UserRepository:
    async def get_by_telegram(self, telegram_id: int) -> Optional[User]:
        return await User.filter(telegram_id=telegram_id).first()

    async def create(self, telegram_id: int, chat_id: Optional[int] = None, username: Optional[str] = None) -> User:
        return await User.create(telegram_id=telegram_id, chat_id=chat_id, username=username)

    async def update_by_telegram(self, telegram_id: int, **updates) -> Optional[User]:
        updated_count = await User.filter(telegram_id=telegram_id).update(**updates)
        if updated_count > 0:
            return await User.filter(telegram_id=telegram_id).first()
        return None
