from app.models.user import User
from typing import Optional

class UserRepository:
    async def get_by_telegram(self, telegram_id: int) -> Optional[User]:
        return await User.filter(telegram_id=telegram_id).first()

    async def create(self, telegram_id: int) -> User:
        return await User.create(telegram_id=telegram_id)
