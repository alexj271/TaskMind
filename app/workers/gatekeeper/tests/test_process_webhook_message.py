"""
Тесты для упрощенного Gatekeeper Worker.
Тестируем контроль доступа через проверку таймзоны.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.workers.gatekeeper.tasks import process_webhook_message_internal as _process_webhook_message_internal
from app.models.user import User
from app.models.dialog_session import DialogSession


@pytest.mark.database
@pytest.mark.asyncio
class TestGatekeeperAccess:
    """Тесты для контроля доступа через Gatekeeper"""

    @patch('app.workers.gatekeeper.tasks.telegram_send_message')
    @patch('app.workers.gatekeeper.tasks.set_timezone_setup_flag')
    async def test_new_user_timezone_request(self, mock_set_flag, mock_send):
        """Тест: новый пользователь получает запрос на установку таймзоны"""
        update_id = 12345
        message_data = {
            "from": {"id": 999999, "first_name": "NewUser"},
            "chat": {"id": 999999},
            "text": "Hello!"
        }

        with patch('app.workers.gatekeeper.tasks.UserRepository') as MockUserRepo, \
             patch('app.workers.gatekeeper.tasks.DialogRepository') as MockDialogRepo, \
             patch('app.workers.gatekeeper.tasks.get_timezone_setup_flag') as mock_get_flag:

            # Создаем mock instances
            mock_user_repo = MockUserRepo.return_value
            mock_dialog_repo = MockDialogRepo.return_value

            # Новый пользователь без таймзоны
            mock_user = Mock(spec=User)
            mock_user.timezone = None
            mock_user.chat_id = 999999
            mock_user_repo.get_by_telegram = AsyncMock(return_value=None)
            mock_user_repo.create = AsyncMock(return_value=mock_user)

            # Dialog session
            mock_session = Mock(spec=DialogSession)
            mock_dialog_repo.get_or_create_for_user = AsyncMock(return_value=mock_session)
            mock_dialog_repo.add_message_to_session = AsyncMock()

            # Флаг не установлен
            mock_get_flag.return_value = False
            mock_send.return_value = None
            mock_set_flag.return_value = None

            # Вызываем функцию
            await _process_webhook_message_internal(update_id, message_data)

            # Проверки
            mock_user_repo.create.assert_called_once_with(999999, chat_id=999999, username="NewUser")
            mock_set_flag.assert_called_once_with(999999)
            mock_send.assert_called_once()
            # Проверяем, что отправлено приветственное сообщение с запросом таймзоны
            args, _ = mock_send.call_args
            assert "часовой пояс" in args[1] or "таймзону" in args[1]

    @patch('app.workers.gatekeeper.tasks.process_chat_message')
    async def test_existing_user_with_timezone_forwarded_to_chat(self, mock_chat):
        """Тест: пользователь с таймзоной пересылается в чат"""
        update_id = 12346
        message_data = {
            "from": {"id": 123456, "first_name": "ExistingUser"},
            "chat": {"id": 123456},
            "text": "Create task for tomorrow"
        }

        with patch('app.workers.gatekeeper.tasks.UserRepository') as MockUserRepo, \
             patch('app.workers.gatekeeper.tasks.DialogRepository') as MockDialogRepo, \
             patch('app.workers.gatekeeper.tasks.get_timezone_setup_flag') as mock_get_flag:

            # Создаем mock instances
            mock_user_repo = MockUserRepo.return_value
            mock_dialog_repo = MockDialogRepo.return_value

            # Пользователь с таймзоной
            mock_user = Mock(spec=User)
            mock_user.timezone = "Europe/Moscow"
            mock_user.chat_id = 123456
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)

            # Dialog session
            mock_session = Mock(spec=DialogSession)
            mock_dialog_repo.get_or_create_for_user = AsyncMock(return_value=mock_session)
            mock_dialog_repo.add_message_to_session = AsyncMock()

            # Флаг не установлен
            mock_get_flag.return_value = False
            mock_chat.send = Mock()

            # Вызываем функцию
            await _process_webhook_message_internal(update_id, message_data)

            # Проверки
            mock_user_repo.create.assert_not_called()  # Пользователь уже существует
            mock_chat.send.assert_called_once_with(
                user_id=123456,
                chat_id=123456,
                message_text="Create task for tomorrow",
                user_name="ExistingUser"
            )

    @patch('app.workers.gatekeeper.tasks.clear_timezone_setup_flag')
    @patch('app.workers.gatekeeper.tasks.telegram_send_message')
    @patch('app.workers.gatekeeper.tasks.process_timezone_message')
    async def test_timezone_setup_success(self, mock_process_tz, mock_send, mock_clear_flag):
        """Тест: успешная установка таймзоны"""
        update_id = 12347
        message_data = {
            "from": {"id": 123456, "first_name": "User"},
            "chat": {"id": 123456},
            "text": "Moscow"
        }

        with patch('app.workers.gatekeeper.tasks.UserRepository') as MockUserRepo, \
             patch('app.workers.gatekeeper.tasks.DialogRepository') as MockDialogRepo, \
             patch('app.workers.gatekeeper.tasks.get_timezone_setup_flag') as mock_get_flag:

            # Создаем mock instances
            mock_user_repo = MockUserRepo.return_value
            mock_dialog_repo = MockDialogRepo.return_value

            # Пользователь в режиме установки таймзоны
            mock_user = Mock(spec=User)
            mock_user.timezone = None
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)

            # Dialog session
            mock_session = Mock(spec=DialogSession)
            mock_dialog_repo.get_or_create_for_user = AsyncMock(return_value=mock_session)
            mock_dialog_repo.add_message_to_session = AsyncMock()

            # Флаг установлен, таймзона успешно определена
            mock_get_flag.return_value = True
            mock_process_tz.return_value = (True, "Europe/Moscow")
            mock_send.return_value = None
            mock_clear_flag.return_value = None

            # Вызываем функцию
            await _process_webhook_message_internal(update_id, message_data)

            # Проверки
            mock_process_tz.assert_called_once()
            mock_clear_flag.assert_called_once_with(123456)
            mock_send.assert_called_once()
            # Проверяем, что отправлено сообщение об успехе
            args, _ = mock_send.call_args
            assert "установлена" in args[1]

    @patch('app.workers.gatekeeper.tasks.telegram_send_message')
    @patch('app.workers.gatekeeper.tasks.process_timezone_message')
    async def test_timezone_setup_failure(self, mock_process_tz, mock_send):
        """Тест: неуспешная установка таймзоны"""
        update_id = 12348
        message_data = {
            "from": {"id": 123456, "first_name": "User"},
            "chat": {"id": 123456},
            "text": "Some unclear message"
        }

        with patch('app.workers.gatekeeper.tasks.UserRepository') as MockUserRepo, \
             patch('app.workers.gatekeeper.tasks.DialogRepository') as MockDialogRepo, \
             patch('app.workers.gatekeeper.tasks.get_timezone_setup_flag') as mock_get_flag:

            # Создаем mock instances
            mock_user_repo = MockUserRepo.return_value
            mock_dialog_repo = MockDialogRepo.return_value

            # Пользователь в режиме установки таймзоны
            mock_user = Mock(spec=User)
            mock_user.timezone = None
            mock_user_repo.get_by_telegram = AsyncMock(return_value=mock_user)

            # Dialog session
            mock_session = Mock(spec=DialogSession)
            mock_dialog_repo.get_or_create_for_user = AsyncMock(return_value=mock_session)
            mock_dialog_repo.add_message_to_session = AsyncMock()

            # Флаг установлен, но таймзону определить не удалось
            mock_get_flag.return_value = True
            mock_process_tz.return_value = (False, "Не удалось определить таймзону")
            mock_send.return_value = None

            # Вызываем функцию
            await _process_webhook_message_internal(update_id, message_data)

            # Проверки
            mock_process_tz.assert_called_once()
            mock_send.assert_called_once()
            # Проверяем, что отправлено сообщение об ошибке
            args, _ = mock_send.call_args
            assert "Не удалось" in args[1]

    @patch('app.workers.gatekeeper.tasks.logger')
    async def test_error_handling(self, mock_logger):
        """Тест обработки ошибок"""
        update_id = 12349
        message_data = {
            "from": {"id": 123456},
            "chat": {"id": 123456},
            "text": "Test message"
        }

        # Mock репозитории с ошибкой
        with patch('app.workers.gatekeeper.tasks.UserRepository') as MockUserRepo:
            mock_user_repo = MockUserRepo.return_value
            mock_user_repo.get_by_telegram = AsyncMock(side_effect=Exception("DB Error"))

            # Вызываем функцию - должна обработать ошибку
            with pytest.raises(Exception, match="DB Error"):
                await _process_webhook_message_internal(update_id, message_data)

            # Проверяем логирование ошибки
            mock_logger.error.assert_called_once_with("Gatekeeper: ошибка обработки сообщения update_id=12349: DB Error")