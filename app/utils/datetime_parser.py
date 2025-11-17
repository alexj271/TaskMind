from datetime import datetime
from zoneinfo import ZoneInfo
from app.core.config import settings

# TODO: replace with robust NLP date parsing (e.g. dateparser with tz)

async def extract_datetime(text: str) -> datetime | None:
    # Placeholder: always None
    return None

async def now_utc() -> datetime:
    return datetime.now(tz=ZoneInfo(settings.timezone))
