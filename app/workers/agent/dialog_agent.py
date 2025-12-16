"""
Dialog Agent - понимание естественного языка и формирование ответов
Использует gpt-4.1-mini для сложных языковых задач
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.utils.prompt_manager import get_prompt

settings = get_settings()
logger = logging.getLogger(__name__)


class DialogAgent:
    """
    Dialog Agent (gpt-4.1-mini) - агент для понимания намерений и формирования ответов
    
    Responsibilities:
    1. Понимание намерения пользователя из естественного языка
    2. Определение необходимости уточнения
    3. Формирование человеческих ответов на основе результатов
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        self.prompt_dir = str(Path(__file__).parent / "prompts")
    
    async def understand_intent(self, message_text: str) -> Dict[str, Any]:
        """
        Понимание намерения пользователя из естественного языка
        
        Args:
            message_text: сообщение пользователя
            
        Returns:
            {
                "intent": str,  # create_task, list_tasks, update_task, etc.
                "entities": List[str],  # извлечённые сущности
                "needs_clarification": bool,  # требуется ли уточнение
                "clarification_question": str  # вопрос для уточнения (optional)
            }
        """
        try:
            system_prompt = get_prompt(
                prompt_name="dialog_agent_intent",
                template_dir=self.prompt_dir
            )
            
            logger.debug(f"[DialogAgent {self.user_id}] понимание намерения: {message_text}")
            
            # Используем gpt-4.1-mini для понимания
            response = await self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_text}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"[DialogAgent {self.user_id}] intent: {result.get('intent')}, "
                       f"clarification: {result.get('needs_clarification', False)}")
            
            return result
            
        except Exception as e:
            logger.error(f"[DialogAgent {self.user_id}] ошибка понимания намерения: {e}")
            # Fallback: возвращаем безопасный результат
            return {
                "intent": "unknown",
                "entities": [],
                "needs_clarification": False
            }
    
    async def format_response(
        self, 
        intent: str,
        tool_name: str,
        tool_result: Dict[str, Any]
    ) -> str:
        """
        Формирование человеческого ответа на основе результата выполнения
        
        Args:
            intent: намерение пользователя
            tool_name: название выполненного инструмента
            tool_result: результат выполнения
            
        Returns:
            str: естественный человеческий ответ
        """
        try:
            system_prompt = get_prompt(
                prompt_name="dialog_agent_response",
                template_dir=self.prompt_dir
            )
            
            # Формируем контекст для ответа
            response_input = {
                "intent": intent,
                "tool_name": tool_name,
                "tool_result": tool_result,
                "success": tool_result.get("success", False)
            }
            
            logger.debug(f"[DialogAgent {self.user_id}] формирование ответа для {tool_name}")
            
            response = await self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(response_input, ensure_ascii=False)}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            result = response.choices[0].message.content.strip()
            logger.debug(f"[DialogAgent {self.user_id}] ответ сформирован: {len(result)} символов")
            
            return result
            
        except Exception as e:
            logger.error(f"[DialogAgent {self.user_id}] ошибка формирования ответа: {e}")
            # Fallback на базовый ответ
            if tool_result.get("success"):
                return f"✅ Выполнено: {tool_name}"
            else:
                return f"❌ Ошибка: {tool_result.get('error', 'неизвестная ошибка')}"
    
    async def format_simple_response(self, message: str) -> str:
        """
        Формирование простого ответа без выполнения инструментов (для noop)
        
        Args:
            message: базовое сообщение
            
        Returns:
            str: дружелюбный ответ
        """
        # Для noop можем использовать простые шаблоны или тоже LLM
        # Пока используем простые ответы
        return message
