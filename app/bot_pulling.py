import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь поиска модулей
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import aiohttp
import logging
import json
from app.core.config import get_settings
from app.schemas.telegram import TelegramUpdate
import redis.asyncio as aioredis


settings = get_settings()
r = aioredis.from_url(settings.redis_url)

# Настраиваем логирование для вывода в консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Telegram Update модели теперь импортируются из app.schemas.telegram


async def run_long_polling():
    """Асинхронный long polling для Telegram бота"""
    settings = get_settings()
    telegram_token = settings.telegram_token

    if not telegram_token or telegram_token == "TEST_TOKEN":
        logger.error("TELEGRAM_TOKEN не установлен или является тестовым")
        return

    offset = 0
    base_url = f"https://api.telegram.org/bot{telegram_token}"

    print(f"Асинхронный long polling запущен с токеном: {telegram_token}")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Делаем запрос к Telegram API
                params = {"offset": offset, "timeout": 25}
                async with session.get(f"{base_url}/getUpdates", params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"Ошибка Telegram API: {resp.status}")
                        await asyncio.sleep(5)
                        continue

                    data = await resp.json()

                    if not data.get("ok") or not data.get("result"):
                        await asyncio.sleep(0.1)
                        continue

                    for update_data in data["result"]:
                        try:
                            # Парсим update
                            update = TelegramUpdate(**update_data)
                            logger.info(f"Получено обновление: {update.update_id}")

                            if update.message:
                                logger.info(f"Сообщение от пользователя {update.message.from_.id if update.message.from_ else 'неизвестен'}: {update.message.text or 'без текста'}")

                                user_id = update.message.from_.id if update.message.from_ else None
                                if user_id is None:
                                    raise Exception("Отсутствует ID пользователя в сообщении")

                                stream = f"agent:{user_id}:stream"
                                message_data = json.dumps(update.message.model_dump(), ensure_ascii=False)
                                await r.xadd(stream, {"message": message_data})

                                # Отправляем сообщение в Gatekeeper для классификации и обработки
                                # process_webhook_message.send(
                                #     update_id=update.update_id,
                                #     message_data=update.message.model_dump()
                                # )

                                # logger.info(f"Сообщение отправлено в очередь Dramatiq для обработки")

                            # Обновляем offset
                            offset = update.update_id + 1

                        except Exception as e:
                            logger.error(f"Ошибка обработки обновления {update_data.get('update_id')}: {e}")
                            continue

                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Ошибка в long polling: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_long_polling())