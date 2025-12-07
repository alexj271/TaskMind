"""
Dramatiq задачи для Gatekeeper Worker.
Определяет доступ пользователя к чату через проверку и установку таймзоны.
"""
from pathlib import Path
import dramatiq
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from app.core.config import get_settings
from app.core.dramatiq_setup import redis_broker
from app.services.openai_tools import OpenAIService
from app.utils.prompt_manager import get_prompt
from app.utils.datetime_parser import detect_timezone
from app.repositories.user_repository import UserRepository
from app.repositories.dialog_repository import DialogRepository
from app.services.telegram_client import send_message as telegram_send_message
from app.services.redis_client import get_timezone_setup_flag, set_timezone_setup_flag, clear_timezone_setup_flag
from .models import IncomingMessage
from ..chat.tasks import process_chat_message
from app.core.db import init_db



logger = logging.getLogger(__name__)

# OpenAI сервис будет инициализирован в функции
openai_service = None

# Инструмент для определения таймзоны из сообщения пользователя
timezone_tool = [
    {
        "name": "create_timezone",
        "description": "Определяет и возвращает таймзону на основе текста сообщения.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": { "type": "string", "description": "Таймзона в формате IANA (например, Europe/Moscow)" },
                "city": { "type": "string", "description": "Город на английском для определения таймзоны" },
                "error": {
                    "type": "string",
                    "description": "Заполняется только если невозможно определить таймзону из сообщения"
                }
            }
        }
    }
]


# Удаляем старые функции - теперь gatekeeper только управляет доступом через таймзону


async def process_timezone_message(incoming_msg: IncomingMessage) -> Tuple[bool, Optional[str]]:
    """
    Обрабатывает сообщение для установки таймзоны с помощью AI.
    
    Args:
        incoming_msg: Входящее сообщение
        
    Returns:
        Tuple[bool, Optional[str]]: (успех, установленная таймзона или ошибка)
    """
    try:
        # Инициализируем OpenAI сервис
        settings = get_settings()
        openai_service = OpenAIService(settings.gpt_model_fast)
        
        logger.info(f"Gatekeeper: определяем таймзону из сообщения пользователя {incoming_msg.user_id}: '{incoming_msg.message_text[:50]}...'")
        
        timezone_prompt = get_prompt(
            prompt_name="timezone_parse",
            template_dir=str(Path(__file__).parent / "prompts"),
            current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        message_list = [
            {"role": "user", "content": incoming_msg.message_text}
        ]      
        
        ai_response, function_call = await openai_service.chat_with_tools(
            message_list,
            incoming_msg.user_id,
            system_prompt=timezone_prompt,
            tools=timezone_tool
        )

        logger.debug(f"Gatekeeper: AI ответ для определения таймзоны: {ai_response}, вызов функции: {function_call}")
              
        if function_call and function_call.get("function_name") == "create_timezone":
            timezone_args = function_call.get("arguments", {})
            logger.info(f"Gatekeeper: AI определил таймзону с аргументами: {timezone_args}")
            
            timezone = timezone_args.get("timezone", "").strip()
            city = timezone_args.get("city", "").strip() 
            error = timezone_args.get("error", "").strip()
            
            # Пытаемся определить таймзону используя все доступные параметры
            final_timezone = None
            
            try:
                # Используем универсальный метод detect_timezone со всеми параметрами
                final_timezone = await detect_timezone(
                    city=city if city else None,
                    timezone_str=timezone if timezone else None,
                    current_time=None  # Можно добавить извлечение времени из сообщения
                )
                
                if final_timezone:
                    params_used = []
                    if city: params_used.append(f"город: {city}")
                    if timezone: params_used.append(f"таймзона: {timezone}")
                    logger.info(f"Gatekeeper: определена таймзона '{final_timezone}' по параметрам: {', '.join(params_used)}")
                    
            except Exception as detect_error:
                logger.warning(f"Gatekeeper: ошибка detect_timezone: {detect_error}")
                final_timezone = None
            
            if final_timezone:    
                # Обновляем таймзону пользователя в базе
                user_repo = UserRepository()
                user = await user_repo.update_by_telegram(incoming_msg.user_id, timezone=final_timezone)
                if user:
                    logger.info(f"Gatekeeper: таймзона пользователя {incoming_msg.user_id} установлена на {final_timezone}")
                    return True, final_timezone
                else:
                    logger.error(f"Gatekeeper: не удалось обновить пользователя {incoming_msg.user_id}")
                    return False, "Не удалось обновить пользователя в базе данных"
            elif error:
                logger.info(f"Gatekeeper: AI не смог определить таймзону: {error}")
                return False, error
            else:
                city_info = f" (город: {city})" if city else ""
                logger.error(f"Gatekeeper: неверные аргументы от AI: {timezone_args}")
                return False, f"Не удалось определить таймзону{city_info}. Попробуйте указать крупный город или таймзону в формате 'Europe/Moscow'"
        else:           
            logger.info(f"Gatekeeper: AI не вызвал функцию определения таймзоны")
            return False, "Не удалось определить таймзону из вашего сообщения"
        
    except Exception as e:      
        logger.error(f"Gatekeeper: ошибка определения таймзоны для пользователя {incoming_msg.user_id}: {str(e)}")
        return False, f"Произошла ошибка при обработке: {str(e)}"
        

async def process_webhook_message_internal(update_id: int, message_data: Dict[str, Any]):
    """
    Gatekeeper: проверяет доступ пользователя к чату через валидацию таймзоны.
    Если таймзона установлена - пересылает в chat worker, иначе - устанавливает таймзону.
    """
    try:
        logger.info(f"Gatekeeper: проверяем доступ для сообщения update_id={update_id}")
        
        # Создаем объект входящего сообщения
        incoming_msg = IncomingMessage(
            update_id=update_id,
            user_id=message_data.get("from", {}).get("id", 0),
            chat_id=message_data.get("chat", {}).get("id", 0),
            message_text=message_data.get("text", ""),
            user_name=message_data.get("from", {}).get("first_name", "Unknown"),
            timestamp=datetime.utcnow()
        )
               
        # Получение/создание пользователя
        user_repo = UserRepository()
        user = await user_repo.get_by_telegram(incoming_msg.user_id)
        if user is None:
            user = await user_repo.create(
                incoming_msg.user_id, 
                chat_id=incoming_msg.chat_id, 
                username=incoming_msg.user_name
            )
            logger.info(f"Gatekeeper: создан новый пользователь {incoming_msg.user_id}")
        
        # Сохраняем сообщение в историю диалога
        dialog_repo = DialogRepository()
        dialog_session = await dialog_repo.get_or_create_for_user(user)
        await dialog_repo.add_message_to_session(dialog_session, incoming_msg.message_text, "user")
        
        # Проверяем флаг ожидания установки таймзоны
        timezone_setup_flag = await get_timezone_setup_flag(incoming_msg.user_id)
        
        if timezone_setup_flag:
            # Пользователь в режиме установки таймзоны
            logger.info(f"Gatekeeper: пользователь {incoming_msg.user_id} устанавливает таймзону")
            
            success, result = await process_timezone_message(incoming_msg)
            
            if success:
                # Таймзона установлена - разрешаем доступ к чату
                await clear_timezone_setup_flag(incoming_msg.user_id)
                response_text = f"✅ Таймзона установлена: {result}. Теперь вы можете создавать задачи и общаться со мной!"
                await telegram_send_message(incoming_msg.chat_id, response_text)
                await dialog_repo.add_message_to_session(dialog_session, response_text, "assistant")
                
                logger.info(f"Gatekeeper: пользователь {incoming_msg.user_id} получил доступ к чату")
            else:
                # Не удалось установить таймзону - остаемся в режиме установки
                response_text = f"❌ Не удалось определить таймзону: {result}. " \
                              "Попробуйте указать ваш город или текущее время."
                await telegram_send_message(incoming_msg.chat_id, response_text)
                await dialog_repo.add_message_to_session(dialog_session, response_text, "assistant")
                
        elif not user.timezone:
            # У пользователя нет таймзоны - запрашиваем установку
            logger.info(f"Gatekeeper: пользователь {incoming_msg.user_id} без таймзоны, запрашиваем установку")
            
            await set_timezone_setup_flag(incoming_msg.user_id)
            
            welcome_text = "👋 Привет! Для работы с задачами мне нужно знать ваш часовой пояс.\n" \
                          "📍 Напишите название вашего города или текущее время на ваших часах."
            await telegram_send_message(incoming_msg.chat_id, welcome_text)
            await dialog_repo.add_message_to_session(dialog_session, welcome_text, "assistant")
        else:        
            # У пользователя есть таймзона - передаем в chat worker
            logger.info(f"Gatekeeper: пользователь {incoming_msg.user_id} имеет таймзону {user.timezone}, пересылаем в чат")
            
            # Отправляем в chat worker для полноценной обработки
            process_chat_message.send(
                user_id=incoming_msg.user_id,
                chat_id=incoming_msg.chat_id,
                message_text=incoming_msg.message_text,
                user_name=incoming_msg.user_name
            )
                
        logger.info(f"Gatekeeper: сообщение update_id={update_id} обработано")
            
    except Exception as e:
        logger.error(f"Gatekeeper: ошибка обработки сообщения update_id={update_id}: {str(e)}")
        raise


@dramatiq.actor(max_retries=3, min_backoff=1000, max_backoff=30000)
async def process_webhook_message(update_id: int, message_data: Dict[str, Any]):
    """
    Главная точка входа для всех webhook сообщений.
    Логирует историю сообщений и запускает классификацию.
    
    Args:
        update_id: ID обновления от Telegram
        message_data: Данные сообщения в формате словаря
    """
    print(f"Gatekeeper: получено сообщение update_id={update_id}", message_data)

    # Инициализируем Tortoise ORM для воркера
    await init_db()    
    
    try:
        await process_webhook_message_internal(update_id, message_data)
    finally:
        # Закрываем соединения после обработки
        from tortoise import Tortoise
        await Tortoise.close_connections()
