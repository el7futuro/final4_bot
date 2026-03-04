import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from bot.config import load_config

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Конфигурация и создание движка базы данных
# ──────────────────────────────────────────────────────────────

config = load_config()

DATABASE_URL = (
    f"postgresql+asyncpg://{config.db.user}:{config.db.password}@"
    f"{config.db.host}:{config.db.port}/{config.db.database}"
)

logger.info(f"Подключение к БД: {config.db.host}:{config.db.port}/{config.db.database}")

try:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,  # True для отладки SQL-запросов (в продакшене False)
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args={
            "command_timeout": 60,
            "server_settings": {"application_name": "final4_bot"},
        },
    )

    # Фабрика асинхронных сессий
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    Base = declarative_base()

    logger.info("Движок базы данных создан успешно")

except Exception as e:
    logger.error(f"Ошибка при создании движка БД: {e}")
    raise


# ──────────────────────────────────────────────────────────────
# Функции инициализации и работы с БД
# ──────────────────────────────────────────────────────────────


async def init_db() -> None:
    """
    Инициализация базы данных: создаёт все таблицы, если их ещё нет.

    Примечание:
        - Импортирует все модели перед созданием таблиц, чтобы SQLAlchemy их увидел.
        - Использует `Base.metadata.create_all` — безопасно, не удаляет существующие данные.
    """
    try:
        # Импортируем все модели (SQLAlchemy должен знать о них)
        from models.user import User
        from models.match import Match
        from models.bet import Bet, BetType, BetStatus
        from models.card import Card
        from models.tournament import Tournament

        # Создаём таблицы в транзакции
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Все таблицы созданы или уже существуют")
        logger.info("✅ База данных инициализирована")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при создании таблиц: {e}")
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при инициализации БД: {e}")
        raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Генератор асинхронной сессии для работы с БД.

    Использование:
        async with get_session() as session:
            ...

    Особенности:
        - Автоматически коммитит изменения при успешном завершении блока
        - Откатывает транзакцию при ошибке
        - Всегда закрывает сессию в finally
    """
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
    """
    Проверяет, активно ли соединение с базой данных.

    Возвращает:
        True  — подключение успешно
        False — ошибка подключения

    Примечание:
        Выполняет простой запрос SELECT 1 для проверки.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Подключение к базе данных успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе данных: {e}")
        return False


async def close_db() -> None:
    """
    Корректно закрывает все пулы соединений с базой данных.

    Вызывать при завершении работы приложения.
    """
    await engine.dispose()
    logger.info("Соединение с БД закрыто")