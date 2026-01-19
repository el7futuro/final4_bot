from sqlalchemy import Column, Integer, String, BigInteger, DateTime, func
from sqlalchemy.orm import relationship
from models.base import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(64))
    first_name = Column(String(64))
    last_name = Column(String(64))


    games_played = Column(Integer, default=0)
    games_won = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"

    @property
    def win_rate(self) -> float:
        """Процент побед"""
        if self.games_played == 0:
            return 0.0
        return (self.games_won / self.games_played) * 100

    def to_dict(self):
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'username': self.username,
            'first_name': self.first_name,


            'games_played': self.games_played,
            'games_won': self.games_won,
            'win_rate': round(self.win_rate, 1)
        }