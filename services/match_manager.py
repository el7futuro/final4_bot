# services/match_manager.py
"""
Сервис для управления матчами Final 4.
Содержит бизнес-логику матчей.
"""

import asyncio
import random
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from models.user import User
from models.team import Team
from models.match import Match, MatchStatus, MatchType
from models.bet import Bet, BetStatus
from models.card import Card, CardInstance, CardDeck, CardType
from models.tournament import Tournament, TournamentMatch
from core.game_engine import Final4GameEngine, BetType as EngineBetType, CardType as EngineCardType
from core.bot_ai import Final4BotAI, BotDifficulty
from core.match_calculator import MatchCalculator
from services.redis_client import redis_client

logger = logging.getLogger(__name__)


class MatchManager:
    """Менеджер матчей Final 4"""

    def __init__(self):
        self.game_engine = Final4GameEngine()
        self.match_calculator = MatchCalculator()

    # === Создание матчей ===

    async def create_vs_random_match(self, session: AsyncSession, user_id: int) -> Optional[Match]:
        """Создает матч против случайного соперника"""
        try:
            # Проверяем, есть ли уже активный матч
            active_match = await self.get_active_match(session, user_id)
            if active_match:
                return None

            # Получаем пользователя и команду
            user = await session.get(User, user_id)
            team = await session.get(Team, user_id)

            if not user or not team:
                return None

            # Создаем матч
            match = Match(
                player1_id=user_id,
                match_type=MatchType.VS_RANDOM,
                status=MatchStatus.WAITING
            )

            # Сохраняем данные команды
            match.player1_team_data = team.to_dict()
            match.player1_formation = team.formation

            session.add(match)
            await session.commit()

            # Запускаем поиск соперника в фоне
            asyncio.create_task(self._find_opponent_for_match(session, match.id))

            logger.info(f"Created vs_random match {match.id} for user {user_id}")
            return match

        except Exception as e:
            logger.error(f"Error creating vs_random match: {e}")
            await session.rollback()
            return None

    async def create_vs_bot_match(self, session: AsyncSession, user_id: int,
                                  difficulty: str = "medium") -> Optional[Match]:
        """Создает матч против бота"""
        try:
            # Проверяем, есть ли уже активный матч
            active_match = await self.get_active_match(session, user_id)
            if active_match:
                return None

            # Получаем пользователя и команду
            user = await session.get(User, user_id)
            team = await session.get(Team, user_id)

            if not user or not team:
                return None

            # Определяем сложность бота
            difficulty_map = {
                'easy': BotDifficulty.EASY,
                'medium': BotDifficulty.MEDIUM,
                'hard': BotDifficulty.HARD
            }
            bot_difficulty = difficulty_map.get(difficulty, BotDifficulty.MEDIUM)

            # Создаем матч
            match = Match(
                player1_id=user_id,
                match_type=MatchType.VS_BOT,
                status=MatchStatus.CREATED,
                bot_difficulty=bot_difficulty.value
            )

            # Сохраняем данные команды игрока
            match.player1_team_data = team.to_dict()
            match.player1_formation = team.formation

            # Создаем команду для бота
            bot_team = self._create_bot_team(bot_difficulty)
            match.player2_team_data = bot_team
            match.player2_formation = bot_team['formation']
            match.player2_id = -1  # Специальный ID для бота

            session.add(match)
            await session.commit()

            # Создаем колоду карточек для матча
            await self._create_card_deck_for_match(session, match.id)

            logger.info(f"Created vs_bot match {match.id} for user {user_id}, difficulty {difficulty}")
            return match

        except Exception as e:
            logger.error(f"Error creating vs_bot match: {e}")
            await session.rollback()
            return None

    async def create_tournament_match(self, session: AsyncSession, tournament_id: int,
                                      player1_id: int, player2_id: int) -> Optional[Match]:
        """Создает турнирный матч"""
        try:
            # Проверяем турнир
            tournament = await session.get(Tournament, tournament_id)
            if not tournament or tournament.status != "in_progress":
                return None

            # Получаем команды игроков
            team1 = await session.get(Team, player1_id)
            team2 = await session.get(Team, player2_id)

            if not team1 or not team2:
                return None

            # Создаем матч
            match = Match(
                player1_id=player1_id,
                player2_id=player2_id,
                match_type=MatchType.TOURNAMENT,
                status=MatchStatus.CREATED
            )

            # Сохраняем данные команд
            match.player1_team_data = team1.to_dict()
            match.player1_formation = team1.formation
            match.player2_team_data = team2.to_dict()
            match.player2_formation = team2.formation

            session.add(match)
            await session.commit()

            # Создаем колоду карточек
            await self._create_card_deck_for_match(session, match.id)

            logger.info(f"Created tournament match {match.id} for tournament {tournament_id}")
            return match

        except Exception as e:
            logger.error(f"Error creating tournament match: {e}")
            await session.rollback()
            return None

    # === Поиск соперника ===

    async def _find_opponent_for_match(self, session: AsyncSession, match_id: int):
        """Ищет соперника для матча (фоновый процесс)"""
        try:
            # Получаем матч
            match = await session.get(Match, match_id)
            if not match or match.status != MatchStatus.WAITING:
                return

            # Получаем данные игрока 1
            player1 = await session.get(User, match.player1_id)
            if not player1:
                await self._cancel_match(session, match_id, "Player not found")
                return

            # Ищем подходящего соперника
            opponent = await self._find_suitable_opponent(session, player1, match_id)

            if opponent:
                # Нашли соперника
                await self._pair_with_opponent(session, match_id, opponent.id)
            else:
                # Не нашли соперника - отменяем через время
                await asyncio.sleep(300)  # 5 минут
                await self._check_and_cancel_match(session, match_id)

        except Exception as e:
            logger.error(f"Error finding opponent for match {match_id}: {e}")

    async def _find_suitable_opponent(self, session: AsyncSession, player: User, exclude_match_id: int) -> Optional[
        User]:
        """Ищет подходящего соперника по рейтингу"""
        # Ищем матчи в ожидании, исключая текущий
        waiting_matches = await session.execute(
            select(Match).where(
                Match.status == MatchStatus.WAITING,
                Match.id != exclude_match_id,
                Match.match_type == MatchType.VS_RANDOM
            ).order_by(Match.created_at)
        )
        waiting_matches = waiting_matches.scalars().all()

        for waiting_match in waiting_matches:
            # Получаем игрока из ожидающего матча
            opponent = await session.get(User, waiting_match.player1_id)
            if not opponent:
                continue

            # Проверяем разницу в рейтинге (макс ±200)
            rating_diff = abs(player.rating - opponent.rating)
            if rating_diff <= 200:
                return opponent

        return None

    async def _pair_with_opponent(self, session: AsyncSession, match1_id: int, opponent_id: int):
        """Объединяет два матча в один"""
        try:
            # Начинаем транзакцию
            async with session.begin():
                # Получаем оба матча
                match1 = await session.get(Match, match1_id)
                match2_stmt = select(Match).where(
                    Match.player1_id == opponent_id,
                    Match.status == MatchStatus.WAITING,
                    Match.match_type == MatchType.VS_RANDOM
                ).order_by(Match.created_at).limit(1)
                match2 = (await session.execute(match2_stmt)).scalar_one_or_none()

                if not match1 or not match2:
                    return

                # Получаем команду соперника
                opponent_team = await session.get(Team, opponent_id)
                if not opponent_team:
                    return

                # Обновляем первый матч
                match1.player2_id = opponent_id
                match1.player2_team_data = opponent_team.to_dict()
                match1.player2_formation = opponent_team.formation
                match1.status = MatchStatus.CREATED
                match1.current_player = match1.player1_id  # Первым ходит создатель

                # Удаляем второй матч
                await session.delete(match2)

                # Создаем колоду карточек
                await self._create_card_deck_for_match(session, match1_id)

                logger.info(
                    f"Paired matches {match1_id} and {match2.id} with players {match1.player1_id} and {opponent_id}")

        except Exception as e:
            logger.error(f"Error pairing matches: {e}")
            await session.rollback()

    async def _check_and_cancel_match(self, session: AsyncSession, match_id: int):
        """Проверяет и отменяет матч, если не нашелся соперник"""
        match = await session.get(Match, match_id)
        if match and match.status == MatchStatus.WAITING:
            match.status = MatchStatus.CANCELLED
            await session.commit()
            logger.info(f"Cancelled match {match_id} (no opponent found)")

    async def _cancel_match(self, session: AsyncSession, match_id: int, reason: str):
        """Отменяет матч"""
        match = await session.get(Match, match_id)
        if match:
            match.status = MatchStatus.CANCELLED
            await session.commit()
            logger.info(f"Cancelled match {match_id}: {reason}")

    # === Управление ходом матча ===

    async def start_match(self, session: AsyncSession, match_id: int) -> bool:
        """Начинает матч"""
        try:
            match = await session.get(Match, match_id)
            if not match or match.status != MatchStatus.CREATED:
                return False

            match.status = MatchStatus.IN_PROGRESS
            match.started_at = func.now()
            match.current_player = match.player1_id  # Первым ходит создатель

            await session.commit()
            logger.info(f"Started match {match_id}")
            return True

        except Exception as e:
            logger.error(f"Error starting match {match_id}: {e}")
            await session.rollback()
            return False

    async def make_bet(self, session: AsyncSession, match_id: int, user_id: int,
                       player_id: int, bet_type: str, bet_value: str) -> Tuple[bool, Dict]:
        """Делает ставку в матче"""
        try:
            match = await session.get(Match, match_id)
            if not match or match.status != MatchStatus.IN_PROGRESS:
                return False, {"error": "Матч не активен"}

            if match.current_player != user_id:
                return False, {"error": "Сейчас не ваш ход"}

            # Получаем информацию об игроке
            player_number = self._get_player_number(match, user_id)
            team_data = match.player1_team_data if player_number == 1 else match.player2_team_data

            player_info = self._get_player_info(team_data, player_id)
            if not player_info:
                return False, {"error": "Игрок не найден"}

            # Проверяем, можно ли делать такую ставку по правилам
            can_bet, error_msg = self._can_make_bet(match, user_id, player_info['position'], bet_type)
            if not can_bet:
                return False, {"error": error_msg}

            # Бросок кубика
            dice_roll = random.randint(1, 6)

            # Проверяем ставку
            bet_won = self._check_bet_result(bet_type, dice_roll, bet_value)

            # Создаем запись о ставке
            bet = Bet(
                match_id=match_id,
                user_id=user_id,
                player_id=player_id,
                bet_type=bet_type,
                bet_value=bet_value,
                player_position=player_info['position'],
                dice_roll=dice_roll,
                bet_result=BetStatus.WON if bet_won else BetStatus.LOST,
                turn_number=match.current_turn,
                bet_order=self._get_next_bet_order(session, match_id, user_id, match.current_turn)
            )

            # Рассчитываем полученные действия
            if bet_won:
                actions = self._calculate_actions(player_info['position'], bet_type)
                bet.actions_gained = actions

                # Обновляем действия игрока в матче
                if player_number == 1:
                    current = match.player1_actions
                    for key, value in actions.items():
                        current[key] += value
                    match.player1_actions = current
                else:
                    current = match.player2_actions
                    for key, value in actions.items():
                        current[key] += value
                    match.player2_actions = current

                # Если ставка выиграла, берем карточку
                card_instance = await self._draw_card(session, match_id, user_id)
                if card_instance:
                    bet.card_drawn_id = card_instance.id

            session.add(bet)

            # Обновляем счетчики ставок
            await self._update_bet_counters(session, match_id, user_id, player_info['position'], bet_type)

            # Если это матч против бота и ходил игрок, делаем ход бота
            if match.match_type == MatchType.VS_BOT and user_id == match.player1_id:
                await self._make_bot_move(session, match_id)
            else:
                # Передаем ход
                match.current_player = match.get_opponent_id(user_id)

            # Проверяем, завершился ли ход
            if await self._is_turn_complete(session, match_id, match.current_turn):
                # Переходим к следующему ходу
                match.current_turn += 1

                # Если это был 4-й ход, завершаем матч
                if match.current_turn > 4:
                    await self._finish_match(session, match_id)
                else:
                    # Сбрасываем текущего игрока для нового хода
                    match.current_player = match.player1_id if match.current_turn % 2 == 1 else match.player2_id

            await session.commit()

            result = {
                "success": True,
                "dice_roll": dice_roll,
                "bet_won": bet_won,
                "actions_gained": bet.actions_gained if bet_won else {},
                "card_drawn": bool(card_instance) if bet_won else False,
                "current_turn": match.current_turn,
                "current_player": match.current_player,
                "match_completed": match.status == MatchStatus.FINISHED
            }

            logger.info(f"User {user_id} made bet in match {match_id}: {bet_type} {bet_value}, won={bet_won}")
            return True, result

        except Exception as e:
            logger.error(f"Error making bet in match {match_id}: {e}")
            await session.rollback()
            return False, {"error": str(e)}

    async def use_card(self, session: AsyncSession, match_id: int, user_id: int,
                       card_instance_id: int, target_player_id: Optional[int] = None) -> Tuple[bool, Dict]:
        """Использует карточку «Свисток»"""
        try:
            match = await session.get(Match, match_id)
            card_instance = await session.get(CardInstance, card_instance_id)

            if not match or not card_instance:
                return False, {"error": "Матч или карточка не найдены"}

            if card_instance.owner_id != user_id or card_instance.is_used:
                return False, {"error": "Нельзя использовать эту карточку"}

            # Получаем карточку
            card = await session.get(Card, card_instance.card_id)
            if not card:
                return False, {"error": "Карточка не найдена"}

            # Применяем эффект карточки
            player_number = self._get_player_number(match, user_id)

            if player_number == 1:
                player_actions = match.player1_actions
                opponent_actions = match.player2_actions
            else:
                player_actions = match.player2_actions
                opponent_actions = match.player1_actions

            # Применяем эффект
            new_player_actions, new_opponent_actions = self._apply_card_effect(
                card, player_actions, opponent_actions, target_player_id
            )

            # Обновляем действия
            if player_number == 1:
                match.player1_actions = new_player_actions
                match.player2_actions = new_opponent_actions
            else:
                match.player2_actions = new_player_actions
                match.player1_actions = new_opponent_actions

            # Помечаем карточку как использованную
            card_instance.is_used = True
            card_instance.used_at = func.now()
            card_instance.turn_used = match.current_turn

            if target_player_id:
                card_instance.target_player_id = target_player_id

            await session.commit()

            result = {
                "success": True,
                "card_name": card.name,
                "card_effect": card.description,
                "player_actions": new_player_actions,
                "opponent_actions": new_opponent_actions
            }

            logger.info(f"User {user_id} used card {card.name} in match {match_id}")
            return True, result

        except Exception as e:
            logger.error(f"Error using card in match {match_id}: {e}")
            await session.rollback()
            return False, {"error": str(e)}

    async def surrender_match(self, session: AsyncSession, match_id: int, user_id: int) -> bool:
        """Сдача в матче"""
        try:
            match = await session.get(Match, match_id)
            if not match or match.status != MatchStatus.IN_PROGRESS:
                return False

            if not match.is_player_in_match(user_id):
                return False

            # Определяем победителя (соперник)
            winner_id = match.get_opponent_id(user_id)

            # Завершаем матч
            match.status = MatchStatus.FINISHED
            match.finished_at = func.now()
            match.winner_id = winner_id
            match.is_draw = False

            # Обновляем рейтинги
            await self._update_ratings(session, match, winner_id, user_id)

            await session.commit()
            logger.info(f"User {user_id} surrendered match {match_id}, winner: {winner_id}")
            return True

        except Exception as e:
            logger.error(f"Error surrendering match {match_id}: {e}")
            await session.rollback()
            return False

    # === Вспомогательные методы ===

    def _create_bot_team(self, difficulty: BotDifficulty) -> dict:
        """Создает команду для бота"""
        formations = ['1-4-4-2', '1-4-3-3', '1-5-3-2', '1-3-5-2']

        players = []

        # Вратарь
        players.append({
            'id': 1,
            'position': 'GK',
            'name': f'Бот-вратарь ({difficulty.name})',
            'number': 1
        })

        # Защитники (5)
        for i in range(5):
            players.append({
                'id': 2 + i,
                'position': 'DF',
                'name': f'Бот-защитник {i + 1}',
                'number': 2 + i,
                            })

        # Полузащитники (6)
        for i in range(6):
            players.append({
                'id': 7 + i,
                'position': 'MF',
                'name': f'Бот-полузащитник {i + 1}',
                'number': 7 + i,

            })

        # Нападающие (4)
        for i in range(4):
            players.append({
                'id': 13 + i,
                'position': 'FW',
                'name': f'Бот-нападающий {i + 1}',
                'number': 13 + i,

            })

        return {
            'name': f'Команда бота ({difficulty.name})',
            'formation': random.choice(formations),
            'players': players
        }

    async def _create_card_deck_for_match(self, session: AsyncSession, match_id: int):
        """Создает колоду карточек для матча"""
        try:
            # Получаем все карточки из БД
            cards_result = await session.execute(select(Card))
            all_cards = cards_result.scalars().all()

            if not all_cards:
                logger.warning("No cards found in database")
                return

            # Создаем колоду согласно правилам (40 карт)
            deck = []
            for card in all_cards:
                # Добавляем карточку нужное количество раз
                for _ in range(card.count_in_deck):
                    deck.append(card.id)

            # Перемешиваем колоду
            random.shuffle(deck)

            # Создаем запись колоды
            card_deck = CardDeck(
                match_id=match_id,
                deck_order=deck,
                current_index=0
            )

            session.add(card_deck)

        except Exception as e:
            logger.error(f"Error creating card deck for match {match_id}: {e}")

    async def _draw_card(self, session: AsyncSession, match_id: int, user_id: int) -> Optional[CardInstance]:
        """Вытягивает карточку из колоды"""
        try:
            # Получаем колоду
            card_deck_stmt = select(CardDeck).where(CardDeck.match_id == match_id)
            card_deck = (await session.execute(card_deck_stmt)).scalar_one_or_none()

            if not card_deck or card_deck.current_index >= len(card_deck.deck_order):
                return None

            # Берем следующую карточку
            card_id = card_deck.deck_order[card_deck.current_index]
            card_deck.current_index += 1
            card_deck.cards_drawn_count += 1

            # Создаем экземпляр карточки
            card_instance = CardInstance(
                card_id=card_id,
                match_id=match_id,
                owner_id=user_id,
                drawn_by_player=self._get_player_number_from_match(session, match_id, user_id),
                is_drawn=True,
                turn_drawn=self._get_current_turn(session, match_id)
            )

            session.add(card_instance)
            return card_instance

        except Exception as e:
            logger.error(f"Error drawing card for match {match_id}: {e}")
            return None

    def _get_player_number(self, match: Match, user_id: int) -> int:
        """Возвращает номер игрока (1 или 2)"""
        return 1 if user_id == match.player1_id else 2

    async def _get_player_number_from_match(self, session: AsyncSession, match_id: int, user_id: int) -> int:
        """Возвращает номер игрока из матча"""
        match = await session.get(Match, match_id)
        return self._get_player_number(match, user_id) if match else 0

    def _get_player_info(self, team_data: dict, player_id: int) -> Optional[dict]:
        """Получает информацию об игроке из данных команды"""
        for player in team_data.get('players', []):
            if player.get('id') == player_id:
                return player
        return None

    def _can_make_bet(self, match: Match, user_id: int, position: str, bet_type: str) -> Tuple[bool, str]:
        """Проверяет, можно ли сделать ставку по правилам"""
        # TODO: Реализовать полную проверку по правилам Final 4
        # Пока базовая проверка

        if position == 'GK' and bet_type != 'odd_even':
            return False, "Вратарь может ставить только Чет/Нечет"

        if position == 'FW' and bet_type == 'odd_even':
            return False, "Форварды не могут ставить Чет/Нечет"

        return True, ""

    def _check_bet_result(self, bet_type: str, dice_roll: int, bet_value: str) -> bool:
        """Проверяет результат ставки"""
        if bet_type == 'odd_even':
            is_even = dice_roll % 2 == 0
            return (bet_value == 'чет' and is_even) or (bet_value == 'нечет' and not is_even)

        elif bet_type == 'less_more':
            is_less = dice_roll <= 3
            return (bet_value == 'меньше' and is_less) or (bet_value == 'больше' and not is_less)

        elif bet_type == 'exact':
            return str(dice_roll) == bet_value

        return False

    def _calculate_actions(self, position: str, bet_type: str) -> Dict[str, int]:
        """Рассчитывает полезные действия по правилам"""
        actions = {'goals': 0, 'passes': 0, 'defenses': 0}

        if position == 'GK' and bet_type == 'odd_even':
            actions['defenses'] = 3

        elif position == 'DF':
            if bet_type == 'odd_even':
                actions['defenses'] = 2
            elif bet_type == 'less_more':
                actions['passes'] = 1
            elif bet_type == 'exact':
                actions['goals'] = 1

        elif position == 'MF':
            if bet_type == 'odd_even':
                actions['defenses'] = 1
            elif bet_type == 'less_more':
                actions['passes'] = 2
            elif bet_type == 'exact':
                actions['goals'] = 1

        elif position == 'FW':
            if bet_type == 'less_more':
                actions['passes'] = 1
            elif bet_type == 'exact':
                actions['goals'] = 1

        return actions

    async def _get_next_bet_order(self, session: AsyncSession, match_id: int, user_id: int, turn: int) -> int:
        """Возвращает порядковый номер ставки в ходе"""
        bet_count = await session.execute(
            select(func.count(Bet.id)).where(
                Bet.match_id == match_id,
                Bet.user_id == user_id,
                Bet.turn_number == turn
            )
        )
        return bet_count.scalar() + 1

    async def _update_bet_counters(self, session: AsyncSession, match_id: int, user_id: int,
                                   position: str, bet_type: str):
        """Обновляет счетчики ставок для проверки правил"""
        # TODO: Реализовать полный учет ставок по правилам
        pass

    async def _make_bot_move(self, session: AsyncSession, match_id: int):
        """Делает ход бота"""
        try:
            match = await session.get(Match, match_id)
            if not match or match.match_type != MatchType.VS_BOT:
                return

            # Создаем ИИ бота
            bot_ai = Final4BotAI(BotDifficulty(match.bot_difficulty))

            # Получаем команду бота
            bot_team = match.player2_team_data

            # Получаем активных игроков бота
            active_players = self._get_active_players(bot_team, match.player2_formation)

            # Бот делает ставку
            bot_decision = bot_ai.make_turn_decision(
                turn=match.current_turn,
                my_team=active_players,
                my_formation=match.player2_formation,
                opponent_actions=match.player1_actions
            )

            if bot_decision:
                # Выполняем ставку бота
                await self.make_bet(
                    session, match_id, -1,  # -1 = ID бота
                    bot_decision['player_id'],
                    bot_decision['bet_type'],
                    bot_decision['bet_value']
                )

        except Exception as e:
            logger.error(f"Error making bot move in match {match_id}: {e}")

    def _get_active_players(self, team_data: dict, formation: str) -> List[dict]:
        """Возвращает активных игроков по формации"""
        parts = formation.split('-')
        gk_needed = int(parts[0])
        df_needed = int(parts[1])
        mf_needed = int(parts[2])
        fw_needed = int(parts[3])

        active = []
        counts = {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}

        for player in team_data.get('players', []):
            pos = player.get('position', '')
            if counts.get(pos, 0) < {'GK': gk_needed, 'DF': df_needed,
                                     'MF': mf_needed, 'FW': fw_needed}.get(pos, 0):
                active.append(player)
                counts[pos] = counts.get(pos, 0) + 1

        return active

    async def _is_turn_complete(self, session: AsyncSession, match_id: int, turn: int) -> bool:
        """Проверяет, завершился ли ход"""
        # В каждом ходе каждый игрок делает по 2 ставки
        bet_count = await session.execute(
            select(func.count(Bet.id)).where(
                Bet.match_id == match_id,
                Bet.turn_number == turn
            )
        )
        total_bets = bet_count.scalar()

        # 2 игрока × 2 ставки = 4 ставки за ход
        return total_bets >= 4

    async def _finish_match(self, session: AsyncSession, match_id: int):
        """Завершает матч и рассчитывает результат"""
        try:
            match = await session.get(Match, match_id)
            if not match:
                return

            # Рассчитываем счет
            p1_score, p2_score = self.match_calculator.calculate_match_score(
                match.player1_actions, match.player2_actions
            )

            match.player1_score = p1_score
            match.player2_score = p2_score

            # Определяем победителя
            if p1_score > p2_score:
                match.winner_id = match.player1_id
                match.is_draw = False
            elif p2_score > p1_score:
                match.winner_id = match.player2_id
                match.is_draw = False
            else:
                # Ничья - дополнительное время
                match.status = MatchStatus.EXTRA_TIME
                match.winner_id = None
                match.is_draw = True

                # TODO: Реализовать дополнительное время
                # Пока просто оставляем ничью
                match.status = MatchStatus.FINISHED

            if match.status == MatchStatus.FINISHED:
                match.finished_at = func.now()

                # Обновляем рейтинги игроков
                if match.winner_id:
                    loser_id = match.player2_id if match.winner_id == match.player1_id else match.player1_id
                    await self._update_ratings(session, match, match.winner_id, loser_id)

                # Обновляем статистику игроков
                await self._update_player_stats(session, match)

            logger.info(f"Finished match {match_id}: {p1_score}:{p2_score}, winner: {match.winner_id}")

        except Exception as e:
            logger.error(f"Error finishing match {match_id}: {e}")

    async def _update_ratings(self, session: AsyncSession, match: Match, winner_id: int, loser_id: int):
        """Обновляет рейтинги ELO игроков"""
        try:
            if match.match_type == MatchType.VS_BOT:
                return  # В матчах с ботом рейтинг не меняется

            winner = await session.get(User, winner_id)
            loser = await session.get(User, loser_id)

            if not winner or not loser:
                return

            # Простая система ELO
            K = 32  # Коэффициент K

            # Ожидаемый результат
            expected_winner = 1 / (1 + 10 ** ((loser.rating - winner.rating) / 400))
            expected_loser = 1 - expected_winner

            # Новые рейтинги
            winner.rating = int(winner.rating + K * (1 - expected_winner))
            loser.rating = int(loser.rating + K * (0 - expected_loser))

            # Минимальный рейтинг
            winner.rating = max(100, winner.rating)
            loser.rating = max(100, loser.rating)

        except Exception as e:
            logger.error(f"Error updating ratings: {e}")

    async def _update_player_stats(self, session: AsyncSession, match: Match):
        """Обновляет статистику игроков"""
        try:
            for user_id in [match.player1_id, match.player2_id]:
                if user_id and user_id > 0:  # Исключаем бота
                    user = await session.get(User, user_id)
                    if user:
                        user.games_played += 1
                        if match.winner_id == user_id:
                            user.games_won += 1

        except Exception as e:
            logger.error(f"Error updating player stats: {e}")

    def _apply_card_effect(self, card: Card, player_actions: dict,
                           opponent_actions: dict, target_player_id: Optional[int]) -> Tuple[dict, dict]:
        """Применяет эффект карточки"""
        # TODO: Реализовать полную логику карточек
        # Пока просто возвращаем исходные действия
        return player_actions.copy(), opponent_actions.copy()

    async def _get_current_turn(self, session: AsyncSession, match_id: int) -> int:
        """Возвращает текущий ход матча"""
        match = await session.get(Match, match_id)
        return match.current_turn if match else 1

    # === Публичные методы для получения данных ===

    async def get_active_match(self, session: AsyncSession, user_id: int) -> Optional[Match]:
        """Возвращает активный матч пользователя"""
        result = await session.execute(
            select(Match).where(
                or_(
                    Match.player1_id == user_id,
                    Match.player2_id == user_id
                ),
                Match.status.in_([
                    MatchStatus.CREATED,
                    MatchStatus.WAITING,
                    MatchStatus.IN_PROGRESS,
                    MatchStatus.EXTRA_TIME
                ])
            ).order_by(Match.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_match_by_id(self, session: AsyncSession, match_id: int) -> Optional[Match]:
        """Возвращает матч по ID"""
        return await session.get(Match, match_id)

    async def get_user_matches(self, session: AsyncSession, user_id: int,
                               limit: int = 10, offset: int = 0) -> List[Match]:
        """Возвращает историю матчей пользователя"""
        result = await session.execute(
            select(Match).where(
                or_(
                    Match.player1_id == user_id,
                    Match.player2_id == user_id
                ),
                Match.status == MatchStatus.FINISHED
            ).order_by(Match.finished_at.desc())
            .offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def get_match_bets(self, session: AsyncSession, match_id: int) -> List[Bet]:
        """Возвращает ставки матча"""
        result = await session.execute(
            select(Bet).where(Bet.match_id == match_id).order_by(Bet.turn_number, Bet.bet_order)
        )
        return result.scalars().all()

    async def get_player_cards(self, session: AsyncSession, match_id: int, user_id: int) -> List[CardInstance]:
        """Возвращает карточки игрока в матче"""
        result = await session.execute(
            select(CardInstance).where(
                CardInstance.match_id == match_id,
                CardInstance.owner_id == user_id,
                CardInstance.is_drawn == True
            ).order_by(CardInstance.drawn_at)
        )
        return result.scalars().all()

    async def cleanup_old_matches(self, session: AsyncSession, days: int = 7):
        """Очищает старые завершенные матчи"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            result = await session.execute(
                select(Match.id).where(
                    Match.status == MatchStatus.FINISHED,
                    Match.finished_at < cutoff_date
                ).limit(100)
            )
            old_match_ids = result.scalars().all()

            for match_id in old_match_ids:
                # Удаляем связанные данные
                await session.execute(
                    delete(Bet).where(Bet.match_id == match_id)
                )
                await session.execute(
                    delete(CardInstance).where(CardInstance.match_id == match_id)
                )
                await session.execute(
                    delete(CardDeck).where(CardDeck.match_id == match_id)
                )

                # Удаляем матч
                await session.execute(
                    delete(Match).where(Match.id == match_id)
                )

            await session.commit()
            logger.info(f"Cleaned up {len(old_match_ids)} old matches")

        except Exception as e:
            logger.error(f"Error cleaning up old matches: {e}")
            await session.rollback()


# Глобальный экземпляр менеджера
match_manager = MatchManager()