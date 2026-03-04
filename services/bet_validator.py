# services/bet_validator.py
"""
Валидатор ставок в Final 4.

Проверяет:
- доступность игрока в текущем ходе
- соблюдение лимитов ставок на игрока
- допустимые типы ставок для позиции
- ограничения квот на голы
- сохранение допустимой формации до конца матча
- стратегическую целесообразность выбора (возможность двух разных ставок в следующем ходу)
"""

from __future__ import annotations

import copy
import logging
from typing import List, Dict, Tuple

from models.bet_tracker import BetTracker, BetType
from models.match import Match

logger = logging.getLogger(__name__)

# Допустимые итоговые формации (DF-MF-FW) после 11 ходов
PERMITTED_FORMATIONS = [
    (5, 3, 2), (5, 2, 3), (4, 4, 2), (4, 3, 3),
    (3, 5, 2), (3, 4, 3), (3, 3, 4)
]


class BetValidator:
    """
    Статический класс для всех проверок, связанных со ставками.

    Методы возвращают кортеж (успех: bool, сообщение: str).
    Пустое сообщение означает успешную проверку.
    """

    @staticmethod
    async def validate_player_selection(
        match: Match,
        user_id: int,
        player_id: int,
        player_position: str,
        all_players: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Основная проверка: можно ли выбрать этого игрока для ставки в текущем ходе.

        Проверяет:
        1. Лимиты BetTracker
        2. Формацию (с 5-го хода)
        3. Стратегию на следующий ход (наличие игрока с двумя разными ставками)

        Args:
            match: объект матча
            user_id: id пользователя (проверяется участие в матче)
            player_id: id игрока внутри команды
            player_position: 'GK', 'DF', 'MF', 'FW'
            all_players: полный список игроков команды

        Returns:
            (можно выбрать, причина отказа или пустая строка)
        """
        if not match.is_player_in_match(user_id):
            return False, "Вы не участник этого матча"

        tracker = match.bet_tracker

        # 1. Базовая проверка доступности по правилам BetTracker
        can_bet, reason = tracker.can_bet_on_player(player_id, player_position, match.current_turn)
        if not can_bet:
            return False, reason

        # 2. Защита от двойных ставок (на всякий случай, хотя tracker уже проверяет)
        if player_position != 'GK':
            if tracker.player_bets.get(player_id, 0) >= 2:
                return False, "У этого игрока уже две ставки за матч"

        # 3. Проверка формации (начиная с 5-го хода)
        if match.current_turn >= 5:
            temp_field = copy.deepcopy(match.current_on_field or {'DF': 0, 'MF': 0, 'FW': 0})
            temp_field[player_position] = temp_field.get(player_position, 0) + 1

            used_ids = set(match.used_players or [])
            remaining = [
                p for p in all_players
                if p.get('id') not in used_ids and p.get('id') != player_id
            ]

            slots_left = 11 - match.current_turn

            if not BetValidator.can_reach_valid_end(temp_field, remaining, slots_left):
                return False, "Этот выбор нарушит допустимую формацию к концу основного времени"

        # 4. Стратегическая проверка на следующий ход
        if not tracker.is_extra_time and match.current_turn < 11:
            ok, msg = await BetValidator.check_future_strategy(
                match, user_id, player_id, player_position, all_players
            )
            if not ok:
                return False, msg

        return True, ""

    @staticmethod
    def can_reach_valid_end(
        current_field: Dict[str, int],
        remaining_players: List[Dict],
        slots_left: int
    ) -> bool:
        """
        Проверяет, можно ли из оставшихся игроков добрать до одной из разрешённых формаций.

        Использует быстрый подсчёт по позициям (без полного перебора комбинаций).
        """
        avail = {'DF': 0, 'MF': 0, 'FW': 0}
        for p in remaining_players:
            pos = p.get('position', '').upper()
            if pos in avail:
                avail[pos] += 1

        cur_df = current_field.get('DF', 0)
        cur_mf = current_field.get('MF', 0)
        cur_fw = current_field.get('FW', 0)

        for target_df, target_mf, target_fw in PERMITTED_FORMATIONS:
            need_df = target_df - cur_df
            need_mf = target_mf - cur_mf
            need_fw = target_fw - cur_fw

            if (need_df >= 0 and need_mf >= 0 and need_fw >= 0 and
                need_df <= avail['DF'] and
                need_mf <= avail['MF'] and
                need_fw <= avail['FW'] and
                need_df + need_mf + need_fw == slots_left):
                return True

        return False

    @staticmethod
    async def get_available_players(
        match: Match,
        user_id: int,
        all_players: List[Dict]
    ) -> List[Dict]:
        """
        Возвращает список игроков, на которых сейчас можно сделать ставку.

        Учитывает BetTracker + формацию + стратегию.
        """
        if not match.is_player_in_match(user_id):
            return []

        tracker = match.bet_tracker
        available = []

        for player in all_players:
            p_id = player.get('id')
            p_pos = player.get('position', '')

            can_bet, _ = tracker.can_bet_on_player(p_id, p_pos, match.current_turn)
            if not can_bet:
                continue

            # Проверка формации с 5-го хода
            if match.current_turn >= 5:
                temp_field = copy.deepcopy(match.current_on_field or {'DF': 0, 'MF': 0, 'FW': 0})
                temp_field[p_pos] = temp_field.get(p_pos, 0) + 1

                used_ids = set(match.used_players or [])
                remaining = [
                    p for p in all_players
                    if p.get('id') not in used_ids and p.get('id') != p_id
                ]

                slots_left = 11 - match.current_turn

                if not BetValidator.can_reach_valid_end(temp_field, remaining, slots_left):
                    continue

            # Проверка стратегии (опционально, но включаем)
            if not tracker.is_extra_time and match.current_turn < 11:
                ok, _ = await BetValidator.check_future_strategy(
                    match, user_id, p_id, p_pos, all_players
                )
                if not ok:
                    continue

            available.append(player)

        return available

    @staticmethod
    async def check_future_strategy(
        match: Match,
        user_id: int,
        player_id: int,
        player_position: str,
        all_players: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Проверяет, останется ли после текущего выбора
        хотя бы один игрок, способный сделать ДВЕ РАЗНЫЕ ставки в следующем ходу.

        Это предотвращает ситуации, когда в следующем ходу игроку будет доступен
        только один тип ставки (или вообще ничего).
        """
        tracker = match.bet_tracker
        next_turn = match.current_turn + 1

        # Если уже ДВ или последний ход — не проверяем
        if tracker.is_extra_time or next_turn > 11:
            return True, ""

        # Симулируем состояние трекера после текущей ставки
        simulated_tracker = copy.deepcopy(tracker)

        # Определяем, какую ставку симулировать (берём самую "дорогую" для консервативности)
        possible_types = simulated_tracker.get_available_bet_types(
            player_id, player_position, is_second_bet=False
        )

        if not possible_types:
            return True, ""  # уже невалидно выше

        # GOAL — самая строгая по квотам, берём её, если доступна
        simulated_type = next((t for t in possible_types if t == BetType.GOAL), possible_types[0])

        simulated_tracker.register_bet(
            player_id=player_id,
            position=player_position,
            bet_type=simulated_type,
            bet_value="?"  # значение не важно
        )

        # Проверяем следующий ход
        has_player_with_two_bets = False
        players_with_one_bet = []

        for p in all_players:
            pid = p.get('id')
            pos = p.get('position', '')

            can_bet, _ = simulated_tracker.can_bet_on_player(pid, pos, next_turn)
            if not can_bet:
                continue

            available_types = simulated_tracker.get_available_bet_types(
                pid, pos, is_second_bet=False
            )

            if len(available_types) >= 2:
                has_player_with_two_bets = True
                break
            elif len(available_types) == 1:
                name = p.get('name', f"ID {pid} ({pos})")
                players_with_one_bet.append(name)

        if has_player_with_two_bets:
            return True, ""

        # Формируем понятное сообщение
        if players_with_one_bet:
            examples = ", ".join(players_with_one_bet[:3])
            if len(players_with_one_bet) > 3:
                examples += f" и ещё {len(players_with_one_bet) - 3}"
            msg = (
                f"После этого хода в следующем ходу у всех оставшихся игроков "
                f"останет только один тип ставки ({examples}). "
                "Это сильно ограничит игру. Продолжить?"
            )
        else:
            msg = (
                "После этого хода в следующем ходу, похоже, не останется "
                "игроков, на которых можно будет сделать ставку. "
                "Это приведёт к тупиковой ситуации. Вы уверены?"
            )

        return False, msg

    @staticmethod
    def check_extra_time_players(
        match: Match,
        user_id: int,
        selected_ids: List[int],
        all_players: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Проверка выбора 5 игроков для дополнительного времени.

        Требования:
        - ровно 5 игроков
        - ни один из них не делал ставок в основном времени
        """
        if len(selected_ids) != 5:
            return False, "Нужно выбрать ровно 5 игроков для дополнительного времени"

        tracker = match.bet_tracker
        selected_set = set(selected_ids)

        for player in all_players:
            pid = player.get('id')
            if pid in selected_set:
                if tracker.get_player_bet_count(pid) > 0:
                    name = player.get('name', f"ID {pid}")
                    return False, (
                        f"Игрок {name} уже делал ставки в основном времени. "
                        "В дополнительное время можно выбирать только запасных без ставок."
                    )

        return True, ""

    @staticmethod
    def calculate_match_result(
        player1_actions: Dict[str, int],
        player2_actions: Dict[str, int]
    ) -> Tuple[int, int, str]:
        """
        Рассчитывает итоговый счёт по накопленным действиям обеих команд.

        Формула:
        Если передач >= отбитий соперника → все голы засчитываются
        Иначе каждый 2 отбития «съедают» 1 гол (остаток 1 = ещё -1 гол)
        """
        p1_g = player1_actions.get('goals',   0)
        p1_p = player1_actions.get('passes',  0)
        p1_d = player1_actions.get('defenses',0)

        p2_g = player2_actions.get('goals',   0)
        p2_p = player2_actions.get('passes',  0)
        p2_d = player2_actions.get('defenses',0)

        p1_scored = BetValidator._calculate_goals_scored(p1_g, p1_p, p2_d)
        p2_scored = BetValidator._calculate_goals_scored(p2_g, p2_p, p1_d)

        explanation = (
            f"Команда 1: {p1_g} гол(ов), {p1_p} пас, {p1_d} отб → {p1_scored} забито\n"
            f"Команда 2: {p2_g} гол(ов), {p2_p} пас, {p2_d} отб → {p2_scored} забито"
        )

        return p1_scored, p2_scored, explanation

    @staticmethod
    def _calculate_goals_scored(
        goals: int,
        passes: int,
        opponent_defenses: int
    ) -> int:
        """Внутренняя формула подсчёта забитых голов."""
        if passes >= opponent_defenses:
            return goals

        remaining_def = opponent_defenses - passes
        goals_blocked = remaining_def // 2
        if remaining_def % 2 == 1:
            goals_blocked += 1

        return max(0, goals - goals_blocked)

    @staticmethod
    def get_available_bet_types_with_names(
        match: Match,
        player_id: int,
        position: str,
        is_second_bet: bool = False
    ) -> List[Tuple[BetType, str, List[str]]]:
        """
        Возвращает список доступных типов ставок с русскими названиями и вариантами значений.
        """
        tracker = match.bet_tracker
        result = []

        # Вратарь — только Чет/Нечет и только одна ставка
        if position == 'GK':
            if not is_second_bet:
                result.append(
                    (BetType.EVEN_ODD, "Чёт / Нечёт", ["чёт", "нечёт"])
                )
            return result

        # Защитник
        if position == 'DF':
            can_eo, _ = tracker.can_bet_EVEN_ODD(player_id, position)
            if can_eo:
                result.append((BetType.EVEN_ODD, "Чёт / Нечёт", ["чёт", "нечёт"]))

            can_bs, _ = tracker.can_bet_big_small(player_id, position, is_second_bet)
            if can_bs:
                result.append((BetType.BIG_SMALL, "Больше / Меньше", ["меньше", "больше"]))

            can_goal, _ = tracker.can_bet_goal(position, player_id)
            if can_goal:
                result.append((BetType.GOAL, "Точное число", ["1","2","3","4","5","6"]))

        # Полузащитник
        elif position == 'MF':
            can_eo, _ = tracker.can_bet_EVEN_ODD(player_id, position)
            if can_eo:
                result.append((BetType.EVEN_ODD, "Чёт / Нечёт", ["чёт", "нечёт"]))

            can_bs, _ = tracker.can_bet_big_small(player_id, position, is_second_bet)
            if can_bs:
                result.append((BetType.BIG_SMALL, "Больше / Меньше", ["меньше", "больше"]))

            can_goal, _ = tracker.can_bet_goal(position, player_id)
            if can_goal:
                result.append((BetType.GOAL, "Точное число", ["1","2","3","4","5","6"]))

        # Нападающий — без Чёт/Нечёт
        elif position == 'FW':
            can_bs, _ = tracker.can_bet_big_small(player_id, position, is_second_bet)
            if can_bs:
                result.append((BetType.BIG_SMALL, "Больше / Меньше", ["меньше", "больше"]))

            can_goal, _ = tracker.can_bet_goal(position, player_id)
            if can_goal:
                result.append((BetType.GOAL, "Точное число", ["1","2","3","4","5","6"]))

        return result


# Глобальный экземпляр для удобного импорта
bet_validator = BetValidator()