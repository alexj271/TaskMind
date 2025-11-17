from fastapi import APIRouter

router = APIRouter()

@router.post("/telegram")
async def telegram_webhook():
    # TODO: validate & dispatch to dramatiq actor
    return {"status": "queued"}
