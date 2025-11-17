from app.models.dialog_session import DialogSession
from typing import Optional
import uuid

class DialogRepository:
    async def get(self, session_id: uuid.UUID) -> Optional[DialogSession]:
        return await DialogSession.filter(id=session_id).first()

    async def create(self, user_id: uuid.UUID) -> DialogSession:
        return await DialogSession.create(user_id=user_id)

    async def append_message(self, session_id: uuid.UUID, message: str) -> None:
        session = await DialogSession.filter(id=session_id).first()
        if not session:
            return
        data = list(session.last_messages)
        data.append(message)
        session.last_messages = data[-20:]  # keep last 20
        await session.save()
