# models/match.py
import json
import logging

from sqlalchemy import Column, Integer, String, JSON, DateTime, func, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from models.base import Base
import enum
from typing import Optional, Dict
from models.bet_tracker import BetTracker
logger = logging.getLogger(__name__)

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

    # === ДОБАВЛЯЕМ БЕТТРЕКЕР ===
    bet_tracker_data = Column(JSON, default={})  # Данные BetTracker для контроля ограничений

    # Текущий ход (1-11 основное время, 12+ ДВ)
    current_turn = Column(Integer, default=1)

    # Чей сейчас ход (player1 или player2)
    current_player_turn = Column(String(10), default="player1")  # "player1" или "player2"

    # Флаг дополнительного времени
    is_extra_time = Column(Boolean, default=False)

    # Игроки для дополнительного времени
    extra_time_players = Column(JSON, default={
        'player1': [],  # ID игроков player1 для ДВ
        'player2': []  # ID игроков player2 для ДВ
    })

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

    # === СВОЙСТВА ДЛЯ BETTRACKER ===


    @property
    def bet_tracker(self) -> BetTracker:
        """Получает BetTracker из JSON данных."""
        # from models.bet_tracker import BetTracker  # УДАЛИТЬ - уже импортировано выше

        if not self.bet_tracker_data:
            # Создаем новый BetTracker с текущим ходом
            tracker = BetTracker()
            tracker.current_turn = self.current_turn
            tracker.is_extra_time = self.is_extra_time
            return tracker

        # Если данные есть, загружаем их
        try:
            if isinstance(self.bet_tracker_data, str):
                data = json.loads(self.bet_tracker_data)
            else:
                data = self.bet_tracker_data  # Уже словарь

            tracker = BetTracker.from_dict(data)

            # Убедимся, что трекер синхронизирован с состоянием матча
            if tracker.current_turn != self.current_turn:
                tracker.current_turn = self.current_turn

            if tracker.is_extra_time != self.is_extra_time:
                tracker.is_extra_time = self.is_extra_time

            return tracker
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"Error loading BetTracker: {e}, creating new one")
            # Если ошибка декодирования, создаем новый
            tracker = BetTracker()
            tracker.current_turn = self.current_turn
            tracker.is_extra_time = self.is_extra_time
            return tracker


    @bet_tracker.setter
    def bet_tracker(self, tracker):
        """Сохраняет BetTracker в JSON данные."""
        from models.bet_tracker import BetTracker

        # Проверяем, что это BetTracker
        if not hasattr(tracker, 'to_dict'):
            raise TypeError("Объект должен иметь метод to_dict()")

        # Получаем словарь и преобразуем в JSON строку
        tracker_dict = tracker.to_dict()
        self.bet_tracker_data = json.dumps(tracker_dict)  # ← Важно: dumps!

        # Синхронизируем основные поля
        self.current_turn = tracker.current_turn
        self.is_extra_time = tracker.is_extra_time

    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===

    def get_current_user_id(self) -> Optional[int]:
        """Возвращает ID пользователя, чей сейчас ход."""
        if self.current_player_turn == "player1":
            return self.player1_id
        elif self.current_player_turn == "player2":
            return self.player2_id
        return None

    def switch_turn(self):
        """Переключает ход между игроками."""
        if self.current_player_turn == "player1":
            self.current_player_turn = "player2"
        else:
            self.current_player_turn = "player1"
            # Если переключились на player1, значит завершили ход
            if not self.is_extra_time:
                self.current_turn += 1
                # Обновляем трекер
                tracker = self.bet_tracker
                tracker.current_turn = self.current_turn
                tracker.reset_current_turn()
                self.bet_tracker = tracker

    def get_player_team_data(self, user_id: int) -> Optional[Dict]:
        """Возвращает данные команды игрока."""
        if user_id == self.player1_id:
            return self.player1_team_data
        elif user_id == self.player2_id:
            return self.player2_team_data
        return None

    def get_player_number(self, user_id: int) -> int:
        """Возвращает номер игрока в матче (1 для player1, 2 для player2)."""
        if user_id == self.player1_id:
            return 1
        else:  # user_id == self.player2_id
            return 2

    # models/match.py - добавить в класс Match
    def is_player_in_match(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь участником матча"""
        return user_id in [self.player1_id, self.player2_id]

    def get_player_actions(self, user_id: int) -> Dict:
        """Возвращает действия игрока."""
        if user_id == self.player1_id:
            return self.player1_actions
        elif user_id == self.player2_id:
            return self.player2_actions
        return {'goals': 0, 'passes': 0, 'defenses': 0}

    def update_player_actions(self, user_id: int, actions: Dict):
        """Обновляет действия игрока."""
        if user_id == self.player1_id:
            current = self.player1_actions.copy()
            current['goals'] += actions.get('goals', 0)
            current['passes'] += actions.get('passes', 0)
            current['defenses'] += actions.get('defenses', 0)
            self.player1_actions = current
        elif user_id == self.player2_id:
            current = self.player2_actions.copy()
            current['goals'] += actions.get('goals', 0)
            current['passes'] += actions.get('passes', 0)
            current['defenses'] += actions.get('defenses', 0)
            self.player2_actions = current

    def start_extra_time(self, player1_players: list, player2_players: list):
        """Начинает дополнительное время."""
        self.is_extra_time = True
        self.current_turn = 1
        self.current_player_turn = "player1"
        self.extra_time_players = {
            'player1': player1_players,
            'player2': player2_players
        }
        # Обновляем трекер
        tracker = self.bet_tracker
        tracker.start_extra_time([])  # Игроки будут загружены при запросе
        self.bet_tracker = tracker



    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'type': self.match_type.value,
            'status': self.status.value,
            'player1_id': self.player1_id,
            'player2_id': self.player2_id,
            'player1_score': self.player1_score,
            'player2_score': self.player2_score,
            'current_turn': self.current_turn,
            'current_player_turn': self.current_player_turn,
            'is_extra_time': self.is_extra_time,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None
        }


# Добавляем отношения в User
from models.user import User

User.matches_as_player1 = relationship("Match", foreign_keys="Match.player1_id", back_populates="player1")
User.matches_as_player2 = relationship("Match", foreign_keys="Match.player2_id", back_populates="player2")