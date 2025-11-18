from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.db import init_db
from app.routers import tasks, webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown 
    from tortoise import Tortoise
    await Tortoise.close_connections()


app = FastAPI(
    title="TaskMind API",
    description="Высокопроизводительный асинхронный API для управления задачами через Telegram Bot",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])

__all__ = ["app"]
