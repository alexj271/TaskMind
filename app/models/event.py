from tortoise import fields, models
from typing import List, Optional
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


class Event(models.Model):
    """
    Модель события для планирования и организации
    """
    id = fields.UUIDField(pk=True)
    title = fields.CharField(max_length=200, description="Название события")
    description = fields.TextField(null=True, description="Описание события")
    event_type = fields.CharEnumField(EventType, default=EventType.GENERAL, description="Тип события")
    
    # Временные метки
    start_date = fields.DatetimeField(null=True, description="Дата и время начала")
    end_date = fields.DatetimeField(null=True, description="Дата и время окончания")
    
    # Локация
    location = fields.CharField(max_length=500, null=True, description="Место проведения")
    
    # Участники (JSON поле со списком имен или ID)
    participants = fields.JSONField(default=list, description="Список участников")
    
    # Системные поля
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    
    # Связь с пользователем-создателем
    creator = fields.ForeignKeyField("models.User", related_name="created_events", null=True)
    
    class Meta:
        table = "events"
        indexes = [
            models.Index(fields=["title"], name="idx_event_title"),
            models.Index(fields=["event_type"], name="idx_event_type"),
            models.Index(fields=["start_date"], name="idx_event_start_date"),
            models.Index(fields=["creator"], name="idx_event_creator"),
        ]
    
    def __str__(self):
        return f"Event: {self.title} ({self.event_type})"
    
    @property 
    def participant_list(self) -> List[str]:
        """Возвращает список участников"""
        if isinstance(self.participants, list):
            return self.participants
        return []
    
    @participant_list.setter
    def participant_list(self, participants: List[str]):
        """Устанавливает список участников"""
        self.participants = participants if participants else []
    
    def add_participant(self, participant: str):
        """Добавляет участника"""
        participants = self.participant_list
        if participant not in participants:
            participants.append(participant)
            self.participants = participants
    
    def remove_participant(self, participant: str):
        """Удаляет участника"""
        participants = self.participant_list
        if participant in participants:
            participants.remove(participant)
            self.participants = participants