from app.repositories.dialog_repository import DialogRepository
import uuid

class DialogService:
    def __init__(self, repo: DialogRepository):
        self.repo = repo

    async def ensure_session(self, user_id: uuid.UUID):
        # For MVP always create new
        return await self.repo.create(user_id)

    async def add_message(self, session_id: uuid.UUID, message: str):
        await self.repo.append_message(session_id, message)
