"""
Тесты для промпта parse.md с использованием OpenAI function calling.
Динамически генерирует тесты из process_message.json через метакласс.
"""
import pytest
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.services.openai_tools import OpenAIService
from app.core.config import settings
from app.workers.gatekeeper.tasks import tools as gatekeeper_tools
from app.utils.prompt_manager import prompt_manager

# Настройка логирования
logger = logging.getLogger(__name__)

# Преобразуем tools в формат OpenAI function calling
tools = [
    {
        "type": "function",
        "function": tool
    }
    for tool in gatekeeper_tools
]


def load_parse_prompt() -> str:
    """Загружает промпт parse.md с параметрами времени"""
    from datetime import datetime
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Нужно использовать PromptManager с правильным путем к gatekeeper промптам
    gatekeeper_prompts_dir = Path(__file__).parent.parent / "prompts"
    from app.utils.prompt_manager import PromptManager
    gatekeeper_prompt_manager = PromptManager(str(gatekeeper_prompts_dir))
    
    return gatekeeper_prompt_manager.render(
        "parse",
        current_datetime=current_datetime,
        timezone="Europe/Moscow"
    )


def load_test_cases() -> list:
    """Загружает тестовые случаи из JSON"""
    test_file = Path(__file__).parent / "process_message.json"
    with open(test_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data["tests"]


def create_test_method(test_case: Dict[str, Any]):
    """Создает метод теста для конкретного тестового случая"""
    
    @pytest.mark.requires_api_key
    @pytest.mark.asyncio
    async def test_method(self):
        test_id = test_case["id"]
        input_text = test_case["input"]
        expected = test_case["expected"]
        
        logger.info(f"🧪 Тест {test_id}: {input_text}")
        
        # Инициализация
        openai_service = OpenAIService(settings.gpt_model_fast)
        system_prompt = load_parse_prompt()
        
        # Вызываем AI с промптом и tools
        response, function_call = await openai_service.chat_with_tools(
            history_messages=[{"role": "user", "content": input_text}],
            user_id=12345,
            system_prompt=system_prompt,
            tools=tools
        )
        
        # Проверяем что AI вызвал функцию
        assert function_call is not None, f"AI не вызвал функцию"
        assert function_call["function_name"] == "create_gatekeeper_task", \
            f"неверное имя функции: ожидалось create_gatekeeper_task, получено {function_call['function_name']}"
        
        # Получаем аргументы функции
        args = function_call["arguments"]
        
        # Проверяем success
        success = not function_call["arguments"].get("error") is None
        assert success, \
            f"сполучен {response}, {json.dumps(function_call, indent=4)}"
        
        if success == expected['success']:
            # Проверяем успешную задачу
            assert "task" in args, "отсутствует поле task"
            task = args["task"]
            expected_task = expected["task"]
            
            # Проверяем обязательные поля
            assert "title" in task and task["title"].strip(), "отсутствует или пустой title"
            assert "datetime" in task and task["datetime"], "отсутствует datetime"
            assert "timezone" in task and task["timezone"], "отсутствует timezone"
            
            # Проверяем timezone (точное совпадение)
            assert task["timezone"] == expected_task["timezone"], \
                f"неверный timezone: ожидался {expected_task['timezone']}, получен {task['timezone']}"
            
            # Проверяем что datetime валидный ISO формат
            try:
                datetime.fromisoformat(task["datetime"].replace('Z', '+00:00'))
            except ValueError:
                raise AssertionError(f"невалидный ISO datetime: {task['datetime']}")
            
            logger.info(f"✅ Тест {test_id} пройден. Task: {task}")
            
        else:
            # Проверяем ошибку
            assert "error" in args, f"отсутствует поле error {json.dumps(function_call, indent=4)}"
            error = args["error"]
            expected_error = expected["error"]
            
            # Проверяем обязательные поля ошибки
            assert "error_code" in error, "отсутствует error_code"
            assert "error_message" in error and error["error_message"].strip(), \
                "отсутствует или пустое error_message"
            
            # Проверяем код ошибки (точное совпадение)
            assert error["error_code"] == expected_error["error_code"], \
                f"неверный error_code: ожидался {expected_error['error_code']}, получен {error['error_code']}. {error['error_message']}"
            
            logger.info(f"✅ Тест {test_id} пройден. Error: {error}")
    
    # Устанавливаем имя метода и описание
    test_method.__name__ = f"test_case_{test_case['id'].replace('.', '_')}"
    test_method.__doc__ = f"Тест {test_case['id']}: {test_case['input'][:50]}..."
    
    return test_method


class ParsePromptTestMeta(type):
    """Метакласс для динамической генерации тестов из JSON"""
    
    def __new__(mcs, name, bases, namespace, **kwargs):
        # Загружаем тестовые случаи
        test_cases = load_test_cases()
        
        # Создаем методы тестов для каждого случая
        for test_case in test_cases:
            test_method = create_test_method(test_case)
            namespace[test_method.__name__] = test_method
        
        return super().__new__(mcs, name, bases, namespace)


class TestParsePrompt(metaclass=ParsePromptTestMeta):
    """Класс тестов для промпта parse.md
    
    Методы тестов генерируются автоматически из process_message.json
    через метакласс ParsePromptTestMeta.
    """
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        logger.info("Настройка теста...")
    
    def teardown_method(self):
        """Очистка после каждого теста"""
        logger.info("Очистка после теста...")


if __name__ == "__main__":
    # Запуск тестов напрямую
    pytest.main([__file__, "-v", "-s"])