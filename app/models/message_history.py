from tortoise import fields, models
from datetime import datetime


class MessageHistory(models.Model):
    """История сообщений от пользователей"""
    id = fields.IntField(pk=True)
    update_id = fields.IntField(unique=True, description="ID обновления от Telegram")
    user_id = fields.IntField(description="ID пользователя Telegram")
    chat_id = fields.IntField(description="ID чата Telegram")
    message_text = fields.TextField(description="Текст сообщения")
    user_name = fields.CharField(max_length=255, null=True, description="Имя пользователя")
    timestamp = fields.DatetimeField(default=datetime.utcnow, description="Время получения сообщения")
    message_type = fields.CharField(max_length=50, null=True, description="Тип сообщения (task/chat/timezone)")
    ai_response = fields.TextField(null=True, description="Ответ от AI")
    function_called = fields.CharField(max_length=255, null=True, description="Вызванная функция AI")
    summary = fields.TextField(null=True, description="Саммари сообщения")

    class Meta:
        table = "message_history"
        indexes = [
            models.Index(fields=["user_id"], name="idx_message_history_user_id"),
            models.Index(fields=["timestamp"], name="idx_message_history_timestamp"),
        ]

    def __str__(self):
        return f"MessageHistory(id={self.id}, user_id={self.user_id}, text='{self.message_text[:50]}...')"