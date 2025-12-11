"""
Утилиты для MCP сервера TaskMind
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from app.repositories.user_repository import UserRepository

class EventStorage:
    """Временное хранилище событий (до добавления в БД)"""
    
    def __init__(self):
        self.events = {}
    
    def create_event(self, event_data: dict) -> str:
        """Создать событие"""
        event_id = str(uuid4())
        event_data['id'] = event_id
        event_data['created_at'] = datetime.utcnow().isoformat()
        event_data['updated_at'] = datetime.utcnow().isoformat()
        
        self.events[event_id] = event_data
        return event_id
    
    def get_event(self, event_id: str) -> Optional[dict]:
        """Получить событие по ID"""
        return self.events.get(event_id)
    
    def get_all_events(self) -> list:
        """Получить все события"""
        return list(self.events.values())
    
    def get_events_by_type(self, event_type: str) -> list:
        """Получить события по типу"""
        return [event for event in self.events.values() 
                if event.get('event_type') == event_type]
    
    def search_events(self, query: str) -> list:
        """Поиск событий по названию или описанию"""
        query_lower = query.lower()
        results = []
        
        for event in self.events.values():
            title = event.get('title', '').lower()
            description = event.get('description', '').lower()
            
            if query_lower in title or query_lower in description:
                results.append(event)
        
        return results

class MCPUtils:
    """Утилиты для MCP сервера"""
    
    @staticmethod
    async def get_or_create_user(user_id: int):
        """Получить или создать пользователя"""
        user_repo = UserRepository()
        user = await user_repo.get_by_telegram(user_id)
        
        if not user:
            user = await user_repo.create(
                telegram_user_id=user_id,
                username=f"user_{user_id}",
                first_name="Unknown",
                last_name=None
            )
        
        return user
    
    @staticmethod
    def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
        """Парсинг строки даты в datetime"""
        if not date_str:
            return None
        
        try:
            # Попробуем стандартный ISO формат
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Попробуем другие форматы
                for fmt in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d",
                    "%d.%m.%Y %H:%M",
                    "%d.%m.%Y"
                ]:
                    return datetime.strptime(date_str, fmt)
            except ValueError:
                logging.warning(f"Не удалось распарсить дату: {date_str}")
                return None

# Глобальное хранилище событий
event_storage = EventStorage()