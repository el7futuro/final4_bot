# services/game_manager.py
"""
Сервис для управления игровыми процессами Final 4.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from models.user import User
from models.team import Team
from models.match import Match
from services.match_manager import match_manager

logger = logging.getLogger(__name__)


class GameManager:
    """Менеджер игровых процессов Final 4"""

    async def get_user_game_state(self, session: AsyncSession, user_id: int) -> dict:
        """Получает текущее игровое состояние пользователя"""
        try:
            # Получаем пользователя
            user = await session.get(User, user_id)
            if not user:
                return {"error": "Пользователь не найден"}

            # Получаем команду
            team = await session.get(Team, user_id)

            # Получаем активный матч
            active_match = await match_manager.get_active_match(session, user_id)

            return {
                "user": user,
                "team": team,
                "active_match": active_match,
                "has_active_match": active_match is not None
            }

        except Exception as e:
            logger.error(f"Error getting game state for user {user_id}: {e}")
            return {"error": str(e)}

    async def can_start_match(self, session: AsyncSession, user_id: int) -> tuple[bool, str]:
        """Проверяет, может ли пользователь начать матч"""
        try:
            # Проверяем наличие активного матча
            active_match = await match_manager.get_active_match(session, user_id)
            if active_match:
                return False, f"У вас уже есть активный матч #{active_match.id}"

            # Проверяем наличие команды
            team = await session.get(Team, user_id)
            if not team:
                return False, "Сначала создайте команду"

            # Проверяем состав команды (1-5-6-4)
            formation_valid, error_msg = self._validate_team_formation(team)
            if not formation_valid:
                return False, f"Некорректный состав команды: {error_msg}"

            return True, ""

        except Exception as e:
            logger.error(f"Error checking if user can start match: {e}")
            return False, "Ошибка проверки"

    def _validate_team_formation(self, team: Team) -> tuple[bool, str]:
        """Проверяет корректность формации команды (1-5-6-4)"""
        if not team.players:
            return False, "Нет игроков в команде"

        # Подсчитываем игроков по позициям
        counts = {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}

        for player in team.players:
            position = player.get('position', '').upper()
            if position in counts:
                counts[position] += 1

        # Проверяем формацию 1-5-6-4
        if counts['GK'] != 1:
            return False, f"Нужен 1 вратарь (у вас {counts['GK']})"
        if counts['DF'] != 5:
            return False, f"Нужно 5 защитников (у вас {counts['DF']})"
        if counts['MF'] != 6:
            return False, f"Нужно 6 полузащитников (у вас {counts['MF']})"
        if counts['FW'] != 4:
            return False, f"Нужно 4 нападающих (у вас {counts['FW']})"

        return True, ""


# Глобальный экземпляр менеджера
game_manager = GameManager()