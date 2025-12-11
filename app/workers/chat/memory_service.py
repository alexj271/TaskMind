"""
Сервис для управления памятью диалогов Chat Worker.
Реализует краткосрочную память (Memory Summary) для эффективной работы с контекстом.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from app.workers.chat.models import MemorySummary, DialogGoal, TaskAction
from app.models.dialog_session import DialogSession
from app.repositories.dialog_repository import DialogRepository
from app.services.openai_tools import OpenAIService
from app.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class DialogMemoryService:
    """Сервис управления памятью диалогов"""
    
    def __init__(self):
        self.dialog_repo = DialogRepository()
        self.openai_service = OpenAIService(gpt_model="gpt-4.1-nano")
        # Указываем путь к промптам chat worker
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        chat_prompts_dir = os.path.join(current_dir, "prompts")
        self.prompt_manager = PromptManager(template_dir=chat_prompts_dir)
    
    async def get_or_create_memory(self, user_id: int, session_id: Optional[str] = None) -> MemorySummary:
        """
        Получает существующую память диалога или создает новую.
        
        Args:
            user_id: ID пользователя
            session_id: ID сессии (если None, используется активная сессия)
        
        Returns:
            MemorySummary: Объект памяти диалога
        """
        try:
            # Ищем активную сессию пользователя
            if not session_id:
                dialog_session = await self.dialog_repo.get_active_session(user_id)
            else:
                dialog_session = await self.dialog_repo.get_session(session_id)
            
            if dialog_session and dialog_session.memory_summary:
                # Парсим существующую память
                import json
                memory_data = json.loads(dialog_session.memory_summary)
                return MemorySummary(**memory_data)
            else:
                # Создаем новую память
                return MemorySummary(
                    user_goal=DialogGoal.GENERAL_CHAT,
                    context="Новый диалог",
                    clarifications=[],
                    tasks_actions=[],
                    last_updated=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Ошибка получения памяти диалога для пользователя {user_id}: {e}")
            # Возвращаем базовую память при ошибке
            return MemorySummary(
                user_goal=DialogGoal.GENERAL_CHAT,
                context="Ошибка загрузки контекста",
                clarifications=[],
                tasks_actions=[],
                last_updated=datetime.utcnow()
            )
    
    async def update_memory(
        self, 
        user_id: int, 
        memory: MemorySummary, 
        session_id: Optional[str] = None
    ) -> bool:
        """
        Обновляет память диалога в базе данных.
        
        Args:
            user_id: ID пользователя
            memory: Объект памяти для сохранения
            session_id: ID сессии
        
        Returns:
            bool: True если обновление прошло успешно
        """
        try:
            memory.last_updated = datetime.utcnow()
            
            # Сериализуем память в JSON
            import json
            memory_json = json.dumps(memory.dict(), default=str)
            
            # Сохраняем в базе данных
            if not session_id:
                session = await self.dialog_repo.get_or_create_active_session(user_id)
                session_id = str(session.id)
            
            await self.dialog_repo.update_memory(session_id, memory_json)
            
            logger.info(f"Память диалога обновлена для пользователя {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления памяти для пользователя {user_id}: {e}")
            return False
    
    def update_goal(self, memory: MemorySummary, new_goal: DialogGoal, context: str = "") -> None:
        """Обновляет цель пользователя в памяти"""
        memory.user_goal = new_goal
        if context:
            memory.context = context
    
    def add_clarification(self, memory: MemorySummary, clarification: str) -> None:
        """Добавляет уточнение в память"""
        memory.clarifications.append(clarification)
        # Ограничиваем количество уточнений
        if len(memory.clarifications) > 10:
            memory.clarifications = memory.clarifications[-10:]
    
    def add_task_action(
        self, 
        memory: MemorySummary, 
        action: TaskAction, 
        task_id: str, 
        task_title: str,
        details: Optional[str] = None
    ) -> None:
        """Добавляет действие с задачей в память"""
        task_action = {
            "action": action.value,
            "task_id": task_id,
            "task_title": task_title,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details
        }
        memory.tasks_actions.append(task_action)
        
        # Ограничиваем количество действий
        if len(memory.tasks_actions) > 20:
            memory.tasks_actions = memory.tasks_actions[-20:]
    
    def get_recent_actions_summary(self, memory: MemorySummary, limit: int = 5) -> str:
        """Возвращает краткое описание последних действий"""
        if not memory.tasks_actions:
            return "Недавних действий нет"
        
        recent = memory.tasks_actions[-limit:]
        actions_text = []
        
        for action in recent:
            action_desc = {
                TaskAction.CREATED.value: "создана",
                TaskAction.UPDATED.value: "обновлена", 
                TaskAction.DELETED.value: "удалена",
                TaskAction.COMPLETED.value: "выполнена",
                TaskAction.SCHEDULED.value: "запланирована"
            }.get(action["action"], action["action"])
            
            actions_text.append(f"• {action['task_title']} - {action_desc}")
        
        return "Недавние действия:\n" + "\n".join(actions_text)
    
    def should_cleanup_memory(self, memory: MemorySummary) -> bool:
        """Определяет нужно ли очистить память (например, если диалог очень старый)"""
        if not memory.last_updated:
            return False
        
        # Очищаем память если она старше 24 часов
        age = datetime.utcnow() - memory.last_updated
        return age > timedelta(hours=24)
    
    def cleanup_memory(self, memory: MemorySummary) -> None:
        """Очищает устаревшие данные из памяти"""
        memory.clarifications = []
        memory.tasks_actions = []
        memory.context = "Диалог продолжен после перерыва"
        memory.user_goal = DialogGoal.GENERAL_CHAT
        memory.last_updated = datetime.utcnow()
    
    async def update_summary_with_ai(self, current_summary: str, new_message: str, user_name: str = "") -> str:
        """
        Обновляет резюме диалога с помощью ИИ.
        
        Args:
            current_summary: Текущее резюме диалога
            new_message: Новое сообщение пользователя
            user_name: Имя пользователя (опционально)
            
        Returns:
            str: Обновленное резюме диалога
        """
        try:
            user_prefix = f"{user_name}: " if user_name else "Пользователь: "
            
            # Загружаем промпт из файла
            prompt = self.prompt_manager.render(
                "dialog_summarizer",
                current_summary=current_summary,
                user_prefix=user_prefix,
                new_message=new_message
            )
            
            response = await self.openai_service.client.chat.completions.create(
                model=self.openai_service.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3  # Низкая температура для консистентности
            )
            
            updated_summary = response.choices[0].message.content.strip()
            
            logger.info(f"Резюме диалога обновлено с помощью ИИ")
            return updated_summary
            
        except Exception as e:
            logger.error(f"Ошибка обновления резюме с помощью ИИ: {e}")
            # Возвращаем базовое обновление при ошибке
            return self._fallback_summary_update(current_summary, new_message, user_name)
    
    def _fallback_summary_update(self, current_summary: str, new_message: str, user_name: str = "") -> str:
        """
        Резервный метод обновления резюме без ИИ.
        """
        timestamp = datetime.utcnow().strftime("%H:%M")
        user_prefix = f"{user_name} " if user_name else "Пользователь "
        
        # Простое добавление нового сообщения к резюме
        if "АКТУАЛЬНОЕ СОСТОЯНИЕ:" in current_summary:
            lines = current_summary.split("\n")
            # Находим секцию АКТУАЛЬНОЕ СОСТОЯНИЕ и добавляем туда новое сообщение
            for i, line in enumerate(lines):
                if line.startswith("АКТУАЛЬНОЕ СОСТОЯНИЕ:"):
                    lines.insert(i + 1, f"[{timestamp}] {user_prefix}написал: {new_message[:100]}...")
                    break
            return "\n".join(lines)
        else:
            # Если формат не распознан, создаем базовое резюме
            return f"""ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:
Управление задачами через диалог

АКТУАЛЬНЫЕ ДАННЫЕ:
Последнее сообщение: {new_message[:150]}...

СДЕЛАННЫЕ ШАГИ:
Начат диалог

АКТУАЛЬНОЕ СОСТОЯНИЕ:
В процессе обсуждения: {new_message[:100]}..."""
    
    async def update_context_with_ai_summary(
        self, 
        memory: MemorySummary, 
        new_message: str, 
        user_name: str = ""
    ) -> None:
        """
        Обновляет контекст памяти с помощью ИИ-резюмирования.
        
        Args:
            memory: Объект памяти диалога
            new_message: Новое сообщение пользователя  
            user_name: Имя пользователя
        """
        try:
            # Получаем текущий контекст или создаем базовый
            current_summary = memory.context if memory.context and memory.context != "Новый диалог" else """ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:
нет данных

АКТУАЛЬНЫЕ ДАННЫЕ:
нет данных

СДЕЛАННЫЕ ШАГИ:
нет данных

АКТУАЛЬНОЕ СОСТОЯНИЕ:
начало диалога
"""
            
            # Обновляем резюме с помощью ИИ
            updated_summary = await self.update_summary_with_ai(
                current_summary, 
                new_message, 
                user_name
            )
            
            # Сохраняем обновленное резюме в контекст
            memory.context = updated_summary
            memory.last_updated = datetime.utcnow()
            
            logger.debug(f"Контекст памяти обновлен с помощью ИИ-резюмирования")
            
        except Exception as e:
            logger.error(f"Ошибка обновления контекста с ИИ: {e}")
            # При ошибке добавляем сообщение простым способом
            if memory.context:
                memory.context += f"\n[{datetime.utcnow().strftime('%H:%M')}] Новое сообщение: {new_message[:100]}..."
            else:
                memory.context = f"Диалог начат. Последнее сообщение: {new_message[:100]}..."
    
    def get_summary_for_prompt(self, memory: MemorySummary) -> str:
        """
        Возвращает резюме диалога в удобном для промпта формате.
        
        Returns:
            str: Отформатированное резюме для использования в промптах ИИ
        """
        if not memory.context or memory.context in ["Новый диалог", "Ошибка загрузки контекста"]:
            return "Новый диалог, контекст отсутствует"
        
        # Если контекст уже в формате резюме, возвращаем как есть
        if "ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:" in memory.context:
            return memory.context
        
        # Иначе создаем краткое резюме из доступных данных
        goal_text = {
            DialogGoal.CREATE_TASK: "создание новой задачи",
            DialogGoal.EDIT_TASK: "редактирование задачи",
            DialogGoal.FIND_TASK: "поиск задач", 
            DialogGoal.DELETE_TASK: "удаление задачи",
            DialogGoal.SCHEDULE_TASK: "планирование задачи",
            DialogGoal.SET_REMINDER: "настройка напоминания",
            DialogGoal.GENERAL_CHAT: "общее общение",
            DialogGoal.CLARIFICATION: "уточнение деталей"
        }.get(memory.user_goal, "неопределенная цель")
        
        recent_actions = self.get_recent_actions_summary(memory, limit=3)
        
        return f"""Цель: {goal_text}
Контекст: {memory.context[:200]}...
{recent_actions}"""