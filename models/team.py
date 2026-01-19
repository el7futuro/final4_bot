from sqlalchemy import Column, Integer, String, JSON, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from models.base import Base


class Team(Base):
    __tablename__ = 'teams'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    name = Column(String(64), default='Моя команда')
    formation = Column(String(16), default='1-4-4-2')
    players = Column(JSON, nullable=False)  # Список футболистов
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="team")

    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}', user_id={self.user_id})>"

    def get_players_by_position(self, position: str) -> list:
        """Возвращает игроков по позиции"""
        return [p for p in self.players if p['position'] == position]

    def get_player_count(self) -> dict:
        """Подсчитывает количество игроков по позициям"""
        counts = {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}
        for player in self.players:
            counts[player['position']] += 1
        return counts

    def validate_team(self) -> tuple[bool, str]:
        """Проверяет, что команда соответствует требованиям"""
        counts = self.get_player_count()

        # Проверяем количество игроков
        required_counts = {'GK': 1, 'DF': 5, 'MF': 6, 'FW': 4}

        for pos, required in required_counts.items():
            if counts[pos] != required:
                return False, f"Нужно {required} {pos}, а у вас {counts[pos]}"

        # Проверяем, что всего 16 игроков
        total = sum(counts.values())
        if total != 16:
            return False, f"В команде должно быть 16 игроков, а у вас {total}"

        return True, "Команда валидна"

    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'formation': self.formation,
            'players': self.players,
            'player_count': self.get_player_count()
        }


# Добавляем relationship в User
from models.user import User

User.team = relationship("Team", back_populates="user", uselist=False)