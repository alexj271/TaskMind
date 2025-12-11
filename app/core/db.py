from tortoise import Tortoise
from app.core.config import get_settings

# Получаем настройки
settings = get_settings()

TORTOISE_ORM = {
    "connections": {"default": settings.postgres_dsn},
    "apps": {
        "models": {
            "models": [
                "app.models.user",
                "app.models.task",
                "app.models.dialog_session",
                "app.models.city",
                "app.models.event",
                "app.models.message_history",
                "aerich.models",
            ],
            "default_connection": "default",
        }
    },
}

async def init_db() -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    # Generate schemas only in dev (migrations handle prod)
    # await Tortoise.generate_schemas()
