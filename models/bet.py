# models/bet.py
"""
Модель ставок менеджера на броски кубика в Final 4.
"""

from sqlalchemy import Column, Integer, String, JSON, DateTime, func, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
import enum
from models.base import Base


class BetType(enum.Enum):
    """Типы ставок в Final 4"""
    EVEN_ODD = "even_odd"  # Чет/нечет
    BIG_SMALL = "big_small"  # 1-3 (Меньше) / 4-6 (Больше)
    GOAL = "goal"  # Точное число

class BetStatus(enum.Enum):
    """Статусы ставки"""
    PENDING = "pending"  # Ожидает броска
    WON = "won"  # Выиграла
    LOST = "lost"  # Проиграла
    CANCELLED = "cancelled"  # Отменена


class Bet(Base):
    __tablename__ = 'bets'

    id = Column(Integer, primary_key=True)

    # Связи
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    player_id = Column(Integer, nullable=False)  # ID игрока в команде (не путать с user_id)

    # Данные ставки
    bet_type = Column(Enum(BetType), nullable=False)
    bet_value = Column(String(10), nullable=False)  # "чет", "нечет", "меньше", "больше", "1", "2", "3", "4", "5", "6"
    player_position = Column(String(2), nullable=False)  # GK, DF, MF, FW

    # Результат броска
    dice_roll = Column(Integer)  # Результат броска кубика (1-6)
    bet_result = Column(Enum(BetStatus), default=BetStatus.PENDING)

    # Полученные действия
    actions_gained = Column(JSON, default={
        'goals': 0,
        'passes': 0,
        'defenses': 0
    })

    # Порядок ставки в ходе
    turn_number = Column(Integer, nullable=False)  # 1-4
    bet_order = Column(Integer, nullable=False)  # Порядок ставки в ходе (1 или 2)

    # Карточка, полученная за эту ставку
    card_drawn_id = Column(Integer, ForeignKey('card_instances.id'))

    # Время
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))

    # Связи
    # УДАЛИТЕ эту строку - нет связи match, так как bets хранятся в JSON в Match
    # match = relationship("Match", back_populates="bets")

    user = relationship("User", back_populates="bets")
    card_drawn = relationship("CardInstance", back_populates="source_bet", foreign_keys=[card_drawn_id])

    def __repr__(self):
        return f"<Bet(id={self.id}, match={self.match_id}, player={self.player_id}, type={self.bet_type.value})>"

    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'match_id': self.match_id,
            'user_id': self.user_id,
            'player_id': self.player_id,
            'player_position': self.player_position,
            'bet_type': self.bet_type.value,
            'bet_value': self.bet_value,
            'dice_roll': self.dice_roll,
            'bet_result': self.bet_result.value if self.bet_result else None,
            'turn_number': self.turn_number,
            'bet_order': self.bet_order,
            'actions_gained': self.actions_gained,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }

    def check_win(self) -> bool:
        """Проверяет, выиграла ли ставка"""
        if not self.dice_roll:
            return False

        if self.bet_type == BetType.EVEN_ODD:  # ← ИЗМЕНЕНО
            is_even = self.dice_roll % 2 == 0
            return (self.bet_value == "чет" and is_even) or (self.bet_value == "нечет" and not is_even)

        elif self.bet_type == BetType.BIG_SMALL:  # ← ИЗМЕНЕНО
            is_less = self.dice_roll <= 3
            return (self.bet_value == "больше" and not is_less) or (
                        self.bet_value == "меньше" and is_less)  # ← Исправлены значения

        elif self.bet_type == BetType.GOAL:  # ← ИЗМЕНЕНО
            return str(self.dice_roll) == self.bet_value

        return False

    def calculate_actions(self) -> dict:
        """Рассчитывает полезные действия согласно правилам"""
        if not self.check_win():
            return {'goals': 0, 'passes': 0, 'defenses': 0}

        actions = {'goals': 0, 'passes': 0, 'defenses': 0}

        # Согласно правилам игры:
        # Вратарь: только ставка на Чет/Нечет → 3 отбития
        if self.player_position == 'GK':
            if self.bet_type == BetType.EVEN_ODD:  # ← ИЗМЕНЕНО
                actions['defenses'] = 3

        # Защитник
        elif self.player_position == 'DF':
            if self.bet_type == BetType.EVEN_ODD:  # ← ИЗМЕНЕНО
                actions['defenses'] = 2
            elif self.bet_type == BetType.BIG_SMALL:  # ← ИЗМЕНЕНО
                actions['passes'] = 1
            elif self.bet_type == BetType.GOAL:  # ← ИЗМЕНЕНО
                actions['goals'] = 1

        # Полузащитник
        elif self.player_position == 'MF':
            if self.bet_type == BetType.EVEN_ODD:  # ← ИЗМЕНЕНО
                actions['defenses'] = 1
            elif self.bet_type == BetType.BIG_SMALL:  # ← ИЗМЕНЕНО
                actions['passes'] = 2
            elif self.bet_type == BetType.GOAL:  # ← ИЗМЕНЕНО
                actions['goals'] = 1

        # Нападающий
        elif self.player_position == 'FW':
            if self.bet_type == BetType.BIG_SMALL:  # ← ИЗМЕНЕНО
                actions['passes'] = 1
            elif self.bet_type == BetType.GOAL:  # ← ИЗМЕНЕНО
                actions['goals'] = 1

        return actions

    def resolve(self, dice_roll: int):
        """Разрешает ставку после броска кубика"""
        self.dice_roll = dice_roll

        if self.check_win():
            self.bet_result = BetStatus.WON
            self.actions_gained = self.calculate_actions()
        else:
            self.bet_result = BetStatus.LOST

        self.resolved_at = func.now()


# Обратная связь для CardInstance
try:
    from models.card import CardInstance

    CardInstance.source_bet = relationship("Bet", back_populates="card_drawn", foreign_keys="Bet.card_drawn_id",
                                           uselist=False)
except:
    pass

# Обратная связь для User
try:
    from models.user import User

    User.bets = relationship("Bet", back_populates="user", cascade="all, delete-orphan")
except:
    pass