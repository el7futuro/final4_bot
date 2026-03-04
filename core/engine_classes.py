# core/engine_classes.py
"""
Отдельный модуль для классов, перечислений и моделей, чтобы разорвать циклический импорт.
Здесь хранятся все классы, enum'ы и Base, которые используются в нескольких местах.
"""

from enum import Enum
from typing import Dict, List, Tuple, Optional

from sqlalchemy import Column, Integer, String, Enum as SQLEnum, JSON, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from datetime import datetime

import random

Base = declarative_base()


# ──────────────────────────────────────────────────────────────
# Перечисления (Enum) для игры
# ──────────────────────────────────────────────────────────────


class BetType(Enum):
    """Типы ставок в Final 4.

    Используется в модели Bet и при валидации ставок.
    """
    EVEN_ODD = "EVEN_ODD"  # Чёт/Нечёт
    BIG_SMALL = "BIG_SMALL"  # Больше/Меньше (1-3 / 4-6)
    GOAL = "exact"  # Точное число на кубике


class CardType(Enum):
    """Типы карточек «Свисток».

    Каждая карточка имеет уникальное название и эффект.
    """
    HAT_TRICK = "hat_trick"  # +3 гола
    DOUBLE = "double"  # +2 гола
    GOAL = "goal"  # +1 гол
    OWN_GOAL = "own_goal"  # +1 гол сопернику
    VAR = "var"  # отменяет карточку соперника
    OFFSIDE = "offside"  # отменяет гол
    PENALTY = "penalty"  # пенальти (дополнительная ставка)
    RED_CARD = "red_card"  # удаление (теряет все действия)
    YELLOW_CARD = "yellow_card"  # предупреждение (теряет одно действие)
    FOUL = "foul"  # фол (-1 отбитие)
    LOST_BALL = "lost_ball"  # потеря (-1 передача)
    INTERCEPTION = "interception"  # перехват (+1 передача)
    TACKLE = "tackle"  # отбор (+1 отбитие)


class BetStatus(Enum):
    """Статусы ставки в БД.

    Используется в модели Bet для отслеживания состояния ставки.
    """
    PENDING = "PENDING"  # ставка сделана, но не разыграна
    WON = "WON"  # выиграна
    LOST = "LOST"  # проиграна


# ──────────────────────────────────────────────────────────────
# Модель ставки (Bet)
# ──────────────────────────────────────────────────────────────


class Bet(Base):
    """
    Модель ставки в базе данных.

    Хранит информацию о каждой ставке игрока или бота.
    """
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    player_id = Column(Integer, nullable=False)  # ID игрока из команды
    bet_type = Column(SQLEnum(BetType), nullable=False)
    bet_value = Column(String, nullable=False)  # "чёт", "нечёт", "меньше", "больше", "1" и т.д.
    player_position = Column(String, nullable=False)  # "GK", "DF", "MF", "FW"
    dice_roll = Column(Integer, nullable=True)  # результат кубика
    bet_result = Column(SQLEnum(BetStatus), default=BetStatus.PENDING)
    actions_gained = Column(JSON, nullable=True)  # {"goals": 0, "passes": 0, "defenses": 0}
    turn_number = Column(Integer, nullable=False)  # номер хода
    bet_order = Column(Integer, nullable=False)  # 1 или 2 (первая/вторая ставка в ход)
    card_drawn_id = Column(Integer, ForeignKey("cards.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Связи с другими моделями
    match = relationship("Match", back_populates="bets")
    user = relationship("User", back_populates="bets")

    def __repr__(self) -> str:
        return f"<Bet id={self.id} match={self.match_id} player={self.player_id} type={self.bet_type} value={self.bet_value}>"


# ──────────────────────────────────────────────────────────────
# Основной игровой движок
# ──────────────────────────────────────────────────────────────


class Final4GameEngine:
    """
    Основной движок игры Final 4.

    Содержит всю игровую логику:
    - Броски кубика
    - Расчёт действий по ставкам
    - Обработка карточек «Свисток»
    - Применение эффектов карточек
    - Расчёт результата матча
    """

    def __init__(self):
        """
        Инициализация игрового движка.

        Особенности:
            - Создаёт колоду карточек
            - Инициализирует состояние текущего раунда
        """
        self.card_deck = self._create_card_deck()

        # Состояние текущего раунда
        self.current_round_cards = {'player1': None, 'player2': None}
        self.actions_before_cards = {'player1': None, 'player2': None}

    def _create_card_deck(self) -> List[Dict]:
        """
        Создаёт полную колоду карточек «Свисток» (40 карт) и перемешивает её.

        Возвращает:
            Список словарей с информацией о каждой карточке
        """
        cards = []

        # Количество карточек каждого типа (по правилам игры)
        card_counts = [
            (CardType.HAT_TRICK, 1),
            (CardType.DOUBLE, 1),
            (CardType.GOAL, 2),
            (CardType.OWN_GOAL, 1),
            (CardType.VAR, 2),
            (CardType.OFFSIDE, 2),
            (CardType.PENALTY, 2),
            (CardType.RED_CARD, 2),
            (CardType.YELLOW_CARD, 3),
            (CardType.FOUL, 6),
            (CardType.LOST_BALL, 6),
            (CardType.INTERCEPTION, 6),
            (CardType.TACKLE, 6),
        ]

        for card_type, count in card_counts:
            for i in range(count):
                cards.append({
                    'id': len(cards) + 1,
                    'type': card_type.value,
                    'name': self._get_card_name(card_type),
                    'description': self._get_card_description(card_type)
                })

        random.shuffle(cards)
        return cards

    def _get_card_name(self, card_type: CardType) -> str:
        """
        Возвращает человекочитаемое название карточки.

        Параметры:
            card_type: Тип карточки из CardType

        Возвращает:
            Название на русском языке
        """
        names = {
            CardType.HAT_TRICK: "Хэт-трик",
            CardType.DOUBLE: "Дубль",
            CardType.GOAL: "Гол",
            CardType.OWN_GOAL: "Автогол",
            CardType.VAR: "ВАР",
            CardType.OFFSIDE: "Офсайд",
            CardType.PENALTY: "Пенальти",
            CardType.RED_CARD: "Удаление",
            CardType.YELLOW_CARD: "Предупреждение",
            CardType.FOUL: "Фол",
            CardType.LOST_BALL: "Потеря",
            CardType.INTERCEPTION: "Перехват",
            CardType.TACKLE: "Отбор"
        }
        return names.get(card_type, "Неизвестная карта")

    def _get_card_description(self, card_type: CardType) -> str:
        """
        Возвращает описание эффекта карточки.

        Параметры:
            card_type: Тип карточки из CardType

        Возвращает:
            Текст описания эффекта
        """
        descriptions = {
            CardType.HAT_TRICK: "Футболист получает 3 гола",
            CardType.DOUBLE: "Футболист получает 2 гола",
            CardType.GOAL: "Футболист получает гол",
            CardType.OWN_GOAL: "Соперник получает +1 гол",
            CardType.VAR: "Отменяет действие карточки соперника",
            CardType.OFFSIDE: "Отменяет гол футболиста соперника",
            CardType.PENALTY: "Дает право на дополнительную ставку Меньше/Больше",
            CardType.RED_CARD: "Футболист теряет все полезные действия",
            CardType.YELLOW_CARD: "Футболист теряет одно полезное действие",
            CardType.FOUL: "Футболист теряет одно «отбитие»",
            CardType.LOST_BALL: "Футболист теряет «передачу»",
            CardType.INTERCEPTION: "Футболист получает дополнительную «передачу»",
            CardType.TACKLE: "Футболист получает дополнительное «отбитие»"
        }
        return descriptions.get(card_type, "Неизвестный эффект")

    def roll_dice(self) -> int:
        """
        Выполняет бросок кубика (1-6).

        Возвращает:
            Число от 1 до 6
        """
        return random.randint(1, 6)

    def get_actions_for_player(self, position: str, bet_type: BetType, bet_success: bool) -> Dict[str, int]:
        """
        Возвращает полезные действия для футболиста по результату ставки.

        Параметры:
            position: Позиция игрока (GK, DF, MF, FW)
            bet_type: Тип ставки
            bet_success: Успешна ли ставка

        Возвращает:
            Словарь {'goals': int, 'passes': int, 'defenses': int}
        """
        actions = {'goals': 0, 'passes': 0, 'defenses': 0}

        if not bet_success:
            return actions

        # Логика расчёта действий (можно вынести в отдельный класс, если нужно)
        if position == 'GK':
            if bet_type == BetType.EVEN_ODD:
                actions['defenses'] = 3
        elif position == 'DF':
            if bet_type == BetType.EVEN_ODD:
                actions['defenses'] = 2
            elif bet_type == BetType.BIG_SMALL:
                actions['passes'] = 1
            elif bet_type == BetType.GOAL:
                actions['goals'] = 1
        elif position == 'MF':
            if bet_type == BetType.EVEN_ODD:
                actions['defenses'] = 1
            elif bet_type == BetType.BIG_SMALL:
                actions['passes'] = 2
            elif bet_type == BetType.GOAL:
                actions['goals'] = 1
        elif position == 'FW':
            if bet_type == BetType.BIG_SMALL:
                actions['passes'] = 1
            elif bet_type == BetType.GOAL:
                actions['goals'] = 1

        return actions

    def draw_card(self) -> Optional[Dict]:
        """
        Вытягивает случайную карточку из колоды.

        Возвращает:
            Словарь с информацией о карточке или None, если колода пуста
        """
        if not self.card_deck:
            return None
        return self.card_deck.pop()

    def start_new_round(self, player1_actions: Dict, player2_actions: Dict):
        """
        Начинает новый раунд: сохраняет действия до применения карточек.

        Параметры:
            player1_actions: Действия игрока 1 до карточек
            player2_actions: Действия игрока 2 до карточек
        """
        self.actions_before_cards['player1'] = player1_actions.copy()
        self.actions_before_cards['player2'] = player2_actions.copy()
        self.current_round_cards['player1'] = None
        self.current_round_cards['player2'] = None

    def record_card_in_round(self, player: str, card_type: CardType):
        """
        Записывает карточку, использованную в текущем раунде.

        Параметры:
            player: 'player1' или 'player2'
            card_type: Тип использованной карточки
        """
        self.current_round_cards[player] = card_type

    def apply_card_effect(
            self,
            card_type: CardType,
            player_actions: Dict,
            opponent_actions: Dict,
            player: str = 'player1',
            target_player_actions: Optional[Dict] = None,
            chosen_action: Optional[str] = None
    ) -> Tuple[Dict, Dict, Dict]:
        """
        Применяет эффект карточки «Свисток».

        Параметры:
            card_type: Тип карточки
            player_actions: Действия игрока, который использовал карточку
            opponent_actions: Действия соперника
            player: Кто использовал карточку ('player1' или 'player2')
            target_player_actions: Действия целевого игрока (для RED/YELLOW)
            chosen_action: Выбранное действие для удаления (для YELLOW)

        Возвращает:
            (обновлённые действия игрока, действия соперника, словарь с информацией о результате)
        """
        player_copy = player_actions.copy()
        opponent_copy = opponent_actions.copy()
        result_info = {'message': '', 'requires_choice': False, 'penalty_available': False}

        # Записываем карточку в текущем раунде
        self.record_card_in_round(player, card_type)

        if card_type == CardType.HAT_TRICK:
            player_copy['goals'] += 3
            result_info['message'] = "Хэт-трик! +3 гола"

        elif card_type == CardType.DOUBLE:
            player_copy['goals'] += 2
            result_info['message'] = "Дубль! +2 гола"

        elif card_type == CardType.GOAL:
            player_copy['goals'] += 1
            result_info['message'] = "Гол! +1 гол"

        elif card_type == CardType.OWN_GOAL:
            opponent_copy['goals'] += 1
            result_info['message'] = "Автогол! +1 гол сопернику"

        elif card_type == CardType.VAR:
            opponent_player = 'player2' if player == 'player1' else 'player1'
            opponent_card = self.current_round_cards[opponent_player]

            if opponent_card:
                result_info['message'] = f"ВАР отменил карточку соперника: {opponent_card['name']}"
                result_info['cancelled_card'] = opponent_card

                if self.actions_before_cards[opponent_player]:
                    if opponent_player == 'player1':
                        opponent_copy = self.actions_before_cards[opponent_player].copy()
                    else:
                        player_copy = self.actions_before_cards[opponent_player].copy()
            else:
                result_info['message'] = "ВАР: у соперника не было карточки в этом раунде"
                result_info['no_effect'] = True

        elif card_type == CardType.OFFSIDE:
            if opponent_copy['goals'] > 0:
                opponent_copy['goals'] -= 1
                result_info['message'] = "Офсайд! -1 гол сопернику"
            else:
                result_info['message'] = "Офсайд: у соперника нет голов"
                result_info['no_effect'] = True

        elif card_type == CardType.PENALTY:
            result_info['penalty_available'] = True
            result_info['message'] = "Пенальти! Вы можете сделать ставку Меньше/Больше"

        elif card_type == CardType.RED_CARD:
            if target_player_actions:
                result_info['message'] = "Красная карточка! Игрок удалён, все действия потеряны"
                return {'goals': 0, 'passes': 0, 'defenses': 0}, opponent_copy, result_info
            else:
                result_info['message'] = "Красная карточка: требуется выбор целевого игрока"
                result_info['requires_choice'] = True
                result_info['choice_type'] = 'red_card_target'

        elif card_type == CardType.YELLOW_CARD:
            if target_player_actions and chosen_action:
                if target_player_actions.get(chosen_action, 0) > 0:
                    target_player_actions[chosen_action] -= 1
                    result_info['message'] = f"Желтая карточка! Удалено действие: {chosen_action}"
                    if player == 'player1':
                        player_copy = target_player_actions
                    else:
                        opponent_copy = target_player_actions
                else:
                    result_info['message'] = f"Желтая карточка: действие {chosen_action} не доступно"
                    result_info['no_effect'] = True
            else:
                result_info['message'] = "Желтая карточка: требуется выбор действия для удаления"
                result_info['requires_choice'] = True
                result_info['choice_type'] = 'yellow_card_action'

        elif card_type == CardType.FOUL:
            if player_copy['defenses'] > 0:
                player_copy['defenses'] -= 1
                result_info['message'] = "Фол! -1 отбитие"
            else:
                result_info['message'] = "Фол: нет отбитий для удаления"
                result_info['no_effect'] = True

        elif card_type == CardType.LOST_BALL:
            if player_copy['passes'] > 0:
                player_copy['passes'] -= 1
                result_info['message'] = "Потеря мяча! -1 передача"
            else:
                result_info['message'] = "Потеря мяча: нет передач для удаления"
                result_info['no_effect'] = True

        elif card_type == CardType.INTERCEPTION:
            player_copy['passes'] += 1
            result_info['message'] = "Перехват! +1 передача"

        elif card_type == CardType.TACKLE:
            player_copy['defenses'] += 1
            result_info['message'] = "Отбор мяча! +1 отбитие"

        return player_copy, opponent_copy, result_info

    def process_penalty(self, player_actions: Dict, dice_roll: int, bet_choice: str) -> Tuple[Dict, Dict]:
        """
        Обрабатывает пенальти: дополнительная ставка Меньше/Больше.

        Параметры:
            player_actions: Действия игрока, который выиграл пенальти
            dice_roll: Результат кубика
            bet_choice: Выбор игрока ("меньше" или "больше")

        Возвращает:
            Обновлённые действия и словарь с результатом
        """
        actions = player_actions.copy()
        result_info = {}

        is_less = dice_roll <= 3
        bet_won = (bet_choice == "меньше" and is_less) or (bet_choice == "больше" and not is_less)

        if bet_won:
            actions['goals'] += 1
            result_info['message'] = f"Пенальти забит! +1 гол (выпало: {dice_roll}, ставка: {bet_choice})"
            result_info['success'] = True
        else:
            result_info['message'] = f"Пенальти не забит (выпало: {dice_roll}, ставка: {bet_choice})"
            result_info['success'] = False

        return actions, result_info

    def get_available_actions_for_yellow_card(self, player_actions: Dict) -> List[str]:
        """
        Возвращает список действий, которые можно удалить жёлтой карточкой.

        Параметры:
            player_actions: Действия игрока

        Возвращает:
            Список доступных действий ('goals', 'passes', 'defenses')
        """
        available = []
        if player_actions.get('goals', 0) > 0:
            available.append('goals')
        if player_actions.get('passes', 0) > 0:
            available.append('passes')
        if player_actions.get('defenses', 0) > 0:
            available.append('defenses')
        return available

    def calculate_match_result(self, player1_actions: Dict, player2_actions: Dict) -> Tuple[int, int]:
        """
        Рассчитывает итоговый счёт матча по правилам Final 4.

        Параметры:
            player1_actions: Действия игрока 1 (goals, passes, defenses)
            player2_actions: Действия игрока 2

        Возвращает:
            (score_player1, score_player2) — голы после учёта защит и передач
        """
        p1_goals = player1_actions.get('goals', 0)
        p1_passes = player1_actions.get('passes', 0)
        p1_defenses = player1_actions.get('defenses', 0)

        p2_goals = player2_actions.get('goals', 0)
        p2_passes = player2_actions.get('passes', 0)
        p2_defenses = player2_actions.get('defenses', 0)

        # Голы команды 1 (учитываем защиту соперника)
        p1_remaining_defenses = p2_defenses - p1_passes
        if p1_remaining_defenses <= 0:
            p1_score = p1_goals
        else:
            # 1 гол уничтожает 2 отбития
            defenses_to_remove = p1_remaining_defenses
            goals_needed = (defenses_to_remove + 1) // 2
            p1_score = max(0, p1_goals - goals_needed)

        # Голы команды 2
        p2_remaining_defenses = p1_defenses - p2_passes
        if p2_remaining_defenses <= 0:
            p2_score = p2_goals
        else:
            defenses_to_remove = p2_remaining_defenses
            goals_needed = (defenses_to_remove + 1) // 2
            p2_score = max(0, p2_goals - goals_needed)

        return p1_score, p2_score