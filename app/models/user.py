from tortoise import fields, models
import uuid

class User(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    telegram_id = fields.BigIntField(unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    tasks: fields.ReverseRelation["Task"]
    sessions: fields.ReverseRelation["DialogSession"]

    class Meta:
        table = "users"
