You are GitHub Copilot for TaskMind - a high-performance async Telegram Task Tracker backend.

## Architecture Overview
**Tech Stack**: FastAPI (ASGI) + Tortoise ORM + PostgreSQL + Dramatiq workers + Redis + OpenAI API + Telegram Bot webhooks

**Core Pattern**: Incoming Telegram messages → Gatekeeper Worker → AI Classification → Task Creation OR Chat Worker → Response

## Key Architectural Decisions

### 1. Worker-Based Message Processing
- **Entry Point**: All webhooks → `/webhook/telegram` → `gatekeeper.tasks.process_webhook_message`
- **Gatekeeper Worker** (`app/workers/gatekeeper/`): AI classification, task parsing, message history
- **Chat Worker** (`app/workers/chat/`): Conversational AI responses for non-task messages
- **Shared Tasks** (`app/workers/shared/`): Telegram API, reminders, common utilities

### 2. AI Services Architecture
- **OpenAI Integration**: `app/services/openai_tools.OpenAIService` with model selection (`gpt_model_fast` vs `gpt_model_full`)
- **Prompt Management**: File-based templates in `app/prompts/` + `app/utils/prompt_manager.PromptManager`
- **Template Usage**: `prompt_manager.render("task_parser", current_date="2025-11-17", timezone="Europe/Moscow")`

### 3. Configuration & Environment
- **Settings**: Pydantic `BaseSettings` in `app/core/config.py` with `.env` support
- **Database**: `postgres_dsn` property constructs connection from separate params
- **Redis**: Separate DB indices for production (0) and tests (1)

## Development Workflows

### Running the Application
```bash
# API server
uvicorn app.main:app --reload

# Dramatiq workers
dramatiq app.workers.actors

# Database migrations  
aerich init -t app.core.db.TORTOISE_ORM
aerich init-db
```

### Testing Strategy
- **Markers**: `@pytest.mark.requires_api_key` for OpenAI integration tests
- **Test Structure**: `test/` with `conftest.py` Redis setup, async fixtures
- **Worker Tests**: In `app/workers/{worker}/tests/` for isolated testing
- **Command**: `pytest -m "not requires_api_key"` for offline tests

## Critical Patterns

### Worker Structure (Standardized)
```
app/workers/{worker_name}/
├── models.py        # Pydantic models (MessageType, IncomingMessage)
├── tasks.py         # Dramatiq actors (@dramatiq.actor decorator)
├── prompts/         # AI prompts as .md files
└── tests/           # Worker-specific tests
```

### Dramatiq Actor Pattern
```python
@dramatiq.actor(broker=redis_broker, max_retries=3, min_backoff=1000, max_backoff=30000)
async def process_webhook_message(update_id: int, message_data: Dict[str, Any]):
    # Worker logic here
```

### OpenAI Service Integration
- **Initialization**: Pass `gpt_model` parameter to constructor
- **Error Handling**: Wrap API calls in try/catch, raise `RuntimeError` for API failures
- **System Prompts**: Load via `prompt_manager.render("chat_assistant")`

### Database Models Pattern
- **Base**: Tortoise ORM with async methods
- **Location**: `app/models/` for shared models, worker-specific in `workers/{name}/models.py`
- **Repositories**: CRUD layer in `app/repositories/` with async methods

## Project-Specific Conventions

### Logging
- **Setup**: `app/core/logging_config.setup_logging()` called in `main.py`
- **Usage**: `logger = logging.getLogger(__name__)` in each module
- **Worker Logs**: Include context like `update_id`, `user_id` for traceability

### Error Handling
- **Classification Failures**: Default to chat worker rather than failing
- **API Failures**: Log error, return user-friendly message
- **Worker Retries**: Configured in Dramatiq actor decorator (max_retries=3)

### File Organization
- **Services**: External integrations in `app/services/` (OpenAI, Telegram)
- **Utils**: Helper functions in `app/utils/` (datetime parsing, prompt management)
- **Schemas**: Pydantic I/O models in `app/schemas/`
- **Routers**: FastAPI endpoints in `app/routers/`

## Integration Points
- **Telegram Webhooks**: Validation via Pydantic models in `app/routers/webhook.py`
- **AI Classification**: Text → MessageType enum (TASK/CHAT) via OpenAI tools
- **Task Parsing**: Natural language → structured `ParsedTask` schema
- **Redis Broker**: Connection via `app/core/dramatiq_setup.redis_broker`

Always generate async code with proper error handling, use the worker pattern for message processing, and leverage the prompt management system for AI interactions.

