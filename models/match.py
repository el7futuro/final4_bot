# models/match.py
from sqlalchemy import Column, Integer, String, JSON, DateTime, func, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from models.base import Base
import enum


class MatchStatus(enum.Enum):
    """Статусы матча"""
    CREATED = "created"
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class MatchType(enum.Enum):
    """Типы матчей"""
    VS_RANDOM = "vs_random"
    VS_BOT = "vs_bot"
    TOURNAMENT = "tournament"


class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key=True)
    match_type = Column(Enum(MatchType), nullable=False, default=MatchType.VS_RANDOM)
    status = Column(Enum(MatchStatus), nullable=False, default=MatchStatus.CREATED)

    # Игроки
    player1_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    player2_id = Column(Integer, ForeignKey('users.id'))

    # Статистика матча
    player1_team_data = Column(JSON)  # Данные команды игрока 1 на момент матча
    player2_team_data = Column(JSON)  # Данные команды игрока 2 на момент матча

    # Действия в матче
    dice_rolls = Column(JSON, default=[])  # Броски кубиков
    bets = Column(JSON, default=[])  # Ставки игроков
    cards_drawn = Column(JSON, default=[])  # Вытянутые карточки "Свисток"

    # Результаты
    player1_actions = Column(JSON, default={'goals': 0, 'passes': 0, 'defenses': 0})
    player2_actions = Column(JSON, default={'goals': 0, 'passes': 0, 'defenses': 0})
    player1_score = Column(Integer, default=0)
    player2_score = Column(Integer, default=0)

    # Пенальти
    penalty_shootout = Column(JSON, default=None)

    # Время
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))

    # Связи
    player1 = relationship("User", foreign_keys=[player1_id], back_populates="matches_as_player1")
    player2 = relationship("User", foreign_keys=[player2_id], back_populates="matches_as_player2")


    def __repr__(self):
        return f"<Match(id={self.id}, player1={self.player1_id}, player2={self.player2_id}, status={self.status.value})>"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'type': self.match_type.value,
            'status': self.status.value,
            'player1_id': self.player1_id,
            'player2_id': self.player2_id,
            'player1_score': self.player1_score,
            'player2_score': self.player2_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None
        }


# Добавляем отношения в User
from models.user import User

User.matches_as_player1 = relationship("Match", foreign_keys="Match.player1_id", back_populates="player1")
User.matches_as_player2 = relationship("Match", foreign_keys="Match.player2_id", back_populates="player2")