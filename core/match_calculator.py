# core/match_calculator.py
"""
Расчет результатов матча по правилам Final 4.
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class MatchResult:
    """Результат матча"""
    player1_score: int
    player2_score: int
    winner: Optional[int]  # ID победителя или None при ничье
    is_draw: bool
    details: Dict

    def get_winner_text(self) -> str:
        """Текстовое описание результата"""
        if self.is_draw:
            return "Ничья"
        elif self.winner == 1:
            return f"Победил игрок 1 ({self.player1_score}:{self.player2_score})"
        else:
            return f"Победил игрок 2 ({self.player1_score}:{self.player2_score})"


class MatchCalculator:
    """Калькулятор результатов матча по правилам Final 4"""

    @staticmethod
    def calculate_goals(defenses: int, passes: int, goals: int) -> int:
        """
        Рассчитывает количество забитых голов по правилам:
        1. Из отбитий соперника вычитаем свои передачи
        2. Если передач >= отбитий → все голы засчитываются
        3. Если отбитий больше → тратим голы на уничтожение отбитий (1 гол = 2 отбития)
        4. Если осталось 1 отбитие → тратится 1 гол целиком
        """
        remaining_defenses = defenses - passes

        if remaining_defenses <= 0:
            # Все отбития уничтожены, все голы засчитываются
            return goals

        # Уничтожаем отбития голами
        goals_needed = (remaining_defenses + 1) // 2  # Округление вверх
        remaining_goals = goals - goals_needed

        return max(0, remaining_goals)

    @staticmethod
    def calculate_match_score(
            player1_actions: Dict[str, int],
            player2_actions: Dict[str, int]
    ) -> Tuple[int, int]:
        """Рассчитывает финальный счет матча"""
        # Извлекаем действия
        p1_goals = player1_actions.get('goals', 0)
        p1_passes = player1_actions.get('passes', 0)
        p1_defenses = player1_actions.get('defenses', 0)

        p2_goals = player2_actions.get('goals', 0)
        p2_passes = player2_actions.get('passes', 0)
        p2_defenses = player2_actions.get('defenses', 0)

        # Голы команды 1
        p1_score = MatchCalculator.calculate_goals(
            defenses=p2_defenses,
            passes=p1_passes,
            goals=p1_goals
        )

        # Голы команды 2
        p2_score = MatchCalculator.calculate_goals(
            defenses=p1_defenses,
            passes=p2_passes,
            goals=p2_goals
        )

        return p1_score, p2_score

    @staticmethod
    def create_match_result(
            player1_id: int,
            player2_id: int,
            player1_actions: Dict[str, int],
            player2_actions: Dict[str, int],
            match_details: Optional[Dict] = None
    ) -> MatchResult:
        """Создает полный результат матча"""
        p1_score, p2_score = MatchCalculator.calculate_match_score(
            player1_actions, player2_actions
        )

        # Определяем победителя
        if p1_score > p2_score:
            winner = player1_id
            is_draw = False
        elif p2_score > p1_score:
            winner = player2_id
            is_draw = False
        else:
            winner = None
            is_draw = True

        details = {
            'player1_actions': player1_actions,
            'player2_actions': player2_actions,
            'player1_score': p1_score,
            'player2_score': p2_score,
            'calculation_details': {
                'p1_defenses_vs_p2_passes': player2_actions.get('defenses', 0) - player1_actions.get('passes', 0),
                'p2_defenses_vs_p1_passes': player1_actions.get('defenses', 0) - player2_actions.get('passes', 0),
                'p1_goals_needed': (max(0, player2_actions.get('defenses', 0) - player1_actions.get('passes',
                                                                                                    0)) + 1) // 2,
                'p2_goals_needed': (max(0,
                                        player1_actions.get('defenses', 0) - player2_actions.get('passes', 0)) + 1) // 2
            }
        }

        if match_details:
            details.update(match_details)

        return MatchResult(
            player1_score=p1_score,
            player2_score=p2_score,
            winner=winner,
            is_draw=is_draw,
            details=details
        )

    @staticmethod
    def validate_actions(actions: Dict[str, int]) -> bool:
        """Проверяет корректность действий"""
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
    def get_match_summary(player1_actions: Dict[str, int], player2_actions: Dict[str, int]) -> str:
        """Возвращает текстовое описание матча"""
        p1_score, p2_score = MatchCalculator.calculate_match_score(player1_actions, player2_actions)

        summary = "📊 **Итог матча:**\n\n"

        summary += f"🔵 **Команда 1:**\n"
        summary += f"• Голы: {player1_actions.get('goals', 0)} → {p1_score} забито\n"
        summary += f"• Передачи: {player1_actions.get('passes', 0)}\n"
        summary += f"• Отбития: {player1_actions.get('defenses', 0)}\n\n"

        summary += f"🔴 **Команда 2:**\n"
        summary += f"• Голы: {player2_actions.get('goals', 0)} → {p2_score} забито\n"
        summary += f"• Передачи: {player2_actions.get('passes', 0)}\n"
        summary += f"• Отбития: {player2_actions.get('defenses', 0)}\n\n"

        summary += f"🎯 **Финальный счет: {p1_score}:{p2_score}**\n"

        return summary