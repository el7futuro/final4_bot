# core/game_utils.py
"""
Общие утилиты для расчёта ставок и действий в Final 4.

Модуль содержит вспомогательные функции, которые используются в нескольких местах проекта:
- bot_ai.py (при расчёте хода бота)
- game_manager.py (при валидации ставок)
- handlers (при обработке ходов игрока)

Особенности:
- Функции чистые (без побочных эффектов)
- Не зависят от состояния игры (не используют БД, матч или сессию)
- Избегают циклических импортов, поэтому вынесены в отдельный модуль
"""

from typing import Dict


# ──────────────────────────────────────────────────────────────
# Проверка результата ставки
# ──────────────────────────────────────────────────────────────


def check_bet(bet_type: str, dice_roll: int, bet_value: str) -> bool:
    """
    Проверяет, выиграла ли ставка по результату броска кубика.

    Параметры:
        bet_type: Тип ставки ('EVEN_ODD', 'BIG_SMALL', 'GOAL')
        dice_roll: Результат броска кубика (целое число 1–6)
        bet_value: Значение ставки (например 'чёт', 'меньше', '4')

    Возвращает:
        True — ставка выиграна
        False — ставка проиграна

    Особенности:
        - bet_value приводится к нижнему регистру и очищается от пробелов
        - Поддерживает русские варианты написания ('чёт'/'чет', 'нечёт'/'нечет')
        - Для GOAL сравнивает как строки (str(dice_roll) == bet_value)

    Примеры:
        check_bet('EVEN_ODD', 4, 'чёт') → True
        check_bet('BIG_SMALL', 2, 'меньше') → True
        check_bet('GOAL', 5, '5') → True
        check_bet('GOAL', 5, '6') → False
    """
    bet_value = bet_value.lower().strip()

    if bet_type == "EVEN_ODD":
        is_even = dice_roll % 2 == 0
        return (is_even and bet_value in ["чёт", "чет"]) or \
               (not is_even and bet_value in ["нечёт", "нечет"])

    elif bet_type == "BIG_SMALL":
        is_small = dice_roll <= 3
        return (is_small and bet_value == "меньше") or \
               (not is_small and bet_value == "больше")

    elif bet_type == "GOAL":
        return str(dice_roll) == bet_value

    return False


# ──────────────────────────────────────────────────────────────
# Расчёт полезных действий по результату ставки
# ──────────────────────────────────────────────────────────────


def calculate_actions(position: str, bet_type: str) -> Dict[str, int]:
    """
    Рассчитывает полезные действия (goals, passes, defenses) для футболиста
    в зависимости от его позиции и типа ставки (при условии, что ставка выиграна).

    Параметры:
        position: Позиция игрока ('GK', 'DF', 'MF', 'FW') — регистр не важен
        bet_type: Тип ставки ('EVEN_ODD', 'BIG_SMALL', 'GOAL')

    Возвращает:
        Словарь {'goals': int, 'passes': int, 'defenses': int}

    Особенности:
        - Позиция приводится к верхнему регистру
        - Если позиция неизвестна или ставка не поддерживается — возвращает 0
        - Правила жёстко закодированы по позициям и типам ставок
        - Если ставка не выиграна — вызывать функцию не нужно (она всегда возвращает действия при успехе)

    Примеры:
        calculate_actions('GK', 'EVEN_ODD') → {'goals': 0, 'passes': 0, 'defenses': 3}
        calculate_actions('DF', 'GOAL') → {'goals': 1, 'passes': 0, 'defenses': 0}
        calculate_actions('FW', 'EVEN_ODD') → {'goals': 0, 'passes': 0, 'defenses': 0}  # не поддерживается
    """
    actions = {'goals': 0, 'passes': 0, 'defenses': 0}
    position = position.upper()

    if position == 'GK':
        if bet_type == "EVEN_ODD":
            actions['defenses'] = 3

    elif position == 'DF':
        if bet_type == "EVEN_ODD":
            actions['defenses'] = 2
        elif bet_type == "BIG_SMALL":
            actions['passes'] = 1
        elif bet_type == "GOAL":
            actions['goals'] = 1

    elif position == 'MF':
        if bet_type == "EVEN_ODD":
            actions['defenses'] = 1
        elif bet_type == "BIG_SMALL":
            actions['passes'] = 2
        elif bet_type == "GOAL":
            actions['goals'] = 1

    elif position == 'FW':
        if bet_type == "BIG_SMALL":
            actions['passes'] = 1
        elif bet_type == "GOAL":
            actions['goals'] = 1

    return actions