# core/match_calculator.py
"""
Расчёт результатов матча по правилам Final 4.

Модуль содержит:
- Класс MatchResult — структура результата матча (счёт, победитель, детали)
- Класс MatchCalculator — статические методы для расчёта счёта и валидации действий

Основные правила расчёта голов:
- Передачи вычитают отбития соперника
- Если передач >= отбитий → все голы засчитываются
- Если отбитий больше → тратим голы на уничтожение (1 гол = 2 отбития)
- Оставшееся 1 отбитие уничтожает 1 гол целиком
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass


# ──────────────────────────────────────────────────────────────
# Структура результата матча
# ──────────────────────────────────────────────────────────────


@dataclass
class MatchResult:
    """
    Результат матча после расчёта.

    Атрибуты:
        player1_score: Итоговые голы команды 1 после учёта защит
        player2_score: Итоговые голы команды 2 после учёта защит
        winner: ID победителя (1 или 2) или None при ничьей
        is_draw: True, если счёт равный
        details: Словарь с дополнительными данными (можно расширить)

    Методы:
        get_winner_text — текстовое описание результата (для сообщений игроку)
    """
    player1_score: int
    player2_score: int
    winner: Optional[int]  # 1 или 2, или None при ничьей
    is_draw: bool
    details: Dict

    def get_winner_text(self) -> str:
        """
        Возвращает человекочитаемое текстовое описание результата матча.

        Возвращает:
            Строка вида:
            - "Ничья"
            - "Победил игрок 1 (3:2)"
            - "Победил игрок 2 (1:4)"

        Особенности:
            - Использует итоговые голы после расчёта
            - Подходит для отправки в чат игроку
        """
        if self.is_draw:
            return "Ничья"

        score_text = f"{self.player1_score}:{self.player2_score}"
        if self.winner == 1:
            return f"Победил игрок 1 ({score_text})"
        else:
            return f"Победил игрок 2 ({score_text})"


# ──────────────────────────────────────────────────────────────
# Калькулятор результатов матча
# ──────────────────────────────────────────────────────────────


class MatchCalculator:
    """
    Калькулятор результатов матча по правилам Final 4.

    Все методы статические — класс используется как пространство имён.
    Не хранит состояние, чистые функции.

    Основные методы:
    - calculate_goals: Расчёт голов одной команды по её голам/передачам и отбитиям соперника
    - calculate_match_score: Расчёт итогового счёта обеих команд
    - validate_actions: Проверка корректности словаря действий
    - get_match_summary: Текстовое описание матча для игрока
    """

    @staticmethod
    def calculate_goals(
        defenses: int,
        passes: int,
        goals: int
    ) -> int:
        """
        Рассчитывает количество забитых голов одной команды.

        Правила:
        1. Из отбитий соперника вычитаем свои передачи
        2. Если передач >= отбитий → все голы засчитываются
        3. Если отбитий больше → тратим голы на уничтожение (1 гол = 2 отбития)
        4. Оставшееся 1 отбитие уничтожает 1 гол целиком

        Параметры:
            defenses: Количество отбитий у соперника
            passes: Количество передач у атакующей команды
            goals: Количество голов у атакующей команды

        Возвращает:
            Итоговое количество забитых голов (не меньше 0)

        Примеры:
            calculate_goals(defenses=5, passes=6, goals=3) → 3 (передачи покрыли все отбития)
            calculate_goals(defenses=5, passes=2, goals=3) → 1 (3 гола - 2 на уничтожение 3 отбитий)
            calculate_goals(defenses=1, passes=0, goals=1) → 0 (1 гол уничтожен оставшимся отбитием)
        """
        remaining_defenses = defenses - passes

        if remaining_defenses <= 0:
            return goals

        # 1 гол уничтожает 2 отбития
        goals_needed = (remaining_defenses + 1) // 2  # округление вверх
        return max(0, goals - goals_needed)

    @staticmethod
    def calculate_match_score(
        player1_actions: Dict[str, int],
        player2_actions: Dict[str, int]
    ) -> Tuple[int, int]:
        """
        Рассчитывает итоговый счёт матча для обеих команд.

        Параметры:
            player1_actions: Действия команды 1 {'goals', 'passes', 'defenses'}
            player2_actions: Действия команды 2

        Возвращает:
            (score_player1, score_player2) — голы после учёта защит и передач

        Особенности:
            - Вызывает calculate_goals для каждой команды
            - Порядок важен: передача одной команды уничтожает защиту другой
        """
        p1_score = MatchCalculator.calculate_goals(
            defenses=player2_actions.get('defenses', 0),
            passes=player1_actions.get('passes', 0),
            goals=player1_actions.get('goals', 0)
        )

        p2_score = MatchCalculator.calculate_goals(
            defenses=player1_actions.get('defenses', 0),
            passes=player2_actions.get('passes', 0),
            goals=player2_actions.get('goals', 0)
        )

        return p1_score, p2_score

    @staticmethod
    def validate_actions(actions: Dict[str, int]) -> bool:
        """
        Проверяет корректность словаря действий игрока.

        Параметры:
            actions: Словарь {'goals': int, 'passes': int, 'defenses': int}

        Возвращает:
            True — словарь корректен
            False — ошибка (отсутствует ключ, неверный тип, отрицательное значение)

        Особенности:
            - Все три ключа обязательны
            - Значения должны быть целыми числами >= 0
        """
        required_keys = ['goals', 'passes', 'defenses']

        for key in required_keys:
            if key not in actions:
                return False

            if not isinstance(actions[key], int):
                return False

            if actions[key] < 0:
                return False

        return True

    @staticmethod
    def get_match_summary(
        player1_actions: Dict[str, int],
        player2_actions: Dict[str, int]
    ) -> str:
        """
        Возвращает текстовое описание матча для отправки игроку.

        Параметры:
            player1_actions: Действия команды 1
            player2_actions: Действия команды 2

        Возвращает:
            Форматированная строка с итоговым счётом и деталями

        Особенности:
            - Показывает исходные и итоговые голы
            - Учитывает передачи и отбития
            - Подходит для сообщения в чат
        """
        p1_score, p2_score = MatchCalculator.calculate_match_score(
            player1_actions, player2_actions
        )

        summary = "📊 **Итог матча:**\n\n"

        summary += f"🔵 **Команда 1:**\n"
        summary += f"• Голы: {player1_actions.get('goals', 0)} → {p1_score} забито\n"
        summary += f"• Передачи: {player1_actions.get('passes', 0)}\n"
        summary += f"• Отбития: {player1_actions.get('defenses', 0)}\n\n"

        summary += f"🔴 **Команда 2:**\n"
        summary += f"• Голы: {player2_actions.get('goals', 0)} → {p2_score} забито\n"
        summary += f"• Передачи: {player2_actions.get('passes', 0)}\n"
        summary += f"• Отбития: {player2_actions.get('defenses', 0)}\n\n"

        summary += f"🎯 **Финальный счёт: {p1_score}:{p2_score}**\n"

        return summary