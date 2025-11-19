"""
Dramatiq задачи для Gatekeeper Worker.
Обработка входящих сообщений, классификация и маршрутизация.
"""
import dramatiq
import logging
from typing import Dict, Any
from datetime import datetime
from app.core.config import settings
from app.core.dramatiq_setup import redis_broker
from app.services.openai_tools import OpenAIService
from .models import IncomingMessage, MessageType, MessageClassification, ParsedTaskData
from ..chat.tasks import process_chat_message

logger = logging.getLogger(__name__)

# Инициализируем OpenAI сервис
openai_service = OpenAIService(settings.gpt_model_fast)


@dramatiq.actor(broker=redis_broker, max_retries=3, min_backoff=1000, max_backoff=30000)
async def process_webhook_message(update_id: int, message_data: Dict[str, Any]):
    """
    Главная точка входа для всех webhook сообщений.
    Логирует историю сообщений и запускает классификацию.
    
    Args:
        update_id: ID обновления от Telegram
        message_data: Данные сообщения в формате словаря
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
        
        # TODO: Сохранить в MessageHistory модель в БД
        logger.info(f"Gatekeeper: сохраняем историю сообщения от {incoming_msg.user_name}")
        
        # Обрабатываем сообщение с помощью AI
        await process_message_with_ai(
            user_id=incoming_msg.user_id,
            chat_id=incoming_msg.chat_id,
            message_text=incoming_msg.message_text,
            user_name=incoming_msg.user_name
        )
            
        logger.info(f"Gatekeeper: сообщение update_id={update_id} успешно обработано")
        
    except Exception as e:
        logger.error(f"Gatekeeper: ошибка обработки сообщения update_id={update_id}: {str(e)}")
        raise


async def classify_message(message_text: str) -> MessageClassification:
    """
    Совместимость: простая классификация для тестов.
    В продакшене используется process_message_with_ai с полным AI анализом.
    """
    # Простая эвристика для тестов
    task_keywords = ["напомни", "встреча", "дедлайн", "задача", "сделать", "купить", "позвонить"]
    is_task = any(keyword in message_text.lower() for keyword in task_keywords)
    
    return MessageClassification(
        message_type=MessageType.TASK if is_task else MessageType.CHAT,
        confidence=0.8 if is_task else 0.6,
        reasoning=f"Найдены ключевые слова задач" if is_task else "Обычное сообщение"
    )


async def process_message_with_ai(user_id: int, chat_id: int, message_text: str, user_name: str):
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
        
        # Используем chat_with_tools для определения нужна ли функция create_task
        ai_response, function_call = await openai_service.chat_with_tools(message_text, user_id)
              
        if function_call and function_call.get("function_name") == "create_task":
            # AI определил, что нужно создать задачу
            task_args = function_call.get("arguments", {})
            logger.info(f"Gatekeeper: AI вызвал create_task с аргументами: {task_args}")
            
            # Вызываем функцию создания задачи
            from app.services.tools import create_task
            task_result = create_task(**task_args)
            
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
                        
                await send_telegram_message.send(
                    chat_id=chat_id,
                    text=confirmation_text
                )
            else:
                logger.error(f"Gatekeeper: ошибка создания задачи: {task_result}")
                # В случае ошибки отправляем уведомление об ошибке в Telegram
                from ..shared.tasks import send_telegram_message
                error_text = "❌ Произошла ошибка при создании задачи. Попробуйте еще раз."
                await send_telegram_message.send(
                    chat_id=chat_id,
                    text=error_text
                )
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
        
