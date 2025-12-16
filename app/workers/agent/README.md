# Agent Worker - Quick Reference

## Схема работы

```
User Message
     ↓
Dialog Agent (mini) → Intent + Entities
     ↓
Clarification? → YES → Ask User
     ↓ NO
StateManager.optimize_state()
     ↓
Decision Engine (nano) → tool_call/noop
     ↓
Tool Executor → MCP Function
     ↓
State Update → Redis
     ↓
Dialog Agent (mini) → Human Response
     ↓
User
```

## Основные компоненты

| Компонент | Класс | Модель | Роль |
|-----------|-------|--------|------|
| Dialog Agent | `DialogAgent` | gpt-4.1-mini | Понимание языка + ответы |
| Decision Engine | `DecisionEngine` | gpt-4.1-nano | Выбор действия |
| State Manager | `StateManager` | - | Управление состоянием + контекст |
| Agent Session | `AgentSession` | - | Оркестрация компонентов |

## Ключевые методы

### AgentSession (Оркестратор)
**Файл:** `worker.py`

Методы:
- `_handle_user_message()` — главный метод обработки
- `_execute_tool()` — выполнение MCP функций
- `_update_state_from_tool_result()` — обновление state после tool

### DialogAgent
**Файл:** `dialog_agent.py`

Методы:
- `understand_intent(message_text)` — понимание намерения
- `format_response(intent, tool_name, tool_result)` — формирование ответа
- `format_simple_response(message)` — простой ответ (noop)

### DecisionEngine
**Файл:** `decision_engine.py`

Методы:
- `choose_action(intent_payload, state_context, available_tools)` — выбор действия
- `choose_action_with_validation(...)` — с валидацией
- `_validate_decision(decision, available_tools)` — валидация

### StateManager
**Файл:** `state_manager.py`

Методы:
- `load_from_redis()` / `sync_to_redis()` — синхронизация
- `optimize_state()` — трёхуровневая оптимизация
- `get_relevant_context()` — фильтрация для nano
- `add_task()`, `update_task_status()`, `add_action()` — обновления

## Промпты

- `dialog_agent_intent.md` — понимание намерения
- `decision_engine.md` — выбор действия
- `dialog_agent_response.md` — формирование ответа

## State Structure

```python
{
  "current_context": {...},      # Текущий контекст диалога
  "current_tasks": [...],        # Активные задачи (≤20)
  "recent_actions": [...],       # Последние действия (≤10)
  "dialog_history": [...],       # История диалога (≤50)
  "dialog_summary": str,         # Краткая выжимка
  "metadata": {...}              # Счётчики и метрики
}
```

## Оптимизация State

**Structural** (всегда):
- Удаление closed tasks
- Trim recent_actions → 10
- Limit current_tasks → 20

**Semantic** (>30 msg или >2000 tokens):
- GPT-4.1-mini creates summary
- Compress to last 10 messages

**Relevance** (per request):
- Score tasks: mention +3, recent +2, intent +1
- Return top 5 relevant

## Запуск

```bash
# Worker
python -m app.workers.agent.worker

# Тесты
pytest app/workers/agent/tests/test_state_manager.py -v
```

## Логирование

```
[AGENT {user_id}:{agent_id}] started
[AGENT {user_id}] Intent: create_task
[AGENT {user_id}] State optimized: {"tasks_removed": 2, ...}
[AGENT {user_id}] Decision: tool_call
```

## Полная документация

- [AGENT_ARCHITECTURE.md](./AGENT_ARCHITECTURE.md) — полная архитектура
- [CLASS_STRUCTURE.md](./CLASS_STRUCTURE.md) — структура классов и диаграммы
