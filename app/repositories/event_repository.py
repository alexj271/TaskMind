"""
Репозиторий для работы с событиями
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from app.models.event import Event, EventType
from app.models.user import User


class EventRepository:
    """Репозиторий для управления событиями"""

    async def create(
        self,
        title: str,
        creator: Optional[User] = None,
        description: Optional[str] = None,
        event_type: EventType = EventType.GENERAL,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        location: Optional[str] = None,
        participants: Optional[List[str]] = None
    ) -> Event:
        """
        Создать новое событие
        
        Args:
            title: Название события
            creator: Пользователь-создатель
            description: Описание события
            event_type: Тип события
            start_date: Дата начала
            end_date: Дата окончания
            location: Место проведения
            participants: Список участников
            
        Returns:
            Event: Созданное событие
        """
        event = await Event.create(
            title=title,
            creator=creator,
            description=description,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            location=location,
            participants=participants or []
        )
        
        return event

    async def get_by_id(self, event_id: UUID) -> Optional[Event]:
        """
        Получить событие по ID
        
        Args:
            event_id: ID события
            
        Returns:
            Event или None если не найдено
        """
        return await Event.filter(id=event_id).first()

    async def get_by_creator(
        self,
        creator: User,
        event_type: Optional[EventType] = None,
        limit: Optional[int] = None
    ) -> List[Event]:
        """
        Получить события пользователя
        
        Args:
            creator: Создатель событий
            event_type: Фильтр по типу события
            limit: Ограничение количества результатов
            
        Returns:
            List[Event]: Список событий
        """
        query = Event.filter(creator=creator)
        
        if event_type:
            query = query.filter(event_type=event_type)
        
        if limit:
            query = query.limit(limit)
            
        return await query.order_by('-created_at').all()

    async def get_all(
        self,
        event_type: Optional[EventType] = None,
        limit: Optional[int] = None
    ) -> List[Event]:
        """
        Получить все события
        
        Args:
            event_type: Фильтр по типу события
            limit: Ограничение количества результатов
            
        Returns:
            List[Event]: Список событий
        """
        query = Event.all()
        
        if event_type:
            query = query.filter(event_type=event_type)
        
        if limit:
            query = query.limit(limit)
            
        return await query.order_by('-created_at').all()

    async def search(
        self,
        query: str,
        event_type: Optional[EventType] = None,
        creator: Optional[User] = None,
        limit: Optional[int] = None
    ) -> List[Event]:
        """
        Поиск событий по названию или описанию
        
        Args:
            query: Поисковый запрос
            event_type: Фильтр по типу события
            creator: Фильтр по создателю
            limit: Ограничение количества результатов
            
        Returns:
            List[Event]: Найденные события
        """
        db_query = Event.filter(
            title__icontains=query
        ).union(
            Event.filter(description__icontains=query)
        )
        
        if event_type:
            db_query = db_query.filter(event_type=event_type)
        
        if creator:
            db_query = db_query.filter(creator=creator)
        
        if limit:
            db_query = db_query.limit(limit)
            
        return await db_query.order_by('-created_at').all()

    async def get_upcoming_events(
        self,
        creator: Optional[User] = None,
        days_ahead: int = 30,
        limit: Optional[int] = None
    ) -> List[Event]:
        """
        Получить предстоящие события
        
        Args:
            creator: Фильтр по создателю
            days_ahead: Количество дней вперед для поиска
            limit: Ограничение количества результатов
            
        Returns:
            List[Event]: Предстоящие события
        """
        from datetime import timedelta
        
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(days=days_ahead)
        
        query = Event.filter(
            start_date__gte=start_time,
            start_date__lte=end_time
        )
        
        if creator:
            query = query.filter(creator=creator)
        
        if limit:
            query = query.limit(limit)
            
        return await query.order_by('start_date').all()

    async def update(
        self,
        event: Event,
        title: Optional[str] = None,
        description: Optional[str] = None,
        event_type: Optional[EventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        location: Optional[str] = None,
        participants: Optional[List[str]] = None
    ) -> Event:
        """
        Обновить событие
        
        Args:
            event: Событие для обновления
            title: Новое название
            description: Новое описание
            event_type: Новый тип события
            start_date: Новая дата начала
            end_date: Новая дата окончания
            location: Новое место
            participants: Новый список участников
            
        Returns:
            Event: Обновленное событие
        """
        if title is not None:
            event.title = title
        if description is not None:
            event.description = description
        if event_type is not None:
            event.event_type = event_type
        if start_date is not None:
            event.start_date = start_date
        if end_date is not None:
            event.end_date = end_date
        if location is not None:
            event.location = location
        if participants is not None:
            event.participants = participants
            
        await event.save()
        return event

    async def delete(self, event: Event) -> bool:
        """
        Удалить событие
        
        Args:
            event: Событие для удаления
            
        Returns:
            bool: True если удалено успешно
        """
        try:
            await event.delete()
            return True
        except Exception:
            return False

    async def add_participant(self, event: Event, participant: str) -> Event:
        """
        Добавить участника к событию
        
        Args:
            event: Событие
            participant: Имя участника
            
        Returns:
            Event: Обновленное событие
        """
        event.add_participant(participant)
        await event.save()
        return event

    async def remove_participant(self, event: Event, participant: str) -> Event:
        """
        Удалить участника из события
        
        Args:
            event: Событие
            participant: Имя участника
            
        Returns:
            Event: Обновленное событие
        """
        event.remove_participant(participant)
        await event.save()
        return event

    def to_dict(self, event: Event) -> Dict[str, Any]:
        """
        Преобразовать событие в словарь
        
        Args:
            event: Событие для конвертации
            
        Returns:
            Dict[str, Any]: Словарь с данными события
        """
        return {
            "id": str(event.id),
            "title": event.title,
            "description": event.description,
            "event_type": event.event_type.value,
            "start_date": event.start_date.isoformat() if event.start_date else None,
            "end_date": event.end_date.isoformat() if event.end_date else None,
            "location": event.location,
            "participants": event.participant_list,
            "creator_id": event.creator_id,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "updated_at": event.updated_at.isoformat() if event.updated_at else None
        }