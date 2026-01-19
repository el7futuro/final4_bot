# core/extra_time.py
"""
Логика дополнительного времени и пенальти для Final 4.
"""

import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from .dice import DiceManager, BetChecker, ActionCalculator


@dataclass
class ExtraTimePlayer:
    """Игрок для дополнительного времени"""
    player_id: int  # ID в команде
    position: str  # GK, DF, MF, FW
    name: str
    number: int
    has_pass: bool = False  # Есть ли передача для пенальти


class ExtraTimeManager:
    """Управление дополнительным временем"""

    def __init__(self, players: List[Dict]):
        self.players = [
            ExtraTimePlayer(
                player_id=p['id'],
                position=p['position'],

                number=p['number']
            )
            for p in players[:5]  # Берем первых 5 игроков
        ]
        self.dice_manager = DiceManager()
        self.bet_checker = BetChecker()
        self.action_calculator = ActionCalculator()

    def play_extra_time(self) -> Dict[str, int]:
        """Проводит дополнительное время"""
        actions = {'goals': 0, 'passes': 0, 'defenses': 0}

        for player in self.players:
            # В ДВ каждая ставка на гол разрешена
            for _ in range(2):  # Две ставки на игрока
                dice_roll = self.dice_manager.roll(
                    player_id=player.player_id,
                    player_position=player.position,
                    player_db_id=player.player_id
                )

                # В ДВ можно ставить на гол каждому игроку
                bet_success = self.bet_checker.check_exact_number(
                    dice_roll, str(random.randint(1, 6))
                )

                if bet_success:
                    actions['goals'] += 1
                    # Также добавляем передачи для пенальти
                    player.has_pass = True

        return actions

    def get_penalty_order(self) -> List[ExtraTimePlayer]:
        """Определяет порядок пробития пенальти"""
        # Согласно правилам: сначала игроки из ДВ, затем остальные
        return self.players.copy()


class PenaltyShootout:
    """Серия пенальти"""

    def __init__(self, team1_players: List[ExtraTimePlayer], team2_players: List[ExtraTimePlayer]):
        self.team1_players = team1_players
        self.team2_players = team2_players
        self.team1_score = 0
        self.team2_score = 0
        self.shots_taken = 0
        self.max_shots = 5  # Первые 5 ударов

    def take_penalty(self, player: ExtraTimePlayer) -> bool:
        """Пробитие пенальти"""
        self.shots_taken += 1

        # Согласно правилам: если у игрока есть передача, он забивает гол
        if player.has_pass:
            return True

        # Иначе шанс 50%
        return random.random() > 0.5

    def play_round(self) -> Tuple[bool, bool]:
        """Один раунд пенальти (по одному удару от каждой команды)"""
        if self.shots_taken >= len(self.team1_players) * 2:
            return False, False

        # Определяем текущих игроков
        idx = self.shots_taken // 2
        team1_score = False
        team2_score = False

        if idx < len(self.team1_players):
            team1_score = self.take_penalty(self.team1_players[idx])
            if team1_score:
                self.team1_score += 1

        if idx < len(self.team2_players):
            team2_score = self.take_penalty(self.team2_players[idx])
            if team2_score:
                self.team2_score += 1

        return team1_score, team2_score

    def play_full_shootout(self) -> Tuple[int, int, bool]:
        """Проводит полную серию пенальти"""
        # Первые 5 ударов
        for _ in range(self.max_shots):
            self.play_round()

            # Проверяем, можно ли определить победителя
            if self.shots_taken >= self.max_shots * 2:
                diff = abs(self.team1_score - self.team2_score)
                shots_left = (self.max_shots * 2) - self.shots_taken

                if diff > shots_left:
                    # Победитель определен досрочно
                    break

        # Если после 5 ударов ничья, продолжаем до победы
        while self.team1_score == self.team2_score:
            self.play_round()

        winner = 1 if self.team1_score > self.team2_score else 2
        is_finished = True

        return self.team1_score, self.team2_score, winner

    def get_summary(self) -> str:
        """Текстовая сводка по пенальти"""
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