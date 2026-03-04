# services/match_manager.py
"""
Сервис для управления матчами Final 4.
Содержит бизнес-логику матчей.
"""

import asyncio
import random
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta

from sqlalchemy import select, and_, or_, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from models.user import User
from core.engine_classes import Final4GameEngine, BetType as EngineBetType, CardType as EngineCardType
from models.match import Match, MatchStatus, MatchType, logger
from models.bet import Bet, BetStatus
from models.card import Card, CardInstance, CardDeck, CardType, CardEffectType
from models.tournament import Tournament, TournamentMatch
from core.bot_ai import Final4BotAI
from core.match_calculator import MatchCalculator

# Ленивый импорт — загружается только когда нужен


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

            # Создаем матч
            match = Match(
                player1_id=user_id,
                match_type=MatchType.VS_RANDOM,
                status=MatchStatus.WAITING
            )

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

            match = Match(
                player1_id=user_id,
                match_type=MatchType.VS_BOT,
                status=MatchStatus.CREATED,
            )

            # Создаем команду для бота
            bot_team = self._create_bot_team(self)
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

            # Создаем матч
            match = Match(
                player1_id=player1_id,
                player2_id=player2_id,
                match_type=MatchType.TOURNAMENT,
                status=MatchStatus.CREATED
            )

            # Создаем колоду карточек
            await self._create_card_deck_for_match(session, match.id)

            logger.info(f"Created tournament match {match.id} for tournament {tournament_id}")
            return match

        except Exception as e:
            logger.error(f"Error creating tournament match: {e}")
            await session.rollback()
            return None

    # === Фоновая логика поиска соперника ===

    async def _find_opponent_for_match(self, session: AsyncSession, match_id: int) -> None:
        """Фоновая задача поиска соперника для матча vs_random"""
        # Пока заглушка - можно реализовать реальный поиск
        await asyncio.sleep(30)  # имитация поиска

        async with session.begin():
            match = await session.get(Match, match_id)
            if match and match.status == MatchStatus.WAITING:
                # Если соперник не найден - отменяем
                match.status = MatchStatus.CANCELLED
                await session.commit()
                logger.info(f"Match {match_id} cancelled: no opponent found")

    def _create_bot_team(self, difficulty: str = "medium") -> Dict:
        """Создает тестовую команду для бота"""
        # Пока простая реализация - можно улучшить в зависимости от difficulty
        players = []

        # Вратарь
        players.append({
            'id': 1,
            'position': 'GK',
            'name': 'Bot Goalkeeper',
            'number': 1
        })

        # Защитники
        for i in range(5):
            players.append({
                'id': i + 2,
                'position': 'DF',
                'name': f'Bot Defender {i+1}',
                'number': i + 2
            })

        # Полузащитники
        for i in range(6):
            players.append({
                'id': i + 7,
                'position': 'MF',
                'name': f'Bot Midfielder {i+1}',
                'number': i + 7
            })

        # Нападающие
        for i in range(4):
            players.append({
                'id': i + 13,
                'position': 'FW',
                'name': f'Bot Forward {i+1}',
                'number': i + 13
            })

        return {
            'players': players,
            'formation': '1-5-6-4'
        }

    async def _create_card_deck_for_match(self, session: AsyncSession, match_id: int) -> None:
        """Создает колоду карточек для матча"""
        try:
            # Получаем все активные карточки
            result = await session.execute(
                select(Card).where(Card.is_active == True)
            )
            cards = result.scalars().all()

            deck_order = []

            for card in cards:
                for _ in range(card.count_in_deck):
                    deck_order.append(card.id)

            random.shuffle(deck_order)

            deck = CardDeck(
                match_id=match_id,
                deck_order=deck_order,
                current_index=0,
                cards_drawn_count=0,
                discard_pile=[]
            )

            session.add(deck)
            await session.commit()

            logger.info(f"Created card deck for match {match_id}")

        except Exception as e:
            logger.error(f"Error creating card deck for match {match_id}: {e}")
            await session.rollback()

    # === Получение данных ===

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

    async def update_player_stats_after_match(self, session: AsyncSession, match: Match):
        """Обновляет статистику игроков после завершения матча"""
        try:
            if match.winner_id:
                winner = await session.get(User, match.winner_id)
                if winner:
                    winner.games_played += 1
                    winner.games_won += 1

            # Проигравший
            loser_id = match.player1_id if match.winner_id == match.player2_id else match.player2_id
            if loser_id:
                loser = await session.get(User, loser_id)
                if loser:
                    loser.games_played += 1

            await session.commit()

        except Exception as e:
            logger.error(f"Error updating player stats: {e}")

    # ────────────────────────────────────────────────
    # Полная реализация применения эффекта карточки
    # ────────────────────────────────────────────────

    def _apply_card_effect(
        self,
        card: Card,
        player_actions: Dict[str, int],
        opponent_actions: Dict[str, int],
        target_player_id: Optional[int] = None
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Применяет эффект карточки «Свисток» к накопленным действиям игроков.

        Args:
            card: объект Card (шаблон карточки из базы)
            player_actions: {'goals': int, 'passes': int, 'defenses': int} текущего игрока
            opponent_actions: аналогичный словарь соперника
            target_player_id: ID игрока, на которого применяется эффект (если target="specific")

        Returns:
            (обновлённые player_actions, обновлённые opponent_actions)
        """
        # Защищаем входные данные — работаем с копиями
        player = player_actions.copy()
        opponent = opponent_actions.copy()

        effect = card.effect_type
        val = card.effect_value or 0
        tgt = card.target.lower() if card.target else "self"

        # ──────────────────────────────────────────────────────────────
        # Простые модификаторы действий
        # ──────────────────────────────────────────────────────────────
        if effect == CardEffectType.ADD_GOALS:
            if tgt in ("self", "both"):
                player["goals"] += val
            if tgt in ("opponent", "both"):
                opponent["goals"] += val

        elif effect == CardEffectType.REMOVE_GOALS:
            if tgt in ("self", "both"):
                player["goals"] = max(0, player["goals"] - val)
            if tgt in ("opponent", "both"):
                opponent["goals"] = max(0, opponent["goals"] - val)

        elif effect == CardEffectType.ADD_PASSES:
            if tgt in ("self", "both"):
                player["passes"] += val

        elif effect == CardEffectType.REMOVE_PASSES:
            if tgt in ("self", "both"):
                player["passes"] = max(0, player["passes"] - val)
            if tgt in ("opponent", "both"):
                opponent["passes"] = max(0, opponent["passes"] - val)

        elif effect == CardEffectType.ADD_DEFENSES:
            if tgt in ("self", "both"):
                player["defenses"] += val

        elif effect == CardEffectType.REMOVE_DEFENSES:
            if tgt in ("self", "both"):
                player["defenses"] = max(0, player["defenses"] - val)
            if tgt in ("opponent", "both"):
                opponent["defenses"] = max(0, opponent["defenses"] - val)

        # ──────────────────────────────────────────────────────────────
        # Полная потеря действий (Удаление)
        # ──────────────────────────────────────────────────────────────
        elif effect == CardEffectType.REMOVE_ALL_ACTIONS:
            if tgt in ("self", "both"):
                player = {"goals": 0, "passes": 0, "defenses": 0}
            if tgt in ("opponent", "both"):
                opponent = {"goals": 0, "passes": 0, "defenses": 0}

        # ──────────────────────────────────────────────────────────────
        # Отмена гола соперника (Офсайд)
        # ──────────────────────────────────────────────────────────────
        elif effect == CardEffectType.CANCEL_GOAL:
            if tgt in ("opponent", "both"):
                opponent["goals"] = max(0, opponent["goals"] - 1)

        # ──────────────────────────────────────────────────────────────
        # Отмена карточки соперника (ВАР)
        # ──────────────────────────────────────────────────────────────
        elif effect == CardEffectType.CANCEL_CARD:
            # Логика отмены карточки соперника должна быть реализована в resolve_card
            # Здесь просто логируем — реальная отмена в другом месте
            logger.info("ВАР применён — отмена последней карточки соперника (логика в resolve_card)")

        # ──────────────────────────────────────────────────────────────
        # Специальная ставка (Пенальти) — пока заглушка
        # ──────────────────────────────────────────────────────────────
        elif effect == CardEffectType.SPECIAL_BET:
            logger.info("Применена специальная ставка 'Пенальти' — обработка в resolve_turn или отдельном методе")

        else:
            logger.warning(f"Неизвестный тип эффекта карточки: {effect}")

        return player, opponent


    # ────────────────────────────────────────────────
    # Методы применения и разрешения карточек (добавлены)
    # ────────────────────────────────────────────────

    async def use_card(
        self,
        session: AsyncSession,
        card_instance: CardInstance,
        target_player_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Применяет карточку в матче (сохраняет цель, применяет эффект, обновляет действия).

        Args:
            session: сессия БД
            card_instance: экземпляр карточки, которую применяем
            target_player_id: ID игрока, на которого применяется (если target="specific")

        Returns:
            (успех, сообщение об успехе/ошибке)
        """
        if card_instance.is_used:
            return False, "Карточка уже использована"

        if card_instance.is_cancelled:
            return False, "Карточка была отменена ранее"

        match = await session.get(Match, card_instance.match_id)
        if not match:
            return False, "Матч не найден"

        card = card_instance.card

        # Проверка необходимости цели
        if card.target.lower() == "specific" and target_player_id is None:
            return False, "Для этой карточки требуется указать цель (target_player_id)"

        # Сохраняем цель применения
        card_instance.applied_to_player_id = target_player_id
        card_instance.used_at = func.now()
        card_instance.is_used = True

        # Определяем, чьи действия мы модифицируем
        if match.current_player_turn == "player1":
            player_act = match.player1_actions
            opp_act = match.player2_actions
        else:
            player_act = match.player2_actions
            opp_act = match.player1_actions

        # Применяем эффект карточки
        new_player, new_opp = self._apply_card_effect(
            card=card,
            player_actions=player_act,
            opponent_actions=opp_act,
            target_player_id=target_player_id
        )

        # Сохраняем обновлённые действия обратно в матч
        if match.current_player_turn == "player1":
            match.player1_actions = new_player
            match.player2_actions = new_opp
        else:
            match.player1_actions = new_opp
            match.player2_actions = new_player

        await session.commit()

        logger.info(f"Карточка '{card.name}' применена в матче {match.id} "
                    f"(цель: {target_player_id or 'нет'})")

        return True, f"Карточка '{card.name}' успешно применена"


    async def resolve_card(
        self,
        session: AsyncSession,
        card_instance: CardInstance,
        cancelling_card: Optional[CardInstance] = None
    ) -> Tuple[bool, str]:
        """
        Финальное разрешение карточки после всех проверок (включая возможную отмену).

        Args:
            session: сессия БД
            card_instance: карточка, которую разрешаем
            cancelling_card: карточка ВАР, которая отменяет эту (если есть)

        Returns:
            (успех, сообщение)
        """
        if card_instance.is_cancelled:
            return False, "Карточка уже отменена"

        if cancelling_card:
            card_instance.is_cancelled = True
            card_instance.used_at = func.now()  # время отмены
            await session.commit()

            logger.info(f"Карточка '{card_instance.card.name}' отменена ВАРом "
                        f"в матче {card_instance.match_id}")
            return True, f"Карточка '{card_instance.card.name}' отменена"

        # Если не отменена — подтверждаем применение
        card_instance.is_used = True
        card_instance.used_at = func.now()
        await session.commit()

        logger.info(f"Карточка '{card_instance.card.name}' разрешена "
                    f"в матче {card_instance.match_id}")

        return True, f"Карточка '{card_instance.card.name}' успешно разрешена"


# Глобальный экземпляр менеджера
match_manager = MatchManager()