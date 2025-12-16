"""
StateManager - управление состоянием агента с оптимизацией и синхронизацией с Redis
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import redis.asyncio as aioredis
from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Константы для оптимизации
MAX_RECENT_ACTIONS = 10
MAX_DIALOG_HISTORY = 50
MAX_DIALOG_TOKENS = 2000  # Примерная оценка
MAX_CURRENT_TASKS = 20
MAX_CONTEXT_TASKS = 5  # Для relevance pruning


class StateManager:
    """
    Управляет состоянием агента для конкретного пользователя.
    Синхронизируется с Redis и оптимизирует state перед каждым использованием.
    """
    
    def __init__(self, user_id: int, redis_client: aioredis.Redis):
        self.user_id = user_id
        self.redis = redis_client
        self.redis_key = f"agent:state:{user_id}"
        
        # Инициализируем пустой state
        self.state: Dict[str, Any] = {
            "user_id": user_id,
            "current_context": {
                "active_intent": None,
                "mentioned_entities": [],
                "last_interaction": None
            },
            "current_tasks": [],
            "recent_actions": [],
            "dialog_history": [],
            "dialog_summary": None,
            "long_term_context": {},
            "archived_topics": [],
            "metadata": {
                "last_updated": None,
                "total_interactions": 0,
                "optimization_count": 0
            }
        }
        
    async def load_from_redis(self) -> bool:
        """Загружает state из Redis"""
        try:
            data = await self.redis.get(self.redis_key)
            if data:
                self.state = json.loads(data)
                logger.info(f"[StateManager {self.user_id}] загружен state из Redis")
                return True
            else:
                logger.info(f"[StateManager {self.user_id}] state не найден в Redis, используется новый")
                return False
        except Exception as e:
            logger.error(f"[StateManager {self.user_id}] ошибка загрузки из Redis: {e}")
            return False
    
    async def sync_to_redis(self, ttl: int = 86400) -> bool:
        """
        Синхронизирует state с Redis.
        
        Args:
            ttl: время жизни в секундах (по умолчанию 24 часа)
        """
        try:
            self.state["metadata"]["last_updated"] = datetime.now().isoformat()
            data = json.dumps(self.state, ensure_ascii=False, default=str)
            await self.redis.setex(self.redis_key, ttl, data)
            logger.debug(f"[StateManager {self.user_id}] синхронизирован с Redis")
            return True
        except Exception as e:
            logger.error(f"[StateManager {self.user_id}] ошибка синхронизации с Redis: {e}")
            return False
    
    # === Методы обновления полей ===
    
    def update_current_context(self, intent: Optional[str] = None, 
                              entities: Optional[List[str]] = None) -> None:
        """Обновляет текущий контекст взаимодействия"""
        if intent is not None:
            self.state["current_context"]["active_intent"] = intent
        
        if entities is not None:
            # Объединяем с существующими, удаляем дубликаты
            current = set(self.state["current_context"]["mentioned_entities"])
            current.update(entities)
            self.state["current_context"]["mentioned_entities"] = list(current)[-10:]  # Последние 10
        
        self.state["current_context"]["last_interaction"] = datetime.now().isoformat()
    
    def add_task(self, task_id: str, status: str = "active", **kwargs) -> None:
        """Добавляет задачу в current_tasks"""
        task = {
            "task_id": task_id,
            "status": status,
            "added_at": datetime.now().isoformat(),
            **kwargs
        }
        
        # Проверяем, нет ли уже такой задачи
        existing_ids = {t["task_id"] for t in self.state["current_tasks"]}
        if task_id not in existing_ids:
            self.state["current_tasks"].append(task)
    
    def update_task_status(self, task_id: str, new_status: str) -> bool:
        """Обновляет статус задачи"""
        for task in self.state["current_tasks"]:
            if task["task_id"] == task_id:
                task["status"] = new_status
                task["updated_at"] = datetime.now().isoformat()
                return True
        return False
    
    def remove_task(self, task_id: str) -> bool:
        """Удаляет задачу из state"""
        original_len = len(self.state["current_tasks"])
        self.state["current_tasks"] = [
            t for t in self.state["current_tasks"] 
            if t["task_id"] != task_id
        ]
        return len(self.state["current_tasks"]) < original_len
    
    def add_action(self, action_type: str, description: str, **kwargs) -> None:
        """Добавляет действие в recent_actions"""
        action = {
            "type": action_type,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.state["recent_actions"].append(action)
        
        # Ограничиваем размер
        if len(self.state["recent_actions"]) > MAX_RECENT_ACTIONS:
            self.state["recent_actions"] = self.state["recent_actions"][-MAX_RECENT_ACTIONS:]
    
    def add_dialog_message(self, role: str, content: str) -> None:
        """Добавляет сообщение в историю диалога"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self.state["dialog_history"].append(message)
        
        # Ограничиваем размер
        if len(self.state["dialog_history"]) > MAX_DIALOG_HISTORY:
            self.state["dialog_history"] = self.state["dialog_history"][-MAX_DIALOG_HISTORY:]
    
    def update_dialog_summary(self, summary: str) -> None:
        """Обновляет краткое содержание диалога"""
        self.state["dialog_summary"] = summary
        self.state["metadata"]["last_summary_update"] = datetime.now().isoformat()
    
    def add_archived_topic(self, topic: str) -> None:
        """Добавляет тему в архив"""
        if topic not in self.state["archived_topics"]:
            self.state["archived_topics"].append(topic)
            # Ограничиваем до 20 тем
            if len(self.state["archived_topics"]) > 20:
                self.state["archived_topics"] = self.state["archived_topics"][-20:]
    
    def update_long_term_context(self, key: str, value: Any) -> None:
        """Обновляет долгосрочный контекст"""
        self.state["long_term_context"][key] = value
    
    # === Оптимизация state ===
    
    async def optimize_state(self, force_semantic: bool = False) -> Dict[str, int]:
        """
        Оптимизирует state в несколько этапов.
        
        Args:
            force_semantic: принудительно запустить семантическую компрессию
            
        Returns:
            Статистика оптимизации
        """
        stats = {
            "tasks_removed": 0,
            "actions_trimmed": 0,
            "dialog_compressed": 0,
            "semantic_compression": 0
        }
        
        # 1. Structural Optimization (всегда)
        stats.update(self._structural_optimization())
        
        # 2. Semantic Compression (по необходимости или по запросу)
        if force_semantic or self._needs_semantic_compression():
            compression_stats = await self._semantic_compression()
            stats.update(compression_stats)
        
        # Обновляем метаданные
        self.state["metadata"]["optimization_count"] += 1
        self.state["metadata"]["last_optimization"] = datetime.now().isoformat()
        
        logger.info(f"[StateManager {self.user_id}] оптимизация завершена: {stats}")
        return stats
    
    def _structural_optimization(self) -> Dict[str, int]:
        """
        Структурная оптимизация (без LLM):
        - Удаление закрытых задач
        - Ограничение recent_actions
        - Нормализация дат и статусов
        """
        stats = {
            "tasks_removed": 0,
            "actions_trimmed": 0
        }
        
        # 1. Удаляем закрытые задачи (completed, cancelled)
        original_task_count = len(self.state["current_tasks"])
        self.state["current_tasks"] = [
            task for task in self.state["current_tasks"]
            if task.get("status") not in ["completed", "cancelled", "deleted"]
        ]
        stats["tasks_removed"] = original_task_count - len(self.state["current_tasks"])
        
        # 2. Ограничиваем current_tasks по количеству
        if len(self.state["current_tasks"]) > MAX_CURRENT_TASKS:
            # Сортируем по дате обновления (новые первыми)
            self.state["current_tasks"].sort(
                key=lambda t: t.get("updated_at", t.get("added_at", "")),
                reverse=True
            )
            removed = len(self.state["current_tasks"]) - MAX_CURRENT_TASKS
            self.state["current_tasks"] = self.state["current_tasks"][:MAX_CURRENT_TASKS]
            stats["tasks_removed"] += removed
        
        # 3. Ограничиваем recent_actions (оставляем самые свежие)
        if len(self.state["recent_actions"]) > MAX_RECENT_ACTIONS:
            trimmed = len(self.state["recent_actions"]) - MAX_RECENT_ACTIONS
            self.state["recent_actions"] = self.state["recent_actions"][-MAX_RECENT_ACTIONS:]
            stats["actions_trimmed"] = trimmed
        
        # 4. Нормализуем даты (убираем микросекунды, приводим к ISO формату)
        self._normalize_timestamps()
        
        return stats
    
    def _normalize_timestamps(self) -> None:
        """Нормализует все timestamp'ы в state"""
        def normalize_ts(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ["timestamp", "added_at", "updated_at", "last_interaction"]:
                        if isinstance(value, str):
                            try:
                                dt = datetime.fromisoformat(value)
                                obj[key] = dt.replace(microsecond=0).isoformat()
                            except:
                                pass
                    elif isinstance(value, (dict, list)):
                        normalize_ts(value)
            elif isinstance(obj, list):
                for item in obj:
                    normalize_ts(item)
        
        normalize_ts(self.state)
    
    def _needs_semantic_compression(self) -> bool:
        """Проверяет, нужна ли семантическая компрессия"""
        # Проверяем длину dialog_history
        if len(self.state["dialog_history"]) > 30:
            return True
        
        # Проверяем примерное количество токенов
        total_chars = sum(
            len(msg.get("content", "")) 
            for msg in self.state["dialog_history"]
        )
        estimated_tokens = total_chars / 4  # Грубая оценка
        
        if estimated_tokens > MAX_DIALOG_TOKENS:
            return True
        
        return False
    
    async def _semantic_compression(self) -> Dict[str, int]:
        """
        Семантическая компрессия с помощью LLM:
        - Сжимает историю диалога в summary
        - Извлекает долгосрочный контекст
        """
        stats = {
            "semantic_compression": 0,
            "dialog_compressed": 0
        }
        
        if not self.state["dialog_history"]:
            return stats
        
        try:
            client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
            
            # Формируем запрос для компрессии
            dialog_text = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in self.state["dialog_history"]
            ])
            
            prompt = f"""Проанализируй историю диалога и создай краткое резюме.

История диалога:
{dialog_text}

Создай JSON с полями:
- summary: краткое описание основных тем и действий (2-3 предложения)
- topics: список обсуждённых тем
- user_preferences: выявленные предпочтения пользователя (если есть)

Ответь только JSON без дополнительного текста."""

            response = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Парсим JSON
            try:
                # Убираем markdown если есть
                if result_text.startswith("```"):
                    result_text = result_text.split("```")[1]
                    if result_text.startswith("json"):
                        result_text = result_text[4:]
                
                result = json.loads(result_text)
                
                # Обновляем state
                self.state["dialog_summary"] = result.get("summary", "")
                
                # Добавляем темы в архив
                for topic in result.get("topics", []):
                    self.add_archived_topic(topic)
                
                # Обновляем долгосрочный контекст
                if "user_preferences" in result:
                    self.state["long_term_context"]["preferences"] = result["user_preferences"]
                
                # Сокращаем историю диалога, оставляя только последние N сообщений
                original_len = len(self.state["dialog_history"])
                self.state["dialog_history"] = self.state["dialog_history"][-10:]
                
                stats["dialog_compressed"] = original_len - len(self.state["dialog_history"])
                stats["semantic_compression"] = 1
                
                logger.info(f"[StateManager {self.user_id}] семантическая компрессия выполнена")
                
            except json.JSONDecodeError as e:
                logger.error(f"[StateManager {self.user_id}] ошибка парсинга JSON от LLM: {e}")
                logger.debug(f"Ответ LLM: {result_text}")
        
        except Exception as e:
            logger.error(f"[StateManager {self.user_id}] ошибка семантической компрессии: {e}")
        
        return stats
    
    async def get_relevant_context(self, user_message: str, intent: Optional[str] = None) -> Dict[str, Any]:
        """
        Relevance Pruning - возвращает только релевантный контекст для текущего запроса.
        
        Args:
            user_message: текущее сообщение пользователя
            intent: определённый intent (если есть)
            
        Returns:
            Отфильтрованный контекст для использования в LLM
        """
        # Извлекаем ключевые слова из сообщения (простая реализация)
        keywords = set(user_message.lower().split())
        
        # Фильтруем задачи по релевантности
        relevant_tasks = []
        
        for task in self.state["current_tasks"]:
            # Критерии релевантности:
            relevance_score = 0
            
            # 1. Задача упомянута явно (по ID или названию)
            task_text = f"{task.get('task_id', '')} {task.get('title', '')}".lower()
            if any(kw in task_text for kw in keywords):
                relevance_score += 3
            
            # 2. Задача недавно изменена (за последний час)
            updated_at = task.get("updated_at", task.get("added_at"))
            if updated_at:
                try:
                    updated_dt = datetime.fromisoformat(updated_at)
                    if datetime.now() - updated_dt < timedelta(hours=1):
                        relevance_score += 2
                except:
                    pass
            
            # 3. Задача связана с intent
            if intent and task.get("type") == intent:
                relevance_score += 1
            
            if relevance_score > 0:
                relevant_tasks.append({
                    **task,
                    "_relevance": relevance_score
                })
        
        # Сортируем по релевантности и берём топ-N
        relevant_tasks.sort(key=lambda t: t["_relevance"], reverse=True)
        relevant_tasks = relevant_tasks[:MAX_CONTEXT_TASKS]
        
        # Формируем оптимизированный контекст
        context = {
            "current_context": self.state["current_context"],
            "relevant_tasks": [
                {k: v for k, v in t.items() if not k.startswith("_")}
                for t in relevant_tasks
            ],
            "recent_actions": self.state["recent_actions"][-5:],  # Только последние 5
            "dialog_summary": self.state["dialog_summary"],
            "long_term_context": self.state["long_term_context"]
        }
        
        return context
    
    def get_full_state(self) -> Dict[str, Any]:
        """Возвращает полный state (для отладки или специальных случаев)"""
        return self.state.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по state"""
        return {
            "tasks_count": len(self.state["current_tasks"]),
            "actions_count": len(self.state["recent_actions"]),
            "dialog_messages": len(self.state["dialog_history"]),
            "archived_topics": len(self.state["archived_topics"]),
            "has_summary": bool(self.state["dialog_summary"]),
            "metadata": self.state["metadata"]
        }
