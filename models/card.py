# models/card.py
"""
Модели карточек «Свисток» для игры Final 4.

Содержит:
- CardType           — все возможные типы карточек
- CardRarity         — редкость (влияет на количество в колоде)
- CardEffectType     — категории эффектов
- Card               — статическая карточка из колоды (шаблон)
- CardInstance       — конкретный экземпляр карточки в матче (с полем applied_to_player_id)
- CardDeck           — колода + логика вытягивания/сброса/перетасовки
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import enum
from sqlalchemy import Column, Integer, String, JSON, DateTime, func, ForeignKey, Enum, Boolean, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from models.base import Base
from models.match import Match
from models.user import User


class CardType(enum.Enum):
    """Типы карточек «Свисток» согласно правилам игры"""
    HAT_TRICK    = "hat_trick"      # Хэт-трик (3 гола)
    DOUBLE       = "double"         # Дубль (2 гола)
    GOAL         = "goal"           # Гол (1 гол)
    OWN_GOAL     = "own_goal"       # Автогол (+1 гол сопернику)
    VAR          = "var"            # ВАР (отменяет карточку соперника)
    OFFSIDE      = "offside"        # Офсайд (отменяет гол)
    PENALTY      = "penalty"        # Пенальти (ставка на больше/меньше)
    RED_CARD     = "red_card"       # Удаление (теряет все действия)
    YELLOW_CARD  = "yellow_card"    # Предупреждение (теряет 1 действие)
    FOUL         = "foul"           # Фол (теряет 1 отбитие)
    LOST_BALL    = "lost_ball"      # Потеря (теряет 1 передачу)
    INTERCEPTION = "interception"   # Перехват (+1 передача)
    TACKLE       = "tackle"         # Отбор (+1 отбитие)


class CardRarity(enum.Enum):
    """Редкость карточек (по количеству в колоде)"""
    LEGENDARY = "legendary"   # 1 штука
    EPIC      = "epic"        # 1-2 штуки
    RARE      = "rare"        # 2-3 штуки
    COMMON    = "common"      # 6 штук


class CardEffectType(enum.Enum):
    """Типы эффектов карточек"""
    ADD_GOALS         = "add_goals"
    REMOVE_GOALS      = "remove_goals"
    ADD_PASSES        = "add_passes"
    REMOVE_PASSES     = "remove_passes"
    ADD_DEFENSES      = "add_defenses"
    REMOVE_DEFENSES   = "remove_defenses"
    CANCEL_CARD       = "cancel_card"
    CANCEL_GOAL       = "cancel_goal"
    SPECIAL_BET       = "special_bet"
    REMOVE_ALL_ACTIONS = "remove_all"


class Card(Base):
    """
    Шаблон карточки «Свисток» — одна запись на каждый уникальный тип.
    """
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True)

    card_type     = Column(Enum(CardType), nullable=False, unique=True)
    name          = Column(String(64), nullable=False)
    description   = Column(Text, nullable=False)
    rarity        = Column(Enum(CardRarity), nullable=False, default=CardRarity.COMMON)

    count_in_deck = Column(Integer, nullable=False)

    effect_type   = Column(Enum(CardEffectType), nullable=False)
    effect_value  = Column(Integer, nullable=True)
    target        = Column(String(32), default="self")  # self, opponent, both, specific

    conditions    = Column(JSON, default=dict)
    special_rules = Column(Text, nullable=True)

    is_active     = Column(Boolean, default=True)

    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    instances = relationship("CardInstance", back_populates="card", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Card id={self.id} {self.name} ({self.card_type.value})>"

    def apply_effect(
        self,
        player_actions: Dict[str, int],
        opponent_actions: Dict[str, int],
        target_player_id: Optional[int] = None
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Применяет эффект карточки к действиям (внутренний метод).
        Возвращает обновлённые словари.
        """
        player = player_actions.copy()
        opponent = opponent_actions.copy()

        effect = self.effect_type
        val = self.effect_value or 0
        tgt = self.target.lower()

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

        elif effect == CardEffectType.REMOVE_ALL_ACTIONS:
            if tgt in ("self", "both"):
                player = {"goals": 0, "passes": 0, "defenses": 0}
            if tgt in ("opponent", "both"):
                opponent = {"goals": 0, "passes": 0, "defenses": 0}

        elif effect == CardEffectType.CANCEL_GOAL:
            if tgt in ("opponent", "both"):
                opponent["goals"] = max(0, opponent["goals"] - 1)

        elif effect == CardEffectType.CANCEL_CARD:
            # Отмена карточки обрабатывается в resolve_card
            pass

        elif effect == CardEffectType.SPECIAL_BET:
            # Логика пенальти — в resolve_turn
            pass

        return player, opponent


class CardInstance(Base):
    """
    Конкретный экземпляр карточки в матче.

    Добавлено поле applied_to_player_id для карточек с target="specific".
    """
    __tablename__ = "card_instances"

    id = Column(Integer, primary_key=True)

    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    drawn_by_player = Column(Integer)  # 1 или 2 (номер игрока в матче)

    is_drawn     = Column(Boolean, default=False)
    is_used      = Column(Boolean, default=False)
    is_cancelled = Column(Boolean, default=False)

    turn_drawn   = Column(Integer, nullable=True)
    turn_used    = Column(Integer, nullable=True)

    # Новое поле: на какого игрока применена карточка (если target="specific")
    applied_to_player_id = Column(Integer, nullable=True)

    target_player_position = Column(String(10), nullable=True)

    effect_applied = Column(JSON, default=dict)

    drawn_at = Column(DateTime(timezone=True), nullable=True)
    used_at  = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Отношения
    card  = relationship("Card", back_populates="instances")
    match = relationship("Match", back_populates="card_instances")
    owner = relationship("User", back_populates="card_instances")

    def __repr__(self) -> str:
        status = "used" if self.is_used else "drawn" if self.is_drawn else "in_deck"
        return f"<CardInstance id={self.id} card={self.card_id} status={status}>"


class CardDeck(Base):
    """
    Колода карточек для конкретного матча.
    """
    __tablename__ = "card_decks"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, unique=True)

    deck_order: List[int] = Column(JSON, default=list)
    current_index: int = Column(Integer, default=0)
    cards_drawn_count: int = Column(Integer, default=0)
    discard_pile: List[int] = Column(JSON, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    match = relationship("Match", back_populates="card_deck")

    def cards_left(self) -> int:
        return len(self.deck_order) - self.current_index

    def draw_card(self) -> Optional[int]:
        if self.current_index >= len(self.deck_order):
            self.reshuffle_discard()
        if self.current_index >= len(self.deck_order):
            return None
        card_id = self.deck_order[self.current_index]
        self.current_index += 1
        self.cards_drawn_count += 1
        return card_id

    def discard_card(self, card_id: int) -> None:
        self.discard_pile.append(card_id)

    def reshuffle_discard(self) -> None:
        if not self.discard_pile:
            return
        self.deck_order.extend(self.discard_pile)
        self.discard_pile = []

    def peek_next_card(self) -> Optional[int]:
        if self.current_index < len(self.deck_order):
            return self.deck_order[self.current_index]
        return None


# Обратные связи (защита от циклического импорта)
try:
    from models.match import Match
    from models.user import User

    Match.card_instances = relationship(
        "CardInstance",
        back_populates="match",
        cascade="all, delete-orphan"
    )
    Match.card_deck = relationship(
        "CardDeck",
        back_populates="match",
        uselist=False,
        cascade="all, delete-orphan"
    )

    User.card_instances = relationship(
        "CardInstance",
        back_populates="owner",
        cascade="all, delete-orphan"
    )
except ImportError:
    pass


# ────────────────────────────────────────────────
# Методы применения и разрешения карточек
# ────────────────────────────────────────────────

async def use_card(
    session: AsyncSession,
    card_instance: CardInstance,
    target_player_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Применяет карточку в матче.

    Args:
        session: сессия БД
        card_instance: экземпляр карточки
        target_player_id: на какого игрока применяем (если требуется)

    Returns:
        (успех, сообщение)
    """
    if card_instance.is_used:
        return False, "Карточка уже использована"

    if card_instance.is_cancelled:
        return False, "Карточка была отменена"

    match = await session.get(Match, card_instance.match_id)
    if not match:
        return False, "Матч не найден"

    card = card_instance.card

    # Проверяем, нужна ли цель
    if card.target == "specific" and target_player_id is None:
        return False, "Для этой карточки требуется указать цель"

    # Сохраняем цель применения
    card_instance.applied_to_player_id = target_player_id
    card_instance.used_at = func.now()
    card_instance.is_used = True

    # Применяем эффект (логика в модели Card)
    player_act = match.player1_actions if match.current_player_turn == "player1" else match.player2_actions
    opp_act = match.player2_actions if match.current_player_turn == "player1" else match.player1_actions

    new_player, new_opp = card.apply_effect(
        player_actions=player_act,
        opponent_actions=opp_act,
        target_player_id=target_player_id
    )

    # Сохраняем обновлённые действия
    if match.current_player_turn == "player1":
        match.player1_actions = new_player
        match.player2_actions = new_opp
    else:
        match.player1_actions = new_opp
        match.player2_actions = new_player

    await session.commit()

    return True, f"Карточка '{card.name}' применена"


async def resolve_card(
    session: AsyncSession,
    card_instance: CardInstance,
    cancelling_card: Optional[CardInstance] = None
) -> Tuple[bool, str]:
    """
    Финальное разрешение карточки (после всех проверок и возможной отмены).

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
        return True, f"Карточка '{card_instance.card.name}' отменена ВАРом"

    # Если не отменена — подтверждаем применение
    card_instance.is_used = True
    card_instance.used_at = func.now()
    await session.commit()

    return True, f"Карточка '{card_instance.card.name}' успешно разрешена"