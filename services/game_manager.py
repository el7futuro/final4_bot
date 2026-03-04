# services/game_manager.py
"""
Сервис-менеджер игровых процессов Final 4.

Отвечает за:
- проверку возможности начать матч
- получение доступных игроков для ставки
- валидацию и обработку ставок
- работу с дополнительным временем
- расчёт итогового результата матча

Интегрирован с BetValidator и BetTracker.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Tuple, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.user import User
from models.match import Match, MatchStatus
from models.bet_tracker import BetTracker, BetType
from services.bet_validator import bet_validator
from services.match_manager import match_manager   # предполагается, что есть

logger = logging.getLogger(__name__)


class GameManager:
    """
    Центральный менеджер игровых механик Final 4.
    """

    # Константы состава команды
    REQUIRED_FORMATION = {
        'GK': 1,
        'DF': 5,
        'MF': 6,
        'FW': 4
    }

    TOTAL_PLAYERS = 16

    async def get_user_game_state(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Получает текущее игровое состояние пользователя:
        - данные пользователя
        - активный матч (если есть)
        """
        try:
            user = await session.get(User, user_id)
            if not user:
                return {"error": "Пользователь не найден"}

            active_match = await match_manager.get_active_match(session, user_id)

            return {
                "user": user,
                "active_match": active_match,
                "has_active_match": active_match is not None
            }

        except Exception as e:
            logger.error(f"Ошибка получения состояния игры для user {user_id}: {e}")
            return {"error": str(e)}

    async def can_start_match(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Tuple[bool, str]:
        """
        Проверяет, может ли пользователь начать новый матч.

        Возвращает: (можно_начать, причина_если_нельзя)
        """
        try:
            active_match = await match_manager.get_active_match(session, user_id)
            if active_match:
                return False, f"У вас уже есть активный матч #{active_match.id}"

            # Здесь можно добавить другие проверки:
            # - рейтинг
            # - баланс
            # - таймаут после предыдущего матча и т.д.

            return True, ""

        except Exception as e:
            logger.error(f"Ошибка проверки возможности начать матч для {user_id}: {e}")
            return False, "Ошибка проверки"

    def _validate_team_formation(self, team_data: Dict) -> Tuple[bool, str]:
        """
        Проверяет, что команда соответствует требуемой формации 1-5-6-4.
        """
        if not team_data or 'players' not in team_data:
            return False, "Нет данных о команде"

        players = team_data.get('players', [])

        if len(players) != self.TOTAL_PLAYERS:
            return False, f"Нужно ровно {self.TOTAL_PLAYERS} игроков (у вас {len(players)})"

        counts = {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}

        for player in players:
            pos = player.get('position', '').upper()
            if pos in counts:
                counts[pos] += 1
            else:
                return False, f"Неизвестная позиция игрока: {pos}"

        for pos, required in self.REQUIRED_FORMATION.items():
            if counts[pos] != required:
                pos_names = {
                    'GK': 'вратарь',
                    'DF': 'защитников',
                    'MF': 'полузащитников',
                    'FW': 'нападающих'
                }
                return False, f"Нужно {required} {pos_names[pos]} (у вас {counts[pos]})"

        return True, ""

    async def get_available_players(
        self,
        session: AsyncSession,
        match_id: int,
        user_id: int
    ) -> List[Dict]:
        """
        Возвращает список игроков, доступных для ставки в текущем ходе.

        Использует bet_validator.get_available_players — уже включает все проверки.
        """
        try:
            match = await session.get(Match, match_id)
            if not match:
                logger.error(f"Матч {match_id} не найден")
                return []

            if not match.is_player_in_match(user_id):
                logger.error(f"Пользователь {user_id} не участник матча {match_id}")
                return []

            team_data = match.get_player_team_data(user_id)
            if not team_data:
                logger.error(f"Нет данных команды для user {user_id} в матче {match_id}")
                return []

            team_players = team_data.get('players', [])

            # Основная логика делегируется в bet_validator
            available = await bet_validator.get_available_players(
                match=match,
                user_id=user_id,
                all_players=team_players
            )

            return available

        except Exception as e:
            logger.error(f"Ошибка получения доступных игроков для {user_id} в матче {match_id}: {e}")
            return []

    async def validate_bet(
        self,
        session: AsyncSession,
        match_id: int,
        user_id: int,
        player_id: int,
        player_position: str,
        bet_type: BetType,
        bet_value: str,
        is_second_bet: bool = False
    ) -> Tuple[bool, str]:
        """
        Полная валидация ставки перед её регистрацией.

        Проверяет:
        - ход пользователя
        - доступность игрока
        - допустимость типа и значения ставки
        - квоты BetTracker
        """
        try:
            match = await session.get(Match, match_id)
            if not match:
                return False, "Матч не найден"

            if match.get_current_user_id() != user_id:
                return False, "Сейчас не ваш ход"

            team_data = match.get_player_team_data(user_id)
            if not team_data:
                return False, "Данные команды не найдены"

            player = next((p for p in team_data.get('players', []) if p.get('id') == player_id), None)
            if not player:
                return False, "Игрок не найден в вашей команде"

            # Делегируем основную проверку в bet_validator
            # (можно расширить дополнительными проверками)
            tracker = match.bet_tracker

            if bet_type == BetType.EVEN_ODD:
                can, msg = tracker.can_bet_EVEN_ODD(player_id, player_position)
            elif bet_type == BetType.BIG_SMALL:
                can, msg = tracker.can_bet_big_small(player_id, player_position, is_second_bet)
            elif bet_type == BetType.GOAL:
                can, msg = tracker.can_bet_goal(player_position, player_id)
            else:
                return False, "Неизвестный тип ставки"

            if not can:
                return False, msg

            # Дополнительно проверяем значение ставки
            if bet_type == BetType.EVEN_ODD:
                if bet_value not in ("чёт", "нечёт"):
                    return False, "Неверное значение для Чёт/Нечёт"
            elif bet_type == BetType.BIG_SMALL:
                if bet_value not in ("меньше", "больше"):
                    return False, "Неверное значение для Больше/Меньше"
            elif bet_type == BetType.GOAL:
                if bet_value not in ("1","2","3","4","5","6"):
                    return False, "Неверное значение для точного числа"

            return True, ""

        except Exception as e:
            logger.error(f"Ошибка валидации ставки в матче {match_id}: {e}")
            return False, f"Ошибка проверки: {str(e)}"

    async def process_bet(
        self,
        session: AsyncSession,
        match_id: int,
        user_id: int,
        player_id: int,
        bet_type: BetType,
        bet_value: str
    ) -> Tuple[bool, str, Dict]:
        """
        Регистрирует ставку в BetTracker и сохраняет изменения.
        """
        try:
            match = await session.get(Match, match_id)
            if not match:
                return False, "Матч не найден", {}

            if match.get_current_user_id() != user_id:
                return False, "Сейчас не ваш ход", {}

            team_data = match.get_player_team_data(user_id)
            if not team_data:
                return False, "Данные команды не найдены", {}

            player = next((p for p in team_data.get('players', []) if p.get('id') == player_id), None)
            if not player:
                return False, "Игрок не найден", {}

            position = player.get('position')

            # Регистрируем в трекере
            tracker = match.bet_tracker
            tracker.register_bet(player_id, position, bet_type, bet_value)
            match.bet_tracker = tracker

            await session.commit()

            return True, "Ставка принята", {
                'player_id': player_id,
                'position': position,
                'bet_type': bet_type.value,
                'bet_value': bet_value
            }

        except Exception as e:
            logger.error(f"Ошибка обработки ставки в матче {match_id}: {e}")
            await session.rollback()
            return False, f"Ошибка обработки ставки: {str(e)}", {}

    async def get_extra_time_players(
        self,
        session: AsyncSession,
        match_id: int,
        user_id: int
    ) -> List[Dict]:
        """
        Возвращает игроков, доступных для выбора в дополнительное время:
        те, кто НЕ делал ставок в основном времени.
        """
        try:
            match = await session.get(Match, match_id)
            if not match:
                return []

            team_data = match.get_player_team_data(user_id)
            if not team_data:
                return []

            team_players = team_data.get('players', [])
            tracker = match.bet_tracker

            extra = []
            for player in team_players:
                pid = player.get('id')
                if tracker.get_player_bet_count(pid) == 0:
                    extra.append(player)

            return extra

        except Exception as e:
            logger.error(f"Ошибка получения запасных для ДВ в матче {match_id}: {e}")
            return []

    async def validate_extra_time_selection(
        self,
        session: AsyncSession,
        match_id: int,
        user_id: int,
        selected_player_ids: List[int]
    ) -> Tuple[bool, str]:
        """
        Проверяет корректность выбора 5 игроков для дополнительного времени.
        """
        try:
            match = await session.get(Match, match_id)
            if not match:
                return False, "Матч не найден"

            team_data = match.get_player_team_data(user_id)
            if not team_data:
                return False, "Данные команды не найдены"

            team_players = team_data.get('players', [])

            return bet_validator.check_extra_time_players(
                match=match,
                user_id=user_id,
                selected_ids=selected_player_ids,
                all_players=team_players
            )

        except Exception as e:
            logger.error(f"Ошибка проверки выбора ДВ в матче {match_id}: {e}")
            return False, f"Ошибка проверки: {str(e)}"

    def calculate_match_result(
        self,
        player1_actions: Dict[str, int],
        player2_actions: Dict[str, int]
    ) -> Tuple[int, int, str]:
        """
        Рассчитывает итоговый счёт матча по накопленным действиям.
        """
        return bet_validator.calculate_match_result(player1_actions, player2_actions)


# Глобальный экземпляр
game_manager = GameManager()