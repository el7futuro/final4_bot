# tests/conftest.py
import sys
import os
import pytest
import asyncio
from typing import AsyncGenerator

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Фикстура для event loop
@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для асинхронных тестов"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Фикстура для конфигурации
@pytest.fixture(scope="session")
def config():
    """Фикстура для загрузки конфигурации"""
    from bot.config import load_config
    return load_config()


# Фикстура для подключения к базе данных
@pytest.fixture(scope="function")
async def db_connection(config):
    """Фикстура для подключения к БД через asyncpg"""
    import asyncpg
    conn = await asyncpg.connect(
        host=config.db.host,
        port=config.db.port,
        user=config.db.user,
        password=config.db.password,
        database=config.db.database
    )
    yield conn
    await conn.close()


# Фикстура для SQLAlchemy сессии
@pytest.fixture(scope="function")
async def db_session():
    """Фикстура для SQLAlchemy сессии"""
    from bot.database import AsyncSessionLocal, close_db
    async with AsyncSessionLocal() as session:
        yield session
    await close_db()