# core/game_engine.py
"""
Основной движок игры Final 4.
Объединяет все компоненты игры.
"""

from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
import random

# Импортируем все нужные компоненты
from .dice import DiceManager, BetChecker, ActionCalculator, DiceRoll
from .match_calculator import MatchCalculator, MatchResult
from .extra_time import ExtraTimeManager, PenaltyShootout
from .bot_ai import Final4BotAI, BotDifficulty


# Свои перечисления оставляем здесь
class BetType(Enum):
    """Типы ставок в Final 4"""
    ODD_EVEN = "odd_even"  # Чет/нечет
    LESS_MORE = "less_more"  # 1-3 (Меньше) / 4-6 (Больше)
    EXACT_NUMBER = "exact"  # Точное число


class CardType(Enum):
    """Типы карточек «Свисток» """
    HAT_TRICK = "hat_trick"  # Хэт-трик (+3 гола)
    DOUBLE = "double"  # Дубль (+2 гола)
    GOAL = "goal"  # Гол (+1 гол)
    OWN_GOAL = "own_goal"  # Автогол (+1 гол сопернику)
    VAR = "var"  # ВАР (отменяет карточку соперника)
    OFFSIDE = "offside"  # Офсайд (отменяет гол)
    PENALTY = "penalty"  # Пенальти
    RED_CARD = "red_card"  # Удаление
    YELLOW_CARD = "yellow_card"  # Предупреждение
    FOUL = "foul"  # Фол
    LOST_BALL = "lost_ball"  # Потеря
    INTERCEPTION = "interception"  # Перехват
    TACKLE = "tackle"  # Отбор


# Теперь класс Final4GameEngine может использовать все импортированные компоненты
class Final4GameEngine:
    """Движок игры Final 4"""

    def __init__(self):
        # Используем компоненты
        self.dice_manager = DiceManager()
        self.bet_checker = BetChecker()
        self.action_calculator = ActionCalculator()
        self.match_calculator = MatchCalculator()

        self.card_deck = self._create_card_deck()

        # Для отслеживания карточек в раунде
        self.current_round_cards = {'player1': None, 'player2': None}
        self.actions_before_cards = {'player1': None, 'player2': None}

    def _create_card_deck(self) -> List[Dict]:
        """Создает колоду карточек «Свисток» (40 карт)"""
        cards = []

        # Добавляем карточки согласно правилам
        card_types = [
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
            (CardType.TACKLE, 6)
        ]

        for card_type, count in card_types:
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
        """Возвращает название карточки"""
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
        """Возвращает описание эффекта карточки"""
        descriptions = {
            CardType.HAT_TRICK: "Футболист получает 3 гола",
            CardType.DOUBLE: "Футболист получает 2 гола",
            CardType.GOAL: "Футболист получает гол",
            CardType.OWN_GOAL: "Соперник получает +1 гол",
            CardType.VAR: "Отменяет действие карточки «Свисток» у соперника",
            CardType.OFFSIDE: "Отменяет гол футболиста соперника",
            CardType.PENALTY: "Ставка на Больше-Меньше для получения гола",
            CardType.RED_CARD: "Футболист теряет все полезные действия",
            CardType.YELLOW_CARD: "Футболист теряет одно полезное действие",
            CardType.FOUL: "Футболист теряет одно «отбитие»",
            CardType.LOST_BALL: "Футболист теряет «передачу»",
            CardType.INTERCEPTION: "Футболист получает дополнительную «передачу»",
            CardType.TACKLE: "Футболист получает дополнительное «отбитие»"
        }
        return descriptions.get(card_type, "")

    def roll_dice(self) -> int:
        """Бросок кубика (1-6)"""
        return random.randint(1, 6)

    def check_bet(self, bet_type: BetType, dice_roll: int, bet_value: str) -> bool:
        """Проверяет, сыграла ли ставка"""
        if bet_type == BetType.ODD_EVEN:
            # Чет/нечет
            is_even = dice_roll % 2 == 0
            return (bet_value == "чет" and is_even) or (bet_value == "нечет" and not is_even)

        elif bet_type == BetType.LESS_MORE:
            # Меньше/Больше (1-3 / 4-6)
            is_less = dice_roll <= 3
            return (bet_value == "меньше" and is_less) or (bet_value == "больше" and not is_less)

        elif bet_type == BetType.EXACT_NUMBER:
            # Точное число
            return str(dice_roll) == bet_value

        return False

    def get_actions_for_player(self, position: str, bet_type: BetType, bet_success: bool) -> Dict[str, int]:
        """Возвращает полезные действия для футболиста в зависимости от позиции и типа ставки"""
        actions = {'goals': 0, 'passes': 0, 'defenses': 0}

        if not bet_success:
            return actions

        # Согласно правилам игры
        if position == 'GK':  # Вратарь
            if bet_type == BetType.ODD_EVEN:
                actions['defenses'] = 3

        elif position == 'DF':  # Защитник
            if bet_type == BetType.ODD_EVEN:
                actions['defenses'] = 2
            elif bet_type == BetType.LESS_MORE:
                actions['passes'] = 1
            elif bet_type == BetType.EXACT_NUMBER:
                actions['goals'] = 1

        elif position == 'MF':  # Полузащитник
            if bet_type == BetType.ODD_EVEN:
                actions['defenses'] = 1
            elif bet_type == BetType.LESS_MORE:
                actions['passes'] = 2
            elif bet_type == BetType.EXACT_NUMBER:
                actions['goals'] = 1

        elif position == 'FW':  # Нападающий
            if bet_type == BetType.LESS_MORE:
                actions['passes'] = 1
            elif bet_type == BetType.EXACT_NUMBER:
                actions['goals'] = 1

        return actions

    def draw_card(self) -> Optional[Dict]:
        """Тянет карточку из колоды"""
        if not self.card_deck:
            return None
        return self.card_deck.pop()

    def start_new_round(self, player1_actions: Dict, player2_actions: Dict):
        """Начинает новый раунд, сохраняя действия до применения карточек"""
        self.actions_before_cards['player1'] = player1_actions.copy()
        self.actions_before_cards['player2'] = player2_actions.copy()
        self.current_round_cards['player1'] = None
        self.current_round_cards['player2'] = None

    def record_card_in_round(self, player: str, card_type: CardType):
        """Записывает карточку, использованную в текущем раунде"""
        self.current_round_cards[player] = card_type

    def apply_card_effect(self, card_type: CardType, player_actions: Dict,
                          opponent_actions: Dict, player: str = 'player1',
                          target_player_actions: Optional[Dict] = None,
                          chosen_action: Optional[str] = None) -> Tuple[Dict, Dict, Dict]:
        """
        Применяет эффект карточки.

        Args:
            card_type: Тип карточки
            player_actions: Действия игрока, который использовал карточку
            opponent_actions: Действия соперника
            player: 'player1' или 'player2' - кто использовал карточку
            target_player_actions: Действия игрока, на которого применяется карточка (для красной/желтой)
            chosen_action: Выбранное действие для удаления (для желтой карточки)

        Returns:
            Кортеж (новые_действия_игрока, новые_действия_соперника, информация_о_результате)
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
            # ВАР: отменяет карточку соперника, вытянутую в этом раунде
            opponent_player = 'player2' if player == 'player1' else 'player1'
            opponent_card = self.current_round_cards[opponent_player]

            if opponent_card:
                # Отменяем эффект карточки соперника
                result_info['message'] = f"ВАР отменил карточку соперника: {opponent_card.name}"
                result_info['cancelled_card'] = opponent_card

                # Возвращаем действия к состоянию до карточки соперника
                if self.actions_before_cards[opponent_player]:
                    if opponent_player == 'player1':
                        opponent_copy = self.actions_before_cards[opponent_player].copy()
                    else:
                        player_copy = self.actions_before_cards[opponent_player].copy()
            else:
                result_info['message'] = "ВАР: у соперника не было карточки в этом раунде"
                result_info['no_effect'] = True

        elif card_type == CardType.OFFSIDE:
            # Офсайд: отменяет один гол соперника
            if opponent_copy['goals'] > 0:
                opponent_copy['goals'] -= 1
                result_info['message'] = "Офсайд! -1 гол сопернику"
            else:
                result_info['message'] = "Офсайд: у соперника нет голов"
                result_info['no_effect'] = True

        elif card_type == CardType.PENALTY:
            # Пенальти: дает право на дополнительную ставку Меньше/Больше
            result_info['penalty_available'] = True
            result_info['message'] = "Пенальти! Вы можете сделать ставку Меньше/Больше"
            # Действия не изменяются здесь - пенальти будет обработано позже

        elif card_type == CardType.RED_CARD:
            # Удаление: игрок теряет все полезные действия, полученные в этом раунде
            if target_player_actions:
                # Обнуляем все действия, полученные в текущем раунде
                result_info['message'] = "Красная карточка! Игрок удален, все действия потеряны"
                return {'goals': 0, 'passes': 0, 'defenses': 0}, opponent_copy, result_info
            else:
                result_info['message'] = "Красная карточка: требуется выбор целевого игрока"
                result_info['requires_choice'] = True
                result_info['choice_type'] = 'red_card_target'

        elif card_type == CardType.YELLOW_CARD:
            # Предупреждение: соперник выбирает, какое полезное действие удалить
            if target_player_actions and chosen_action:
                # Проверяем, что выбранное действие есть у игрока
                if target_player_actions.get(chosen_action, 0) > 0:
                    # Удаляем одно действие выбранного типа
                    if chosen_action == 'goals':
                        target_player_actions['goals'] -= 1
                    elif chosen_action == 'passes':
                        target_player_actions['passes'] -= 1
                    elif chosen_action == 'defenses':
                        target_player_actions['defenses'] -= 1

                    result_info['message'] = f"Желтая карточка! Удалено действие: {chosen_action}"

                    # Возвращаем обновленные действия
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
        """Обрабатывает пенальти: если ставка выиграла, добавляет гол"""
        actions = player_actions.copy()
        result_info = {}

        # Проверяем ставку Меньше/Больше
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
        """Возвращает список действий, которые можно удалить желтой карточкой"""
        available = []
        if player_actions.get('goals', 0) > 0:
            available.append('goals')
        if player_actions.get('passes', 0) > 0:
            available.append('passes')
        if player_actions.get('defenses', 0) > 0:
            available.append('defenses')
        return available

    def calculate_match_result(self, player1_actions: Dict, player2_actions: Dict) -> Tuple[int, int]:
        """Рассчитывает результат матча по правилам Final 4"""
        # Извлекаем действия
        p1_goals = player1_actions.get('goals', 0)
        p1_passes = player1_actions.get('passes', 0)
        p1_defenses = player1_actions.get('defenses', 0)

        p2_goals = player2_actions.get('goals', 0)
        p2_passes = player2_actions.get('passes', 0)
        p2_defenses = player2_actions.get('defenses', 0)

        # Рассчитываем голы по правилам
        # Голы команды 1
        p1_remaining_defenses = p2_defenses - p1_passes
        if p1_remaining_defenses <= 0:
            p1_score = p1_goals
        else:
            # На уничтожение "отбитий" тратятся голы (1 гол = 2 отбития)
            defenses_to_remove = p1_remaining_defenses
            goals_needed = (defenses_to_remove + 1) // 2  # Округление вверх
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