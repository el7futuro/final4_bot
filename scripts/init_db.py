# scripts/init_db.py
"""
Скрипт инициализации базы данных.
"""

import asyncio
import logging
from sqlalchemy import text

from bot.database import init_db, engine, Base
from models.user import User
from models.team import Team
from models.match import Match
from models.card import Card, init_cards
from models.bet import Bet
from models.tournament import Tournament, TournamentMatch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def initialize_database():
    """Инициализирует базу данных"""
    try:
        # Создаем таблицы
        logger.info("Creating database tables...")
        await init_db()

        # Создаем карточки "Свисток"
        logger.info("Creating cards...")
        async with engine.begin() as conn:
            await init_cards(conn)

        logger.info("✅ Database initialized successfully!")

    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        raise


async def create_test_data():
    """Создает тестовые данные"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Создаем тестового пользователя
            test_user = User(
                telegram_id=123456789,
                username="test_user",
                first_name="Test",
                last_name="User",
                balance=1000,
                rating=1200
            )
            session.add(test_user)

            # Создаем тестовую команду
            test_team = Team(
                user_id=123456789,
                name="Тестовая команда",
                formation="1-4-4-2",
                players=[
                    {
                        'id': 1, 'position': 'GK', 'name': 'Тест Вратарь', 'number': 1,
                        'skill': {'reflex': 80, 'positioning': 75, 'handling': 78}
                    },
                    # ... остальные игроки
                ]
            )
            session.add(test_team)

            await session.commit()
            logger.info("✅ Test data created successfully!")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Error creating test data: {e}")


async def cleanup_old_data(days: int = 30):
    """Очищает старые данные"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from datetime import datetime, timedelta
    from sqlalchemy import delete

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            # Удаляем старые завершенные матчи
            result = await session.execute(
                delete(Match).where(
                    Match.status == "finished",
                    Match.finished_at < cutoff_date
                )
            )
            deleted_matches = result.rowcount

            await session.commit()
            logger.info(f"✅ Cleaned up {deleted_matches} old matches")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Error cleaning up old data: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "init":
            asyncio.run(initialize_database())
        elif command == "test_data":
            asyncio.run(create_test_data())
        elif command == "cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            asyncio.run(cleanup_old_data(days))
        else:
            print("Usage: python -m scripts.init_db [init|test_data|cleanup]")
    else:
        print("Usage: python -m scripts.init_db [init|test_data|cleanup]")