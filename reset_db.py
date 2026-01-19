# reset_db.py
import asyncio
import logging
from bot.database import engine, Base, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def reset_database():
    """Удалить и пересоздать все таблицы"""
    try:
        logger.warning("⚠️ УДАЛЕНИЕ ВСЕХ ТАБЛИЦ И ДАННЫХ!")

        # Удаляем все таблицы
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("✅ Все таблицы удалены")

        # Создаем таблицы заново
        await init_db()
        logger.info("✅ Таблицы созданы заново с актуальной структурой")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(reset_database())