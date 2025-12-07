"""
Тесты для промпта timezone_parse.md с использованием OpenAI function calling.
Динамически генерирует тесты из timezone_message.json через метакласс.
"""
import pytest
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any

from app.services.openai_tools import OpenAIService
from app.core.config import settings
from app.workers.gatekeeper.tasks import timezone_tool as timezone_tools
from app.utils.prompt_manager import PromptManager

# Настройка логирования
logger = logging.getLogger(__name__)


def load_timezone_prompt() -> str:
    """Загружает промпт timezone_parse.md с параметрами времени"""
    current_datetime = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    # Нужно использовать PromptManager с правильным путем к gatekeeper промптам
    gatekeeper_prompts_dir = Path(__file__).parent.parent / "prompts"
    gatekeeper_prompt_manager = PromptManager(str(gatekeeper_prompts_dir))
    
    return gatekeeper_prompt_manager.render(
        "timezone_parse",
        current_datetime=current_datetime
    )


def load_test_cases() -> list:
    """Загружает тестовые случаи из JSON"""
    test_file = Path(__file__).parent / "timezone_message.json"
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
        system_prompt = load_timezone_prompt()
        
        # Вызываем AI с промптом и tools
        response, function_call = await openai_service.chat_with_tools(
            history_messages=[{"role": "user", "content": input_text}],
            user_id=12345,
            system_prompt=system_prompt,
            tools=timezone_tools
        )
        
        # Проверяем что AI вызвал функцию
        assert function_call is not None, f"AI не вызвал функцию"
        assert function_call["function_name"] == "create_timezone", \
            f"неверное имя функции: ожидалось create_timezone, получено {function_call['function_name']}"
        
        # Получаем аргументы функции
        args = function_call["arguments"]
        
        # Проверяем success
        success = not args.get("error")
        expected_success = expected.get("success", False)
        
        if success == expected_success:
            if success:
                expected_task = expected["task"]
                
                if "city" in expected_task:
                    assert "city" in args and args["city"], "отсутствует city"
                    assert args["city"] == expected_task["city"], \
                        f"неверный city: ожидался {expected_task['city']}, получен {args['city']}"
                
                if "timezone" in expected_task:
                    assert "timezone" in args and args["timezone"], "отсутствует timezone"
                    assert args["timezone"] == expected_task["timezone"], \
                        f"неверный timezone: ожидался {expected_task['timezone']}, получен {args['timezone']}"
                
                if "datetime" in expected_task:
                    assert "datetime" in args and args["datetime"], "отсутствует datetime"
                    assert expected_task["datetime"] in args["datetime"], \
                        f"неверный datetime: ожидался {expected_task['datetime']}, получен {args['datetime']}"
                
                logger.info(f"✅ Тест {test_id} пройден. Task: {args}")
            else:
                # Проверяем ошибку
                assert "error" in args, f"отсутствует поле error {json.dumps(function_call, indent=4)}"
                error = args["error"]
                
                # Проверяем обязательные поля ошибки
                assert error, "отсутствует error_code"
                               
                logger.info(f"✅ Тест {test_id} пройден. Error: {error}")
        else:
            raise AssertionError(f"Ожидался success={expected_success}, получен success={success}. Response: {response}, Function call: {json.dumps(function_call, indent=4)}")
    
    # Устанавливаем имя метода и описание
    test_method.__name__ = f"test_case_{test_case['id'].replace('.', '_')}"
    test_method.__doc__ = f"Тест {test_case['id']}: {test_case['input'][:50]}..."
    
    return test_method


class TimezonePromptTestMeta(type):
    """Метакласс для динамической генерации тестов из JSON"""
    
    def __new__(mcs, name, bases, namespace, **kwargs):
        # Загружаем тестовые случаи
        test_cases = load_test_cases()
        
        # Создаем методы тестов для каждого случая
        for test_case in test_cases:
            test_method = create_test_method(test_case)
            namespace[test_method.__name__] = test_method
        
        return super().__new__(mcs, name, bases, namespace)


class TestTimezonePrompt(metaclass=TimezonePromptTestMeta):
    """Класс тестов для промпта timezone_parse.md
    
    Методы тестов генерируются автоматически из timezone_message.json
    через метакласс TimezonePromptTestMeta.
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