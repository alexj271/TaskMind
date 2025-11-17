from app.schemas.task import ParsedTask
from app.services.openai_tools import parse_task as openai_parse_task

class AIParseService:
    async def parse_task(self, text: str) -> ParsedTask:
        # Используем OpenAI для парсинга
        try:
            return await openai_parse_task(text)
        except Exception:
            # Fallback: простой парсинг без AI
            return ParsedTask(title=text[:50], description=None)
