# services/user_manager.py
"""
Сервис для управления пользователями Final 4.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from models.user import User

from bot.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class UserManager:
    """Менеджер пользователей Final 4"""

    async def get_or_create_user(self, session: AsyncSession, user_id: int,
                                 username: str = None, full_name: str = None) -> User:
        """Получает или создает пользователя"""
        try:
            user = await session.get(User, user_id)
            if not user:
                user = User(
                    id=user_id,
                    username=username,
                    full_name=full_name,
                    rating=1000  # Начальный рейтинг
                )
                session.add(user)

                # Создаем начальную команду для пользователя
                await self._create_initial_team(session, user_id)

                await session.commit()
                logger.info(f"Created new user {user_id}")
            else:
                # Обновляем информацию
                if username and user.username != username:
                    user.username = username
                if full_name and user.full_name != full_name:
                    user.full_name = full_name

            return user

        except Exception as e:
            logger.error(f"Error creating user {user_id}: {e}")
            await session.rollback()
            raise

    async def _create_initial_team(self, session: AsyncSession, user_id: int):
        """Создает начальную команду для пользователя"""
        team = Team(
            user_id=user_id,
            name=f"Команда #{user_id}",
            formation="1-4-4-2",
            players=self._create_initial_players()
        )
        session.add(team)

    def _create_initial_players(self) -> list:
        """Создает начальный состав команды (1-5-6-4)"""
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

    async def get_user_stats(self, session: AsyncSession, user_id: int) -> dict:
        """Получает статистику пользователя"""
        user = await session.get(User, user_id)
        if not user:
            return {}

        team = await session.get(Team, user_id)

        return {
            'user': user,
            'team': team,
            'games_played': user.games_played,
            'games_won': user.games_won,
            'rating': user.rating,
            'win_rate': user.games_won / user.games_played if user.games_played > 0 else 0
        }

    async def update_user_rating(self, session: AsyncSession, user_id: int, rating_change: int):
        """Обновляет рейтинг пользователя"""
        user = await session.get(User, user_id)
        if user:
            user.rating += rating_change
            user.rating = max(100, user.rating)  # Минимальный рейтинг


# Глобальный экземпляр менеджера
user_manager = UserManager()