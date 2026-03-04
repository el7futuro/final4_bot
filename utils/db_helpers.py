# utils/db_helpers.py
"""
Вспомогательные функции для работы с базой данных.
"""

import json
import logging
from typing import Optional, Tuple, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User

logger = logging.getLogger(__name__)


async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
    update_last_active: bool = False
) -> Optional[User]:
    """
    Получает пользователя по telegram_id.

    Args:
        session: Асинхронная сессия SQLAlchemy
        telegram_id: ID пользователя в Telegram
        update_last_active: Если True — обновляет поле last_active на текущее время

    Returns:
        Объект User или None, если пользователь не найден
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
    """
    Получает пользователя и десериализованные данные его команды.

    Args:
        session: Асинхронная сессия SQLAlchemy
        user_id: ID пользователя в базе (не telegram_id!)

    Returns:
        (User или None, словарь team_data или None)
    """
    try:
        user = await session.get(User, user_id)
        if not user:
            return None, None

        team_data = None
        if user.team_data:
            try:
                # Если в базе строка — парсим JSON
                if isinstance(user.team_data, str):
                    team_data = json.loads(user.team_data)
                else:
                    # Если уже словарь — оставляем как есть
                    team_data = user.team_data
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга team_data пользователя {user_id}: {e}")
                team_data = None

        return user, team_data

    except Exception as e:
        logger.error(f"Ошибка получения пользователя {user_id} с командой: {e}")
        return None, None


async def get_admin_ids(session: AsyncSession) -> List[int]:
    """
    Возвращает список telegram_id всех администраторов.

    Returns:
        Список ID администраторов
    """
    try:
        result = await session.execute(
            select(User.telegram_id).where(User.is_admin == True)
        )
        return [row[0] for row in result.all()]
    except Exception as e:
        logger.error(f"Ошибка получения списка администраторов: {e}")
        return []