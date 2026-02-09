# utils/db_helpers.py
"""
Хелперы для работы с базой данных.
"""
import json
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Tuple, Optional, List

from models.user import User
logger = logging.getLogger(__name__)


async def get_user_by_telegram_id(
        session: AsyncSession,
        telegram_id: int,
        update_last_active: bool = False
) -> Optional[User]:
    """
    Получить пользователя по telegram_id.

    Args:
        session: Асинхронная сессия SQLAlchemy
        telegram_id: ID пользователя в Telegram
        update_last_active: Обновить ли время последней активности

    Returns:
        Объект User или None если не найден
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user and update_last_active:
        user.last_active = func.now()

    return user


async def get_user_with_team(
        session: AsyncSession,
        user_id: int
) -> Tuple[Optional[User], Optional[dict]]:
    """Получает пользователя и его команду."""
    try:
        user = await session.get(User, user_id)
        if not user:
            return None, None

        team_data = None
        if user.team_data:
            try:
                if isinstance(user.team_data, str):
                    team_data = json.loads(user.team_data)
                else:
                    team_data = user.team_data
            except json.JSONDecodeError:
                team_data = None

        return user, team_data
    except Exception as e:
        logger.error(f"Error getting user with team: {e}")
        return None, None




async def get_admin_ids(session: AsyncSession) -> List[int]:
    """
    Получить список ID администраторов.

    Returns:
        Список telegram_id администраторов
    """
    result = await session.execute(
        select(User.telegram_id).where(User.is_admin == True)
    )
    return [row[0] for row in result.all()]