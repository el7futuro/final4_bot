# services/user_manager.py
"""
Сервис для управления пользователями Final 4.
"""

from typing import Optional, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

import logging

from models.user import User

logger = logging.getLogger(__name__)


class UserManager:
    """Менеджер пользователей Final 4"""

    async def get_or_create_user(
        self,
        session: AsyncSession,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """
        Получает пользователя по telegram_id или создаёт нового.

        При создании:
        - задаёт начальный рейтинг 1000
        - создаёт стандартную команду 1-5-6-4
        """
        try:
            # Ищем пользователя
            stmt = select(User).where(User.telegram_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                # Создаём нового
                user = User(
                    telegram_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    rating=1000  # Начальный рейтинг
                )
                session.add(user)

                # Создаём начальную команду
                await self._create_initial_team(session, user_id)

                await session.commit()
                await session.refresh(user)

                logger.info(f"Создан новый пользователь {user_id} (@{username or 'без имени'})")

            else:
                # Обновляем актуальные данные из Telegram (если изменились)
                updated = False
                if username is not None and user.username != username:
                    user.username = username
                    updated = True
                if first_name is not None and user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if last_name is not None and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True

                if updated:
                    await session.commit()
                    logger.debug(f"Обновлены данные пользователя {user_id}")

            return user

        except Exception as e:
            logger.error(f"Ошибка при получении/создании пользователя {user_id}: {e}")
            await session.rollback()
            raise

    async def _create_initial_team(self, session: AsyncSession, user_id: int) -> None:
        """
        Создаёт начальный состав команды 1-5-6-4 для нового пользователя.
        Сохраняет в поле team_data модели User.
        """
        players = self._create_initial_players()

        team_data = {
            "formation": "1-5-6-4",
            "players": players
        }

        # Обновляем пользователя
        stmt = (
            update(User)
            .where(User.telegram_id == user_id)
            .values(team_data=team_data)
        )
        await session.execute(stmt)
        await session.commit()

        logger.debug(f"Создана начальная команда для пользователя {user_id}")

    def _create_initial_players(self) -> list:
        """Генерирует стандартный состав команды (1 GK, 5 DF, 6 MF, 4 FW)"""
        players = []

        # Вратарь (1)
        players.append({
            'id': 1,
            'position': 'GK',
            'name': 'Вратарь',
            'number': 1,
        })

        # Защитники (5)
        for i in range(5):
            players.append({
                'id': 2 + i,
                'position': 'DF',
                'name': f'Защитник {i + 1}',
                'number': 2 + i,
            })

        # Полузащитники (6)
        for i in range(6):
            players.append({
                'id': 7 + i,
                'position': 'MF',
                'name': f'Полузащитник {i + 1}',
                'number': 7 + i,
            })

        # Нападающие (4)
        for i in range(4):
            players.append({
                'id': 13 + i,
                'position': 'FW',
                'name': f'Нападающий {i + 1}',
                'number': 13 + i,
            })

        return players

    async def get_user_stats(self, session: AsyncSession, user_id: int) -> Dict:
        """
        Возвращает базовую статистику пользователя.
        """
        try:
            user = await session.get(User, user_id)
            if not user:
                return {}

            games_played = user.games_played or 0
            games_won = user.games_won or 0

            return {
                'games_played': games_played,
                'games_won': games_won,
                'rating': user.rating,
                'win_rate': round(games_won / games_played * 100, 1) if games_played > 0 else 0.0
            }

        except Exception as e:
            logger.error(f"Ошибка получения статистики пользователя {user_id}: {e}")
            return {}

    async def update_user_rating(
        self,
        session: AsyncSession,
        user_id: int,
        rating_change: int
    ) -> None:
        """
        Изменяет рейтинг пользователя.
        Минимальный рейтинг — 100.
        """
        try:
            user = await session.get(User, user_id)
            if user:
                user.rating = max(100, user.rating + rating_change)
                await session.commit()
                logger.debug(f"Рейтинг пользователя {user_id} изменён на {rating_change} → {user.rating}")

        except Exception as e:
            logger.error(f"Ошибка обновления рейтинга пользователя {user_id}: {e}")
            await session.rollback()


# Глобальный экземпляр менеджера
user_manager = UserManager()