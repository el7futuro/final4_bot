# services/game_manager.py
"""
Сервис для управления игровыми процессами Final 4.
Обновленная версия с интеграцией BetValidator.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from typing import List, Dict, Tuple, Optional

from models.user import User
from models.match import Match, MatchStatus
from models.bet_tracker import BetTracker, BetType
from services.bet_validator import bet_validator
from services.match_manager import match_manager

logger = logging.getLogger(__name__)


class GameManager:
    """Менеджер игровых процессов Final 4 с проверкой ставок"""

    # Константа - состав команды по умолчанию
    REQUIRED_FORMATION = {
        'GK': 1,  # 1 вратарь
        'DF': 5,  # 5 защитников
        'MF': 6,  # 6 полузащитников
        'FW': 4  # 4 форварда
    }

    # Всего 16 игроков
    TOTAL_PLAYERS = 16

    async def get_user_game_state(self, session: AsyncSession, user_id: int) -> dict:
        """Получает текущее игровое состояние пользователя"""
        try:
            # Получаем пользователя
            user = await session.get(User, user_id)
            if not user:
                return {"error": "Пользователь не найден"}

            # Получаем активный матч
            active_match = await match_manager.get_active_match(session, user_id)

            return {
                "user": user,
                "active_match": active_match,
                "has_active_match": active_match is not None
            }

        except Exception as e:
            logger.error(f"Error getting game state for user {user_id}: {e}")
            return {"error": str(e)}

    async def can_start_match(self, session: AsyncSession, user_id: int) -> Tuple[bool, str]:
        """Проверяет, может ли пользователь начать матч"""
        try:
            # Проверяем наличие активного матча
            active_match = await match_manager.get_active_match(session, user_id)
            if active_match:
                return False, f"У вас уже есть активный матч #{active_match.id}"




        except Exception as e:
            logger.error(f"Error checking if user can start match: {e}")
            return False, "Ошибка проверки"

    def _validate_team_formation(self, team_data: dict) -> Tuple[bool, str]:
        """Проверяет корректность формации команды (1-5-6-4)"""
        if not team_data or 'players' not in team_data:
            return False, "Нет данных о команде"

        players = team_data.get('players', [])

        if len(players) != self.TOTAL_PLAYERS:
            return False, f"Нужно {self.TOTAL_PLAYERS} игроков (у вас {len(players)})"

        # Подсчитываем игроков по позициям
        counts = {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}

        for player in players:
            position = player.get('position', '').upper()
            if position in counts:
                counts[position] += 1
            else:
                return False, f"Неизвестная позиция: {position}"

        # Проверяем формацию 1-5-6-4
        for position, required in self.REQUIRED_FORMATION.items():
            if counts[position] != required:
                pos_names = {'GK': 'вратарей', 'DF': 'защитников', 'MF': 'полузащитников', 'FW': 'нападающих'}
                return False, f"Нужно {required} {pos_names[position]} (у вас {counts[position]})"

        return True, ""

    async def get_available_players(
            self,
            session: AsyncSession,
            match_id: int,
            user_id: int
    ) -> List[Dict]:
        """
        Возвращает доступных для ставки игроков с учетом всех ограничений.

        Args:
            session: Сессия БД
            match_id: ID матча
            user_id: ID пользователя

        Returns:
            Список доступных игроков
        """
        try:
            # Получаем матч
            match = await session.get(Match, match_id)
            if not match:
                logger.error(f"Match {match_id} not found")
                return []

            # Проверяем, что это матч пользователя
            if match.player1_id != user_id and match.player2_id != user_id:
                logger.error(f"User {user_id} is not in match {match_id}")
                return []

            # Получаем данные команды пользователя ИЗ МАТЧА
            team_data = match.get_player_team_data(user_id)
            if not team_data:
                logger.error(f"User {user_id} has no team data in match {match_id}")
                return []

            team_players = team_data.get('players', [])

            # ДОБАВЬТЕ DEBUG PRINT ЗДЕСЬ:
            print(f"DEBUG get_available_players: user_id={user_id}, match_id={match_id}")
            print(f"DEBUG: player1_id={match.player1_id}, player2_id={match.player2_id}")
            print(f"DEBUG: team_data exists? {bool(team_data)}")
            print(f"DEBUG: team_players count={len(team_players)}")
            print(f"DEBUG: Positions in team: {[p.get('position') for p in team_players]}")
            print(f"DEBUG: GK players: {[p for p in team_players if p.get('position') == 'GK']}")

            # Используем BetValidator для получения доступных игроков
            available_players = await bet_validator.get_available_players(
                match, user_id, team_players
            )

            logger.info(f"Found {len(available_players)} available players for user {user_id} in match {match_id}")
            return available_players

        except Exception as e:
            logger.error(f"Error getting available players for user {user_id} in match {match_id}: {e}")
            return []
    async def get_available_bet_types(
            self,
            match: Match,
            player_id: int,
            position: str,
            is_second_bet: bool = False
    ) -> List[Tuple[str, str, List[str]]]:
        """
        Возвращает доступные типы ставок для игрока с русскими названиями.

        Args:
            match: Объект матча
            player_id: ID игрока
            position: Позиция игрока
            is_second_bet: Это вторая ставка?

        Returns:
            Список кортежей (type_id, название_рус, список_значений)
        """
        try:
            available = bet_validator.get_available_bet_types_with_names(
                match, player_id, position, is_second_bet
            )

            # Преобразуем BetType в строки для удобства
            result = []
            for bet_type, name, values in available:
                result.append((
                    bet_type.value,  # 'even_odd', 'big_small', 'goal'
                    name,
                    values
                ))

            return result

        except Exception as e:
            logger.error(f"Error getting available bet types for player {player_id}: {e}")
            return []

    async def validate_player_selection(
            self,
            session: AsyncSession,
            match_id: int,
            user_id: int,
            player_id: int
    ) -> Tuple[bool, str]:
        """
        Проверяет выбор игрока для ставки.

        Args:
            session: Сессия БД
            match_id: ID матча
            user_id: ID пользователя
            player_id: ID выбранного игрока

        Returns:
            (валидно, сообщение_об_ошибке)
        """
        try:
            # Получаем матч
            match = await session.get(Match, match_id)
            if not match:
                return False, "Матч не найден"

            # Проверяем, что это матч пользователя
            if match.player1_id != user_id and match.player2_id != user_id:
                return False, "Вы не участвуете в этом матче"

            # Получаем данные команды пользователя ИЗ МАТЧА
            team_data = match.get_player_team_data(user_id)  # ← ИЗМЕНЕНО
            if not team_data:
                return False, "Данные команды не найдены"

            # Находим игрока в команде
            team_players = team_data.get('players', [])  # ← ИЗМЕНЕНО
            player = next((p for p in team_players if p.get('id') == player_id), None)

            if not player:
                return False, "Игрок не найден в вашей команде"

            # Используем BetValidator для проверки
            is_valid, message = await bet_validator.validate_player_selection(
                match, user_id, player_id, player.get('position'), team_players
            )

            return is_valid, message

        except Exception as e:
            logger.error(f"Error validating player selection: {e}")
            return False, f"Ошибка проверки: {str(e)}"

    async def validate_bet(
            self,
            match: Match,
            player_id: int,
            position: str,
            bet_type_str: str,
            bet_value: str,  # Может быть пустым при выборе типа
            is_second_bet: bool = False
    ) -> Tuple[bool, str]:
        """
        Проверяет ставку на корректность.

        Args:
            match: Объект матча
            player_id: ID игрока
            position: Позиция игрока
            bet_type_str: Тип ставки (строка)
            bet_value: Значение ставки (может быть пустым при проверке типа)
            is_second_bet: Это вторая ставка?

        Returns:
            (валидно, сообщение_об_ошибке)
        """
        try:
            # Преобразуем строку в BetType
            bet_type = None
            for bt in BetType:
                if bt.value == bet_type_str:
                    bet_type = bt
                    break

            if not bet_type:
                return False, f"Неизвестный тип ставки: {bet_type_str}"

            # Если значение не пустое - проверяем его
            if bet_value and not bet_validator._is_valid_bet_value(bet_type, bet_value):
                return False, f"Некорректное значение ставки: {bet_value}"

            # Используем BetValidator для проверки типа ставки
            # Передаем bet_value (может быть пустым)
            is_valid, message = bet_validator.validate_bet_type(
                match, player_id, position, bet_type, bet_value, is_second_bet
            )

            return is_valid, message

        except Exception as e:
            logger.error(f"Error validating bet: {e}")
            return False, f"Ошибка проверки ставки: {str(e)}"

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
        Обрабатывает ставку игрока.

        Returns:
            (успех, сообщение, данные_результата)
        """
        try:
            # Получаем матч
            match = await session.get(Match, match_id)
            if not match:
                return False, "Матч не найден", {}

            # Проверяем, что это ход пользователя
            current_user_id = match.get_current_user_id()
            if current_user_id != user_id:
                return False, "Сейчас не ваш ход", {}

            # Получаем данные игрока ИЗ МАТЧА
            team_data = match.get_player_team_data(user_id)  # ← ИЗМЕНЕНО
            if not team_data:
                return False, "Данные команды не найдены", {}

            team_players = team_data.get('players', [])  # ← ИЗМЕНЕНО
            player = next((p for p in team_players if p.get('id') == player_id), None)

            if not player:
                return False, "Игрок не найден", {}

            position = player.get('position')

            # Регистрируем ставку в трекере
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
            logger.error(f"Error processing bet: {e}")
            await session.rollback()
            return False, f"Ошибка обработки ставки: {str(e)}", {}

    async def get_extra_time_players(
            self,
            session: AsyncSession,
            match_id: int,
            user_id: int
    ) -> List[Dict]:
        """
        Возвращает игроков, доступных для дополнительного времени.
        Только те, кто не делал ставок в основном времени.
        """
        try:
            # Получаем матч
            match = await session.get(Match, match_id)
            if not match:
                return []

            # Получаем данные команды пользователя
            user = await session.get(User, user_id)
            if not user or not user.team_data:
                return []

            team_players = user.team_data.get('players', [])
            tracker = match.bet_tracker

            # Фильтруем игроков без ставок
            extra_players = []
            for player in team_players:
                player_id = player.get('id')
                if tracker.get_player_bet_count(player_id) == 0:
                    extra_players.append(player)

            return extra_players

        except Exception as e:
            logger.error(f"Error getting extra time players: {e}")
            return []

    async def validate_extra_time_selection(
            self,
            session: AsyncSession,
            match_id: int,
            user_id: int,
            selected_player_ids: List[int]
    ) -> Tuple[bool, str]:
        """
        Проверяет выбор игроков для дополнительного времени.
        """
        try:
            # Получаем матч
            match = await session.get(Match, match_id)
            if not match:
                return False, "Матч не найден"

            # Получаем данные команды пользователя
            user = await session.get(User, user_id)
            if not user or not user.team_data:
                return False, "Данные команды не найдены"

            team_players = user.team_data.get('players', [])

            # Используем BetValidator
            is_valid, message = bet_validator.check_extra_time_players(
                match, user_id, selected_player_ids, team_players
            )

            return is_valid, message

        except Exception as e:
            logger.error(f"Error validating extra time selection: {e}")
            return False, f"Ошибка проверки: {str(e)}"

    def calculate_match_result(
            self,
            player1_actions: Dict,
            player2_actions: Dict
    ) -> Tuple[int, int, str]:
        """
        Рассчитывает результат матча.

        Returns:
            (голы_игрока1, голы_игрока2, описание_расчета)
        """
        return bet_validator.calculate_match_result(player1_actions, player2_actions)


# Глобальный экземпляр менеджера
game_manager = GameManager()