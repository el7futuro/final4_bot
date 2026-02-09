# models/bet_tracker.py
"""
Трекер ограничений по ставкам для матча Final 4.
Отслеживает использованные квоты и ограничения согласно правилам:
1. Ход 1: только вратарь (обязательная ставка чет/нечет)
2. Ходы 2-11: все кроме вратаря
3. Максимум 2 ставки на игрока (1 для вратаря)
4. Квоты на голы: DF=1, MF=3, FW=4 (на всех игроков позиции)
5. Чет/нечет: максимум 6 игроков (включая вратаря), FW нельзя
6. Дополнительное время: 5 запасных, ставки как в основном времени
"""

from typing import Dict, Set, List, Optional, Tuple
from pydantic import BaseModel
from enum import Enum


class BetType(str, Enum):
    """Типы ставок"""
    EVEN_ODD = "even_odd"  # Чет/нечет
    BIG_SMALL = "big_small"  # Больше/меньше
    GOAL = "goal"  # Точное число (гол)


class BetTracker(BaseModel):
    """Трекер ограничений по ставкам в матче."""

    # === БАЗОВЫЕ ДАННЫЕ ===

    # Ставки по игрокам: {player_id: count}
    player_bets: Dict[int, int] = {}

    # Квоты на голы по позициям (на команду)
    goal_quotas_used: Dict[str, int] = {
        'GK': 0,  # 0 (вратарь не может ставить на гол)
        'DF': 0,  # макс 1 на всех защитников
        'MF': 0,  # макс 3 на всех полузащитников
        'FW': 0  # макс 4 на всех форвардов
    }

    # Игроки, которые использовали ставку чет/нечет (макс 6)
    even_odd_players: Set[int] = set()

    # Текущий ход (1-11 основное время, 12+ ДВ)
    current_turn: int = 1

    # Флаг дополнительного времени
    is_extra_time: bool = False

    # Игроки, выбранные для ДВ (только те, кто не делал ставок в основном)
    extra_time_player_ids: List[int] = []

    # Ставки текущего хода [{player_id, bet_type, value}]
    current_turn_bets: List[Dict] = []

    # Карты, полученные в текущем ходе
    current_turn_cards: List[str] = []

    # Флаг: взята ли уже карта в этом ходе (макс 1 карта за ход)
    card_taken_this_turn: bool = False

    # === МЕТОДЫ ДЛЯ ОСНОВНОГО ВРЕМЕНИ ===

    def reset_current_turn(self):
        """Сбрасывает данные текущего хода для следующего."""
        self.current_turn_bets.clear()
        self.current_turn_cards.clear()
        self.card_taken_this_turn = False

    def register_bet(self, player_id: int, position: str, bet_type: BetType, bet_value: str) -> None:
        """Регистрирует ставку и обновляет счетчики."""
        # Обновляем счетчик ставок на игрока
        self.player_bets[player_id] = self.player_bets.get(player_id, 0) + 1

        # Регистрируем в текущем ходе
        self.current_turn_bets.append({
            'player_id': player_id,
            'position': position,
            'bet_type': bet_type,
            'value': bet_value
        })

        # Обновляем квоты
        if bet_type == BetType.GOAL:
            self.goal_quotas_used[position] += 1
        elif bet_type == BetType.EVEN_ODD:
            self.even_odd_players.add(player_id)

    def can_bet_on_player(self, player_id: int, position: str, turn_number: int) -> Tuple[bool, str]:
        """
        Можно ли сделать ставку на этого игрока в текущем ходе?

        Args:
            player_id: ID игрока
            position: Позиция (GK, DF, MF, FW)
            turn_number: Номер текущего хода

        Returns:
            (доступен, сообщение_об_ошибке)
        """
        # 1. Проверка максимума ставок на игрока
        max_bets = 1 if position == 'GK' else 2
        current_bets = self.player_bets.get(player_id, 0)

        if current_bets >= max_bets:
            return False, f"Лимит ставок на игрока ({max_bets}) исчерпан"

        # 2. Проверка для основного времени
        if not self.is_extra_time:
            # Ход 1: только вратарь
            if turn_number == 1:
                if position != 'GK':
                    return False, "В первом ходе доступен только вратарь"
                if current_bets > 0:
                    return False, "Вратарь уже использован в этом матче"

            # Ходы 2-11: все кроме вратаря
            elif 2 <= turn_number <= 11:
                if position == 'GK':
                    return False, "Вратарь доступен только в первом ходе"

        # 3. Проверка для ДВ (только игроки без ставок в основном)
        if self.is_extra_time:
            if player_id not in self.extra_time_player_ids:
                return False, "Игрок не выбран для дополнительного времени"

        return True, ""

    def can_bet_goal(self, position: str, player_id: int) -> Tuple[bool, str]:
        """
        Можно ли сделать ставку на гол для этой позиции?

        Особые правила:
        - В основном времени можно 2 ставки на гол на одного игрока
        - В ДВ нельзя две ставки на гол
        - Квоты действуют на всю команду по позициям
        """
        # 1. Вратарь не может ставить на гол
        if position == 'GK':
            return False, "Вратарь не может ставить на гол"

        limits = {'DF': 1, 'MF': 3, 'FW': 4}

        # 2. Проверяем общую квоту на позицию
        if self.goal_quotas_used[position] >= limits[position]:
            return False, f"Лимит ставок на гол для {position} ({limits[position]}) исчерпан"

        # 3. Проверка возможности второй ставки на гол для того же игрока
        if not self.is_extra_time and self._player_has_goal_bet(player_id):
            # В основном времени можно 2 ставки на гол на одного игрока
            # Но нужно проверить, что квота еще позволяет
            if self.goal_quotas_used[position] + 1 > limits[position]:
                return False, f"Лимит ставок на гол для {position} исчерпан"
            return True, ""

        # 4. В ДВ нельзя две ставки на гол
        if self.is_extra_time and self._player_has_goal_bet(player_id):
            return False, "В дополнительном времени нельзя две ставки на гол на одного игрока"

        return True, ""

    def can_bet_even_odd(self, player_id: int, position: str) -> Tuple[bool, str]:
        """
        Можно ли сделать ставку на чет/нечет?

        Правила:
        - Максимум 6 игроков (включая вратаря)
        - Форварды не могут ставить на чет/нечет
        """
        # 1. Форварды не могут
        if position == 'FW':
            return False, "Форварды не могут ставить на чет/нечет"

        # 2. Максимум 6 игроков
        if len(self.even_odd_players) >= 6:
            return False, "Лимит игроков на чет/нечет (6) исчерпан"

        # 3. Игрок уже ставил чет/нечет?
        if player_id in self.even_odd_players:
            return False, "Игрок уже использовал ставку на чет/нечет"

        return True, ""

    def can_bet_big_small(self, player_id: int, position: str, is_second_bet: bool = False) -> Tuple[bool, str]:
        """
        Можно ли сделать ставку на больше/меньше?

        Правила:
        1. Вратарь (GK) НЕ МОЖЕТ делать ставку на больше/меньше
        2. Нельзя делать две одинаковые ставки Больше/Меньше на одного игрока
        """
        # Правило 1: Вратарь не может делать ставку на больше/меньше
        if position == 'GK':
            return False, "Вратарь не может делать ставку на больше/меньше"

        if not is_second_bet:
            return True, ""

        # Проверяем, есть ли уже ставка big_small на этого игрока в этом ходе
        for bet in self.current_turn_bets:
            if bet['player_id'] == player_id and bet['bet_type'] == BetType.BIG_SMALL:
                return False, "Нельзя делать две одинаковые ставки Больше/Меньше"

        return True, ""

    def get_available_bet_types(self, player_id: int, position: str,
                                is_second_bet: bool = False) -> List[BetType]:
        """
        Возвращает доступные типы ставок для игрока.

        Args:
            player_id: ID игрока
            position: Позиция игрока
            is_second_bet: Это вторая ставка на игрока в этом ходе?
        """
        available = []

        # Чет/нечет
        can_even_odd, _ = self.can_bet_even_odd(player_id, position)
        if can_even_odd:
            available.append(BetType.EVEN_ODD)

        # Больше/меньше
        can_big_small, _ = self.can_bet_big_small(player_id, position, is_second_bet)  # ← ДОБАВЬТЕ position
        if can_big_small:
            available.append(BetType.BIG_SMALL)

        # Гол
        can_goal, _ = self.can_bet_goal(position, player_id)
        if can_goal:
            available.append(BetType.GOAL)

        return available

    def can_player_have_two_bets(self, player_id: int, position: str,
                                 all_players: List[Dict]) -> Tuple[bool, str]:
        """
        Проверяет, можно ли на этого игрока сделать ДВЕ РАЗНЫЕ ставки.
        Используется для предотвращения ситуации, когда в ходе нет доступных игроков.
        """
        available_types = self.get_available_bet_types(player_id, position, False)

        # Нужно минимум 2 разных типа ставок
        if len(available_types) < 2:
            return False, "Недостаточно доступных типов ставок"

        # Проверяем, что эти типы разные (не дважды одно и то же)
        # Например, нельзя [BIG_SMALL, BIG_SMALL]
        if len(set(available_types)) < 2:
            return False, "Нельзя сделать две разные ставки"

        return True, ""

    # === МЕТОДЫ ДЛЯ ДОПОЛНИТЕЛЬНОГО ВРЕМЕНИ ===

    def start_extra_time(self, extra_player_ids: List[int]) -> None:
        """Начинает дополнительное время."""
        self.is_extra_time = True
        self.current_turn = 1  # Начинаем счет ходов заново
        self.extra_time_player_ids = extra_player_ids
        self.reset_current_turn()

    def get_extra_time_players(self, all_players: List[Dict]) -> List[Dict]:
        """
        Возвращает игроков, доступных для ДВ.
        Только те, кто не делал ставок в основном времени.
        """
        return [
            player for player in all_players
            if player['id'] not in self.player_bets  # Не делал ставок
        ]

    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===

    def _player_has_goal_bet(self, player_id: int) -> bool:
        """Проверяет, есть ли у игрока ставка на гол."""
        # Проверяем в истории ставок
        for bet in self.current_turn_bets:
            if bet['player_id'] == player_id and bet['bet_type'] == BetType.GOAL:
                return True
        return False

    def get_player_bet_count(self, player_id: int) -> int:
        """Возвращает количество ставок, сделанных на игрока."""
        return self.player_bets.get(player_id, 0)

    def get_goal_quota_used(self, position: str) -> int:
        """Возвращает использованные ставки на гол для позиции."""
        return self.goal_quotas_used.get(position, 0)

    def get_goal_quota_left(self, position: str) -> int:
        """Возвращает оставшиеся ставки на гол для позиции."""
        limits = {'DF': 1, 'MF': 3, 'FW': 4, 'GK': 0}
        return limits.get(position, 0) - self.goal_quotas_used.get(position, 0)

    def get_even_odd_count(self) -> int:
        """Возвращает количество игроков, использовавших чет/нечет."""
        return len(self.even_odd_players)

    def get_remaining_even_odd(self) -> int:
        """Возвращает оставшееся количество игроков для чет/нечет."""
        return 6 - len(self.even_odd_players)

    # === СТРАТЕГИЧЕСКИЕ ПРОВЕРКИ ===

    def check_future_availability(self, all_players: List[Dict],
                                  current_turn: int) -> Tuple[bool, str]:
        """
        Проверяет, будет ли в следующем ходе доступен хотя бы один игрок
        с возможностью сделать 2 разные ставки.

        Args:
            all_players: Все игроки команды
            current_turn: Текущий ход

        Returns:
            (доступны_игроки, сообщение_об_ошибке)
        """
        if self.is_extra_time:
            return True, ""  # В ДВ своя логика

        next_turn = current_turn + 1
        if next_turn > 11:
            return True, ""  # Основное время закончится

        available_players = []

        for player in all_players:
            # Проверяем доступность в следующем ходе
            can_bet, _ = self.can_bet_on_player(
                player['id'], player['position'], next_turn
            )

            if can_bet:
                # Проверяем, что можно сделать 2 разные ставки
                can_two_bets, _ = self.can_player_have_two_bets(
                    player['id'], player['position'], all_players
                )

                if can_two_bets:
                    available_players.append(player)

        if not available_players:
            return False, (
                f"ВНИМАНИЕ: В ходе {next_turn} не будет доступных игроков! "
                f"Выберите другого игрока в этом ходе."
            )

        return True, ""

    def to_dict(self) -> Dict:
        """Сериализация в словарь для хранения в БД."""
        # Преобразуем BetType объекты в строки
        serialized_turn_bets = []
        for bet in self.current_turn_bets:
            serialized_bet = bet.copy()
            # Преобразуем BetType в строку
            if 'bet_type' in serialized_bet and isinstance(serialized_bet['bet_type'], BetType):
                serialized_bet['bet_type'] = serialized_bet['bet_type'].value
            serialized_turn_bets.append(serialized_bet)

        return {
            'player_bets': self.player_bets,
            'goal_quotas_used': self.goal_quotas_used,
            'even_odd_players': list(self.even_odd_players),
            'current_turn': self.current_turn,
            'is_extra_time': self.is_extra_time,
            'extra_time_player_ids': self.extra_time_player_ids,
            'current_turn_bets': serialized_turn_bets,  # Используем сериализованные ставки
            'current_turn_cards': self.current_turn_cards,
            'card_taken_this_turn': self.card_taken_this_turn,
        }


    @classmethod
    def from_dict(cls, data: Dict) -> 'BetTracker':
        """Десериализация из словаря."""
        if not data:
            return cls()  # ❗️ВАЖНО: Возвращаем пустой трекер
        tracker = cls()

        if 'player_bets' in data:
            tracker.player_bets = data['player_bets']

        if 'goal_quotas_used' in data:
            tracker.goal_quotas_used = data['goal_quotas_used']

        if 'even_odd_players' in data:
            tracker.even_odd_players = set(data['even_odd_players'])

        if 'current_turn' in data:
            tracker.current_turn = data['current_turn']

        if 'is_extra_time' in data:
            tracker.is_extra_time = data['is_extra_time']

        if 'extra_time_player_ids' in data:
            tracker.extra_time_player_ids = data['extra_time_player_ids']

        if 'current_turn_bets' in data:
            # Преобразуем строки обратно в BetType enum
            deserialized_turn_bets = []
            for bet in data['current_turn_bets']:
                deserialized_bet = bet.copy()
                if 'bet_type' in deserialized_bet and isinstance(deserialized_bet['bet_type'], str):
                    # Находим соответствующий BetType enum
                    for bt in BetType:
                        if bt.value == deserialized_bet['bet_type']:
                            deserialized_bet['bet_type'] = bt
                            break
                deserialized_turn_bets.append(deserialized_bet)
            tracker.current_turn_bets = deserialized_turn_bets

        if 'current_turn_cards' in data:
            tracker.current_turn_cards = data['current_turn_cards']

        if 'card_taken_this_turn' in data:
            tracker.card_taken_this_turn = data['card_taken_this_turn']

        return tracker