import os
from pathlib import Path
from typing import Dict, Any

class PromptTemplate:
    """Класс для работы с шаблонами промптов"""
    
    def __init__(self, template_path: str):
        self.template_path = Path(template_path)
        self._template = None
    
    def load(self) -> str:
        """Загружает шаблон из файла"""
        if self._template is None:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                self._template = f.read()
        return self._template
    
    def format(self, **kwargs) -> str:
        """Форматирует шаблон с переданными параметрами"""
        template = self.load()
        return template.format(**kwargs)


class TenolateManager:
    """Менеджер для управления промптами"""
    
    def __init__(self, template_dir: str = None, subdir: str = None):
        if template_dir is None:
            # Автоматически определяем путь к папке prompts
            current_dir = Path(__file__).parent.parent  # app/utils -> app
            self.template_dir = current_dir / subdir
        else:
            self.template_dir = Path(template_dir)
        
        self._templates: Dict[str, PromptTemplate] = {}
    
    def get_template(self, name: str) -> PromptTemplate:
        """Получает шаблон по имени"""
        if name not in self._templates:
            template_path = self.template_dir / f"{name}.md"
            if not template_path.exists():
                raise FileNotFoundError(f"Prompt template '{name}' not found at {template_path}")
            self._templates[name] = PromptTemplate(template_path)
        
        return self._templates[name]
    
    def render(self, template_name: str, **kwargs) -> str:
        """Рендерит шаблон с параметрами"""
        template = self.get_template(template_name)
        return template.format(**kwargs)
    
    def list_templates(self) -> list[str]:
        """Возвращает список доступных шаблонов"""
        if not self.template_dir.exists():
            return []
        
        templates = []
        for file_path in self.template_dir.glob("*.md"):
            templates.append(file_path.stem)
        
        return sorted(templates)


class PromptManager(TenolateManager):
    """Менеджер для работы с промптами в приложении TaskMind"""
    def __init__(self, template_dir: str = None):
        super().__init__(template_dir=template_dir, subdir="prompts")


prompt_manager = PromptManager()


def get_prompt(prompt_name: str, template_dir: str = None, **kwargs) -> TenolateManager:
    """Функция для получения экземпляра PromptManager с указанной поддиректорией"""
    current_dir = Path(__file__).parent.parent  # app/utils -> app
    if template_dir is None:
        template_dir = current_dir / "prompts"
    manager = TenolateManager(template_dir=str(template_dir))

    return manager.render(prompt_name, **kwargs)



def get_template(template_name: str, template_dir: str = None, **kwargs) -> TenolateManager:
    """Функция для получения экземпляра PromptManager с указанной поддиректорией"""
    current_dir = Path(__file__).parent.parent  # app/utils -> app
    if template_dir is None:
        template_dir = current_dir / "templates"
    manager = TenolateManager(template_dir=str(template_dir))

    return manager.render(template_name, **kwargs)