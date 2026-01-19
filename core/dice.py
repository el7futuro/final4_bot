# core/dice.py
"""
Логика бросков кубика и ставок для Final 4.
"""

import random
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass


@dataclass
class DiceRoll:
    """Результат броска кубика"""
    value: int  # 1-6
    timestamp: float
    player_id: int
    player_position: str  # GK, DF, MF, FW
    player_db_id: int

    def is_even(self) -> bool:
        """Четное ли число?"""
        return self.value % 2 == 0

    def is_odd(self) -> bool:
        """Нечетное ли число?"""
        return self.value % 2 == 1

    def is_less(self) -> bool:
        """Меньше или равно 3?"""
        return self.value <= 3

    def is_more(self) -> bool:
        """Больше 3?"""
        return self.value > 3

    def to_dict(self) -> dict:
        return {
            'value': self.value,
            'timestamp': self.timestamp,
            'player_id': self.player_id,
            'player_position': self.player_position,
            'player_db_id': self.player_db_id,
            'is_even': self.is_even(),
            'is_odd': self.is_odd(),
            'is_less': self.is_less(),
            'is_more': self.is_more()
        }


class DiceManager:
    """Управление бросками кубика"""

    def __init__(self, seed: Optional[int] = None):
        if seed:
            random.seed(seed)

    def roll(self, player_id: int, player_position: str, player_db_id: int) -> DiceRoll:
        """Бросок кубика 1-6"""
        return DiceRoll(
            value=random.randint(1, 6),
            timestamp=random.random(),
            player_id=player_id,
            player_position=player_position,
            player_db_id=player_db_id
        )

    def roll_multiple(self, count: int, player_id: int, player_position: str, player_db_id: int) -> List[DiceRoll]:
        """Несколько бросков"""
        return [self.roll(player_id, player_position, player_db_id) for _ in range(count)]


class BetChecker:
    """Проверка ставок менеджера"""

    @staticmethod
    def check_odd_even(dice_roll: DiceRoll, bet_value: str) -> bool:
        """Проверяет ставку на Чет/Нечет"""
        if bet_value == "чет":
            return dice_roll.is_even()
        elif bet_value == "нечет":
            return dice_roll.is_odd()
        return False

    @staticmethod
    def check_less_more(dice_roll: DiceRoll, bet_value: str) -> bool:
        """Проверяет ставку на Меньше/Больше (1-3 / 4-6)"""
        if bet_value == "меньше":
            return dice_roll.is_less()
        elif bet_value == "больше":
            return dice_roll.is_more()
        return False

    @staticmethod
    def check_exact_number(dice_roll: DiceRoll, bet_value: str) -> bool:
        """Проверяет ставку на точное число"""
        try:
            return dice_roll.value == int(bet_value)
        except ValueError:
            return False

    @staticmethod
    def check_bet(bet_type: str, dice_roll: DiceRoll, bet_value: str) -> bool:
        """Проверяет ставку любого типа"""
        if bet_type == "odd_even":
            return BetChecker.check_odd_even(dice_roll, bet_value)
        elif bet_type == "less_more":
            return BetChecker.check_less_more(dice_roll, bet_value)
        elif bet_type == "exact":
            return BetChecker.check_exact_number(dice_roll, bet_value)
        return False


class ActionCalculator:
    """Расчет полезных действий по правилам Final 4"""

    RULES = {
        'GK': {
            'odd_even': {'defenses': 3},  # Вратарь: Чет/Нечет → 3 отбития
            'less_more': {},  # Не допускается
            'exact': {}  # Не допускается
        },
        'DF': {
            'odd_even': {'defenses': 2},  # Защитник: Чет/Нечет → 2 отбития
            'less_more': {'passes': 1},  # Меньше/Больше → 1 передача
            'exact': {'goals': 1}  # Точное число → 1 гол
        },
        'MF': {
            'odd_even': {'defenses': 1},  # Полузащитник: Чет/Нечет → 1 отбитие
            'less_more': {'passes': 2},  # Меньше/Больше → 2 передачи
            'exact': {'goals': 1}  # Точное число → 1 гол
        },
        'FW': {
            'odd_even': {},  # Не допускается
            'less_more': {'passes': 1},  # Меньше/Больше → 1 передача
            'exact': {'goals': 1}  # Точное число → 1 гол
        }
    }

    @staticmethod
    def calculate_actions(player_position: str, bet_type: str, bet_success: bool) -> Dict[str, int]:
        """Рассчитывает полезные действия для футболиста"""
        actions = {'goals': 0, 'passes': 0, 'defenses': 0}

        if not bet_success:
            return actions

        if player_position in ActionCalculator.RULES:
            if bet_type in ActionCalculator.RULES[player_position]:
                actions.update(ActionCalculator.RULES[player_position][bet_type])

        return actions

    @staticmethod
    def get_allowed_bets(player_position: str) -> List[str]:
        """Возвращает разрешенные типы ставок для позиции"""
        allowed = []

        if player_position in ActionCalculator.RULES:
            for bet_type in ActionCalculator.RULES[player_position]:
                if ActionCalculator.RULES[player_position][bet_type]:
                    allowed.append(bet_type)

        return allowed