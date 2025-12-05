"""
Модели данных для Chat Worker.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class DialogGoal(str, Enum):
    """Цели диалога пользователя"""
    CREATE_TASK = "create_task"
    EDIT_TASK = "edit_task"
    FIND_TASK = "find_task"
    DELETE_TASK = "delete_task"
    SCHEDULE_TASK = "schedule_task"
    SET_REMINDER = "set_reminder"
    GENERAL_CHAT = "general_chat"
    CLARIFICATION = "clarification"


class TaskAction(str, Enum):
    """Действия с задачами"""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"


class MemorySummary(BaseModel):
    """Краткое резюме диалога для долговременной памяти"""
    user_goal: DialogGoal
    context: str  # Краткое описание контекста
    clarifications: List[str] = []  # Что уточнялось
    tasks_actions: List[Dict[str, Any]] = []  # Действия с задачами
    last_updated: datetime
    
    class Config:
        use_enum_values = True


class TaskSearchResult(BaseModel):
    """Результат поиска задач"""
    task_id: str
    title: str
    description: Optional[str]
    similarity_score: float
    created_at: datetime


class ChatRequest(BaseModel):
    """Запрос к Chat Worker"""
    user_id: int
    chat_id: int
    message_text: str
    user_name: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Ответ Chat Worker"""
    response_text: str
    tasks_created: List[Dict[str, Any]] = []
    tasks_updated: List[Dict[str, Any]] = []
    memory_updated: bool = False
    requires_clarification: bool = False
    suggested_actions: List[str] = []