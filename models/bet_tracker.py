# models/bet_tracker.py
"""
Трекер ограничений и квот по ставкам для одного матча в Final 4.

Отслеживает:
- сколько раз ставили на каждого игрока
- использованные квоты на голы по позициям (DF:1, MF:3, FW:4)
- использованных игроков под Чет/Нечет (макс 6, FW запрещены)
- состояние текущего хода (ставки, карточки)
- переход в дополнительное время и его ограничения

Все проверки доступности ставок реализованы здесь.
"""

from __future__ import annotations

from typing import Dict, Set, List, Tuple, Optional, Any

from enum import Enum
from pydantic import BaseModel, Field


class BetType(str, Enum):
    """Типы ставок, поддерживаемые в игре"""
    EVEN_ODD = "EVEN_ODD"     # Чёт / Нечёт → отбития
    BIG_SMALL = "big_small"   # Меньше (1-3) / Больше (4-6) → передачи
    GOAL = "goal"             # Точное число → голы


class BetTracker(BaseModel):
    """
    Основной класс-трекер ограничений ставок для матча.

    Хранит состояние квот и использованных ресурсов,
    предоставляет методы проверки возможности ставки и регистрации.
    """

    # ─── Постоянные данные матча ───────────────────────────────────────

    # Сколько раз ставили на каждого игрока (player_id → count)
    player_bets: Dict[int, int] = Field(default_factory=dict)

    # Использованные квоты на голы по позициям
    goal_quotas_used: Dict[str, int] = Field(
        default_factory=lambda: {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}
    )

    # Игроки, уже использовавшие ставку Чет/Нечет (максимум 6)
    EVEN_ODD_players: Set[int] = Field(default_factory=set)

    # ─── Состояние текущего хода ───────────────────────────────────────

    current_turn: int = 1
    is_extra_time: bool = False

    # Список id игроков, выбранных для дополнительного времени
    extra_time_player_ids: List[int] = Field(default_factory=list)

    # Ставки, сделанные в текущем ходе
    current_turn_bets: List[Dict[str, Any]] = Field(default_factory=list)

    # Карточки, полученные в текущем ходе (их идентификаторы или коды)
    current_turn_cards: List[str] = Field(default_factory=list)

    # Уже взята карточка в этом ходе? (макс 1 за ход)
    card_taken_this_turn: bool = False

    # ─── Методы сброса и регистрации ───────────────────────────────────

    def reset_current_turn(self) -> None:
        """Сбрасывает временные данные текущего хода перед следующим."""
        self.current_turn_bets.clear()
        self.current_turn_cards.clear()
        self.card_taken_this_turn = False

    def register_bet(
        self,
        player_id: int,
        position: str,
        bet_type: BetType,
        bet_value: str
    ) -> None:
        """
        Регистрирует сделанную ставку и обновляет все счётчики.

        Args:
            player_id:   id игрока в команде
            position:    GK / DF / MF / FW
            bet_type:    тип ставки
            bet_value:   "чет", "нечет", "меньше", "больше", "1"…"6"
        """
        # Обновляем общее количество ставок на игрока
        self.player_bets[player_id] = self.player_bets.get(player_id, 0) + 1

        # Запоминаем в текущем ходе
        self.current_turn_bets.append({
            'player_id': player_id,
            'position': position,
            'bet_type': bet_type,
            'value': bet_value
        })

        # Обновляем глобальные квоты
        if bet_type == BetType.GOAL:
            self.goal_quotas_used[position] = \
                self.goal_quotas_used.get(position, 0) + 1

        elif bet_type == BetType.EVEN_ODD:
            self.EVEN_ODD_players.add(player_id)

    # ─── Проверки доступности ставок ───────────────────────────────────

    def can_bet_on_player(
        self,
        player_id: int,
        position: str,
        turn_number: int
    ) -> Tuple[bool, str]:
        """
        Можно ли поставить на этого игрока в указанном ходе.

        Возвращает: (можно, причина_если_нельзя)
        """
        # 1. Лимит ставок на одного игрока
        max_bets_per_player = 1 if position == 'GK' else 2
        used = self.player_bets.get(player_id, 0)

        if used >= max_bets_per_player:
            return False, f"Исчерпан лимит ставок на игрока ({max_bets_per_player})"

        # 2. Правила основного времени
        if not self.is_extra_time:
            if turn_number == 1:
                # Ход 1 — только вратарь, и только один раз
                if position != 'GK':
                    return False, "В первом ходе можно ставить только на вратаря"
                if used > 0:
                    return False, "Вратарь уже использован в этом матче"
                return True, ""

            if 2 <= turn_number <= 11:
                if position == 'GK':
                    return False, "Вратарь доступен только в первом ходе"

        # 3. Правила дополнительного времени
        if self.is_extra_time:
            if player_id not in self.extra_time_player_ids:
                return False, "Игрок не выбран для дополнительного времени"

        return True, ""

    def can_bet_goal(self, position: str, player_id: int) -> Tuple[bool, str]:
        """
        Можно ли поставить на гол (точное число) для данной позиции и игрока.
        """
        if position == 'GK':
            return False, "Вратарь не может ставить на гол"

        limits = {'DF': 1, 'MF': 3, 'FW': 4}
        max_for_pos = limits.get(position, 0)

        if self.goal_quotas_used.get(position, 0) >= max_for_pos:
            return False, f"Исчерпана квота на голы для {position} ({max_for_pos})"

        # В ДВ — только одна ставка на гол на игрока
        if self.is_extra_time and self._player_has_goal_bet(player_id):
            return False, "В дополнительном времени нельзя две ставки на гол"

        return True, ""

    def can_bet_EVEN_ODD(self, player_id: int, position: str) -> Tuple[bool, str]:
        """
        Можно ли поставить на Чет/Нечет.
        """
        if position == 'FW':
            return False, "Нападающие не могут ставить на чет/нечет"

        if len(self.EVEN_ODD_players) >= 6:
            return False, "Исчерпан лимит игроков на чет/нечет (6)"

        if player_id in self.EVEN_ODD_players:
            return False, "Игрок уже использовал ставку чет/нечет"

        return True, ""

    def can_bet_big_small(
        self,
        player_id: int,
        position: str,
        is_second_bet: bool = False
    ) -> Tuple[bool, str]:
        """
        Можно ли поставить на Больше/Меньше.
        """
        if position == 'GK':
            return False, "Вратарь не может ставить на больше/меньше"

        if not is_second_bet:
            return True, ""

        # Нельзя две одинаковые ставки в одном ходе
        for bet in self.current_turn_bets:
            if (bet['player_id'] == player_id and
                    bet['bet_type'] == BetType.BIG_SMALL):
                return False, "Нельзя делать две ставки Больше/Меньше в одном ходе"

        return True, ""

    def get_available_bet_types(
        self,
        player_id: int,
        position: str,
        is_second_bet: bool = False
    ) -> List[BetType]:
        """
        Возвращает список типов ставок, которые сейчас можно сделать на игрока.
        """
        available: List[BetType] = []

        can_even_odd, _ = self.can_bet_EVEN_ODD(player_id, position)
        if can_even_odd:
            available.append(BetType.EVEN_ODD)

        can_big_small, _ = self.can_bet_big_small(player_id, position, is_second_bet)
        if can_big_small:
            available.append(BetType.BIG_SMALL)

        can_goal, _ = self.can_bet_goal(position, player_id)
        if can_goal:
            available.append(BetType.GOAL)

        return available

    # ─── Вспомогательные проверки ──────────────────────────────────────

    def _player_has_goal_bet(self, player_id: int) -> bool:
        """Есть ли уже ставка на гол у этого игрока в текущем ходе?"""
        for bet in self.current_turn_bets:
            if bet['player_id'] == player_id and bet['bet_type'] == BetType.GOAL:
                return True
        return False

    def get_player_bet_count(self, player_id: int) -> int:
        """Сколько ставок уже сделано на этого игрока за весь матч."""
        return self.player_bets.get(player_id, 0)

    def get_goal_quota_used(self, position: str) -> int:
        """Сколько ставок на гол уже использовано для данной позиции."""
        return self.goal_quotas_used.get(position, 0)

    def get_goal_quota_left(self, position: str) -> int:
        """Сколько ставок на гол ещё осталось для позиции."""
        limits = {'GK': 0, 'DF': 1, 'MF': 3, 'FW': 4}
        return limits.get(position, 0) - self.goal_quotas_used.get(position, 0)

    def get_EVEN_ODD_count(self) -> int:
        """Сколько игроков уже использовали Чет/Нечет."""
        return len(self.EVEN_ODD_players)

    def get_remaining_EVEN_ODD(self) -> int:
        """Сколько ещё игроков можно поставить на Чет/Нечет."""
        return 6 - len(self.EVEN_ODD_players)

    # ─── Дополнительное время ──────────────────────────────────────────

    def start_extra_time(self, extra_player_ids: List[int]) -> None:
        """
        Запускает дополнительное время с выбранными запасными.
        """
        self.is_extra_time = True
        self.current_turn = 1
        self.extra_time_player_ids = extra_player_ids[:]
        self.reset_current_turn()
        # Не сбрасываем player_bets - они нужны для проверки,
        # что в ДВ используются только новые игроки
    def get_extra_time_players(self, all_players: List[Dict]) -> List[Dict]:
        """
        Возвращает список игроков, допущенных к ставкам в дополнительное время.
        Только те, кто не делал ставок в основном времени.
        """
        used_ids = set(self.player_bets.keys())
        return [
            p for p in all_players
            if p.get('id') not in used_ids
        ]

    # ─── Сериализация / десериализация ─────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует состояние трекера в словарь для сохранения в БД."""
        serialized_turn_bets = []
        for bet in self.current_turn_bets:
            bet_copy = bet.copy()
            if isinstance(bet_copy.get('bet_type'), BetType):
                bet_copy['bet_type'] = bet_copy['bet_type'].value
            serialized_turn_bets.append(bet_copy)

        return {
            'player_bets': dict(self.player_bets),
            'goal_quotas_used': dict(self.goal_quotas_used),
            'EVEN_ODD_players': list(self.EVEN_ODD_players),
            'current_turn': self.current_turn,
            'is_extra_time': self.is_extra_time,
            'extra_time_player_ids': self.extra_time_player_ids,
            'current_turn_bets': serialized_turn_bets,
            'current_turn_cards': self.current_turn_cards,
            'card_taken_this_turn': self.card_taken_this_turn,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BetTracker':
        """Восстанавливает трекер из словаря (из БД)."""
        if not data:
            return cls()

        tracker = cls()

        tracker.player_bets = data.get('player_bets', {})
        tracker.goal_quotas_used = data.get('goal_quotas_used', {
            'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0
        })
        tracker.EVEN_ODD_players = set(data.get('EVEN_ODD_players', []))

        tracker.current_turn = data.get('current_turn', 1)
        tracker.is_extra_time = data.get('is_extra_time', False)
        tracker.extra_time_player_ids = data.get('extra_time_player_ids', [])

        # Восстановление ставок текущего хода
        current_bets = data.get('current_turn_bets', [])
        restored_bets = []
        for bet in current_bets:
            bet_copy = bet.copy()
            bt_str = bet_copy.get('bet_type')
            if isinstance(bt_str, str):
                try:
                    bet_copy['bet_type'] = BetType(bt_str)
                except ValueError:
                    pass  # оставляем как есть, если значение некорректно
            restored_bets.append(bet_copy)
        tracker.current_turn_bets = restored_bets

        tracker.current_turn_cards = data.get('current_turn_cards', [])
        tracker.card_taken_this_turn = data.get('card_taken_this_turn', False)

        return tracker