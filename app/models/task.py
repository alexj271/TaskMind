from tortoise import fields, models
import uuid

class Task(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="tasks", on_delete=fields.CASCADE)
    title = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    embedding_bge_small = fields.TextField(null=True)  # pgvector(384) для BGE-small эмбеддингов - реальный тип vector(384) в БД
    scheduled_at = fields.DatetimeField(null=True)
    reminder_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "tasks"
        indexes = [
            models.Index(fields=["user_id"], name="idx_task_user"),
            models.Index(fields=["created_at"], name="idx_task_created"),
        ]
