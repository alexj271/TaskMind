import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI
from app.core.config import settings
from app.schemas.task import ParsedTask
from app.utils.prompt_manager import prompt_manager
from app.services.tools import TOOL_SCHEMAS


class OpenAIService:
    def __init__(self, gpt_model: str = None):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for AI services")
        
        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
            
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = gpt_model or settings.gpt_model_full

    async def chat(self, message: str) -> str:
        """Простой чат с OpenAI используя системный промпт"""
        try:
            # Загружаем системный промпт для чат-ассистента
            system_prompt = prompt_manager.render("chat_assistant")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    async def chat_with_tools(self, message: str, user_id: int, tools: List[Dict[str, Any]] = None) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Чат с AI используя function calling.
        Возвращает tuple: (ответ, вызванная_функция_с_аргументами или None)
        """
        if tools is None:
            tools = TOOL_SCHEMAS
            
        try:
            system_prompt = prompt_manager.render("chat_assistant")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                tools=tools,
                tool_choice="auto",  # Оставляем auto, но с улучшенным промптом
                max_tokens=400,
                temperature=0.3  # Снижаем температуру для более точного следования инструкциям
            )
            
            message_response = response.choices[0].message
            
            # Проверяем был ли вызов функции
            if message_response.tool_calls:
                tool_call = message_response.tool_calls[0]
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Добавляем user_id если его нет в аргументах
                if 'user_id' not in function_args:
                    function_args['user_id'] = user_id
                
                return message_response.content or "", {
                    "function_name": function_name,
                    "arguments": function_args
                }
            
            # Если функция не вызвана, возвращаем только текстовый ответ
            return message_response.content or "", None
            
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    async def parse_task(self, text: str, timezone: str = "Europe/Moscow") -> ParsedTask:
        """
        Парсит естественный язык в структурированную задачу.
        Пример: "завтра встреча с коллегой в 8 утра" -> ParsedTask с title, scheduled_at, etc.
        """
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Загружаем промпт из шаблона
        system_prompt = prompt_manager.render(
            "task_parser",
            current_date=current_date,
            timezone=timezone
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=200,
                temperature=0.1  # Низкая температура для более предсказуемых результатов
            )
            
            content = response.choices[0].message.content.strip()
            
            # Парсим JSON ответ
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: если JSON некорректный, создаем базовую задачу
                return ParsedTask(
                    title=text[:50],
                    description=None,
                    scheduled_at=None,
                    reminder_at=None
                )
            
            # Конвертируем строки в datetime объекты
            scheduled_at = None
            reminder_at = None
            
            if data.get("scheduled_at"):
                try:
                    scheduled_at = datetime.fromisoformat(data["scheduled_at"].replace("Z", "+00:00"))
                except ValueError:
                    pass
                    
            if data.get("reminder_at"):
                try:
                    reminder_at = datetime.fromisoformat(data["reminder_at"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            
            return ParsedTask(
                title=data.get("title", text[:50]),
                description=data.get("description"),
                scheduled_at=scheduled_at,
                reminder_at=reminder_at
            )
            
        except Exception as e:
            # В случае ошибки возвращаем базовую задачу
            return ParsedTask(
                title=text[:50],
                description=f"Ошибка парсинга: {str(e)}",
                scheduled_at=None,
                reminder_at=None
            )


# Глобальный экземпляр сервиса
_openai_service: Optional[OpenAIService] = None


def get_openai_service() -> OpenAIService:
    """Dependency injection для OpenAI сервиса"""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service


# Удобные функции для прямого использования
async def chat(message: str) -> str:
    """Простой чат с AI"""
    service = get_openai_service()
    return await service.chat(message)


async def chat_with_tools(message: str, user_id: int, tools: List[Dict[str, Any]] = None) -> tuple[str, Optional[Dict[str, Any]]]:
    """Чат с AI используя function calling"""
    service = get_openai_service()
    return await service.chat_with_tools(message, user_id, tools)


async def parse_task(text: str, timezone: str = "Europe/Moscow") -> ParsedTask:
    """Парсинг текста задачи через AI"""
    service = get_openai_service()
    return await service.parse_task(text, timezone)