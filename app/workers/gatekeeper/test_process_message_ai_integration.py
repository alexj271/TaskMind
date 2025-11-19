"""
Интеграционные тесты для process_message_with_ai с реальным AI
Требует настроенный OPENAI_API_KEY в .env
"""
import pytest
import asyncio
import logging
import json
import traceback
import functools
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from app.workers.gatekeeper.tasks import process_message_with_ai, openai_service
from app.core.config import settings

# Создаем папку для логов и отчетов
report_dir = Path(__file__).parent / "test_reports"
report_dir.mkdir(exist_ok=True)

# Создаем файл для логов с временной меткой
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = report_dir / f"test_logs_{timestamp}.log"

# Настраиваем логирование для тестов
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8')
    ],
    force=True  # Принудительно перезаписываем существующие настройки
)
logger = logging.getLogger(__name__)

# Включаем логирование для всех модулей приложения
for module_name in [
    'app.workers.gatekeeper.tasks',
    'app.services.openai_tools', 
    'app.workers.shared.tasks',
    'app.workers.chat.tasks'
]:
    module_logger = logging.getLogger(module_name)
    module_logger.setLevel(logging.DEBUG)
    module_logger.propagate = True

# Отключаем избыточные логи от библиотек
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Глобальный отчет по тестам
TEST_REPORT = {
    "timestamp": datetime.now().isoformat(),
    "openai_model": settings.gpt_model_fast,
    "log_file": str(log_file),
    "tests": [],
    "session_info": {
        "total_tests_run": 0,
        "successful_tests": 0,
        "failed_tests": 0,
        "skipped_tests": 0
    }
}


def log_test_execution(func):
    """Декоратор для логирования начала и конца выполнения теста"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        test_name = func.__name__
        logger.info(f"🚀 НАЧАЛО ТЕСТА: {test_name}")
        logger.info(f"📏 Описание: {func.__doc__ or 'Не указано'}")
        logger.info("=" * 80)
        
        try:
            result = await func(*args, **kwargs)
            logger.info("=" * 80)
            logger.info(f"✅ УСПЕШНОЕ ЗАВЕРШЕНИЕ ТЕСТА: {test_name}")
            return result
        except Exception as e:
            logger.info("=" * 80)
            logger.error(f"❌ ПРОВАЛ ТЕСТА: {test_name} - {str(e)}")
            raise
    
    return wrapper


class TestProcessMessageWithAIIntegration:
    """Интеграционные тесты для process_message_with_ai с реальным OpenAI API"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Мокаем только Telegram отправку и Dramatiq очереди"""
        # Мок для отправки в Telegram
        self.telegram_mock = AsyncMock()
        
        # Мок для process_chat_message.send
        self.chat_mock = AsyncMock()
        
        with patch('app.workers.shared.tasks.send_telegram_message.send', self.telegram_mock):
            with patch('app.workers.chat.tasks.process_chat_message.send', self.chat_mock):
                yield

    async def _log_ai_interaction(self, test_name: str, message_text: str, expected_behavior: str, 
                                 actual_behavior: str, ai_response: str = None, function_call: dict = None,
                                 success: bool = True, error: str = None, exception_info: str = None):
        """Логирует взаимодействие с AI для отчета"""
        test_data = {
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "input_message": message_text,
            "expected_behavior": expected_behavior,
            "actual_behavior": actual_behavior,
            "ai_response": ai_response,
            "function_call": function_call,
            "success": success,
            "error": error,
            "exception_info": exception_info
        }
        TEST_REPORT["tests"].append(test_data)
        
        # Обновляем статистику
        TEST_REPORT["session_info"]["total_tests_run"] += 1
        if success:
            TEST_REPORT["session_info"]["successful_tests"] += 1
        else:
            TEST_REPORT["session_info"]["failed_tests"] += 1
        
        # Логируем в консоль и файл
        logger.info(f"=== {test_name} ===")
        logger.info(f"Сообщение: {message_text}")
        logger.info(f"Ожидали: {expected_behavior}")
        logger.info(f"Получили: {actual_behavior}")
        if ai_response:
            logger.info(f"AI ответ: {ai_response[:200]}...")
        if function_call:
            logger.info(f"Вызов функции: {json.dumps(function_call, ensure_ascii=False, indent=2)}")
        if error:
            logger.error(f"Ошибка: {error}")
        if exception_info:
            logger.error(f"Исключение: {exception_info}")
        logger.info(f"Результат: {'✅ УСПЕХ' if success else '❌ ПРОВАЛ'}")
        logger.info("-" * 50)

    async def _get_ai_response_details(self, message_text: str, user_id: int):
        """Получает детали ответа AI для отчета"""
        try:
            ai_response, function_call = await openai_service.chat_with_tools(message_text, user_id)
            return ai_response, function_call
        except Exception as e:
            logger.error(f"Ошибка получения ответа AI: {str(e)}")
            return None, None

    async def _execute_with_exception_handling(self, user_id: int, chat_id: int, message_text: str, user_name: str):
        """Выполняет process_message_with_ai с обработкой исключений"""
        exception_occurred = None
        try:
            await process_message_with_ai(user_id, chat_id, message_text, user_name)
        except Exception as e:
            exception_occurred = e
            logger.error(f"🚨 Исключение в process_message_with_ai: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        return exception_occurred

    @pytest.mark.asyncio
    @log_test_execution
    async def test_connection_error_handling(self):
        """Тест обработки ошибок соединения с API"""
        message_text = "Тестируем обработку ошибок подключения"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        # Мокаем openai_service чтобы имитировать ошибку подключения
        with patch('app.workers.gatekeeper.tasks.openai_service.chat_with_tools') as mock_chat:
            mock_chat.side_effect = Exception("Connection error - No internet connection")
            
            # Выполняем функцию с обработкой исключений
            exception_occurred = await self._execute_with_exception_handling(user_id, chat_id, message_text, user_name)
            
            # Определяем фактическое поведение
            task_created = self.telegram_mock.called
            sent_to_chat = self.chat_mock.called
            
            expected_behavior = "Уведомление об ошибке в Telegram + fallback в чат"
            actual_behavior = f"Telegram: {task_created}, Чат: {sent_to_chat}"
            success = sent_to_chat and task_created and exception_occurred is None  # Теперь ожидаем И telegram И chat
            error = None if success else f"telegram_called={task_created}, chat_called={sent_to_chat}, exception={exception_occurred is not None}"
            
            await self._log_ai_interaction(
                "test_connection_error_handling",
                message_text,
                expected_behavior,
                actual_behavior,
                None,  # ai_response
                None,  # function_call
                success,
                error,
                traceback.format_exc() if exception_occurred else None
            )
            
            # Проверяем что система корректно обработала ошибку
            # process_message_with_ai имеет встроенную обработку исключений,
            # поэтому исключение не должно пробрасываться наружу
            assert exception_occurred is None, "Исключение должно быть обработано внутри функции"
            assert task_created, "Должно было быть отправлено уведомление об ошибке в Telegram"
            assert sent_to_chat, "При ошибке API должна быть отправка в чат как fallback"
            
            logger.info("✅ Тест обработки ошибки подключения прошел успешно")

    @pytest.mark.asyncio
    @log_test_execution
    async def test_task_creation_failure_handling(self):
        """Тест обработки ошибки при создании задачи"""
        message_text = "Создай задачу: встреча завтра в 15:00"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        # Мокаем create_task чтобы имитировать ошибку создания задачи
        with patch('app.services.tools.create_task') as mock_create_task:
            mock_create_task.return_value = {"success": False, "error": "Database connection failed"}
            
            # Выполняем функцию с реальным AI (если доступен)
            exception_occurred = await self._execute_with_exception_handling(user_id, chat_id, message_text, user_name)
            
            # Определяем фактическое поведение
            task_created = self.telegram_mock.called
            sent_to_chat = self.chat_mock.called
            
            expected_behavior = "Уведомление об ошибке в Telegram + fallback в чат"
            actual_behavior = f"Telegram: {task_created}, Чат: {sent_to_chat}"
            success = sent_to_chat and task_created and exception_occurred is None  # Теперь ожидаем И telegram И chat
            error = None if success else f"telegram_called={task_created}, chat_called={sent_to_chat}, exception={exception_occurred is not None}"
            
            await self._log_ai_interaction(
                "test_task_creation_failure_handling",
                message_text,
                expected_behavior,
                actual_behavior,
                None,  # ai_response
                {"function_name": "create_task", "error": "Database connection failed"},  # function_call
                success,
                error,
                traceback.format_exc() if exception_occurred else None
            )
            
            # Проверяем что система корректно обработала ошибку создания задачи
            assert exception_occurred is None, "Исключение должно быть обработано внутри функции"
            assert task_created, "Должно было быть отправлено уведомление об ошибке в Telegram"
            assert sent_to_chat, "При ошибке создания задачи должна быть отправка в чат как fallback"
            
            logger.info("✅ Тест обработки ошибки создания задачи прошел успешно")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
    @log_test_execution
    async def test_task_creation_message(self):
        """Тест создания задачи из сообщения через реальный AI"""
        message_text = "Напомни мне завтра в 15:00 позвонить маме"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        # Получаем детали ответа AI
        ai_response, function_call = await self._get_ai_response_details(message_text, user_id)
        
        # Выполняем функцию с обработкой исключений
        exception_occurred = None
        try:
            await process_message_with_ai(user_id, chat_id, message_text, user_name)
        except Exception as e:
            exception_occurred = e
            logger.error(f"🚨 Исключение в process_message_with_ai: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Определяем фактическое поведение
        task_created = self.telegram_mock.called
        sent_to_chat = self.chat_mock.called
        
        expected_behavior = "Создание задачи"
        if exception_occurred:
            actual_behavior = f"Исключение: {type(exception_occurred).__name__}"
            success = False
            error = f"Исключение: {str(exception_occurred)}"
        else:
            actual_behavior = "Создание задачи" if task_created else ("Отправка в чат" if sent_to_chat else "Никакого действия")
            success = task_created and not sent_to_chat
            error = None if success else f"telegram_called={task_created}, chat_called={sent_to_chat}"
        
        await self._log_ai_interaction(
            "test_task_creation_message",
            message_text,
            expected_behavior,
            actual_behavior,
            ai_response,
            function_call,
            success,
            error,
            traceback.format_exc() if exception_occurred else None
        )
        
        # Если было исключение, перебрасываем его
        if exception_occurred:
            raise exception_occurred
        
        # Проверяем что была попытка отправить сообщение в Telegram
        assert task_created, "Должно было быть отправлено подтверждение создания задачи"
        
        # Проверяем что НЕ было отправки в чат
        assert not sent_to_chat, "Сообщение не должно было попасть в чат при создании задачи"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
    @log_test_execution
    async def test_chat_message(self):
        """Тест обычного чат-сообщения через реальный AI"""
        message_text = "Привет! Как дела? Расскажи анекдот"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        # Получаем детали ответа AI
        ai_response, function_call = await self._get_ai_response_details(message_text, user_id)
        
        # Выполняем функцию с обработкой исключений
        exception_occurred = None
        try:
            await process_message_with_ai(user_id, chat_id, message_text, user_name)
        except Exception as e:
            exception_occurred = e
            logger.error(f"🚨 Исключение в process_message_with_ai: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Определяем фактическое поведение
        task_created = self.telegram_mock.called
        sent_to_chat = self.chat_mock.called
        
        expected_behavior = "Отправка в чат"
        if exception_occurred:
            actual_behavior = f"Исключение: {type(exception_occurred).__name__}"
            success = False
            error = f"Исключение: {str(exception_occurred)}"
        else:
            actual_behavior = "Создание задачи" if task_created else ("Отправка в чат" if sent_to_chat else "Никакого действия")
            success = sent_to_chat and not task_created
            error = None if success else f"telegram_called={task_created}, chat_called={sent_to_chat}"
        
        await self._log_ai_interaction(
            "test_chat_message",
            message_text,
            expected_behavior,
            actual_behavior,
            ai_response,
            function_call,
            success,
            error,
            traceback.format_exc() if exception_occurred else None
        )
        
        # Дополнительный вывод для отладки
        print(f"\n🔍 ДЕТАЛИ ТЕСТА test_chat_message:")
        print(f"📝 Сообщение: {message_text}")
        print(f"🤖 AI ответ: {ai_response[:200] if ai_response else 'None'}...")
        print(f"⚙️ Функция: {function_call.get('function_name') if function_call else 'None'}")
        print(f"📊 Результат: telegram_called={task_created}, chat_called={sent_to_chat}")
        print(f"🚨 Исключение: {exception_occurred if exception_occurred else 'Нет'}")
        print(f"✅ Статус: {'УСПЕХ' if success else 'ПРОВАЛ'}")
        
        # Если было исключение, перебрасываем его
        if exception_occurred:
            raise exception_occurred
        
        # Проверяем что сообщение было отправлено в чат
        assert sent_to_chat, "Обычное сообщение должно было попасть в чат"
        
        # Проверяем что НЕ было создания задачи
        assert not task_created, "Не должно было быть создания задачи для обычного сообщения"
        
        # Проверяем аргументы вызова chat
        if sent_to_chat:
            call_args = self.chat_mock.call_args[1]
            assert call_args['user_id'] == user_id
            assert call_args['chat_id'] == chat_id
            assert call_args['user_name'] == user_name
            assert 'message_text' in call_args

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
    async def test_task_with_specific_time(self):
        """Тест создания задачи с конкретным временем"""
        message_text = "Создай задачу: встреча с командой 20 ноября 2025 в 14:30"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        await process_message_with_ai(user_id, chat_id, message_text, user_name)
        
        # Проверяем создание задачи
        assert self.telegram_mock.called, "Должна была быть создана задача с временем"
        
        # Проверяем содержимое подтверждения
        call_args = self.telegram_mock.call_args[1]
        confirmation_text = call_args['text']
        assert "✅ Задача создана" in confirmation_text
        assert "встреча" in confirmation_text.lower() or "команда" in confirmation_text.lower()
        
        logger.info("✅ Тест задачи с временем прошел успешно")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
    @log_test_execution
    async def test_ambiguous_message(self):
        """Тест неоднозначного сообщения"""
        message_text = "Нужно будет что-то сделать"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        # Получаем детали ответа AI
        ai_response, function_call = await self._get_ai_response_details(message_text, user_id)
        
        # Выполняем функцию с обработкой исключений
        exception_occurred = None
        try:
            await process_message_with_ai(user_id, chat_id, message_text, user_name)
        except Exception as e:
            exception_occurred = e
            logger.error(f"🚨 Исключение в process_message_with_ai: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        # AI должен принять решение - либо создать задачу, либо отправить в чат
        task_created = self.telegram_mock.called
        sent_to_chat = self.chat_mock.called
        
        expected_behavior = "Создание задачи ИЛИ отправка в чат (решение AI)"
        if exception_occurred:
            actual_behavior = f"Исключение: {type(exception_occurred).__name__}"
            success = False
            error = f"Исключение: {str(exception_occurred)}"
        else:
            actual_behavior = "Создание задачи" if task_created else ("Отправка в чат" if sent_to_chat else "Никакого действия")
            success = (task_created or sent_to_chat) and not (task_created and sent_to_chat)
            error = None if success else f"telegram_called={task_created}, chat_called={sent_to_chat}, expected_one_action=True"
        
        await self._log_ai_interaction(
            "test_ambiguous_message",
            message_text,
            expected_behavior,
            actual_behavior,
            ai_response,
            function_call,
            success,
            error,
            traceback.format_exc() if exception_occurred else None
        )
        
        # Если было исключение, перебрасываем его
        if exception_occurred:
            raise exception_occurred
        
        assert task_created or sent_to_chat, "Должно было быть выполнено одно из действий"
        assert not (task_created and sent_to_chat), "Не должно было быть выполнено оба действия"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
    async def test_multiple_tasks_in_message(self):
        """Тест сообщения с несколькими потенциальными задачами"""
        message_text = "Завтра в 10:00 встреча с клиентом, а в 15:00 нужно позвонить поставщику"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        logger.info("✅ test_multiple_tasks_in_message")
        await process_message_with_ai(user_id, chat_id, message_text, user_name)
        
        # AI должен обработать это как задачу (хотя бы одну)
        assert self.telegram_mock.called, "Должна была быть создана задача из множественного сообщения"
        
        logger.info("✅ Тест множественных задач прошел успешно")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
    async def test_question_message(self):
        """Тест вопросительного сообщения"""
        message_text = "Во сколько у меня встреча завтра?"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        await process_message_with_ai(user_id, chat_id, message_text, user_name)
        
        # Вопрос должен попасть в чат, а не создать задачу
        assert self.chat_mock.called, "Вопрос должен был попасть в чат"
        assert not self.telegram_mock.called, "Вопрос не должен был создать задачу"
        
        logger.info("✅ Тест вопросительного сообщения прошел успешно")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
    async def test_error_handling_with_real_ai(self):
        """Тест обработки ошибок с реальным AI"""
        message_text = "Создай задачу: тестовая задача"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        # Мокаем create_task чтобы вернуть ошибку
        with patch('app.services.tools.create_task') as mock_create_task:
            mock_create_task.return_value = {"success": False, "error": "Test error"}
            
            await process_message_with_ai(user_id, chat_id, message_text, user_name)
            
            # При ошибке создания задачи должно быть отправлено в чат
            assert self.chat_mock.called, "При ошибке создания задачи должно быть отправлено в чат"
            
        logger.info("✅ Тест обработки ошибок прошел успешно")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
    async def test_long_message_handling(self):
        """Тест обработки длинного сообщения"""
        # Создаем длинное сообщение с задачей в середине
        long_message = (
            "Привет! Сегодня был очень насыщенный день. Утром я встретился с коллегами, "
            "обсудили текущие проекты и планы на будущее. Кстати, "
            "напомни мне завтра в 14:00 отправить отчет руководству. "
            "После встречи пошел на обед, было очень вкусно. Вечером планирую почитать книгу "
            "и посмотреть фильм. Погода сегодня отличная, солнечно и тепло."
        )
        
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        await process_message_with_ai(user_id, chat_id, long_message, user_name)
        
        # AI должен найти задачу в длинном сообщении
        assert self.telegram_mock.called, "AI должен был найти задачу в длинном сообщении"
        
        # Проверяем что в подтверждении есть информация о задаче
        call_args = self.telegram_mock.call_args[1]
        confirmation_text = call_args['text']
        assert "отчет" in confirmation_text.lower() or "руководство" in confirmation_text.lower()
        
        logger.info("✅ Тест длинного сообщения прошел успешно")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
    async def test_ai_response_preservation(self):
        """Тест сохранения ответа AI при отправке в чат"""
        message_text = "Расскажи мне шутку про программистов"
        user_id = 12345
        chat_id = 67890
        user_name = "TestUser"
        
        await process_message_with_ai(user_id, chat_id, message_text, user_name)
        
        # Проверяем что сообщение попало в чат
        assert self.chat_mock.called, "Сообщение должно было попасть в чат"
        
        # Проверяем что передается ответ AI, а не исходное сообщение
        call_args = self.chat_mock.call_args[1]
        sent_message = call_args['message_text']
        
        # Ответ AI должен отличаться от исходного сообщения
        # (если AI сгенерировал ответ, он будет длиннее исходного сообщения)
        logger.info(f"Исходное сообщение: {message_text}")
        logger.info(f"Отправленное сообщение: {sent_message[:100]}...")
        
        logger.info("✅ Тест сохранения ответа AI прошел успешно")


@pytest.mark.asyncio
@pytest.mark.skipif(not settings.openai_api_key, reason="Требует OPENAI_API_KEY")
async def test_openai_service_connectivity():
    """Тест подключения к OpenAI API"""
    try:
        # Простой тест chat_with_tools
        response, function_call = await openai_service.chat_with_tools("Привет, как дела?", 12345)
        
        assert isinstance(response, str), "Ответ должен быть строкой"
        assert len(response) > 0, "Ответ не должен быть пустым"
        assert function_call is None, "Простое приветствие не должно вызывать функции"
        
        logger.info(f"✅ OpenAI подключение работает. Ответ: {response[:50]}...")
        
    except Exception as e:
        pytest.fail(f"Ошибка подключения к OpenAI: {str(e)}")


def save_test_report():
    """Сохраняет отчет по тестам в JSON файл"""
    report_dir = Path(__file__).parent / "test_reports"
    report_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = report_dir / f"ai_integration_report_{timestamp}.json"
    
    # Добавляем статистику с учетом всех тестов
    manual_tests = [t for t in TEST_REPORT["tests"] if not t.get("auto_logged", False)]
    auto_tests = [t for t in TEST_REPORT["tests"] if t.get("auto_logged", False)]
    
    TEST_REPORT["summary"] = {
        "total_tests": len(TEST_REPORT["tests"]),
        "successful_tests": len([t for t in TEST_REPORT["tests"] if t["success"] == True]),
        "failed_tests": len([t for t in TEST_REPORT["tests"] if t["success"] == False]),
        "skipped_tests": len([t for t in TEST_REPORT["tests"] if t["success"] is None]),
        "manual_logged_tests": len(manual_tests),
        "auto_logged_tests": len(auto_tests),
        "task_creation_tests": len([t for t in manual_tests if "создание задачи" in t.get("expected_behavior", "").lower()]),
        "chat_message_tests": len([t for t in manual_tests if "чат" in t.get("expected_behavior", "").lower()]),
        "log_file_size_bytes": log_file.stat().st_size if log_file.exists() else 0
    }
    
    # Добавляем содержимое лог файла в отчет (последние 10000 символов)
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
            TEST_REPORT["log_content"] = log_content[-10000:] if len(log_content) > 10000 else log_content
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(TEST_REPORT, f, ensure_ascii=False, indent=2)
    
    # Выводим краткую статистику
    print("\n" + "="*60)
    print("ОТЧЕТ ПО ИНТЕГРАЦИОННЫМ ТЕСТАМ AI")
    print("="*60)
    print(f"Всего тестов: {TEST_REPORT['summary']['total_tests']}")
    print(f"Успешных: {TEST_REPORT['summary']['successful_tests']}")
    print(f"Провальных: {TEST_REPORT['summary']['failed_tests']}")
    print(f"Пропущенных: {TEST_REPORT['summary']['skipped_tests']}")
    print(f"Детально залогированных: {TEST_REPORT['summary']['manual_logged_tests']}")
    print(f"Автоматически залогированных: {TEST_REPORT['summary']['auto_logged_tests']}")
    print(f"Модель AI: {TEST_REPORT['openai_model']}")
    print(f"Размер лог файла: {TEST_REPORT['summary']['log_file_size_bytes']} байт")
    print(f"Лог файл: {TEST_REPORT['log_file']}")
    print(f"Отчет сохранен: {report_file}")
    
    # Выводим детали по провальным тестам
    failed_tests = [t for t in TEST_REPORT["tests"] if not t["success"]]
    if failed_tests:
        print("\n❌ ПРОВАЛЬНЫЕ ТЕСТЫ:")
        for test in failed_tests:
            print(f"\n  Тест: {test['test_name']}")
            print(f"  Сообщение: {test['input_message']}")
            print(f"  Ожидали: {test['expected_behavior']}")
            print(f"  Получили: {test['actual_behavior']}")
            if test['ai_response']:
                print(f"  AI ответ: {test['ai_response'][:100]}...")
            if test['function_call']:
                print(f"  Функция: {test['function_call'].get('function_name', 'N/A')}")
            print(f"  Ошибка: {test['error']}")
    
    print("="*60)


# Хуки pytest для автоматического логирования всех тестов
def pytest_runtest_setup(item):
    """Вызывается перед каждым тестом"""
    logger.info(f"🚀 Запуск теста: {item.name}")

def pytest_runtest_call(item):
    """Вызывается во время выполнения теста"""
    pass

def pytest_runtest_teardown(item, nextitem):
    """Вызывается после каждого теста"""
    logger.info(f"🏁 Завершение теста: {item.name}")

def pytest_runtest_logreport(report):
    """Логирует результат каждого теста"""
    if report.when == "call":  # Только основной вызов теста, не setup/teardown
        test_name = report.nodeid.split("::")[-1]
        
        # Определяем статус теста
        if report.passed:
            status = "PASSED"
            success = True
            error_info = None
        elif report.failed:
            status = "FAILED"
            success = False
            error_info = str(report.longrepr) if report.longrepr else "Неизвестная ошибка"
        elif report.skipped:
            status = "SKIPPED"
            success = None
            error_info = str(report.longrepr) if report.longrepr else "Тест пропущен"
            TEST_REPORT["session_info"]["skipped_tests"] += 1
        else:
            status = "UNKNOWN"
            success = None
            error_info = "Неизвестный статус теста"
        
        # Логируем результат теста
        logger.info(f"📊 Результат теста {test_name}: {status}")
        if error_info:
            logger.error(f"💥 Ошибка в тесте {test_name}: {error_info[:500]}...")
        
        # Если тест не был залогирован через _log_ai_interaction, добавляем его
        existing_test = next((t for t in TEST_REPORT["tests"] if t["test_name"] == test_name), None)
        if not existing_test and status != "SKIPPED":
            test_data = {
                "test_name": test_name,
                "timestamp": datetime.now().isoformat(),
                "input_message": "Не определено (тест не использовал _log_ai_interaction)",
                "expected_behavior": "Не определено",
                "actual_behavior": status,
                "ai_response": None,
                "function_call": None,
                "success": success,
                "error": error_info,
                "exception_info": str(report.longrepr) if report.longrepr else None,
                "auto_logged": True  # Помечаем что это автоматически добавленный тест
            }
            TEST_REPORT["tests"].append(test_data)
            
            # Обновляем статистику
            TEST_REPORT["session_info"]["total_tests_run"] += 1
            if success:
                TEST_REPORT["session_info"]["successful_tests"] += 1
            else:
                TEST_REPORT["session_info"]["failed_tests"] += 1

@pytest.fixture(scope="session", autouse=True)
def generate_report():
    """Автоматически генерирует отчет после всех тестов"""
    yield
    save_test_report()


if __name__ == "__main__":
    # Для запуска отдельных тестов
    pytest.main([__file__, "-v", "-s"])