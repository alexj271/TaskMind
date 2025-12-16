# Структура классов Agent Worker

## Диаграмма классов

```
┌─────────────────────────────────────────────────────┐
│                  AgentSession                       │
│  (Оркестратор - координирует все компоненты)        │
├─────────────────────────────────────────────────────┤
│ + user_id: int                                      │
│ + redis: Redis                                      │
│ + dialog_agent: DialogAgent                         │
│ + decision_engine: DecisionEngine                   │
│ + state_manager: StateManager                       │
│ + message_builder: MessageBuilder                   │
├─────────────────────────────────────────────────────┤
│ + run()                                             │
│ + _handle_user_message(session, text)               │
│ + _execute_tool(session, name, args)                │
│ + _update_state_from_tool_result(...)               │
│ + _call_mcp_function(...)                           │
│ + _send_telegram_message(...)                       │
└─────────────────────────────────────────────────────┘
                │
                │ использует
                ▼
┌──────────────────────────┬──────────────────────────┬─────────────────────────┐
│                          │                          │                         │
▼                          ▼                          ▼                         ▼
┌────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────┐
│   DialogAgent      │ │  DecisionEngine      │ │   StateManager       │ │ MessageBuilder   │
│   (gpt-4.1-mini)   │ │  (gpt-4.1-nano)      │ │   (Redis sync)       │ │ (Context)        │
├────────────────────┤ ├──────────────────────┤ ├──────────────────────┤ ├──────────────────┤
│ + user_id          │ │ + user_id            │ │ + user_id            │ │ + user_id        │
│ + client: OpenAI   │ │ + client: OpenAI     │ │ + redis              │ │                  │
├────────────────────┤ ├──────────────────────┤ │ + state: Dict        │ ├──────────────────┤
│ + understand_      │ │ + choose_action()    │ ├──────────────────────┤ │ + build_message()│
│   intent(text)     │ │ + choose_action_     │ │ + load_from_redis()  │ │ + _get_last_     │
│                    │ │   with_validation()  │ │ + sync_to_redis()    │ │   tasks()        │
│ + format_response  │ │ + _validate_         │ │ + optimize_state()   │ │ + _get_last_     │
│   (intent, tool,   │ │   decision()         │ │ + get_relevant_      │ │   events()       │
│    result)         │ │                      │ │   context()          │ │ + _get_dialog_   │
│                    │ │                      │ │ + add_task()         │ │   history()      │
│ + format_simple_   │ │                      │ │ + update_task_       │ │                  │
│   response()       │ │                      │ │   status()           │ │                  │
└────────────────────┘ └──────────────────────┘ │ + add_action()       │ └──────────────────┘
                                                │ + add_dialog_        │
                                                │   message()          │
                                                └──────────────────────┘
```

## Поток вызовов

```
User Message
    │
    ▼
AgentSession._handle_user_message()
    │
    ├─► 1. DialogAgent.understand_intent(message_text)
    │       └─► Returns: {intent, entities, needs_clarification}
    │
    ├─► 2. Check clarification
    │       └─► if needs_clarification → return question
    │
    ├─► 3. StateManager.optimize_state()
    │       └─► Returns: optimization stats
    │
    ├─► 4. StateManager.get_relevant_context(message, intent)
    │       └─► Returns: {relevant_tasks, recent_actions, summary}
    │
    ├─► 5. DecisionEngine.choose_action_with_validation(intent, state, tools)
    │       ├─► choose_action() → LLM call
    │       └─► _validate_decision() → check result
    │       └─► Returns: {action_type, tool_name, tool_arguments}
    │
    ├─► 6. if tool_call:
    │       ├─► StateManager.add_action("tool_call_initiated")
    │       ├─► _execute_tool() → _call_mcp_function()
    │       ├─► _update_state_from_tool_result()
    │       │       ├─► StateManager.add_action("success/failed")
    │       │       └─► StateManager.add_task() / update_task_status()
    │       ├─► StateManager.sync_to_redis()
    │       └─► DialogAgent.format_response(intent, tool, result)
    │               └─► Returns: human-friendly text
    │
    ├─► 7. if noop:
    │       └─► Return simple message
    │
    ├─► 8. StateManager.add_dialog_message("user", text)
    │       StateManager.add_dialog_message("assistant", response)
    │       StateManager.sync_to_redis()
    │
    └─► 9. Return response to user
```

## Файловая структура

```
app/workers/agent/
├── worker.py              # AgentSession (оркестратор)
├── dialog_agent.py        # DialogAgent класс
├── decision_engine.py     # DecisionEngine класс
├── state_manager.py       # StateManager класс (состояние + контекст)
├── utils.py               # Утилиты (MCPConfirmationFormatter)
│
├── prompts/               # Промпты для LLM
│   ├── dialog_agent_intent.md
│   ├── dialog_agent_response.md
│   ├── decision_engine.md
│   └── ...
│
├── templates/             # Шаблоны для Telegram сообщений
│   └── ...
│
├── tests/                 # Тесты
│   ├── test_state_manager.py
│   ├── test_dialog_agent.py (TODO)
│   └── test_decision_engine.py (TODO)
│
├── AGENT_ARCHITECTURE.md  # Полная документация
├── CLASS_STRUCTURE.md     # Диаграммы классов
└── README.md              # Quick reference
```

## Зависимости между классами

```
AgentSession
    │
    ├── requires: DialogAgent
    ├── requires: DecisionEngine
    ├── requires: StateManager
    ├── requires: TelegramClient
    └── requires: MCP ClientSession

DialogAgent
    └── requires: AsyncOpenAI

DecisionEngine
    └── requires: AsyncOpenAI

StateManager
    └── requires: Redis (aioredis)
```

## Принципы проектирования

**Single Responsibility:**
- `DialogAgent` — только NLU и NLG
- `DecisionEngine` — только выбор действий
- `StateManager` — только управление состоянием
- `AgentSession` — только оркестрация

**Dependency Injection:**
- Все зависимости передаются через конструктор
- Легко мокировать для тестов

**Interface Segregation:**
- Каждый класс имеет чёткий публичный API
- Внутренние методы приватные (_method)

**Open/Closed:**
- Легко расширять функциональность
- Не нужно модифицировать существующие классы

## Пример использования

```python
# В AgentSession.__init__()
self.dialog_agent = DialogAgent(user_id=user_id)
self.decision_engine = DecisionEngine(user_id=user_id)
self.state_manager = StateManager(user_id=user_id, redis_client=redis)

# В _handle_user_message()
# 1. Понимание
intent_result = await self.dialog_agent.understand_intent(message_text)

# 2. Оптимизация state
await self.state_manager.optimize_state()
context = await self.state_manager.get_relevant_context(message_text, intent_result["intent"])

# 3. Принятие решения
decision = await self.decision_engine.choose_action_with_validation(
    intent_payload=intent_result,
    state_context=context,
    available_tools=tools
)

# 4. Исполнение
if decision["action_type"] == "tool_call":
    result = await self._execute_tool(session, decision["tool_name"], decision["tool_arguments"])
    response = await self.dialog_agent.format_response(
        intent=intent_result["intent"],
        tool_name=decision["tool_name"],
        tool_result=result
    )
```

## Тестирование

```python
# Тест DialogAgent
dialog_agent = DialogAgent(user_id=123)
result = await dialog_agent.understand_intent("Создай задачу купить молоко")
assert result["intent"] == "create_task"

# Тест DecisionEngine
decision_engine = DecisionEngine(user_id=123)
decision = await decision_engine.choose_action(
    intent_payload={"intent": "create_task", "entities": ["купить молоко"]},
    state_context={},
    available_tools=["create_task"]
)
assert decision["action_type"] == "tool_call"

# Тест StateManager
state_manager = StateManager(user_id=123, redis_client=redis_mock)
state_manager.add_task("t_1", "active", "Test")
context = await state_manager.get_relevant_context("купить молоко", "create_task")
assert len(context["relevant_tasks"]) > 0
```
