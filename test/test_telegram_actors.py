"""
Тесты для Dramatiq actors.
Тестирование асинхронной обработки сообщений Telegram.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.workers.telegram_actors import (
    process_telegram_message, 
    parse_and_create_task, 
    schedule_task_reminder,
    send_telegram_message
)


class TestTelegramActors:
    """Тесты для Telegram actors."""
    
    def test_process_telegram_message_with_text(self):
        """Тест обработки сообщения с текстом."""
        message_data = {
            "text": "Купить молоко завтра в 14:00",
            "from_": {
                "id": 123456,
                "first_name": "Иван"
            },
            "chat": {
                "id": 123456
            }
        }
        
        with patch('app.workers.telegram_actors.parse_and_create_task') as mock_parse:
            # Мокируем send метод
            mock_parse.send = Mock()
            
            # Вызываем actor напрямую (не через очередь)
            process_telegram_message(update_id=1, message_data=message_data)
            
            # Проверяем что parse_and_create_task был вызван
            mock_parse.send.assert_called_once_with(
                user_id=123456,
                chat_id=123456,
                message_text="Купить молоко завтра в 14:00",
                user_name="Иван"
            )
    
    def test_process_telegram_message_without_text(self):
        """Тест обработки сообщения без текста."""
        message_data = {
            "from_": {
                "id": 123456,
                "first_name": "Иван"
            },
            "chat": {
                "id": 123456
            }
        }
        
        with patch('app.workers.telegram_actors.parse_and_create_task') as mock_parse:
            mock_parse.send = Mock()
            
            # Вызываем actor
            process_telegram_message(update_id=2, message_data=message_data)
            
            # parse_and_create_task не должен быть вызван
            mock_parse.send.assert_not_called()
    
    def test_process_telegram_message_without_from(self):
        """Тест обработки сообщения без поля from."""
        message_data = {
            "text": "Тестовое сообщение",
            "chat": {
                "id": 123456
            }
        }
        
        with patch('app.workers.telegram_actors.parse_and_create_task') as mock_parse:
            mock_parse.send = Mock()
            
            # Вызываем actor
            process_telegram_message(update_id=3, message_data=message_data)
            
            # Должен быть вызван с user_id=None
            mock_parse.send.assert_called_once_with(
                user_id=None,
                chat_id=123456,
                message_text="Тестовое сообщение",
                user_name="Unknown"
            )
    
    @patch('app.workers.telegram_actors.openai_service')
    def test_parse_and_create_task_success(self, mock_openai_service):
        """Тест успешного парсинга задачи."""
        # Мокируем parsed task
        mock_task = Mock()
        mock_task.title = "Купить продукты"
        mock_task.deadline = None
        
        mock_openai_service.parse_task.return_value = mock_task
        
        with patch('app.workers.telegram_actors.schedule_task_reminder') as mock_reminder:
            mock_reminder.send_with_options = Mock()
            
            # Вызываем actor
            parse_and_create_task(
                user_id=123456,
                chat_id=123456,
                message_text="Купить продукты сегодня",
                user_name="Тест"
            )
            
            # Проверяем что OpenAI был вызван
            mock_openai_service.parse_task.assert_called_once_with("Купить продукты сегодня")
            
            # Напоминание не должно быть запланировано (нет дедлайна)
            mock_reminder.send_with_options.assert_not_called()
    
    @patch('app.workers.telegram_actors.openai_service')
    def test_parse_and_create_task_with_deadline(self, mock_openai_service):
        """Тест парсинга задачи с дедлайном."""
        # Мокируем parsed task с дедлайном
        mock_task = Mock()
        mock_task.title = "Сдать отчет"
        mock_task.deadline = 1640995200  # Timestamp
        
        mock_openai_service.parse_task.return_value = mock_task
        
        with patch('app.workers.telegram_actors.schedule_task_reminder') as mock_reminder:
            mock_reminder.send_with_options = Mock()
            
            # Вызываем actor
            parse_and_create_task(
                user_id=123456,
                chat_id=123456,
                message_text="Сдать отчет до завтра",
                user_name="Тест"
            )
            
            # Проверяем что напоминание запланировано
            mock_reminder.send_with_options.assert_called_once_with(
                args=(123456, 123456, "Сдать отчет", 1640995200),
                eta=1640995200
            )
    
    @patch('app.workers.telegram_actors.openai_service')
    def test_parse_and_create_task_parsing_failed(self, mock_openai_service):
        """Тест когда парсинг задачи не удался."""
        mock_openai_service.parse_task.return_value = None
        
        with patch('app.workers.telegram_actors.schedule_task_reminder') as mock_reminder:
            mock_reminder.send_with_options = Mock()
            
            # Вызываем actor
            parse_and_create_task(
                user_id=123456,
                chat_id=123456,
                message_text="Неясное сообщение",
                user_name="Тест"
            )
            
            # Напоминание не должно быть запланировано
            mock_reminder.send_with_options.assert_not_called()
    
    def test_schedule_task_reminder(self):
        """Тест планирования напоминания."""
        # Пока заглушка, так как реальная отправка не реализована
        schedule_task_reminder(
            user_id=123456,
            chat_id=123456,
            task_title="Тестовая задача",
            deadline_timestamp=1640995200
        )
        
        # Тест проходит если нет исключений
        assert True
    
    def test_send_telegram_message(self):
        """Тест отправки сообщения в Telegram."""
        # Пока заглушка
        send_telegram_message(
            chat_id=123456,
            text="Тестовое сообщение"
        )
        
        # Тест проходит если нет исключений
        assert True


class TestActorErrorHandling:
    """Тесты обработки ошибок в actors."""
    
    def test_process_telegram_message_error_handling(self):
        """Тест обработки ошибок в process_telegram_message."""
        # Некорректные данные сообщения (данные отсутствуют полностью)
        message_data = None
        
        # Actor должен поднять исключение для retry при некорректных данных
        with pytest.raises(Exception):
            process_telegram_message(update_id=999, message_data=message_data)
    
    @patch('app.workers.telegram_actors.openai_service')
    def test_parse_and_create_task_error_handling(self, mock_openai_service):
        """Тест обработки ошибок в parse_and_create_task."""
        # Мокируем исключение в OpenAI сервисе
        mock_openai_service.parse_task.side_effect = Exception("OpenAI API error")
        
        # Actor должен поднять исключение для retry
        with pytest.raises(Exception):
            parse_and_create_task(
                user_id=123456,
                chat_id=123456,
                message_text="Тест",
                user_name="Тест"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])