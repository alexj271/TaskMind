from app.models.dialog_session import DialogSession
from typing import Optional
import uuid
from datetime import datetime
from app.utils.summarizer import generate_dialogue_summary

class DialogRepository:
    async def get(self, session_id: uuid.UUID) -> Optional[DialogSession]:
        return await DialogSession.filter(id=session_id).first()

    async def create(self, user_id: uuid.UUID) -> DialogSession:
        return await DialogSession.create(user_id=user_id)

    async def get_or_create_for_user(self, user) -> DialogSession:
        session = await DialogSession.filter(user=user).first()
        if not session:
            session = await DialogSession.create(user=user)
        return session

    async def get_active_session(self, user_id: int) -> Optional[DialogSession]:
        """Получает активную сессию по telegram user_id"""
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        user = await user_repo.get_by_telegram(user_id)
        if not user:
            return None
        return await DialogSession.filter(user=user).first()

    async def get_session(self, session_id: uuid.UUID) -> Optional[DialogSession]:
        """Получает сессию по ID"""
        return await self.get(session_id)

    async def get_or_create_active_session(self, user_id: int) -> DialogSession:
        """Получает или создает активную сессию по telegram user_id"""
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        user = await user_repo.get_by_telegram(user_id)
        if not user:
            raise ValueError(f"User with telegram_id {user_id} not found")
        return await self.get_or_create_for_user(user)

    async def update_memory(self, session_id: str, memory_json: str) -> None:
        """Обновляет память диалога в сессии"""
        session_uuid = uuid.UUID(session_id)
        session = await self.get(session_uuid)
        if session:
            session.memory_summary = memory_json
            await session.save()

    async def add_message_to_session(self, session: DialogSession, message: str, role: str = "user") -> None:
        """Добавляет сообщение в сессию с ролью (user/assistant)"""
        data = list(session.last_messages)
        data.append({"role": role, "content": message, "timestamp": str(datetime.utcnow())})
        session.last_messages = data[-20:]  # keep last 20
        await session.save()

    async def update_summary(self, session: DialogSession, summary: str) -> None:
        session.summary = summary
        await session.save()

    async def update_dialog_summary(self, session: DialogSession) -> None:
        """
        Обновляет summary диалога по схеме:
        - Берем последнее summary и сообщения
        - Отправляем их в ИИ для генерации нового summary
        - Обновляем summary в сессии
        - Оставляем только последние 2 сообщения в last_messages
        """
        # Собираем контекст для ИИ: только последние сообщения (без previous summary)
        context_messages = []
        
        # Добавляем последние сообщения
        for msg in session.last_messages[-10:]:  # берем последние 10 для контекста
            if isinstance(msg, dict) and 'content' in msg:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                context_messages.append(f"{role}: {content}")
        
        # Генерируем новое summary через ИИ
        new_summary = await generate_dialogue_summary(context_messages, session.summary or "")
        
        # Обновляем summary
        session.summary = new_summary
        
        # Оставляем только последние 2 сообщения
        session.last_messages = session.last_messages[-2:] if len(session.last_messages) > 2 else session.last_messages
        
        await session.save()
