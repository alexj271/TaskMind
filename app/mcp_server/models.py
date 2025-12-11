"""
Модели для MCP сервера TaskMind
Расширения существующих моделей для поддержки событий
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum

class EventType(str, Enum):
    """Типы событий"""
    TRIP = "trip"              # Поездки и путешествия
    MEETING = "meeting"        # Встречи и собрания
    PROJECT = "project"        # Проекты
    PERSONAL = "personal"      # Личные события
    WORK = "work"             # Рабочие события
    HEALTH = "health"         # Здоровье и спорт
    EDUCATION = "education"   # Обучение и образование
    GENERAL = "general"       # Общие события

class MCPEventModel(BaseModel):
    """Модель события для MCP"""
    id: Optional[str] = None
    title: str = Field(..., description="Название события")
    description: Optional[str] = Field(None, description="Описание события")
    event_type: EventType = Field(EventType.GENERAL, description="Тип события")
    start_date: Optional[datetime] = Field(None, description="Дата начала события")
    end_date: Optional[datetime] = Field(None, description="Дата окончания события")
    location: Optional[str] = Field(None, description="Место проведения")
    participants: List[str] = Field(default_factory=list, description="Список участников")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class MCPTaskRequest(BaseModel):
    """Запрос на создание задачи через MCP"""
    user_id: int
    title: str
    description: Optional[str] = None
    scheduled_at: Optional[str] = None  # ISO строка
    reminder_at: Optional[str] = None   # ISO строка
    priority: Optional[str] = "medium"
    event_id: Optional[str] = None

class MCPEventRequest(BaseModel):
    """Запрос на создание события через MCP"""
    title: str
    description: Optional[str] = None
    event_type: EventType = EventType.GENERAL
    start_date: Optional[str] = None  # ISO строка
    end_date: Optional[str] = None    # ISO строка
    location: Optional[str] = None
    participants: Optional[List[str]] = None

class MCPResponse(BaseModel):
    """Базовый ответ MCP"""
    success: bool
    error: Optional[str] = None

class MCPTaskResponse(MCPResponse):
    """Ответ с информацией о задаче"""
    task_id: Optional[str] = None
    user_task_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    linked_event: Optional[dict] = None

class MCPEventResponse(MCPResponse):
    """Ответ с информацией о событии"""
    event_id: Optional[str] = None
    title: Optional[str] = None
    event_type: Optional[EventType] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    participants: Optional[List[str]] = None
    created_at: Optional[str] = None

class MCPListResponse(MCPResponse):
    """Ответ со списком объектов"""
    items: List[dict] = Field(default_factory=list)
    total: int = 0
    query: Optional[str] = None