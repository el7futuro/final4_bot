# services/bet_validator.py
"""
Валидатор ставок с учетом всех ограничений и стратегических проверок для Final 4.
Проверяет доступность игроков, типы ставок и стратегию на будущие ходы.
"""

from typing import List, Dict, Tuple, Optional, Set
from models.bet_tracker import BetTracker, BetType
from models.match import Match
import logging
import copy

logger = logging.getLogger(__name__)


class BetValidator:
    """Валидатор ставок с проверкой стратегии на несколько ходов вперед."""

    @staticmethod
    async def validate_player_selection(
            match: Match,
            user_id: int,
            player_id: int,
            player_position: str,
            all_players: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Основная проверка выбора игрока.

        Проверяет:
        1. Может ли игрок ставить в этом ходе
        2. Можно ли сделать на него 2 разные ставки (кроме вратаря)
        3. Не приведет ли выбор к проблемам в будущих ходах
        """
        tracker = match.bet_tracker

        # 1. Базовая проверка доступности
        can_bet, reason = tracker.can_bet_on_player(
            player_id, player_position, match.current_turn
        )
        if not can_bet:
            return False, reason



        # 3. Проверка стратегии на будущие ходы (только для основного времени)
        if not tracker.is_extra_time and match.current_turn < 11:
            strategic_ok, strategic_msg = await BetValidator.check_future_strategy(
                match, user_id, player_id, all_players
            )
            if not strategic_ok:
                return False, strategic_msg

        return True, ""

    @staticmethod
    async def get_available_players(
            match: Match,
            user_id: int,
            all_players: List[Dict]
    ) -> List[Dict]:
        tracker = match.bet_tracker
        available_players = []

        for player in all_players:
            print(f"DEBUG bet_validator: checking player {player['id']} ({player['position']})")

            # Проверяем базовую доступность
            can_bet, reason = tracker.can_bet_on_player(
                player['id'], player['position'], match.current_turn
            )
            print(f"DEBUG: can_bet_on_player = {can_bet}, reason = {reason}")

            if not can_bet:
                continue



            # Проверяем стратегию (только для основного времени)
            if not tracker.is_extra_time and match.current_turn < 11:
                strategic_ok, reason3 = await BetValidator.check_future_strategy(
                    match, user_id, player['id'], all_players
                )
                print(f"DEBUG: strategic_ok = {strategic_ok}, reason = {reason3}")
                if not strategic_ok:
                    continue

            available_players.append(player)
            print(f"DEBUG: player {player['id']} ADDED to available")

        print(f"DEBUG: Total available players = {len(available_players)}")
        return available_players


    @staticmethod
    async def check_future_strategy(
            match: Match,
            user_id: int,
            selected_player_id: int,
            all_players: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Проверяет стратегию на будущие ходы.

        Симулирует выбор игрока и проверяет, останутся ли доступные игроки
        в следующих ходах.
        """
        tracker = match.bet_tracker

        # Создаем глубокую копию трекера для симуляции
        sim_tracker = copy.deepcopy(tracker)
        selected_player = next(
            (p for p in all_players if p['id'] == selected_player_id), None
        )

        if not selected_player:
            return False, "Игрок не найден"

        # Симулируем 2 ставки на выбранного игрока (максимум, что можно)
        BetValidator._simulate_two_bets(
            sim_tracker, selected_player_id, selected_player['position']
        )

        # Проверяем доступность в будущих ходах
        for future_turn in range(match.current_turn + 1, 12):  # Ходы до 11
            sim_tracker.current_turn = future_turn

            available_players = BetValidator._count_available_players(
                sim_tracker, all_players, future_turn
            )

            if available_players == 0:
                return False, (
                    f"СТРАТЕГИЧЕСКАЯ ОШИБКА: Выбор этого игрока приведет к тому, что "
                    f"в ходе {future_turn} не будет доступных игроков. "
                    f"Выберите другого игрока."
                )

        return True, ""

    @staticmethod
    def _simulate_two_bets(tracker: BetTracker, player_id: int, position: str):
        """Симулирует максимальное количество ставок на игрока для проверки стратегии."""
        # Получаем доступные типы для первой ставки
        available_first = tracker.get_available_bet_types(player_id, position, False)

        if not available_first:
            return

        # Берем первый доступный тип
        first_bet = available_first[0]
        tracker.register_bet(player_id, position, first_bet, "симуляция")

        # Вратарь может сделать только одну ставку
        if position == 'GK':
            return

        # Для остальных: пытаемся сделать вторую ставку
        available_second = tracker.get_available_bet_types(player_id, position, True)

        # Ищем тип, отличный от первого
        second_options = [b for b in available_second if b != first_bet]
        if second_options:
            second_bet = second_options[0]
            tracker.register_bet(player_id, position, second_bet, "симуляция")

    @staticmethod
    def _count_available_players(
            tracker: BetTracker,
            all_players: List[Dict],
            turn_number: int
    ) -> int:
        """Считает игроков, доступных для ставки в указанном ходе."""
        available_count = 0

        for player in all_players:
            # Проверяем базовую доступность
            can_bet, _ = tracker.can_bet_on_player(
                player['id'], player['position'], turn_number
            )

            if can_bet:
                # Проверяем, что можно сделать хотя бы одну ставку
                available_first = tracker.get_available_bet_types(
                    player['id'], player['position'], False
                )

                if available_first:
                    available_count += 1

        return available_count

    @staticmethod
    def validate_bet_type(
            match: Match,
            player_id: int,
            position: str,
            bet_type: BetType,
            bet_value: str,  # Может быть пустым
            is_second_bet: bool = False
    ) -> Tuple[bool, str]:
        """
        Проверяет конкретный тип ставки.

        Args:
            match: Объект матча
            player_id: ID игрока
            position: Позиция игрока
            bet_type: Тип ставки
            bet_value: Значение ставки (может быть пустым)
            is_second_bet: Это вторая ставка на игрока в этом ходе?
        """
        tracker = match.bet_tracker

        # УБИРАЕМ проверку значения здесь - она уже в validate_bet
        # if not BetValidator._is_valid_bet_value(bet_type, bet_value):
        #     return False, f"Некорректное значение ставки: {bet_value}"

        # Проверяем доступность типа ставки
        if bet_type == BetType.EVEN_ODD:
            return tracker.can_bet_even_odd(player_id, position)

        elif bet_type == BetType.GOAL:
            return tracker.can_bet_goal(position, player_id)

        elif bet_type == BetType.BIG_SMALL:
            return tracker.can_bet_big_small(player_id, position, is_second_bet)

        return False, "Неизвестный тип ставки"

    @staticmethod
    def _is_valid_bet_value(bet_type: BetType, value: str) -> bool:
        """Проверяет корректность значения ставки."""
        if bet_type == BetType.EVEN_ODD:
            return value in ["чет", "нечет"]
        elif bet_type == BetType.BIG_SMALL:
            return value in ["больше", "меньше"]
        elif bet_type == BetType.GOAL:
            return value in ["1", "2", "3", "4", "5", "6"]
        return False

    @staticmethod
    def get_available_bet_types_with_names(
            match: Match,
            player_id: int,
            position: str,
            is_second_bet: bool = False
    ) -> List[Tuple[BetType, str, str]]:
        """
        Возвращает доступные типы ставок с русскими названиями и значениями.

        Returns:
            List[(BetType, название, список_значений)]
        """
        tracker = match.bet_tracker
        available = []

        # Чет/нечет
        can_even_odd, _ = tracker.can_bet_even_odd(player_id, position)
        if can_even_odd:
            available.append((
                BetType.EVEN_ODD,
                "Чет/Нечет",
                ["чет", "нечет"]
            ))

        # Больше/меньше
        can_big_small, _ = tracker.can_bet_big_small(player_id, position, is_second_bet)
        print(f"DEBUG: position={position}, can_big_small={can_big_small}")
        if can_big_small:
            available.append((
                BetType.BIG_SMALL,
                "Больше/Меньше",
                ["больше", "меньше"]
            ))

        # Гол
        can_goal, _ = tracker.can_bet_goal(position, player_id)
        if can_goal:
            available.append((
                BetType.GOAL,
                "Точное число (гол)",
                ["1", "2", "3", "4", "5", "6"]
            ))

        return available

    @staticmethod
    async def get_available_players(
            match: Match,
            user_id: int,
            all_players: List[Dict]
    ) -> List[Dict]:
        tracker = match.bet_tracker
        available_players = []

        for player in all_players:
            # ДОБАВЬТЕ DEBUG:
            print(f"DEBUG bet_validator: checking player {player['id']} ({player['position']})")

            # Проверяем базовую доступность
            can_bet, reason = tracker.can_bet_on_player(
                player['id'], player['position'], match.current_turn
            )
            print(f"DEBUG: can_bet_on_player = {can_bet}, reason = {reason}")

            if not can_bet:
                continue





            # Проверяем стратегию (только для основного времени)
            if not tracker.is_extra_time and match.current_turn < 11:
                strategic_ok, reason3 = await BetValidator.check_future_strategy(
                    match, user_id, player['id'], all_players
                )
                print(f"DEBUG: strategic_ok = {strategic_ok}, reason = {reason3}")
                if not strategic_ok:
                    continue

            available_players.append(player)
            print(f"DEBUG: player {player['id']} ADDED to available")

        print(f"DEBUG: Total available players = {len(available_players)}")
        return available_players

    @staticmethod
    def check_extra_time_players(
            match: Match,
            user_id: int,
            selected_players: List[int],
            all_players: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Проверяет выбор игроков для дополнительного времени.

        Правила:
        1. Только те, кто не делал ставок в основном времени
        2. Ровно 5 игроков
        3. Могут быть из разных позиций
        """
        tracker = match.bet_tracker

        # Проверяем количество
        if len(selected_players) != 5:
            return False, "Нужно выбрать ровно 5 игроков для дополнительного времени"

        # Проверяем, что игроки не делали ставок в основном времени
        for player_id in selected_players:
            player = next((p for p in all_players if p['id'] == player_id), None)
            if not player:
                return False, f"Игрок {player_id} не найден"

            # Проверяем, делал ли игрок ставки в основном времени
            if tracker.get_player_bet_count(player_id) > 0:
                return False, (
                    f"Игрок {player.get('name', player_id)} уже делал ставки "
                    f"в основном времени. Для ДВ нужно выбирать только "
                    f"игроков без ставок."
                )

        return True, ""

    @staticmethod
    def calculate_match_result(
            player1_actions: Dict,
            player2_actions: Dict
    ) -> Tuple[int, int, str]:
        """
        Рассчитывает результат матча по правилам Final 4.

        Формула:
        Голы Команды A =
        если (Передачи A >= Отбития B): все голы A забиты
        иначе: (Отбития B - Передачи A) ÷ 2 = голы, которые "съедаются"
        """
        # Извлекаем действия
        p1_passes = player1_actions.get('passes', 0)
        p1_defenses = player1_actions.get('defenses', 0)
        p1_goals = player1_actions.get('goals', 0)

        p2_passes = player2_actions.get('passes', 0)
        p2_defenses = player2_actions.get('defenses', 0)
        p2_goals = player2_actions.get('goals', 0)

        # Считаем голы команды 1
        p1_scored = BetValidator._calculate_goals_scored(
            p1_goals, p1_passes, p2_defenses
        )

        # Считаем голы команды 2
        p2_scored = BetValidator._calculate_goals_scored(
            p2_goals, p2_passes, p1_defenses
        )

        # Формируем описание расчета
        calculation = (
            f"Команда 1: {p1_goals} гола(ов), {p1_passes} передач, {p1_defenses} отбитий → {p1_scored} забито\n"
            f"Команда 2: {p2_goals} гола(ов), {p2_passes} передач, {p2_defenses} отбитий → {p2_scored} забито"
        )

        return p1_scored, p2_scored, calculation

    @staticmethod
    def _calculate_goals_scored(goals: int, passes: int, opponent_defenses: int) -> int:
        """Рассчитывает количество забитых голов по формуле."""
        if passes >= opponent_defenses:
            # Оборона соперника взломана
            return goals

        # Считаем, сколько отбитий осталось
        remaining_defenses = opponent_defenses - passes

        # Каждые 2 отбития съедают 1 гол
        goals_lost = remaining_defenses // 2

        # Если осталось 1 отбитие - съедает целый гол
        if remaining_defenses % 2 == 1:
            goals_lost += 1

        scored = goals - goals_lost
        return max(0, scored)  # Не может быть отрицательным


# Глобальный экземпляр валидатора
bet_validator = BetValidator()