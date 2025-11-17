from fastapi import FastAPI
from app.core.db import init_db
from app.routers import tasks, webhook

app = FastAPI(title="TaskMind")

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.on_event("shutdown")
async def on_shutdown():
    # Tortoise handles connections cleanup automatically via close_connections
    from tortoise import Tortoise
    await Tortoise.close_connections()

app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])

__all__ = ["app"]
