# core/dice.py
"""
Логика бросков кубика и ставок для Final 4.
Содержит классы для работы с результатами бросков и расчётом действий.
"""

import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


# ──────────────────────────────────────────────────────────────
# Результат броска кубика
# ──────────────────────────────────────────────────────────────


@dataclass
class DiceRoll:
    """
    Результат одного броска кубика.

    Атрибуты:
        value: Число от 1 до 6
        timestamp: Время броска (в секундах с эпохи)
        player_id: ID игрока, на которого ставка
        player_position: Позиция игрока (GK, DF, MF, FW)
        player_db_id: ID игрока в базе данных

    Методы:
        is_even, is_odd, is_less, is_more — быстрые проверки результата
        to_dict — для сериализации в JSON/БД
    """
    value: int
    timestamp: float
    player_id: int
    player_position: str
    player_db_id: int

    def __post_init__(self):
        """Проверки при создании экземпляра"""
        if not 1 <= self.value <= 6:
            raise ValueError(f"Неверное значение кубика: {self.value}")

    def is_even(self) -> bool:
        """Чётное ли число?"""
        return self.value % 2 == 0

    def is_odd(self) -> bool:
        """Нечётное ли число?"""
        return self.value % 2 == 1

    def is_less(self) -> bool:
        """Меньше или равно 3? (для ставки Меньше)"""
        return self.value <= 3

    def is_more(self) -> bool:
        """Больше 3? (для ставки Больше)"""
        return self.value > 3

    def to_dict(self) -> dict:
        """Преобразует результат в словарь для сохранения/отправки"""
        return {
            'value': self.value,
            'timestamp': self.timestamp,
            'player_id': self.player_id,
            'player_position': self.player_position,
            'player_db_id': self.player_db_id,
            'is_even': self.is_even(),
            'is_odd': self.is_odd(),
            'is_less': self.is_less(),
            'is_more': self.is_more(),
        }


# ──────────────────────────────────────────────────────────────
# Управление бросками кубика
# ──────────────────────────────────────────────────────────────


class DiceManager:
    """
    Управление бросками кубика.

    Основные задачи:
    - Генерация случайного броска (с опциональным seed для тестов)
    - Хранение истории бросков (если нужно)
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Инициализация менеджера бросков.

        Параметры:
            seed — фиксированное зерно для воспроизводимости (для тестов)
        """
        if seed is not None:
            random.seed(seed)

    def roll(self, player_id: int, player_position: str, player_db_id: int) -> DiceRoll:
        """
        Выполняет бросок кубика для указанного игрока.

        Параметры:
            player_id: ID игрока в команде
            player_position: Позиция игрока (GK, DF, MF, FW)
            player_db_id: ID игрока в базе данных

        Возвращает:
            DiceRoll — объект с результатом броска и метаданными
        """
        value = random.randint(1, 6)
        timestamp = datetime.utcnow().timestamp()

        return DiceRoll(
            value=value,
            timestamp=timestamp,
            player_id=player_id,
            player_position=player_position,
            player_db_id=player_db_id
        )


# ──────────────────────────────────────────────────────────────
# Расчёт действий по результату ставки
# ──────────────────────────────────────────────────────────────


class ActionCalculator:
    """
    Расчёт полезных действий (goals, passes, defenses) по результату ставки.

    RULES — словарь правил: позиция → тип ставки → действия при успехе.
    """

    RULES = {
        'GK': {
            'EVEN_ODD': {'defenses': 3},  # Вратарь: Чёт/Нечёт → 3 отбития
        },
        'DF': {
            'EVEN_ODD': {'defenses': 2},  # Защитник: Чёт/Нечёт → 2 отбития
            'BIG_SMALL': {'passes': 1},   # Меньше/Больше → 1 передача
            'exact': {'goals': 1}         # Точное число → 1 гол
        },
        'MF': {
            'EVEN_ODD': {'defenses': 1},  # Полузащитник: Чёт/Нечёт → 1 отбитие
            'BIG_SMALL': {'passes': 2},   # Меньше/Больше → 2 передачи
            'exact': {'goals': 1}         # Точное число → 1 гол
        },
        'FW': {
            'BIG_SMALL': {'passes': 1},   # Нападающий: Меньше/Больше → 1 передача
            'exact': {'goals': 1}         # Точное число → 1 гол
        }
    }

    @staticmethod
    def calculate_actions(
        player_position: str,
        bet_type: str,
        bet_success: bool = True
    ) -> Dict[str, int]:
        """
        Рассчитывает полезные действия для футболиста по результату ставки.

        Параметры:
            player_position: Позиция ('GK', 'DF', 'MF', 'FW')
            bet_type: Тип ставки ('EVEN_ODD', 'BIG_SMALL', 'exact')
            bet_success: Успешна ли ставка (True/False)

        Возвращает:
            {'goals': int, 'passes': int, 'defenses': int} — действия

        Особенности:
            - Если ставка не выиграна — возвращает пустые действия
            - Правила жёстко закодированы в RULES (по позициям и типам ставок)
        """
        actions = {'goals': 0, 'passes': 0, 'defenses': 0}

        if not bet_success:
            return actions

        if player_position in ActionCalculator.RULES:
            if bet_type in ActionCalculator.RULES[player_position]:
                actions.update(ActionCalculator.RULES[player_position][bet_type])

        return actions

    @staticmethod
    def get_allowed_bets(player_position: str) -> List[str]:
        """
        Возвращает список разрешённых типов ставок для позиции.

        Параметры:
            player_position: Позиция игрока ('GK', 'DF', 'MF', 'FW')

        Возвращает:
            Список типов ставок, для которых есть действия при успехе
        """
        allowed = []

        if player_position in ActionCalculator.RULES:
            for bet_type in ActionCalculator.RULES[player_position]:
                if ActionCalculator.RULES[player_position][bet_type]:
                    allowed.append(bet_type)

        return allowed