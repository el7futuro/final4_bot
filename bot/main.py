# bot/main.py
import asyncio
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage  # ИЗМЕНИЛИ
from bot.config import load_config

# УБРАЛИ импорты Redis
# from services.redis_client import get_redis, close_redis

# Импортируем роутеры
from handlers.start import router as start_router
from handlers.match import router as match_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


async def main():
    try:
        config = load_config()  # Ваш config.py загрузит все, включая Redis

        # ИСПОЛЬЗУЕМ MemoryStorage вместо RedisStorage
        storage = MemoryStorage()  # ВСЕГО 1 СТРОКА ЗДЕСЬ

        # Инициализация бота
        bot = Bot(token=config.bot.token, parse_mode="HTML")
        dp = Dispatcher(bot=bot, storage=storage)

        # Сохраняем конфиг для доступа в хендлерах
        dp["config"] = config

        # Регистрация роутеров
        dp.include_router(start_router)
        dp.include_router(match_router)

        logger.info("Бот запущен (MemoryStorage)")

        # Удаление вебхука и запуск polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            skip_updates=False
        )

    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал завершения")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
    finally:
        # Закрытие ресурсов (без Redis)
        try:
            await bot.session.close()
        except:
            pass

        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот завершил работу")