from tortoise import fields, models
import uuid

class Task(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="tasks", on_delete=fields.CASCADE)
    user_task_id = fields.IntField()  # Стабильный ID задачи в контексте пользователя
    title = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    embedding_bge_small = fields.TextField(null=True)  # pgvector(384) для BGE-small эмбеддингов - реальный тип vector(384) в БД
    scheduled_at = fields.DatetimeField(null=True)
    reminder_at = fields.DatetimeField(null=True)
    
    # Новые поля для MCP интеграции
    priority = fields.CharField(max_length=20, default="medium", description="Приоритет задачи")
    completed = fields.BooleanField(default=False, description="Статус выполнения")
    event_id = fields.UUIDField(null=True, description="ID связанного события")
    
    # Временные метки
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "tasks"
        indexes = [
            models.Index(fields=["user_id"], name="idx_task_user"),
            models.Index(fields=["created_at"], name="idx_task_created"),
            models.Index(fields=["user_id", "user_task_id"], name="idx_user_task_id"),
            models.Index(fields=["completed"], name="idx_task_completed"),
            models.Index(fields=["priority"], name="idx_task_priority"),
            models.Index(fields=["event_id"], name="idx_task_event"),
        ]
        unique_together = (("user_id", "user_task_id"),)
