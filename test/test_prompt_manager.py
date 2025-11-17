import pytest
from app.utils.prompt_manager import PromptManager, PromptTemplate
from pathlib import Path
import tempfile
import os


class TestPromptManager:
    """Тесты для системы управления промптами"""
    
    def test_list_templates(self):
        """Тест: получение списка доступных шаблонов"""
        from app.utils.prompt_manager import prompt_manager
        
        templates = prompt_manager.list_templates()
        assert isinstance(templates, list)
        assert "task_parser" in templates
        assert "chat_assistant" in templates
        assert "welcome_message" in templates
    
    def test_render_task_parser(self):
        """Тест: рендеринг шаблона task_parser"""
        from app.utils.prompt_manager import prompt_manager
        
        rendered = prompt_manager.render(
            "task_parser",
            current_date="2025-11-17 20:30",
            timezone="Europe/Moscow"
        )
        
        assert "2025-11-17 20:30" in rendered
        assert "Europe/Moscow" in rendered
        assert "JSON" in rendered
        assert "title" in rendered
    
    def test_render_chat_assistant(self):
        """Тест: рендеринг шаблона chat_assistant"""
        from app.utils.prompt_manager import prompt_manager
        
        rendered = prompt_manager.render("chat_assistant")
        
        assert "AI-ассистент" in rendered
        assert "русском языке" in rendered
        assert "эмодзи" in rendered
    
    def test_render_welcome_message(self):
        """Тест: рендеринг приветственного сообщения"""
        from app.utils.prompt_manager import prompt_manager
        
        rendered = prompt_manager.render("welcome_message")
        
        assert "Привет" in rendered

    
    def test_custom_prompt_manager(self):
        """Тест: создание кастомного менеджера промптов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создаем тестовый шаблон
            template_path = Path(temp_dir) / "test_template.md"
            template_path.write_text("Hello {name}!", encoding='utf-8')
            
            # Создаем кастомный менеджер
            manager = PromptManager(temp_dir)
            
            # Тестируем
            templates = manager.list_templates()
            assert "test_template" in templates
            
            rendered = manager.render("test_template", name="World")
            assert rendered == "Hello World!"
    
    def test_template_not_found(self):
        """Тест: обработка отсутствующего шаблона"""
        from app.utils.prompt_manager import prompt_manager
        
        with pytest.raises(FileNotFoundError):
            prompt_manager.render("nonexistent_template")
    
    def test_prompt_template_class(self):
        """Тест: работа класса PromptTemplate"""
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "test.md"
            template_path.write_text("Test {value}", encoding='utf-8')
            
            template = PromptTemplate(template_path)
            
            # Тест загрузки
            content = template.load()
            assert content == "Test {value}"
            
            # Тест форматирования
            formatted = template.format(value="123")
            assert formatted == "Test 123"