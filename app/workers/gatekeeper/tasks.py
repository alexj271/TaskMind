"""
Dramatiq задачи для Gatekeeper Worker.
Обработка входящих сообщений, классификация и маршрутизация.
"""
from pathlib import Path
import dramatiq
import logging
from typing import Dict, Any
from datetime import datetime
from app.core.config import settings
from app.core.dramatiq_setup import redis_broker
from app.services.openai_tools import OpenAIService
from app.utils.prompt_manager import get_prompt, get_template
from app.repositories.user_repository import UserRepository
from app.repositories.dialog_repository import DialogRepository
from app.utils.summarizer import generate_dialogue_summary
from app.services.telegram_client import send_message as telegram_send_message
from .models import IncomingMessage, MessageType, MessageClassification, ParsedTaskData
from ..chat.tasks import process_chat_message
from datetime import datetime


async def update_dialog_summary(dialog_session):
    """
    Обновляет summary диалога по новой схеме:
    1. Берем последнее summary и все сообщения
    2. Отправляем в ИИ
    3. Получаем новое summary
    4. Оставляем только последние 2 сообщения в last_messages
    """
    # Собираем контекст для ИИ: summary + все сообщения
    context_parts = []
    if dialog_session.summary:
        context_parts.append(f"Previous summary: {dialog_session.summary}")
    
    messages_text = []
    for msg in dialog_session.last_messages:
        if isinstance(msg, dict) and "content" in msg:
            messages_text.append(msg["content"])
    
    if messages_text:
        context_parts.append(f"Recent messages: {' | '.join(messages_text)}")
    
    context = "\n".join(context_parts)
    
    # Получаем новое summary от ИИ
    new_summary = await generate_dialogue_summary(context)
    
    # Обновляем summary
    dialog_repo = DialogRepository()
    await dialog_repo.update_summary(dialog_session, new_summary)
    
    # Оставляем только последние 2 сообщения
    if len(dialog_session.last_messages) > 2:
        dialog_session.last_messages = dialog_session.last_messages[-2:]
        await dialog_session.save()


logger = logging.getLogger(__name__)

# Инициализируем OpenAI сервис
openai_service = OpenAIService(settings.gpt_model_fast)


tools = [
    {
        "name": "create_gatekeeper_task",
        "description": "Создаёт задачу или возвращает ошибку. Условия создания задачи: валидный заголовок, дата и время в будущем, время и дату можно определить однозначно корректный часовой пояс.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "object",
                    "description": "Заполняется только если четко указаны дата и время задачи в будущем",
                    "properties": {
                        "title": { "type": "string" },
                        "datetime": { "type": "string", "description": "ISO 8601 в UTC" },
                        "timezone": { "type": "string" }
                    }
                },
                "error": {
                    "type": "object",
                    "description": "Заполняется только при невозможности создать задачу. "
                    " - OFF_TOPIC если нет никакой информации о задаче и действиях. Эта ошибка имеет высокий приортитет над остальными."
                    " - INVALID_TIME невозможно точно определить время либо задано сразу несколько вариантов времени"
                    " - INVALID_DATE невозможно точно определить дату либо задано сразу несколько вариантов даты"
                    " - TIME_IN_PAST если время уже прошло сегодня"
                    " - DATE_IN_PAST если дата уже прошла",
                    "properties": {
                        "error_code": {
                            "type": "string",
                            "enum": [
                                "INVALID_DATE",
                                "INVALID_TIME",
                                "DATE_IN_PAST",
                                "TIME_IN_PAST",
                                "OFF_TOPIC"
                            ]
                            },
                            "error_message": { "type": "string" }
                        }
                }
            }
        }
    }
]


tools_create_timezone = [
    {
        "name": "create_timezone",
        "description": "Находит и возвращает таймзону и время на основе текста сообщения.",
        "parameters": {
            "type": "object",
            "properties": {
                "datetime": { "type": "string", "description": "Время в формате ISO 8601" },
                "timezone": { "type": "string", "description": "таймзона в формате IANA" },
                "city": { "type": "string", "description": "City for detect timezone. City on english only." },
                "error": {
                    "type": "string",
                    "description": "Заполняется только если невозможно определить таймзону или город. ",
                }
            }
        }
    }
]


async def process_webhook_message_internal(update_id: int, message_data: Dict[str, Any]):
    """
    Внутренняя функция для обработки webhook сообщения.
    Используется для тестирования логики без Dramatiq.
    """
    try:
        logger.info(f"Gatekeeper: обрабатываем сообщение update_id={update_id}")
        
        # Создаем объект входящего сообщения
        incoming_msg = IncomingMessage(
            update_id=update_id,
            user_id=message_data.get("from", {}).get("id", 0),
            chat_id=message_data.get("chat", {}).get("id", 0),
            message_text=message_data.get("text", ""),
            user_name=message_data.get("from", {}).get("first_name", "Unknown"),
            timestamp=datetime.utcnow()
        )
               
        # Получение объекта пользователя из базы
        user_repo = UserRepository()
        user = await user_repo.get_by_telegram(incoming_msg.user_id)
        if user is None:
            user = await user_repo.create(incoming_msg.user_id, chat_id=incoming_msg.chat_id, username=incoming_msg.user_name)
        
        # Сохраняем сообщение в историю диалога
        dialog_repo = DialogRepository()
        dialog_session = await dialog_repo.get_or_create_for_user(user)
        await dialog_repo.add_message_to_session(dialog_session, incoming_msg.message_text, "user")
        
        user_timezone = user.timezone

        if not user_timezone:
            await process_timezone_message(
                user_id=incoming_msg.user_id,
                message_text=incoming_msg.message_text
            )
        else:        
            # Обрабатываем сообщение с помощью AI
            await process_task_message(
                user_id=incoming_msg.user_id,
                chat_id=incoming_msg.chat_id,
                message_text=incoming_msg.message_text,
                user_name=incoming_msg.user_name,
                user_timezone=user_timezone
            )
                
            logger.info(f"Gatekeeper: сообщение update_id={update_id} успешно обработано")
            
            # Обновляем саммари диалога по новой схеме
            await dialog_repo.update_dialog_summary(dialog_session)
    except Exception as e:
        logger.error(f"Gatekeeper: ошибка обработки сообщения update_id={update_id}: {str(e)}")
        raise


async def process_timezone_message(user_id: int, message_text: str):
    """
    Обрабатывает сообщение с помощью AI используя function calling:
    если AI вызвал create_timezone - устанавливаем часовой пояс, отправляем сообщение в телеграм о необходимости выбрать таймзону.
    
    Args:
        user_id: ID пользователя Telegram
        message_text: Текст сообщения для обработки
    """
    try:
        logger.info(f"Gatekeeper: обрабатываем сообщение для установки таймзоны от пользователя {user_id}: '{message_text[:50]}...'")
        
        gatekeeper_timezone_prompt = get_prompt(
            prompt_name="timezone_parse",
            template_dir=str(Path(__file__) / "prompts"),
            current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )      
        
        ai_response, function_call = await openai_service.chat_with_tools(
            message_text,
            user_id,
            system_prompt=gatekeeper_timezone_prompt,
            tools=tools_create_timezone
        )
              
        if function_call and function_call.get("function_name") == "create_timezone":
            # AI определил, что нужно установить таймзону
            timezone_args = function_call.get("arguments", {})
            logger.info(f"Gatekeeper: AI вызвал create_timezone с аргументами: {timezone_args}")
            timezone = timezone_args.get("timezone")    
            if timezone:    
                # Обновляем таймзону пользователя в базе
                user_repo = UserRepository()
                user = await user_repo.update_by_telegram(user_id, timezone=timezone)
                if user:
                    logger.info(f"Gatekeeper: таймзона пользователя {user_id} установлена на {timezone}")
                    
                    # Отправляем сообщение в Telegram с подтверждением
                    confirmation_text = f"✅ Ваш часовой пояс установлен на {timezone}. Теперь вы можете создавать задачи с указанием времени."
                    await telegram_send_message(user.chat_id, confirmation_text)
                    
                    # Добавляем ответ ассистента в историю диалога
                    from app.repositories.dialog_repository import DialogRepository
                    dialog_repo = DialogRepository()
                    dialog_session = await dialog_repo.get_or_create_for_user(user)
                    await dialog_repo.add_message_to_session(dialog_session, confirmation_text, "assistant")
                else:
                    logger.error(f"Gatekeeper: не удалось найти пользователя {user_id} для обновления таймзоны")
            else:
                logger.error(f"Gatekeeper: неверные аргументы для create_timezone: {timezone_args}")
        else:           
            # AI не вызвал функцию установки таймзоны - отправляем в чат
            logger.info(f"Gatekeeper: сообщение не требует установки таймзоны, отправляем в чат")

    except Exception as e:      
        logger.error(f"Gatekeeper: ошибка обработки сообщения для установки таймзоны от пользователя {user_id}: {str(e)}")
        # В случае ошибки отправляем уведомление об ошибке в Telegram
        try:
            error_text = "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз."
            # Пытаемся получить пользователя для отправки сообщения
            if 'user' in locals() and user and hasattr(user, 'chat_id'):
                await telegram_send_message(user.chat_id, error_text)
            else:
                logger.warning("Gatekeeper: не удалось определить chat_id для отправки уведомления об ошибке")
            
            # Добавляем ответ ассистента в историю диалога (если есть user)
            if 'user' in locals():
                from app.repositories.dialog_repository import DialogRepository
                dialog_repo = DialogRepository()
                dialog_session = await dialog_repo.get_or_create_for_user(user)
                await dialog_repo.add_message_to_session(dialog_session, error_text, "assistant")
        except Exception as telegram_error:
            logger.error(f"Gatekeeper: не удалось отправить уведомление об ошибке в Telegram: {telegram_error}")


async def process_task_message(user_id: int, chat_id: int, message_text: str, user_name: str, user_timezone: str = "Europe/Moscow"):
    """
    Обрабатывает сообщение с помощью AI используя function calling:
    если AI вызвал create_task - создаем задачу, иначе отправляем в чат.
    
    Args:
        user_id: ID пользователя Telegram
        chat_id: ID чата
        message_text: Текст сообщения для обработки
        user_name: Имя пользователя
    """
    try:
        logger.info(f"Gatekeeper: обрабатываем сообщение от {user_name}: '{message_text[:50]}...'")
        
        gatekeeper_task_prompt = get_prompt(
            prompt_name="parse",
            template_dir=str(Path(__file__).parent.parent / "prompts"),
            current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            timezone=user_timezone
        )      
        
        ai_response, function_call = await openai_service.chat_with_tools(message_text, user_id, tools=tools)
              
        if function_call and function_call.get("function_name") == "create_gatekeeper_task":
            # AI определил, что нужно создать задачу
            task_args = function_call.get("arguments", {})
            logger.info(f"Gatekeeper: AI вызвал create_task с аргументами: {task_args}")

            # Вызываем функцию создания задачи
            task_result = await create_gatekeeper_task(**task_args)
            
            if task_result.get("success"):
                logger.info(f"Gatekeeper: задача создана успешно: {task_result}")
                
                # Отправляем подтверждение пользователю
                from ..shared.tasks import send_telegram_message
                confirmation_text = f"✅ Задача создана: {task_args.get('title', 'Без названия')}"
                
                # Добавляем информацию о времени если есть
                if task_args.get('datetime_start'):
                    try:
                        start_dt = datetime.fromisoformat(task_args['datetime_start'])
                        confirmation_text += f"\n⏰ Запланировано на: {start_dt.strftime('%d.%m.%Y %H:%M')}"
                    except ValueError:
                        pass
                await telegram_send_message(chat_id, confirmation_text)
                
                # Добавляем ответ ассистента в историю диалога
                from app.repositories.user_repository import UserRepository
                from app.repositories.dialog_repository import DialogRepository
                user_repo = UserRepository()
                user = await user_repo.get_by_telegram(user_id)
                if user:
                    dialog_repo = DialogRepository()
                    dialog_session = await dialog_repo.get_or_create_for_user(user)
                    await dialog_repo.add_message_to_session(dialog_session, confirmation_text, "assistant")
            else:
                logger.error(f"Gatekeeper: ошибка создания задачи: {task_result}")
                # В случае ошибки отправляем уведомление об ошибке в Telegram
                from ..shared.tasks import send_telegram_message
                error_text = "❌ Произошла ошибка при создании задачи. Попробуйте еще раз."
                await send_telegram_message.send(
                    chat_id=chat_id,
                    text=error_text
                )
                
                # Добавляем ответ ассистента в историю диалога
                from app.repositories.user_repository import UserRepository
                from app.repositories.dialog_repository import DialogRepository
                user_repo = UserRepository()
                user = await user_repo.get_by_telegram(user_id)
                if user:
                    dialog_repo = DialogRepository()
                    dialog_session = await dialog_repo.get_or_create_for_user(user)
                    await dialog_repo.add_message_to_session(dialog_session, error_text, "assistant")
                # Также отправляем в чат для обработки AI
                process_chat_message.send(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_text=ai_response or message_text,
                    user_name=user_name
                )
        else:
            # AI не вызвал функцию создания задачи - отправляем в чат
            logger.info(f"Gatekeeper: сообщение не требует создания задачи, отправляем в чат")
            process_chat_message.send(
                user_id=user_id,
                chat_id=chat_id,
                message_text=ai_response or message_text,
                user_name=user_name
            )
        
    except Exception as e:
        logger.error(f"Gatekeeper: ошибка обработки сообщения от пользователя {user_id}: {str(e)}")
        # В случае ошибки отправляем уведомление об ошибке в Telegram
        try:
            from ..shared.tasks import send_telegram_message
            error_text = "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз."
            await send_telegram_message.send(
                chat_id=chat_id,
                text=error_text
            )
        except Exception as telegram_error:
            logger.error(f"Gatekeeper: не удалось отправить уведомление об ошибке в Telegram: {telegram_error}")
        
