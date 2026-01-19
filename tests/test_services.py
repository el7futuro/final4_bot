# tests/test_services.py
"""
Тесты сервисов.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.match_manager import MatchManager
from models.match import Match, MatchStatus, MatchType
from models.user import User
from models.team import Team


class TestMatchManager:
    """Тесты менеджера матчей"""

    @pytest.mark.asyncio
    async def test_create_vs_random_match(self, test_session, test_user, test_team):
        """Тест создания матча против случайного соперника"""
        manager = MatchManager()

        with patch.object(manager, '_find_opponent_for_match', new_callable=AsyncMock) as mock_find:
            match = await manager.create_vs_random_match(test_session, test_user.telegram_id)

            assert match is not None
            assert match.player1_id == test_user.telegram_id
            assert match.match_type == MatchType.VS_RANDOM
            assert match.status == MatchStatus.WAITING

            # Должен быть запущен поиск соперника
            mock_find.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_vs_bot_match(self, test_session, test_user, test_team):
        """Тест создания матча против бота"""
        manager = MatchManager()

        match = await manager.create_vs_bot_match(
            test_session, test_user.telegram_id, "medium"
        )

        assert match is not None
        assert match.player1_id == test_user.telegram_id
        assert match.match_type == MatchType.VS_BOT
        assert match.status == MatchStatus.CREATED
        assert match.bot_difficulty == 2  # MEDIUM
        assert match.player2_id == -1  # ID бота

    @pytest.mark.asyncio
    async def test_get_active_match(self, test_session, test_user):
        """Тест получения активного матча"""
        manager = MatchManager()

        # Создаем активный матч
        match = Match(
            player1_id=test_user.telegram_id,
            match_type=MatchType.VS_BOT,
            status=MatchStatus.IN_PROGRESS
        )
        test_session.add(match)
        await test_session.commit()

        # Получаем активный матч
        active_match = await manager.get_active_match(test_session, test_user.telegram_id)

        assert active_match is not None
        assert active_match.id == match.id
        assert active_match.status == MatchStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_make_bet(self, test_session):
        """Тест выполнения ставки"""
        manager = MatchManager()

        # Создаем тестовый матч
        match = Match(
            player1_id=111,
            player2_id=222,
            match_type=MatchType.VS_RANDOM,
            status=MatchStatus.IN_PROGRESS,
            current_player=111,
            player1_team_data={
                'name': 'Team 1',
                'formation': '1-4-4-2',
                'players': [
                    {'id': 1, 'position': 'GK', 'name': 'GK 1'},
                    {'id': 2, 'position': 'DF', 'name': 'DF 1'}
                ]
            },
            player2_team_data={
                'name': 'Team 2',
                'formation': '1-4-4-2',
                'players': []
            }
        )
        test_session.add(match)
        await test_session.commit()

        # Мокаем random.randint чтобы получить предсказуемый результат
        with patch('random.randint', return_value=4):
            success, result = await manager.make_bet(
                test_session, match.id, 111,
                player_id=2,  # DF
                bet_type='less_more',
                bet_value='больше'
            )

            assert success == True
            assert 'dice_roll' in result
            assert result['dice_roll'] == 4
            assert 'bet_won' in result
            assert 'actions_gained' in result

    @pytest.mark.asyncio
    async def test_start_match(self, test_session):
        """Тест начала матча"""
        manager = MatchManager()

        # Создаем матч в статусе CREATED
        match = Match(
            player1_id=111,
            player2_id=222,
            match_type=MatchType.VS_RANDOM,
            status=MatchStatus.CREATED
        )
        test_session.add(match)
        await test_session.commit()

        success = await manager.start_match(test_session, match.id)

        assert success == True

        # Проверяем обновление
        await test_session.refresh(match)
        assert match.status == MatchStatus.IN_PROGRESS
        assert match.started_at is not None
        assert match.current_player == match.player1_id

    @pytest.mark.asyncio
    async def test_surrender_match(self, test_session):
        """Тест сдачи в матче"""
        manager = MatchManager()

        match = Match(
            player1_id=111,
            player2_id=222,
            match_type=MatchType.VS_RANDOM,
            status=MatchStatus.IN_PROGRESS
        )
        test_session.add(match)
        await test_session.commit()

        success = await manager.surrender_match(test_session, match.id, 111)

        assert success == True

        await test_session.refresh(match)
        assert match.status == MatchStatus.FINISHED
        assert match.winner_id == 222  # Соперник победил
        assert match.is_draw == False

    def test_create_bot_team(self):
        """Тест создания команды бота"""
        manager = MatchManager()

        from core.bot_ai import BotDifficulty

        # Проверяем создание команды для каждого уровня сложности
        for difficulty in [BotDifficulty.EASY, BotDifficulty.MEDIUM, BotDifficulty.HARD]:
            bot_team = manager._create_bot_team(difficulty)

            assert 'name' in bot_team
            assert 'formation' in bot_team
            assert 'players' in bot_team
            assert len(bot_team['players']) == 16  # Полная команда

            # Проверяем состав
            positions = [p['position'] for p in bot_team['players']]
            assert positions.count('GK') == 1
            assert positions.count('DF') == 5
            assert positions.count('MF') == 6
            assert positions.count('FW') == 4

    def test_calculate_actions(self):
        """Тест расчета полезных действий"""
        manager = MatchManager()

        # Вратарь - Чет/Нечет
        actions = manager._calculate_actions('GK', 'odd_even')
        assert actions['defenses'] == 3
        assert actions['passes'] == 0
        assert actions['goals'] == 0

        # Защитник - Точное число
        actions = manager._calculate_actions('DF', 'exact')
        assert actions['goals'] == 1

        # Полузащитник - Меньше/Больше
        actions = manager._calculate_actions('MF', 'less_more')
        assert actions['passes'] == 2

        # Форвард - Меньше/Больше
        actions = manager._calculate_actions('FW', 'less_more')
        assert actions['passes'] == 1

        # Неверный тип ставки
        actions = manager._calculate_actions('GK', 'exact')
        assert actions['goals'] == 0
        assert actions['passes'] == 0
        assert actions['defenses'] == 0