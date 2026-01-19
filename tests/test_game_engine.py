# tests/test_game_engine.py
"""
Тесты игрового движка.
"""

import pytest
from core.game_engine import Final4GameEngine, BetType, CardType
from core.dice import DiceRoll
from core.match_calculator import MatchCalculator


class TestGameEngine:
    """Тесты игрового движка"""

    def test_engine_initialization(self, game_engine):
        """Тест инициализации движка"""
        assert game_engine is not None
        assert hasattr(game_engine, 'card_deck')
        assert len(game_engine.card_deck) == 40  # 40 карточек по правилам

    def test_roll_dice(self, game_engine):
        """Тест броска кубика"""
        for _ in range(100):  # Многократно для статистики
            roll = game_engine.roll_dice()
            assert 1 <= roll <= 6

    def test_check_bet_odd_even(self, game_engine):
        """Тест проверки ставки Чет/Нечет"""
        # Четные числа
        assert game_engine.check_bet(BetType.ODD_EVEN, 2, "чет") == True
        assert game_engine.check_bet(BetType.ODD_EVEN, 4, "чет") == True
        assert game_engine.check_bet(BetType.ODD_EVEN, 6, "чет") == True

        # Нечетные числа
        assert game_engine.check_bet(BetType.ODD_EVEN, 1, "нечет") == True
        assert game_engine.check_bet(BetType.ODD_EVEN, 3, "нечет") == True
        assert game_engine.check_bet(BetType.ODD_EVEN, 5, "нечет") == True

        # Неверные ставки
        assert game_engine.check_bet(BetType.ODD_EVEN, 2, "нечет") == False
        assert game_engine.check_bet(BetType.ODD_EVEN, 3, "чет") == False

    def test_check_bet_less_more(self, game_engine):
        """Тест проверки ставки Меньше/Больше"""
        # Меньше (1-3)
        assert game_engine.check_bet(BetType.LESS_MORE, 1, "меньше") == True
        assert game_engine.check_bet(BetType.LESS_MORE, 2, "меньше") == True
        assert game_engine.check_bet(BetType.LESS_MORE, 3, "меньше") == True

        # Больше (4-6)
        assert game_engine.check_bet(BetType.LESS_MORE, 4, "больше") == True
        assert game_engine.check_bet(BetType.LESS_MORE, 5, "больше") == True
        assert game_engine.check_bet(BetType.LESS_MORE, 6, "больше") == True

        # Неверные ставки
        assert game_engine.check_bet(BetType.LESS_MORE, 1, "больше") == False
        assert game_engine.check_bet(BetType.LESS_MORE, 6, "меньше") == False

    def test_check_bet_exact(self, game_engine):
        """Тест проверки ставки на точное число"""
        for i in range(1, 7):
            assert game_engine.check_bet(BetType.EXACT_NUMBER, i, str(i)) == True

        # Неверные ставки
        assert game_engine.check_bet(BetType.EXACT_NUMBER, 1, "2") == False
        assert game_engine.check_bet(BetType.EXACT_NUMBER, 6, "5") == False

    def test_get_actions_for_player(self, game_engine):
        """Тест расчета полезных действий"""
        # Вратарь - Чет/Нечет
        actions = game_engine.get_actions_for_player('GK', BetType.ODD_EVEN, True)
        assert actions['defenses'] == 3
        assert actions['passes'] == 0
        assert actions['goals'] == 0

        # Защитник - Чет/Нечет
        actions = game_engine.get_actions_for_player('DF', BetType.ODD_EVEN, True)
        assert actions['defenses'] == 2

        # Защитник - Меньше/Больше
        actions = game_engine.get_engine.get_actions_for_player('DF', BetType.LESS_MORE, True)
        assert actions['passes'] == 1

        # Полузащитник - Меньше/Больше
        actions = game_engine.get_actions_for_player('MF', BetType.LESS_MORE, True)
        assert actions['passes'] == 2

        # Форвард - Точное число
        actions = game_engine.get_actions_for_player('FW', BetType.EXACT_NUMBER, True)
        assert actions['goals'] == 1

        # Проигранная ставка
        actions = game_engine.get_actions_for_player('FW', BetType.EXACT_NUMBER, False)
        assert actions['goals'] == 0
        assert actions['passes'] == 0
        assert actions['defenses'] == 0

    def test_draw_card(self, game_engine):
        """Тест вытягивания карточки"""
        initial_deck_size = len(game_engine.card_deck)

        card = game_engine.draw_card()
        assert card is not None
        assert 'id' in card
        assert 'type' in card
        assert 'name' in card

        # Колода должна уменьшиться
        assert len(game_engine.card_deck) == initial_deck_size - 1

    def test_card_effects(self, game_engine):
        """Тест эффектов карточек"""
        player_actions = {'goals': 0, 'passes': 0, 'defenses': 0}
        opponent_actions = {'goals': 0, 'passes': 0, 'defenses': 0}

        # Тест карточки Гол
        new_player, new_opponent = game_engine.apply_card_effect(
            CardType.GOAL, player_actions, opponent_actions
        )
        assert new_player['goals'] == 1

        # Тест карточки Хэт-трик
        new_player, new_opponent = game_engine.apply_card_effect(
            CardType.HAT_TRICK, player_actions, opponent_actions
        )
        assert new_player['goals'] == 3

        # Тест карточки Автогол
        new_player, new_opponent = game_engine.apply_card_effect(
            CardType.OWN_GOAL, player_actions, opponent_actions
        )
        assert new_opponent['goals'] == 1


class TestMatchCalculator:
    """Тесты калькулятора матчей"""

    def test_calculate_goals(self):
        """Тест расчета голов по правилам"""
        # Пример из правил: 6 отбитий - 6 передач = 0 отбитий → все голы засчитываются
        goals = MatchCalculator.calculate_goals(defenses=6, passes=6, goals=2)
        assert goals == 2

        # Пример: 10 отбитий - 7 передач = 3 отбития → тратятся голы
        goals = MatchCalculator.calculate_goals(defenses=10, passes=7, goals=3)
        # 3 отбития = 2 гола (1 гол = 2 отбития, округление вверх)
        # 3 гол - 2 гола = 1 гол
        assert goals == 1

        # Если передач больше отбитий
        goals = MatchCalculator.calculate_goals(defenses=5, passes=8, goals=3)
        assert goals == 3

        # Если нет голов
        goals = MatchCalculator.calculate_goals(defenses=5, passes=3, goals=0)
        assert goals == 0

    def test_calculate_match_score(self, sample_actions):
        """Тест расчета счета матча"""
        player1_actions = sample_actions
        player2_actions = {'goals': 3, 'passes': 7, 'defenses': 6}

        p1_score, p2_score = MatchCalculator.calculate_match_score(
            player1_actions, player2_actions
        )

        # Проверяем по примеру из правил
        # Команда 1: 2 Г, 6 П, 10 О → должно быть 2 гола
        # Команда 2: 3 Г, 7 П, 6 О → должно быть 1 гол
        assert p1_score == 2
        assert p2_score == 1

    def test_create_match_result(self, sample_actions):
        """Тест создания результата матча"""
        player1_id = 111
        player2_id = 222

        result = MatchCalculator.create_match_result(
            player1_id=player1_id,
            player2_id=player2_id,
            player1_actions=sample_actions,
            player2_actions={'goals': 3, 'passes': 7, 'defenses': 6}
        )

        assert result.player1_score == 2
        assert result.player2_score == 1
        assert result.winner == player1_id
        assert result.is_draw == False
        assert 'details' in result.details

    def test_validate_actions(self):
        """Тест валидации действий"""
        valid_actions = {'goals': 2, 'passes': 6, 'defenses': 10}
        assert MatchCalculator.validate_actions(valid_actions) == True

        # Неполные действия
        invalid_actions = {'goals': 2, 'passes': 6}  # Нет defenses
        assert MatchCalculator.validate_actions(invalid_actions) == False

        # Отрицательные значения
        invalid_actions = {'goals': -1, 'passes': 6, 'defenses': 10}
        assert MatchCalculator.validate_actions(invalid_actions) == False

        # Неверный тип
        invalid_actions = {'goals': "two", 'passes': 6, 'defenses': 10}
        assert MatchCalculator.validate_actions(invalid_actions) == False