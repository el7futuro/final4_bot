# models/bet.py
"""
Модель ставок менеджера на броски кубика в игре Final 4.

Содержит:
- перечисления типов ставок (BetType) и статусов (BetStatus)
- основную модель Bet с полями, методами проверки выигрыша,
  расчёта действий и разрешения ставки после броска кубика
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

import enum
from sqlalchemy import Column, Integer, String, JSON, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class BetType(enum.Enum):
    """
    Типы ставок, которые может сделать менеджер на игрока.

    EVEN_ODD   — Чёт/Нечёт (даёт отбития / защиты)
    BIG_SMALL  — Меньше (1-3) / Больше (4-6) (даёт передачи)
    GOAL       — Точное число на кубике (даёт голы)
    """
    EVEN_ODD = "EVEN_ODD"
    BIG_SMALL = "BIG_SMALL"
    GOAL = "GOAL"


class BetStatus(enum.Enum):
    """
    Статусы обработки ставки после броска кубика.

    PENDING    — ожидает результата броска
    WON        — ставка выиграла → получены действия
    LOST       — ставка проиграла
    CANCELLED  — ставка была отменена до броска
    """
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    CANCELLED = "cancelled"


class Bet(Base):
    """
    Модель одной ставки менеджера в конкретном ходе матча.

    Хранит:
    - связь с матчем и пользователем
    - выбранного игрока и его позицию
    - тип и значение ставки
    - результат броска и статус
    - полученные полезные действия (голы, передачи, отбития)
    - связь с вытянутой карточкой «Свисток» (если была)
    - временные метки создания и разрешения
    """

    __tablename__ = "bets"

    id = Column(Integer, primary_key=True)

    # Связи с другими таблицами
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Игрок, на которого сделана ставка (id внутри команды пользователя)
    player_id = Column(Integer, nullable=False)

    # Основные параметры ставки
    bet_type = Column(enum.Enum(BetType), nullable=False)
    bet_value = Column(String(10), nullable=False)      # "чет", "нечет", "меньше", "больше", "1"…"6"
    player_position = Column(String(2), nullable=False)  # "GK", "DF", "MF", "FW"

    # Результат броска и итог
    dice_roll = Column(Integer)                         # 1–6 или None до броска
    bet_result = Column(enum.Enum(BetStatus), default=BetStatus.PENDING)

    # Полученные действия (заполняется только при выигрыше)
    actions_gained = Column(JSON, default={"goals": 0, "passes": 0, "defenses": 0})

    # Контекст хода
    turn_number = Column(Integer, nullable=False)       # номер хода в матче (1–11 или больше в ДВ)
    bet_order = Column(Integer, nullable=False)         # 1 или 2 (первая / вторая ставка в ходе)

    # Связь с вытянутой карточкой (если ставка выиграла и была выдана карта)
    card_drawn_id = Column(Integer, ForeignKey("card_instances.id"), nullable=True)

    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Отношения (back_populates)
    user = relationship("User", back_populates="bets")
    card_drawn = relationship(
        "CardInstance",
        back_populates="source_bet",
        foreign_keys=[card_drawn_id],
        uselist=False
    )

    def __repr__(self) -> str:
        return (
            f"<Bet id={self.id} "
            f"match={self.match_id} "
            f"user={self.user_id} "
            f"player={self.player_id} "
            f"type={self.bet_type.value} "
            f"value={self.bet_value} "
            f"result={self.bet_result.value if self.bet_result else 'None'}>"
        )

    def to_dict(self) -> Dict:
        """
        Сериализует объект ставки в словарь (удобно для API / отладки / логирования).

        Возвращает:
            словарь со всеми основными полями
        """
        return {
            "id": self.id,
            "match_id": self.match_id,
            "user_id": self.user_id,
            "player_id": self.player_id,
            "player_position": self.player_position,
            "bet_type": self.bet_type.value,
            "bet_value": self.bet_value,
            "dice_roll": self.dice_roll,
            "bet_result": self.bet_result.value if self.bet_result else None,
            "turn_number": self.turn_number,
            "bet_order": self.bet_order,
            "actions_gained": self.actions_gained,
            "card_drawn_id": self.card_drawn_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    def check_win(self) -> bool:
        """
        Проверяет, выиграла ли ставка при данном результате кубика.

        Возвращает:
            True — если ставка сыграла, False — иначе
        """
        if not self.dice_roll:
            return False

        roll = self.dice_roll

        if self.bet_type == BetType.EVEN_ODD:
            is_even = roll % 2 == 0
            return (self.bet_value == "чет" and is_even) or \
                   (self.bet_value == "нечет" and not is_even)

        elif self.bet_type == BetType.BIG_SMALL:
            is_small = roll <= 3
            return (self.bet_value == "больше" and not is_small) or \
                   (self.bet_value == "меньше" and is_small)

        elif self.bet_type == BetType.GOAL:
            return str(roll) == self.bet_value

        return False

    def calculate_actions(self) -> Dict[str, int]:
        """
        Рассчитывает количество полученных действий в случае выигрыша ставки.

        Согласно правилам Final 4:
          - GK → только Чет/Нечет → 3 отбития
          - DF → Чет/Нечет → 2 отбития | Меньше/Больше → 1 передача | Гол → 1 гол
          - MF → Чет/Нечет → 1 отбитие | Меньше/Больше → 2 передачи | Гол → 1 гол
          - FW → Меньше/Больше → 1 передача | Гол → 1 гол

        Возвращает:
            словарь {'goals': int, 'passes': int, 'defenses': int}
        """
        if not self.check_win():
            return {"goals": 0, "passes": 0, "defenses": 0}

        actions = {"goals": 0, "passes": 0, "defenses": 0}

        pos = self.player_position

        if pos == "GK":
            if self.bet_type == BetType.EVEN_ODD:
                actions["defenses"] = 3

        elif pos == "DF":
            if self.bet_type == BetType.EVEN_ODD:
                actions["defenses"] = 2
            elif self.bet_type == BetType.BIG_SMALL:
                actions["passes"] = 1
            elif self.bet_type == BetType.GOAL:
                actions["goals"] = 1

        elif pos == "MF":
            if self.bet_type == BetType.EVEN_ODD:
                actions["defenses"] = 1
            elif self.bet_type == BetType.BIG_SMALL:
                actions["passes"] = 2
            elif self.bet_type == BetType.GOAL:
                actions["goals"] = 1

        elif pos == "FW":
            if self.bet_type == BetType.BIG_SMALL:
                actions["passes"] = 1
            elif self.bet_type == BetType.GOAL:
                actions["goals"] = 1

        return actions

    def resolve(self, dice_roll: int) -> None:
        """
        Разрешает ставку после получения результата броска.

        Устанавливает:
        - значение dice_roll
        - статус WON / LOST
        - полученные действия (если выиграно)
        - время разрешения
        """
        self.dice_roll = dice_roll

        if self.check_win():
            self.bet_result = BetStatus.WON
            self.actions_gained = self.calculate_actions()
        else:
            self.bet_result = BetStatus.LOST

        self.resolved_at = func.now()


# ────────────────────────────────────────────────
# Обратные связи (защита от циклического импорта)
# ────────────────────────────────────────────────

try:
    from models.card import CardInstance
    CardInstance.source_bet = relationship(
        "Bet",
        back_populates="card_drawn",
        foreign_keys="Bet.card_drawn_id",
        uselist=False
    )
except ImportError:
    pass

try:
    from models.user import User
    User.bets = relationship(
        "Bet",
        back_populates="user",
        cascade="all, delete-orphan"
    )
except ImportError:
    pass