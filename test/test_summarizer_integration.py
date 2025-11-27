import pytest
import os
from unittest.mock import patch

from app.core.config import settings
from app.utils.summarizer import generate_dialogue_summary


class TestGenerateDialogueSummaryIntegration:
    """Интеграционные тесты для generate_dialogue_summary с реальным OpenAI API"""

    @pytest.mark.requires_api_key
    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "TEST_TOKEN",
        reason="Нужен реальный OPENAI_API_KEY для интеграционного теста"
    )
    @pytest.mark.asyncio
    async def test_real_dialogue_summary_with_previous(self):
        """Тест: реальная генерация summary с предыдущим резюме"""
        messages = [
            "Пользователь: Привет, нужно создать задачу на завтра",
            "Ассистент: Хорошо, какая задача?",
            "Пользователь: Встреча с клиентом в 14:00",
            "Ассистент: Задача создана: встреча с клиентом завтра в 14:00"
        ]
        previous_summary = "Пользователь планирует задачи"

        summary = await generate_dialogue_summary(messages, previous_summary)

        assert isinstance(summary, str)
        assert len(summary) > 0
        assert len(summary) < 500  # Summary не должен быть слишком длинным

        # Проверяем, что summary содержит ключевую информацию
        summary_lower = summary.lower()
        assert any(word in summary_lower for word in ["встреча", "клиент", "14:00", "задача"])

        print(f"Сгенерированное резюме: {summary}")

    @pytest.mark.requires_api_key
    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "TEST_TOKEN",
        reason="Нужен реальный OPENAI_API_KEY для интеграционного теста"
    )
    @pytest.mark.asyncio
    async def test_real_dialogue_summary_without_previous(self):
        """Тест: реальная генерация summary без предыдущего резюме"""
        messages = [
            "Пользователь: Напомни мне позвонить маме вечером",
            "Ассистент: Задача создана: позвонить маме вечером",
            "Пользователь: И купить продукты по пути домой",
            "Ассистент: Добавлена задача: купить продукты"
        ]

        summary = await generate_dialogue_summary(messages)

        assert isinstance(summary, str)
        assert len(summary) > 0
        assert len(summary) < 500

        # Проверяем, что summary содержит ключевую информацию
        summary_lower = summary.lower()
        assert any(word in summary_lower for word in ["позвонить", "маме", "продукты", "задача"])

        print(f"Сгенерированное резюме: {summary}")

    @pytest.mark.requires_api_key
    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "TEST_TOKEN",
        reason="Нужен реальный OPENAI_API_KEY для интеграционного теста"
    )
    @pytest.mark.asyncio
    async def test_real_dialogue_summary_short_conversation(self):
        """Тест: реальная генерация summary для короткого диалога"""
        messages = [
            "Пользователь: Привет!",
            "Ассистент: Привет! Чем могу помочь?"
        ]

        summary = await generate_dialogue_summary(messages)

        assert isinstance(summary, str)
        # Для коротких диалогов может вернуться пустая строка или простое резюме
        print(f"Сгенерированное резюме для короткого диалога: '{summary}'")

    @pytest.mark.requires_api_key
    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "TEST_TOKEN",
        reason="Нужен реальный OPENAI_API_KEY для интеграционного теста"
    )
    @pytest.mark.asyncio
    async def test_real_dialogue_summary_empty_messages(self):
        """Тест: реальная генерация summary для пустого списка сообщений"""
        messages = []

        summary = await generate_dialogue_summary(messages)

        assert isinstance(summary, str)
        assert summary == ""

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self):
        """Тест: fallback логика при ошибке API"""
        messages = [
            "Пользователь: Создай задачу на завтра",
            "Ассистент: Задача создана"
        ]

        # Мокаем OpenAI клиент, чтобы вызвать ошибку
        with patch('app.services.openai_tools.AsyncOpenAI') as mock_client:
            mock_client.side_effect = Exception("API Error")

            summary = await generate_dialogue_summary(messages)

            assert isinstance(summary, str)
            # При ошибке должен вернуться fallback - последнее пользовательское сообщение
            assert "Создай задачу на завтра" in summary