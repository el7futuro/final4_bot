# core/extra_time.py
"""
Логика дополнительного времени и пенальти для Final 4.

Содержит:
- Класс ExtraTimePlayer — представление игрока в дополнительное время
- Класс ExtraTimeManager — управление дополнительным временем (2 ставки на игрока)
- Класс PenaltyShootout — серия пенальти (5 ударов + до победы)
"""

import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from .dice import DiceManager,  ActionCalculator


# ──────────────────────────────────────────────────────────────
# Игрок в дополнительное время
# ──────────────────────────────────────────────────────────────


@dataclass
class ExtraTimePlayer:
    """
    Представление игрока в дополнительное время.

    Атрибуты:
        player_id: ID игрока в команде
        position: Позиция (GK, DF, MF, FW)
        name: Имя игрока
        number: Номер на футболке
        has_pass: Есть ли передача для пенальти (по умолчанию False)
    """
    player_id: int
    position: str
    name: str
    number: int
    has_pass: bool = False


# ──────────────────────────────────────────────────────────────
# Управление дополнительным временем
# ──────────────────────────────────────────────────────────────


class ExtraTimeManager:
    """
    Управление дополнительным временем (2 ставки на игрока).

    Особенности:
    - Берёт первых 5 игроков из команды
    - Выполняет 2 ставки на каждого игрока (как в правилах ДВ)
    - Использует DiceManager для бросков, BetChecker для проверки, ActionCalculator для действий
    """

    def __init__(self, players: List[Dict]):
        """
        Инициализация менеджера дополнительного времени.

        Параметры:
            players: Список игроков команды (словари с 'id', 'position', 'name', 'number')

        Особенности:
            - Берёт только первых 5 игроков (по правилам ДВ)
            - Преобразует их в ExtraTimePlayer
            - Инициализирует вспомогательные менеджеры
        """
        self.players = [
            ExtraTimePlayer(
                player_id=p['id'],
                position=p['position'],
                name=p.get('name', f'Игрок {p["id"]}'),
                number=p['number']
            )
            for p in players[:5]  # первые 5 игроков
        ]

        self.dice_manager = DiceManager()

        self.action_calculator = ActionCalculator()

    def play_extra_time(self) -> Dict[str, int]:
        """
        Проводит дополнительное время: 2 ставки на каждого из 5 игроков.

        Возвращает:
            {'goals': int, 'passes': int, 'defenses': int} — итоговые действия от ДВ
        """
        actions = {'goals': 0, 'passes': 0, 'defenses': 0}

        for player in self.players:
            # В дополнительное время каждая ставка на гол разрешена
            for _ in range(2):  # две ставки на игрока
                dice_roll = self.dice_manager.roll(
                    player_id=player.player_id,
                    player_position=player.position,
                    player_db_id=player.player_id  # или другой ID, если есть
                )

                # В ДВ можно ставить на гол (exact)
                bet_type = 'exact'  # фиксировано для ДВ
                bet_value = str(random.randint(1, 6))  # случайное точное число

                bet_won = self.bet_checker.check_bet(bet_type, dice_roll.value, bet_value)

                player_actions = self.action_calculator.calculate_actions(
                    player.position, bet_type, bet_won
                )

                actions['goals'] += player_actions['goals']
                actions['passes'] += player_actions['passes']
                actions['defenses'] += player_actions['defenses']

        return actions


# ──────────────────────────────────────────────────────────────
# Серия пенальти
# ──────────────────────────────────────────────────────────────


class PenaltyShootout:
    """
    Управление серией пенальти (5 ударов + до победы).

    Особенности:
    - Играется до 5 ударов на команду
    - Если после 5 ударов ничья — продолжается до первого преимущества
    - Возвращает итоговый счёт и победителя
    """

    def __init__(self, max_shots: int = 5):
        """
        Инициализация серии пенальти.

        Параметры:
            max_shots: Количество ударов на команду (по умолчанию 5)
        """
        self.max_shots = max_shots
        self.shots_taken = 0
        self.team1_score = 0
        self.team2_score = 0

    def play_round(self) -> None:
        """
        Проводит один раунд пенальти (по одному удару от каждой команды).
        """
        # Удар команды 1
        if random.random() < 0.75:  # 75% шанс забить (можно настроить)
            self.team1_score += 1

        # Удар команды 2
        if random.random() < 0.75:
            self.team2_score += 1

        self.shots_taken += 2

    def play_full_series(self) -> Tuple[int, int, int]:
        """
        Проводит полную серию пенальти.

        Возвращает:
            (team1_score, team2_score, winner) — где winner = 1 или 2
        """
        # Первые 5 ударов
        for _ in range(self.max_shots):
            self.play_round()

            # Проверяем, можно ли определить победителя досрочно
            if self.shots_taken >= self.max_shots * 2:
                diff = abs(self.team1_score - self.team2_score)
                shots_left = (self.max_shots * 2) - self.shots_taken

                if diff > shots_left:
                    break

        # Если после 5 ударов ничья — продолжаем до победы
        while self.team1_score == self.team2_score:
            self.play_round()

        winner = 1 if self.team1_score > self.team2_score else 2
        is_finished = True

        return self.team1_score, self.team2_score, winner

    def get_summary(self) -> str:
        """
        Возвращает текстовую сводку по серии пенальти.

        Возвращает:
            Строка с итоговым счётом и победителем
        """
        summary = "🎯 **Серия пенальти:**\n\n"

        summary += f"Команда 1: {self.team1_score} голов\n"
        summary += f"Команда 2: {self.team2_score} голов\n"
        summary += f"Сделано ударов: {self.shots_taken}\n"

        if self.team1_score > self.team2_score:
            summary += "\n🏆 **Победила команда 1!**"
        elif self.team2_score > self.team1_score:
            summary += "\n🏆 **Победила команда 2!**"
        else:
            summary += "\n🤝 **Продолжаем...**"

        return summary