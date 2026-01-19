# scripts/create_admin.py
"""
Создание администратора бота.
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from bot.database import engine
from models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_admin(telegram_id: int, username: str, first_name: str):
    """Создает администратора"""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Проверяем, существует ли уже пользователь
            existing_user = await session.get(User, telegram_id)

            if existing_user:
                logger.info(f"✅ User {telegram_id} already exists")
                return existing_user

            # Создаем администратора
            admin = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name="Admin",
                balance=10000,
                rating=1500
            )

            session.add(admin)
            await session.commit()

            logger.info(f"✅ Admin created: {telegram_id} - @{username}")
            return admin

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Error creating admin: {e}")
            return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 4:
        telegram_id = int(sys.argv[1])
        username = sys.argv[2]
        first_name = sys.argv[3]

        asyncio.run(create_admin(telegram_id, username, first_name))
    else:
        print("Usage: python -m scripts.create_admin <telegram_id> <username> <first_name>")
        print("Example: python -m scripts.create_admin 123456789 admin_user Admin")