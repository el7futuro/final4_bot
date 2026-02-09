import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from bot.config import load_config

logger = logging.getLogger(__name__)

# Загрузка конфигурации
config = load_config()

# Создание движка БД
DATABASE_URL = f"postgresql+asyncpg://{config.db.user}:{config.db.password}@" \
               f"{config.db.host}:{config.db.port}/{config.db.database}"

logger.info(f"Подключение к БД: {config.db.host}:{config.db.port}/{config.db.database}")

try:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,  # Поставьте True для отладки SQL запросов
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args={
            "command_timeout": 60,
            "server_settings": {
                "application_name": "final4_bot"
            }
        }
    )

    # Создание фабрики сессий
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    Base = declarative_base()

    logger.info("Движок базы данных создан успешно")

except Exception as e:
    logger.error(f"Ошибка при создании движка БД: {e}")
    raise


async def init_db() -> None:
    """Инициализация базы данных (создание таблиц)"""
    try:
        # Импортируем модели для создания таблиц
        from models.user import User

        from models.match import Match
        from models.card import Card
        from models.bet import Bet
        from models.tournament import Tournament

        async with engine.begin() as conn:
            # Создаем все таблицы
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Таблицы созданы успешно")

        logger.info("✅ База данных успешно инициализирована")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при инициализации БД: {e}")
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при инициализации БД: {e}")
        raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Получение асинхронной сессии БД"""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка в сессии БД: {e}")
        raise
    finally:
        await session.close()


async def check_db_connection() -> bool:
    """Проверка подключения к базе данных"""
    try:
        async with engine.connect() as conn:
            # Вариант 1: Просто выполнить запрос
            await conn.execute(text("SELECT 1"))

            # Или вариант 2: Получить результат
            # result = await conn.execute(text("SELECT 1"))
            # await result.fetchone()

        logger.info("✅ Подключение к базе данных успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе данных: {e}")
        return False



async def close_db() -> None:
    """Корректное закрытие соединения с БД"""
    await engine.dispose()
    logger.info("Соединение с БД закрыто")