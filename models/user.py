# models/user.py
"""
Модель пользователя в игре Final 4.

Хранит основную информацию о Telegram-пользователе,
статистику игр, дату создания и последней активности.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, func
from sqlalchemy.orm import relationship

from models.base import Base


class User(Base):
    """
    Пользователь игры Final 4 (привязан к Telegram-аккаунту).

    Основные поля:
    - telegram_id      — уникальный ID из Telegram
    - username, first_name, last_name — данные профиля
    - статистика: сыгранные/выигранные матчи, процент побед
    - временные метки: регистрация и последняя активность
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    # Telegram-идентификаторы
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username    = Column(String(64), nullable=True)
    first_name  = Column(String(64), nullable=True)
    last_name   = Column(String(64), nullable=True)

    # Статистика
    games_played = Column(Integer, default=0, nullable=False)
    games_won    = Column(Integer, default=0, nullable=False)

    # Временные метки
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_active = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Отношения (back_populates устанавливаются в других моделях)
    matches_as_player1 = relationship(
        "Match",
        foreign_keys="Match.player1_id",
        back_populates="player1",
        cascade="all, delete-orphan"
    )
    matches_as_player2 = relationship(
        "Match",
        foreign_keys="Match.player2_id",
        back_populates="player2",
        cascade="all, delete-orphan"
    )

    # Дополнительные связи (добавляются в других моделях)
    # bets, card_instances, tournaments_created, tournament_matches_as_player1/2 и т.д.

    def __repr__(self) -> str:
        username_part = f"@{self.username}" if self.username else f"#{self.telegram_id}"
        return f"<User id={self.id} {username_part}>"

    @property
    def win_rate(self) -> float:
        """
        Процент побед (с точностью до одного знака после запятой).

        Возвращает 0.0, если игр ещё не было.
        """
        if self.games_played == 0:
            return 0.0
        return (self.games_won / self.games_played) * 100

    def to_dict(self, include_stats: bool = True) -> Dict[str, Any]:
        """
        Сериализует пользователя в словарь.

        Аргументы:
            include_stats — включать статистику (по умолчанию True)

        Возвращает:
            словарь с основными полями пользователя
        """
        data = {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None,
        }

        if include_stats:
            data.update({
                "games_played": self.games_played,
                "games_won": self.games_won,
                "win_rate": round(self.win_rate, 1),
            })

        return data

    def update_activity(self) -> None:
        """
        Обновляет время последней активности (last_active).
        Вызывается при любом взаимодействии пользователя.
        """
        self.last_active = func.now()

    def register_game(self, won: bool = False) -> None:
        """
        Регистрирует сыгранную игру и (при необходимости) победу.

        Аргументы:
            won — True, если пользователь выиграл этот матч
        """
        self.games_played += 1
        if won:
            self.games_won += 1
        self.update_activity()