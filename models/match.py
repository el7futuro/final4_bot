# models/match.py
"""
Модель матча в игре Final 4.

Содержит всю основную информацию о конкретном матче:
- тип и статус
- участники (игроки или бот)
- данные команд на момент начала
- текущий ход, чей ход, дополнительное время
- действия, счёт, броски кубиков, ставки, карточки
- BetTracker (ограничения ставок) в сериализованном виде
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy import (
    Column, Integer, String, JSON, DateTime, func,
    ForeignKey, Enum, Boolean
)
from sqlalchemy.orm import relationship

from models.base import Base
import enum

from models.bet_tracker import BetTracker

logger = logging.getLogger(__name__)


class MatchStatus(enum.Enum):
    """Текущий статус матча"""
    CREATED     = "created"      # создан, но не начат
    WAITING     = "waiting"      # ожидание соперника (для vs_random)
    IN_PROGRESS = "in_progress"  # идёт игра
    FINISHED    = "finished"     # завершён
    CANCELLED   = "cancelled"    # отменён


class MatchType(enum.Enum):
    """Тип матча"""
    VS_RANDOM    = "vs_random"     # против случайного игрока
    VS_BOT       = "vs_bot"        # против бота
    TOURNAMENT   = "tournament"    # турнирный матч


class Match(Base):
    """
    Основная модель одного матча.

    Хранит состояние игры, статистику, текущий ход,
    действия игроков, ограничения ставок (через BetTracker).
    """

    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)

    match_type = Column(Enum(MatchType), nullable=False, default=MatchType.VS_RANDOM)
    status     = Column(Enum(MatchStatus), nullable=False, default=MatchStatus.CREATED)

    # Участники
    player1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    player2_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Данные команд на момент создания матча (сериализованные)
    player1_team_data = Column(JSON, nullable=True)
    player2_team_data = Column(JSON, nullable=True)

    # Текущее состояние игры
    current_turn       = Column(Integer, default=1)               # 1–11 или больше в ДВ
    current_player_turn = Column(String(10), default="player1")   # "player1" или "player2"

    is_extra_time      = Column(Boolean, default=False)
    extra_time_players = Column(JSON, default={"player1": [], "player2": []})

    # Действия и счёт
    player1_actions = Column(JSON, default={"goals": 0, "passes": 0, "defenses": 0})
    player2_actions = Column(JSON, default={"goals": 0, "passes": 0, "defenses": 0})

    player1_score = Column(Integer, default=0)
    player2_score = Column(Integer, default=0)

    # Текущий состав на поле (кол-во игроков по позициям)
    current_on_field = Column(JSON, default={"DF": 0, "MF": 0, "FW": 0})

    # Использованные игроки (ID)
    used_players = Column(JSON, default=[])

    # История игры
    dice_rolls   = Column(JSON, default=[])   # список бросков
    bets         = Column(JSON, default=[])   # список ставок
    cards_drawn  = Column(JSON, default=[])   # список вытянутых карточек

    # Сериализованный BetTracker (контроль квот ставок)
    bet_tracker_data = Column(JSON, default={})

    # Пенальти (если будет)
    penalty_shootout = Column(JSON, nullable=True)

    # Временные метки
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    started_at  = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Отношения
    player1 = relationship("User", foreign_keys=[player1_id], back_populates="matches_as_player1")
    player2 = relationship("User", foreign_keys=[player2_id], back_populates="matches_as_player2")

    def __repr__(self) -> str:
        p2 = self.player2_id if self.player2_id else "None"
        return f"<Match id={self.id} {self.match_type.value} {self.status.value} p1={self.player1_id} p2={p2}>"

    # ─── BetTracker как свойство (удобный доступ и автоматическая сериализация) ───

    @property
    def bet_tracker(self) -> BetTracker:
        """
        Возвращает объект BetTracker, восстановленный из JSON-поля.
        Если данных нет — создаётся новый с текущим состоянием матча.
        """
        if not self.bet_tracker_data:
            tracker = BetTracker()
            tracker.current_turn = self.current_turn
            tracker.is_extra_time = self.is_extra_time
            return tracker

        try:
            if isinstance(self.bet_tracker_data, str):
                data = json.loads(self.bet_tracker_data)
            else:
                data = self.bet_tracker_data

            tracker = BetTracker.from_dict(data)

            # Синхронизация с основными полями матча
            if tracker.current_turn != self.current_turn:
                tracker.current_turn = self.current_turn
            if tracker.is_extra_time != self.is_extra_time:
                tracker.is_extra_time = self.is_extra_time

            return tracker

        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"Ошибка загрузки BetTracker в матче {self.id}: {e}")
            tracker = BetTracker()
            tracker.current_turn = self.current_turn
            tracker.is_extra_time = self.is_extra_time
            return tracker

    @bet_tracker.setter
    def bet_tracker(self, tracker: BetTracker) -> None:
        """
        Сохраняет состояние BetTracker в JSON-поле и синхронизирует основные поля.
        """
        if not hasattr(tracker, "to_dict"):
            raise TypeError("Ожидался объект BetTracker с методом to_dict()")

        self.bet_tracker_data = json.dumps(tracker.to_dict())

        # Синхронизация ключевых полей
        self.current_turn = tracker.current_turn
        self.is_extra_time = tracker.is_extra_time

    # ─── Удобные методы работы с матчем ──────────────────────────────────────

    def get_current_user_id(self) -> Optional[int]:
        """ID пользователя, чей сейчас ход."""
        if self.current_player_turn == "player1":
            return self.player1_id
        if self.current_player_turn == "player2":
            return self.player2_id
        return None

    def switch_turn(self) -> None:
        """
        Переключает ход на следующего игрока.
        При переходе на player1 — увеличивает номер хода (если не ДВ).
        """
        if self.current_player_turn == "player1":
            self.current_player_turn = "player2"
        else:
            self.current_player_turn = "player1"
            if not self.is_extra_time:
                self.current_turn += 1
                tracker = self.bet_tracker
                tracker.current_turn = self.current_turn
                tracker.reset_current_turn()
                self.bet_tracker = tracker

    def is_player_in_match(self, user_id: int) -> bool:
        """Проверяет, участвует ли пользователь в этом матче."""
        return user_id in (self.player1_id, self.player2_id)

    def get_player_number(self, user_id: int) -> Optional[int]:
        """Возвращает номер игрока: 1 или 2."""
        if user_id == self.player1_id:
            return 1
        if user_id == self.player2_id:
            return 2
        return None

    def get_player_team_data(self, user_id: int) -> Optional[Dict]:
        """Данные команды конкретного игрока."""
        if user_id == self.player1_id:
            return self.player1_team_data
        if user_id == self.player2_id:
            return self.player2_team_data
        return None

    def get_player_actions(self, user_id: int) -> Dict[str, int]:
        """Текущие накопленные действия игрока."""
        if user_id == self.player1_id:
            return self.player1_actions.copy()
        if user_id == self.player2_id:
            return self.player2_actions.copy()
        return {"goals": 0, "passes": 0, "defenses": 0}

    def update_player_actions(self, user_id: int, new_actions: Dict[str, int]) -> None:
        """
        Добавляет новые действия к уже накопленным у игрока.
        """
        actions = self.get_player_actions(user_id)

        for key in ("goals", "passes", "defenses"):
            actions[key] = actions.get(key, 0) + new_actions.get(key, 0)

        if user_id == self.player1_id:
            self.player1_actions = actions
        elif user_id == self.player2_id:
            self.player2_actions = actions

    def start_extra_time(self, player1_ids: List[int], player2_ids: List[int]) -> None:
        """
        Переводит матч в режим дополнительного времени.

        Args:
            player1_ids: список ID 5 запасных игроков для первого игрока
            player2_ids: список ID 5 запасных игроков для второго игрока

        Важно:
            - Вызывается ТОЛЬКО при ничейном счете после 11 ходов
            - Списки должны содержать ровно 5 ID каждый
            - Эти игроки НЕ использовались в основном времени
        """
        # Валидация
        if len(player1_ids) != 5 or len(player2_ids) != 5:
            logger.error(f"Попытка начать ДВ с неверным количеством игроков: "
                         f"p1={len(player1_ids)}, p2={len(player2_ids)}")
            raise ValueError("Для ДВ нужно ровно 5 запасных от каждой команды")

        # Проверяем, что эти игроки действительно не использовались
        used_set = set(self.used_players or [])
        for pid in player1_ids + player2_ids:
            if pid in used_set:
                logger.error(f"Попытка использовать игрока {pid} в ДВ, но он уже играл в основном времени")
                raise ValueError(f"Игрок {pid} уже использовался в основном времени")

        # Устанавливаем флаги ДВ
        self.is_extra_time = True
        self.current_turn = 1  # Сбрасываем счетчик ходов
        self.current_player_turn = "player1"  # Первый игрок начинает ДВ

        # Сохраняем списки запасных
        self.extra_time_players = {
            "player1": player1_ids,
            "player2": player2_ids
        }

        # Обновляем BetTracker для работы в режиме ДВ
        tracker = self.bet_tracker
        tracker.start_extra_time(player1_ids + player2_ids)  # передаем общий список всех запасных
        self.bet_tracker = tracker

        # Сбрасываем used_players? Нет, оставляем историю основного времени
        # В ДВ будем использовать отдельную логику через BetTracker

        logger.info(f"Матч {self.id} перешел в дополнительное время. "
                    f"Запасные p1: {player1_ids}, p2: {player2_ids}")
    def to_dict(self) -> Dict[str, Any]:
        """Краткая сериализация матча (для API, логов, уведомлений)."""
        return {
            "id": self.id,
            "type": self.match_type.value,
            "status": self.status.value,
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "player1_score": self.player1_score,
            "player2_score": self.player2_score,
            "current_turn": self.current_turn,
            "current_player_turn": self.current_player_turn,
            "is_extra_time": self.is_extra_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


# ─── Обратные связи в User ───────────────────────────────────────────────

from models.user import User

User.matches_as_player1 = relationship(
    "Match",
    foreign_keys="Match.player1_id",
    back_populates="player1"
)
User.matches_as_player2 = relationship(
    "Match",
    foreign_keys="Match.player2_id",
    back_populates="player2"
)