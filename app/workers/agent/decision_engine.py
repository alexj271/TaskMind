"""
Decision Engine - выбор действия на основе намерения и состояния
Использует gpt-4.1-nano для быстрых решений
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.utils.prompt_manager import get_prompt

settings = get_settings()
logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Decision Engine (gpt-4.1-nano) - принятие решений о выборе действия
    
    Responsibilities:
    1. Анализ намерения пользователя и текущего состояния
    2. Выбор оптимального действия (tool_call или noop)
    3. Формирование параметров для вызова инструмента
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        self.prompt_dir = str(Path(__file__).parent / "prompts")
    
    async def choose_action(
        self,
        intent_payload: Dict[str, Any],
        state_context: Dict[str, Any],
        available_tools: List[str]
    ) -> Dict[str, Any]:
        """
        Выбор действия на основе намерения и состояния
        
        Args:
            intent_payload: результат от DialogAgent.understand_intent()
                {
                    "intent": str,
                    "entities": List[str],
                    ...
                }
            state_context: релевантный контекст из StateManager.get_relevant_context()
                {
                    "current_context": {...},
                    "relevant_tasks": [...],
                    "recent_actions": [...],
                    "dialog_summary": str
                }
            available_tools: список доступных MCP инструментов
            
        Returns:
            {
                "action_type": "tool_call" | "noop",
                "tool_name": str (if tool_call),
                "tool_arguments": dict (if tool_call),
                "message": str (if noop)
            }
        """
        try:
            system_prompt = get_prompt(
                prompt_name="decision_engine",
                template_dir=self.prompt_dir
            )
            
            # Формируем входные данные для Decision Engine
            decision_input = {
                "intent": intent_payload.get("intent"),
                "entities": intent_payload.get("entities", []),
                "current_state": {
                    "current_context": state_context.get("current_context"),
                    "relevant_tasks": state_context.get("relevant_tasks", []),
                    "recent_actions": state_context.get("recent_actions", [])[:3],  # Последние 3
                    "dialog_summary": state_context.get("dialog_summary")
                },
                "available_tools": available_tools
            }
            
            logger.debug(f"[DecisionEngine {self.user_id}] анализ: intent={intent_payload.get('intent')}, "
                        f"tools={len(available_tools)}")
            
            # Используем gpt-4.1-nano для быстрого принятия решения
            response = await self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(decision_input, ensure_ascii=False)}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Низкая температура для детерминированности
                max_tokens=400
            )
            
            result = json.loads(response.choices[0].message.content)
            
            logger.info(f"[DecisionEngine {self.user_id}] решение: action_type={result.get('action_type')}, "
                       f"tool={result.get('tool_name', 'N/A')}")
            
            return result
            
        except Exception as e:
            logger.error(f"[DecisionEngine {self.user_id}] ошибка принятия решения: {e}")
            # Fallback: безопасный noop
            return {
                "action_type": "noop",
                "message": "Не удалось определить действие."
            }
    
    def _validate_decision(self, decision: Dict[str, Any], available_tools: List[str]) -> bool:
        """
        Валидация решения Decision Engine
        
        Args:
            decision: решение от choose_action
            available_tools: список доступных инструментов
            
        Returns:
            bool: валидно ли решение
        """
        action_type = decision.get("action_type")
        
        if action_type == "tool_call":
            tool_name = decision.get("tool_name")
            tool_arguments = decision.get("tool_arguments")
            
            # Проверяем, что tool существует
            if tool_name not in available_tools:
                logger.warning(f"[DecisionEngine {self.user_id}] недоступный инструмент: {tool_name}")
                return False
            
            # Проверяем наличие аргументов
            if tool_arguments is None:
                logger.warning(f"[DecisionEngine {self.user_id}] отсутствуют аргументы для {tool_name}")
                return False
            
            return True
        
        elif action_type == "noop":
            # noop всегда валиден
            return True
        
        else:
            logger.warning(f"[DecisionEngine {self.user_id}] неизвестный action_type: {action_type}")
            return False
    
    async def choose_action_with_validation(
        self,
        intent_payload: Dict[str, Any],
        state_context: Dict[str, Any],
        available_tools: List[str]
    ) -> Dict[str, Any]:
        """
        Выбор действия с валидацией результата
        
        Wrapper вокруг choose_action с дополнительной валидацией
        """
        decision = await self.choose_action(intent_payload, state_context, available_tools)
        
        # Валидируем решение
        if not self._validate_decision(decision, available_tools):
            logger.warning(f"[DecisionEngine {self.user_id}] невалидное решение, fallback на noop")
            return {
                "action_type": "noop",
                "message": "Не удалось определить корректное действие."
            }
        
        return decision
