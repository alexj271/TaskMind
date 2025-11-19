"""
AI Tools for ChatGPT function calling
These tools will be used by ChatGPT to interact with the tasks system
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    pass
    

def create_task(user_id: int, title: str, datetime_start: str, description: str = "",
               datetime_end: str = "", parent_id: Optional[int] = None, 
               task_type: str = "simple", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a new task for the user
    
    Args:
        user_id: Telegram user ID
        title: Task title
        datetime_start: Start datetime in ISO format
        description: Task description (optional)
        datetime_end: End datetime in ISO format (optional)
        parent_id: ID of parent task for subtasks (optional)
        task_type: Type of task - simple, composite, or subtask (optional)
        metadata: GPT-generated metadata as dict (optional)
    
    Returns:
        Dict with task info and success status
    """
    
    return {
            "success": True,
            "task_id": 123, #task.pk,
            "title": "", #task.title,
            "datetime_start": None, #task.datetime_start.isoformat(),
            "datetime_end": None, #task.datetime_end.isoformat() if task.datetime_end else None,
            "status": 'pending' # task.status
        }


# Tool schemas for OpenAI function calling
TOOL_SCHEMAS = [
    {
        "type": "function", 
        "function": {
            "name": "complete_task_by_keywords",
            "description": "🎯 Mark task as completed by searching with keywords. Use when user says task is done/completed/finished. Combines search and status update in one call. Perfect for natural language like 'I bought milk, task is done' or 'Meeting finished'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "Telegram user ID"
                    },
                    "keywords": {
                        "type": "string", 
                        "description": "Keywords to find the task in title/description. Extract from user message. Examples: 'молоко' for 'I bought milk', 'встреча' for 'Meeting finished'"
                    }
                },
                "required": ["user_id", "keywords"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_task_by_keywords", 
            "description": "🚫 Cancel task by searching with keywords. Use when user wants to cancel/remove a task. Combines search and status update in one call. Perfect for natural language like 'Cancel meeting tomorrow' or 'Remove the doctor appointment'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "Telegram user ID"
                    },
                    "keywords": {
                        "type": "string",
                        "description": "Keywords to find the task in title/description. Extract from user message. Examples: 'встреча' for 'Cancel meeting', 'врач' for 'Remove doctor appointment'"
                    }
                },
                "required": ["user_id", "keywords"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "🎯 ОБЯЗАТЕЛЬНО используй эту функцию когда пользователь упоминает любые задачи, напоминания, встречи, дедлайны или планы! Создает новую задачу с возможностью установки времени. Используй даже если задача упоминается вскользь в длинном сообщении.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "Telegram user ID"
                    },
                    "title": {
                        "type": "string",
                        "description": "Task title"
                    },
                    "datetime_start": {
                        "type": "string",
                        "description": "Start datetime in ISO format (e.g., '2023-12-25T09:00:00')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description (optional)",
                        "default": ""
                    },
                    "datetime_end": {
                        "type": "string",
                        "description": "End datetime in ISO format (optional)",
                        "default": ""
                    },
                    "parent_id": {
                        "type": "integer",
                        "description": "ID of parent task for creating subtasks (optional)"
                    },
                    "task_type": {
                        "type": "string",
                        "enum": ["simple", "composite", "subtask"],
                        "description": "Type of task: simple (default), composite (will have subtasks), subtask (under parent)",
                        "default": "simple"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "GPT-generated metadata as JSON object (e.g., {'context': 'поход', 'related_date': '2025-11-11'})"
                    }
                },
                "required": ["user_id", "title", "datetime_start"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_status",
            "description": "Update the status of a task. REQUIRED for cancelling, completing, or changing task status. Use task_id from get_user_tasks result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task ID"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "done", "failed", "cancelled"],
                        "description": "New task status"
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "Telegram user ID for logging (optional)"
                    }
                },
                "required": ["task_id", "status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_tasks",
            "description": "Get list of user tasks with IDs for viewing or FINDING TASKS TO UPDATE. Each task has an 'id' field - use this id with update_task_status to change task status. If user wants to cancel/complete tasks, use the returned task IDs with update_task_status function.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "Telegram user ID"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["all", "pending", "done", "failed", "cancelled"],
                        "description": "Filter by status",
                        "default": "all"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return",
                        "default": 10
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_task",
            "description": "Reschedule a task to a new date/time by position or title. User says 'move first task' or 'reschedule the meeting task'",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "Telegram user ID"
                    },
                    "task_identifier": {
                        "type": "string",
                        "description": "Task identifier: number (1,2,3), ordinal (первая, вторая, третья), or task title/partial title"
                    },
                    "new_datetime_start": {
                        "type": "string",
                        "description": "New start datetime in ISO format (YYYY-MM-DDTHH:MM:SS)"
                    },
                    "new_datetime_end": {
                        "type": "string",
                        "description": "Optional new end datetime in ISO format (YYYY-MM-DDTHH:MM:SS)"
                    }
                },
                "required": ["user_id", "task_identifier", "new_datetime_start"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_subtask",
            "description": "Create a subtask under an existing parent task. Parent task will automatically become composite type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "Telegram user ID"
                    },
                    "parent_task_id": {
                        "type": "integer",
                        "description": "ID of the parent task"
                    },
                    "title": {
                        "type": "string",
                        "description": "Subtask title"
                    },
                    "datetime_start": {
                        "type": "string",
                        "description": "Start datetime in ISO format (e.g., '2023-12-25T09:00:00')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Subtask description (optional)",
                        "default": ""
                    },
                    "datetime_end": {
                        "type": "string",
                        "description": "End datetime in ISO format (optional)",
                        "default": ""
                    },
                    "metadata": {
                        "type": "object",
                        "description": "GPT-generated metadata as JSON object"
                    }
                },
                "required": ["user_id", "parent_task_id", "title", "datetime_start"]
            }
        }
    }
]


# Function mapping for execution
AVAILABLE_FUNCTIONS = {
    "create_task": create_task,
}
