import logging
from app.utils.prompt_manager import TemplateManager

logger = logging.getLogger(__name__)


class MCPConfirmationFormatter:
    """Класс для форматирования сообщений подтверждения MCP функций"""
    
    def __init__(self, template_manager: TemplateManager):
        self.template_manager = template_manager
    
    def format_mcp_confirmation_message(self, function_name: str, arguments: dict, user_id: str, mcp_tools: list = None) -> str:
        """Форматирует сообщение подтверждения MCP функции используя шаблоны"""
        try:
            # Форматируем аргументы для отображения
            formatted_args = {}
            
            # Специальная обработка для разных функций
            if function_name == "create_task":
                formatted_args = {
                    "title": arguments.get("title", "Без названия"),
                    "description_line": f"📝 **Описание:** {arguments.get('description', 'Не указано')}\n" if arguments.get('description') else "",
                    "scheduled_at_formatted": self._format_datetime(arguments.get("scheduled_at")),
                    "reminder_at_formatted": self._format_datetime(arguments.get("reminder_at")),
                    "priority": arguments.get("priority", "medium").upper(),
                    "event_link_line": f"🔗 **Связано с событием:** {arguments.get('event_id')}\n" if arguments.get('event_id') else ""
                }
            elif function_name == "create_event":
                formatted_args = {
                    "title": arguments.get("title", "Без названия"),
                    "description_line": f"📝 **Описание:** {arguments.get('description', 'Не указано')}\n" if arguments.get('description') else "",
                    "event_date_formatted": self._format_datetime(arguments.get("event_date")),
                    "event_time_formatted": arguments.get("event_time", "Не указано"),
                    "event_type": arguments.get("event_type", "general").upper()
                }
            elif function_name == "search_tasks":
                formatted_args = {
                    "query": arguments.get("query", "Все задачи"),
                    "status": arguments.get("status", "Любой"),
                    "priority": arguments.get("priority", "Любой"),
                    "date_from_formatted": self._format_datetime(arguments.get("date_from")),
                    "date_to_formatted": self._format_datetime(arguments.get("date_to")),
                    "limit": arguments.get("limit", 10)
                }
            elif function_name == "get_user_tasks":
                formatted_args = {
                    "user_id": arguments.get("user_id", user_id),
                    "status": arguments.get("status", "Любой"),
                    "priority": arguments.get("priority", "Любой"),
                    "limit": arguments.get("limit", 10)
                }
            elif function_name == "update_task_status":
                formatted_args = {
                    "task_id": arguments.get("task_id", "Не указан"),
                    "new_status": arguments.get("new_status", "Не указан").upper()
                }
            elif function_name == "get_events":
                formatted_args = {
                    "start_date_formatted": self._format_datetime(arguments.get("start_date")),
                    "end_date_formatted": self._format_datetime(arguments.get("end_date")),
                    "event_type": arguments.get("event_type", "Все типы"),
                    "limit": arguments.get("limit", 10)
                }
            elif function_name == "search_events":
                formatted_args = {
                    "query": arguments.get("query", "Все события"),
                    "event_type": arguments.get("event_type", "Все типы"),
                    "start_date_formatted": self._format_datetime(arguments.get("start_date")),
                    "end_date_formatted": self._format_datetime(arguments.get("end_date")),
                    "limit": arguments.get("limit", 10)
                }
            elif function_name == "get_upcoming_events":
                formatted_args = {
                    "user_id": arguments.get("user_id", user_id),
                    "days": arguments.get("days", 7),
                    "limit": arguments.get("limit", 10)
                }
            elif function_name == "link_task_to_event":
                formatted_args = {
                    "task_id": arguments.get("task_id", "Не указан"),
                    "event_id": arguments.get("event_id", "Не указан")
                }
            else:
                # Используем default шаблон для неизвестных функций
                function_description = "выполнение операции"
                if mcp_tools:
                    for tool in mcp_tools:
                        if tool.get("name") == function_name:
                            function_description = tool.get("description", function_description)
                            break
                
                formatted_args = {
                    "function_name": function_name,
                    "function_description": function_description,
                    "arguments_formatted": self._format_arguments_list(arguments)
                }
                function_name = "default"
            
            # Рендерим шаблон
            try:
                return self.template_manager.render(function_name, **formatted_args)
            except FileNotFoundError:
                # Если шаблон не найден, используем default
                formatted_args = {
                    "function_name": function_name,
                    "function_description": "выполнение операции",
                    "arguments_formatted": self._format_arguments_list(arguments)
                }
                return self.template_manager.render("default", **formatted_args)
                
        except Exception as e:
            logger.error(f"Ошибка форматирования сообщения: {e}")
            return f"🔧 **Запрос на выполнение функции**\n\n📋 **Функция:** {function_name}\n\n❓ Вы подтверждаете выполнение?"

    def _format_datetime(self, dt_str: str) -> str:
        """Форматирует дату и время для отображения"""
        if not dt_str:
            return "Не указано"
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime("%d.%m.%Y %H:%M")
        except:
            return dt_str

    def _format_arguments_list(self, arguments: dict) -> str:
        """Форматирует список аргументов для отображения"""
        if not arguments:
            return "Нет параметров"
        
        formatted_items = []
        for key, value in arguments.items():
            if key != "user_id":  # Скрываем user_id
                formatted_items.append(f"• **{key}**: {value}")
        
        return "\n".join(formatted_items) if formatted_items else "Нет дополнительных параметров"