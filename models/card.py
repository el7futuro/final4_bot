# models/card.py
"""
Модель карточек «Свисток» для игры Final 4.
"""

from sqlalchemy import Column, Integer, String, JSON, DateTime, func, ForeignKey, Enum, Boolean, Text
from sqlalchemy.orm import relationship
import enum
from models.base import Base


class CardType(enum.Enum):
    """Типы карточек «Свисток» согласно правилам игры"""
    HAT_TRICK = "hat_trick"  # Хэт-трик (3 гола)
    DOUBLE = "double"  # Дубль (2 гола)
    GOAL = "goal"  # Гол (1 гол)
    OWN_GOAL = "own_goal"  # Автогол (+1 гол сопернику)
    VAR = "var"  # ВАР (отменяет карточку соперника)
    OFFSIDE = "offside"  # Офсайд (отменяет гол)
    PENALTY = "penalty"  # Пенальти (ставка на больше/меньше)
    RED_CARD = "red_card"  # Удаление (теряет все действия)
    YELLOW_CARD = "yellow_card"  # Предупреждение (теряет 1 действие)
    FOUL = "foul"  # Фол (теряет 1 отбитие)
    LOST_BALL = "lost_ball"  # Потеря (теряет 1 передачу)
    INTERCEPTION = "interception"  # Перехват (+1 передача)
    TACKLE = "tackle"  # Отбор (+1 отбитие)


class CardRarity(enum.Enum):
    """Редкость карточек (по количеству в колоде)"""
    LEGENDARY = "legendary"  # 1 штука
    EPIC = "epic"  # 1-2 штуки
    RARE = "rare"  # 2-3 штуки
    COMMON = "common"  # 6 штук


class CardEffectType(enum.Enum):
    """Типы эффектов карточек"""
    ADD_GOALS = "add_goals"  # Добавляет голы
    REMOVE_GOALS = "remove_goals"  # Убирает голы
    ADD_PASSES = "add_passes"  # Добавляет передачи
    REMOVE_PASSES = "remove_passes"  # Убирает передачи
    ADD_DEFENSES = "add_defenses"  # Добавляет отбития
    REMOVE_DEFENSES = "remove_defenses"  # Убирает отбития
    CANCEL_CARD = "cancel_card"  # Отменяет другую карточку
    CANCEL_GOAL = "cancel_goal"  # Отменяет гол
    SPECIAL_BET = "special_bet"  # Специальная ставка
    REMOVE_ALL_ACTIONS = "remove_all"  # Удаляет все действия


class Card(Base):
    __tablename__ = 'cards'

    id = Column(Integer, primary_key=True)

    # Основная информация
    card_type = Column(Enum(CardType), nullable=False, unique=True)
    name = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)
    rarity = Column(Enum(CardRarity), nullable=False, default=CardRarity.COMMON)

    # Количество в колоде (по правилам игры)
    count_in_deck = Column(Integer, nullable=False)

    # Эффекты карточки
    effect_type = Column(Enum(CardEffectType), nullable=False)
    effect_value = Column(Integer)  # Значение эффекта (например, +3 гола)
    target = Column(String(32), default="self")  # self, opponent, both, specific

    # Для карточек с особыми условиями
    conditions = Column(JSON, default=dict)
    special_rules = Column(Text)

    # Активна ли карточка в игре
    is_active = Column(Boolean, default=True)

    # Время
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Card(id={self.id}, name='{self.name}', type={self.card_type.value})>"

    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'type': self.card_type.value,
            'name': self.name,
            'description': self.description,
            'rarity': self.rarity.value,
            'count_in_deck': self.count_in_deck,
            'effect_type': self.effect_type.value,
            'effect_value': self.effect_value,
            'target': self.target
        }

    def apply_effect(self, player_actions: dict, opponent_actions: dict = None) -> tuple:
        """
        Применяет эффект карточки к действиям игроков.
        Возвращает (новые_действия_игрока, новые_действия_соперника)
        """
        player = player_actions.copy()
        opponent = opponent_actions.copy() if opponent_actions else {'goals': 0, 'passes': 0, 'defenses': 0}

        if self.effect_type == CardEffectType.ADD_GOALS:
            if self.target == "self":
                player['goals'] += self.effect_value
            elif self.target == "opponent":
                opponent['goals'] += self.effect_value

        elif self.effect_type == CardEffectType.REMOVE_GOALS:
            if self.target == "self":
                player['goals'] = max(0, player['goals'] - self.effect_value)
            elif self.target == "opponent":
                opponent['goals'] = max(0, opponent['goals'] - self.effect_value)

        elif self.effect_type == CardEffectType.ADD_PASSES:
            if self.target == "self":
                player['passes'] += self.effect_value

        elif self.effect_type == CardEffectType.REMOVE_PASSES:
            if self.target == "self":
                player['passes'] = max(0, player['passes'] - self.effect_value)
            elif self.target == "opponent":
                opponent['passes'] = max(0, opponent['passes'] - self.effect_value)

        elif self.effect_type == CardEffectType.ADD_DEFENSES:
            if self.target == "self":
                player['defenses'] += self.effect_value

        elif self.effect_type == CardEffectType.REMOVE_DEFENSES:
            if self.target == "self":
                player['defenses'] = max(0, player['defenses'] - self.effect_value)
            elif self.target == "opponent":
                opponent['defenses'] = max(0, opponent['defenses'] - self.effect_value)

        elif self.effect_type == CardEffectType.REMOVE_ALL_ACTIONS:
            if self.target == "self":
                player = {'goals': 0, 'passes': 0, 'defenses': 0}
            elif self.target == "opponent":
                opponent = {'goals': 0, 'passes': 0, 'defenses': 0}

        return player, opponent

    def is_cancellable(self) -> bool:
        """Можно ли отменить эту карточку карточкой ВАР"""
        return self.card_type not in [CardType.VAR, CardType.OFFSIDE]

    def get_emoji(self) -> str:
        """Возвращает emoji для карточки"""
        emojis = {
            CardType.HAT_TRICK: "🎩⚽⚽⚽",
            CardType.DOUBLE: "⚽⚽",
            CardType.GOAL: "⚽",
            CardType.OWN_GOAL: "😱⚽",
            CardType.VAR: "📺",
            CardType.OFFSIDE: "🚫",
            CardType.PENALTY: "🎯",
            CardType.RED_CARD: "🟥",
            CardType.YELLOW_CARD: "🟨",
            CardType.FOUL: "💢",
            CardType.LOST_BALL: "🤲",
            CardType.INTERCEPTION: "🤚",
            CardType.TACKLE: "👟"
        }
        return emojis.get(self.card_type, "🃏")


class CardInstance(Base):
    __tablename__ = 'card_instances'

    id = Column(Integer, primary_key=True)

    # Связь с карточкой
    card_id = Column(Integer, ForeignKey('cards.id'), nullable=False)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False)

    # Кому принадлежит карточка
    owner_id = Column(Integer, ForeignKey('users.id'))
    drawn_by_player = Column(Integer)  # 1 или 2

    # Статус карточки в матче
    is_drawn = Column(Boolean, default=False)  # Вытянута из колоды
    is_used = Column(Boolean, default=False)  # Использована
    is_cancelled = Column(Boolean, default=False)  # Отменена (ВАР)
    turn_drawn = Column(Integer)  # Ход, на котором вытянута
    turn_used = Column(Integer)  # Ход, на котором использована

    # Цель использования (если применимо)
    target_player_id = Column(Integer)  # ID игрока, на которого применена
    target_player_position = Column(String(10))  # Позиция игрока

    # Эффект применен
    effect_applied = Column(JSON, default=dict)

    # Время
    drawn_at = Column(DateTime(timezone=True))
    used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    card = relationship("Card", back_populates="instances")
    match = relationship("Match", back_populates="card_instances")
    owner = relationship("User", back_populates="card_instances")

    def __repr__(self):
        return f"<CardInstance(id={self.id}, card_id={self.card_id}, match_id={self.match_id})>"

    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'card_id': self.card_id,
            'match_id': self.match_id,
            'owner_id': self.owner_id,
            'drawn_by_player': self.drawn_by_player,
            'is_drawn': self.is_drawn,
            'is_used': self.is_used,
            'is_cancelled': self.is_cancelled,
            'turn_drawn': self.turn_drawn,
            'turn_used': self.turn_used
        }


class CardDeck(Base):
    __tablename__ = 'card_decks'

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'), unique=True, nullable=False)

    # Состав колоды
    deck_order = Column(JSON, nullable=False)  # Порядок карт в колоде [card_id, card_id, ...]
    current_index = Column(Integer, default=0)  # Текущая позиция в колоде

    # Карты в сбросе
    discard_pile = Column(JSON, default=list)

    # Статистика
    cards_drawn_count = Column(Integer, default=0)

    # Время
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    match = relationship("Match", back_populates="card_deck")

    def __repr__(self):
        return f"<CardDeck(id={self.id}, match_id={self.match_id}, cards_left={self.cards_left()})>"

    def cards_left(self) -> int:
        """Сколько карт осталось в колоде"""
        return len(self.deck_order) - self.current_index

    def draw_card(self) -> int:
        """Вытягивает карту из колоды, возвращает card_id"""
        if self.current_index >= len(self.deck_order):
            # Перетасовываем сброс, если колода пуста
            self.reshuffle_discard()

        if self.current_index >= len(self.deck_order):
            return None  # Нет карт

        card_id = self.deck_order[self.current_index]
        self.current_index += 1
        self.cards_drawn_count += 1
        return card_id

    def discard_card(self, card_id: int):
        """Сбрасывает карту"""
        self.discard_pile.append(card_id)

    def reshuffle_discard(self):
        """Перетасовывает сброс обратно в колоду"""
        if not self.discard_pile:
            return

        # Добавляем карты из сброса в конец колоды
        self.deck_order.extend(self.discard_pile)
        self.discard_pile = []
        # Можно добавить перемешивание, но в правилах не указано

    def peek_next_card(self) -> int:
        """Смотрит следующую карту, не вытягивая"""
        if self.current_index < len(self.deck_order):
            return self.deck_order[self.current_index]
        return None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'match_id': self.match_id,
            'cards_left': self.cards_left(),
            'cards_drawn': self.cards_drawn_count,
            'discard_pile_size': len(self.discard_pile)
        }


# Добавляем обратные связи
Card.instances = relationship("CardInstance", back_populates="card", cascade="all, delete-orphan")

try:
    from models.match import Match
    from models.user import User

    Match.card_instances = relationship("CardInstance", back_populates="match", cascade="all, delete-orphan")
    Match.card_deck = relationship("CardDeck", back_populates="match", uselist=False, cascade="all, delete-orphan")

    User.card_instances = relationship("CardInstance", back_populates="owner", cascade="all, delete-orphan")
except:
    pass


# Функция для инициализации карточек в БД
async def init_cards(session):
    """Создает все карточки «Свисток» в базе данных"""

    cards_data = [
        # Легендарные (1 шт)
        {
            'card_type': CardType.HAT_TRICK,
            'name': 'Хэт-трик',
            'description': 'Футболист получает 3 гола',
            'rarity': CardRarity.LEGENDARY,
            'count_in_deck': 1,
            'effect_type': CardEffectType.ADD_GOALS,
            'effect_value': 3,
            'target': 'self'
        },

        # Эпические (1 шт)
        {
            'card_type': CardType.DOUBLE,
            'name': 'Дубль',
            'description': 'Футболист получает 2 гола',
            'rarity': CardRarity.EPIC,
            'count_in_deck': 1,
            'effect_type': CardEffectType.ADD_GOALS,
            'effect_value': 2,
            'target': 'self'
        },

        # Редкие (2 шт)
        {
            'card_type': CardType.GOAL,
            'name': 'Гол',
            'description': 'Футболист получает гол',
            'rarity': CardRarity.RARE,
            'count_in_deck': 2,
            'effect_type': CardEffectType.ADD_GOALS,
            'effect_value': 1,
            'target': 'self'
        },
        {
            'card_type': CardType.VAR,
            'name': 'ВАР',
            'description': 'Отменяет действие карточки «Свисток» у соперника',
            'rarity': CardRarity.RARE,
            'count_in_deck': 2,
            'effect_type': CardEffectType.CANCEL_CARD,
            'effect_value': None,
            'target': 'opponent'
        },
        {
            'card_type': CardType.OFFSIDE,
            'name': 'Офсайд',
            'description': 'Отменяет гол футболиста соперника',
            'rarity': CardRarity.RARE,
            'count_in_deck': 2,
            'effect_type': CardEffectType.CANCEL_GOAL,
            'effect_value': None,
            'target': 'opponent'
        },
        {
            'card_type': CardType.PENALTY,
            'name': 'Пенальти',
            'description': 'Ставка на Больше-Меньше: если угадал - гол, если нет - соперник получает отбитие',
            'rarity': CardRarity.RARE,
            'count_in_deck': 2,
            'effect_type': CardEffectType.SPECIAL_BET,
            'effect_value': None,
            'target': 'both'
        },
        {
            'card_type': CardType.RED_CARD,
            'name': 'Удаление',
            'description': 'Футболист теряет все полезные действия',
            'rarity': CardRarity.RARE,
            'count_in_deck': 2,
            'effect_type': CardEffectType.REMOVE_ALL_ACTIONS,
            'effect_value': None,
            'target': 'self'
        },

        # Обычные (3 шт)
        {
            'card_type': CardType.YELLOW_CARD,
            'name': 'Предупреждение',
            'description': 'Футболист теряет одно полезное действие на выбор соперника',
            'rarity': CardRarity.COMMON,
            'count_in_deck': 3,
            'effect_type': CardEffectType.REMOVE_DEFENSES,  # На практике нужно выбирать действие
            'effect_value': 1,
            'target': 'self'
        },

        # Обычные (6 шт)
        {
            'card_type': CardType.FOUL,
            'name': 'Фол',
            'description': 'Футболист теряет одно «отбитие», если оно у него есть',
            'rarity': CardRarity.COMMON,
            'count_in_deck': 6,
            'effect_type': CardEffectType.REMOVE_DEFENSES,
            'effect_value': 1,
            'target': 'self'
        },
        {
            'card_type': CardType.LOST_BALL,
            'name': 'Потеря',
            'description': 'Футболист теряет «передачу», если она у него есть',
            'rarity': CardRarity.COMMON,
            'count_in_deck': 6,
            'effect_type': CardEffectType.REMOVE_PASSES,
            'effect_value': 1,
            'target': 'self'
        },
        {
            'card_type': CardType.INTERCEPTION,
            'name': 'Перехват',
            'description': 'Футболист получает дополнительную «передачу»',
            'rarity': CardRarity.COMMON,
            'count_in_deck': 6,
            'effect_type': CardEffectType.ADD_PASSES,
            'effect_value': 1,
            'target': 'self'
        },
        {
            'card_type': CardType.TACKLE,
            'name': 'Отбор',
            'description': 'Футболист получает дополнительное «отбитие»',
            'rarity': CardRarity.COMMON,
            'count_in_deck': 6,
            'effect_type': CardEffectType.ADD_DEFENSES,
            'effect_value': 1,
            'target': 'self'
        },

        # Особые (1 шт)
        {
            'card_type': CardType.OWN_GOAL,
            'name': 'Автогол',
            'description': 'Соперник получает +1 гол',
            'rarity': CardRarity.LEGENDARY,  # Особый случай
            'count_in_deck': 1,
            'effect_type': CardEffectType.ADD_GOALS,
            'effect_value': 1,
            'target': 'opponent'
        }
    ]

    for card_data in cards_data:
        # Проверяем, существует ли уже карточка
        existing = session.query(Card).filter_by(card_type=card_data['card_type']).first()
        if not existing:
            card = Card(**card_data)
            session.add(card)

    await session.commit()