"""
Тесты для ИИ-резюмирования диалогов в DialogMemoryService.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.workers.chat.memory_service import DialogMemoryService
from app.workers.chat.models import MemorySummary, DialogGoal


class TestAISummarization:
    """Тесты для ИИ-резюмирования диалогов"""
    
    @pytest.fixture
    def memory_service(self):
        return DialogMemoryService()
    
    @pytest.fixture
    def sample_memory(self):
        return MemorySummary(
            user_goal=DialogGoal.CREATE_TASK,
            context="Новый диалог",
            clarifications=[],
            task_action_history=[],
            last_updated=datetime.now(timezone.utc)
        )
    
    @pytest.mark.asyncio
    async def test_update_summary_with_ai_success(self, memory_service):
        """Тест успешного обновления резюме с помощью ИИ"""
        # Мокаем OpenAI ответ
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:
Создание задачи для подготовки отчета

АКТУАЛЬНЫЕ ДАННЫЕ:
Задача: подготовить отчет Retenza до пятницы

СДЕЛАННЫЕ ШАГИ:
Запрошено создание задачи

АКТУАЛЬНОЕ СОСТОЯНИЕ:
Ожидает создания задачи про отчет Retenza"""
        
        with patch.object(memory_service.openai_service, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await memory_service.update_summary_with_ai(
                current_summary="нет данных",
                new_message="Создай задачу: подготовить отчет Retenza до пятницы",
                user_name="TestUser"
            )
            
            # Проверяем что ИИ вызвался с правильными параметрами
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            
            assert "Создай задачу: подготовить отчет Retenza до пятницы" in call_args[1]["messages"][0]["content"]
            assert "TestUser" in call_args[1]["messages"][0]["content"]
            
            # Проверяем результат
            assert "ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:" in result
            assert "отчет Retenza" in result
    
    @pytest.mark.asyncio
    async def test_update_summary_with_ai_error_fallback(self, memory_service):
        """Тест fallback при ошибке ИИ"""
        with patch.object(memory_service.openai_service, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("OpenAI API Error"))
            
            result = await memory_service.update_summary_with_ai(
                current_summary="АКТУАЛЬНОЕ СОСТОЯНИЕ:\nтест",
                new_message="Новое сообщение",
                user_name="TestUser"
            )
            
            # Проверяем что используется fallback - добавляет к существующему контексту
            assert "АКТУАЛЬНОЕ СОСТОЯНИЕ:" in result
            assert "TestUser написал: Новое сообщение" in result
    
    @pytest.mark.asyncio
    async def test_update_context_with_ai_summary(self, memory_service, sample_memory):
        """Тест обновления контекста памяти с ИИ"""
        mock_summary = "Обновленное резюме диалога"
        
        with patch.object(memory_service, 'update_summary_with_ai') as mock_update_ai:
            mock_update_ai.return_value = mock_summary
            
            await memory_service.update_context_with_ai_summary(
                sample_memory,
                "Привет, как дела?",
                "TestUser"
            )
            
            # Проверяем что контекст обновился
            assert sample_memory.context == mock_summary
            assert sample_memory.last_updated is not None
            
            # Проверяем вызов ИИ - метод создает базовое резюме если контекст "Новый диалог"
            mock_update_ai.assert_called_once()
            call_args = mock_update_ai.call_args[0]
            assert "ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:" in call_args[0]  # Базовое резюме
            assert call_args[1] == "Привет, как дела?"
            assert call_args[2] == "TestUser"
    
    @pytest.mark.asyncio 
    async def test_update_context_with_ai_summary_error(self, memory_service, sample_memory):
        """Тест обработки ошибки при обновлении контекста с ИИ"""
        with patch.object(memory_service, 'update_summary_with_ai') as mock_update_ai:
            mock_update_ai.side_effect = Exception("ИИ недоступен")
            
            original_context = sample_memory.context
            
            await memory_service.update_context_with_ai_summary(
                sample_memory,
                "Тестовое сообщение",
                "TestUser"
            )
            
            # Проверяем что контекст обновился простым способом
            assert "Тестовое сообщение" in sample_memory.context
            assert sample_memory.context != original_context
    
    def test_get_summary_for_prompt_with_ai_summary(self, memory_service, sample_memory):
        """Тест получения резюме для промпта когда есть ИИ-резюме"""
        sample_memory.context = """ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:
Управление задачами

АКТУАЛЬНЫЕ ДАННЫЕ:
Есть несколько активных задач

СДЕЛАННЫЕ ШАГИ:
Создано 2 задачи

АКТУАЛЬНОЕ СОСТОЯНИЕ:
Активный диалог"""
        
        result = memory_service.get_summary_for_prompt(sample_memory)
        
        # Если контекст уже в формате резюме, возвращаем как есть
        assert result == sample_memory.context
    
    def test_get_summary_for_prompt_without_ai_summary(self, memory_service, sample_memory):
        """Тест получения резюме для промпта без ИИ-резюме"""
        sample_memory.context = "Простой контекст диалога"
        sample_memory.user_goal = DialogGoal.CREATE_TASK
        
        result = memory_service.get_summary_for_prompt(sample_memory)
        
        # Должно создаваться краткое резюме
        assert "Цель: создание новой задачи" in result
        assert "Простой контекст диалога" in result
    
    def test_fallback_summary_update_with_existing_format(self, memory_service):
        """Тест fallback обновления с существующим форматом"""
        current_summary = """ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:
Тест

АКТУАЛЬНОЕ СОСТОЯНИЕ:
Активный диалог"""
        
        result = memory_service._fallback_summary_update(
            current_summary,
            "Новое сообщение",
            "TestUser"
        )
        
        # Проверяем что новое сообщение добавлено в секцию АКТУАЛЬНОЕ СОСТОЯНИЕ
        assert "TestUser написал: Новое сообщение" in result
        assert "ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:" in result
    
    def test_fallback_summary_update_without_format(self, memory_service):
        """Тест fallback обновления без существующего формата"""
        result = memory_service._fallback_summary_update(
            "Неизвестный формат",
            "Тестовое сообщение",
            "TestUser"
        )
        
        # Должен создаваться новый формат
        assert "ОБЩАЯ ЦЕЛЬ ПОЛЬЗОВАТЕЛЯ:" in result
        assert "АКТУАЛЬНЫЕ ДАННЫЕ:" in result  
        assert "Тестовое сообщение" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])