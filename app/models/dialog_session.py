from tortoise import fields, models
import uuid

class DialogSession(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="sessions", on_delete=fields.CASCADE)
    summary = fields.TextField(null=True)
    memory_summary = fields.TextField(null=True)  # JSON память для chat worker
    last_messages = fields.JSONField(default=list)
    updated_at = fields.DatetimeField(auto_now=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "dialog_sessions"
