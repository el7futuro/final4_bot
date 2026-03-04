# models/tournament.py
"""
Модели турниров для Final 4.

Содержит:
- TournamentStatus     — статусы турнира
- TournamentType       — форматы проведения (single/double/swiss/round-robin)
- TournamentFormat     — размер сетки (4/8/16 участников)
- Tournament           — основная модель турнира (настройки, участники, сетка, призы)
- TournamentMatch      — отдельный матч внутри турнира (ссылка на Match + позиция в сетке)
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Any

import enum
from sqlalchemy import (
    Column, Integer, String, JSON, DateTime, func,
    ForeignKey, Enum, Boolean, Text
)
from sqlalchemy.orm import relationship

from models.base import Base


class TournamentStatus(enum.Enum):
    """
    Текущий статус турнира.
    """
    REGISTRATION = "registration"   # идёт набор участников
    CHECKIN      = "checkin"        # подтверждение присутствия (чек-ин)
    IN_PROGRESS  = "in_progress"    # турнир идёт
    FINISHED     = "finished"       # завершён
    CANCELLED    = "cancelled"      # отменён


class TournamentType(enum.Enum):
    """
    Формат проведения турнира.
    """
    SINGLE_ELIMINATION = "single"       # одиночное выбывание
    DOUBLE_ELIMINATION = "double"       # двойное выбывание
    SWISS              = "swiss"        # швейцарская система
    ROUND_ROBIN        = "round_robin"  # круговая система


class TournamentFormat(enum.Enum):
    """
    Размер турнирной сетки (влияет на количество участников и раундов).
    """
    PLAYOFF_4  = "playoff_4"   # 4 участника
    PLAYOFF_8  = "playoff_8"   # 8 участников
    PLAYOFF_16 = "playoff_16"  # 16 участников


class Tournament(Base):
    """
    Основная модель турнира.

    Хранит:
    - название, описание, тип, формат, статус
    - настройки (взнос, призовой фонд, рейтинг-фильтры)
    - расписание регистрации и проведения
    - распределение призов (в процентах)
    - структура сетки (bracket)
    - список участников и лист ожидания
    - результаты (победитель, места, финальная таблица)
    """

    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True)

    # Основная информация
    name             = Column(String(128), nullable=False)
    description      = Column(Text, nullable=True)
    tournament_type  = Column(Enum(TournamentType), nullable=False, default=TournamentType.SINGLE_ELIMINATION)
    tournament_format = Column(Enum(TournamentFormat), nullable=False, default=TournamentFormat.PLAYOFF_8)
    status           = Column(Enum(TournamentStatus), nullable=False, default=TournamentStatus.REGISTRATION)

    # Настройки участия
    max_players   = Column(Integer, nullable=False)
    entry_fee     = Column(Integer, default=0)          # взнос в очках/валюте
    prize_pool    = Column(Integer, default=0)          # общий призовой фонд
    min_rating    = Column(Integer, default=0)
    max_rating    = Column(Integer, default=9999)

    # Расписание
    registration_start = Column(DateTime(timezone=True), nullable=False)
    registration_end   = Column(DateTime(timezone=True), nullable=False)
    tournament_start   = Column(DateTime(timezone=True), nullable=False)
    estimated_end      = Column(DateTime(timezone=True), nullable=True)

    # Распределение призов (место → процент от prize_pool)
    prize_distribution = Column(JSON, default={
        "1": 50.0,
        "2": 30.0,
        "3": 20.0
    })

    # Сетка турнира
    bracket       = Column(JSON, default=dict)      # полная структура сетки
    current_round = Column(Integer, default=1)

    # Участники
    participants  = Column(JSON, default=list)      # [{'user_id': int, 'checked_in': bool, 'seed': int?}]
    waiting_list  = Column(JSON, default=list)      # лист ожидания

    # Результаты
    winner_id       = Column(Integer, ForeignKey("users.id"), nullable=True)
    second_place_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    third_place_id  = Column(Integer, ForeignKey("users.id"), nullable=True)
    final_standings = Column(JSON, default=list)    # финальная таблица мест

    # Организатор
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Временные метки
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())
    started_at  = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Отношения
    creator       = relationship("User", foreign_keys=[created_by], back_populates="tournaments_created")
    winner        = relationship("User", foreign_keys=[winner_id])
    second_place  = relationship("User", foreign_keys=[second_place_id])
    third_place   = relationship("User", foreign_keys=[third_place_id])
    tournament_matches = relationship(
        "TournamentMatch",
        back_populates="tournament",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tournament id={self.id} '{self.name}' {self.status.value}>"

    def to_dict(self) -> Dict[str, Any]:
        """Краткая сериализация для API / уведомлений."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.tournament_type.value,
            "format": self.tournament_format.value,
            "status": self.status.value,
            "max_players": self.max_players,
            "current_players": len(self.participants),
            "entry_fee": self.entry_fee,
            "prize_pool": self.prize_pool,
            "current_round": self.current_round,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "registration_end": self.registration_end.isoformat() if self.registration_end else None,
            "tournament_start": self.tournament_start.isoformat() if self.tournament_start else None,
        }

    def is_registration_open(self) -> bool:
        """Проверяет, открыта ли сейчас регистрация."""
        from datetime import datetime as dt
        now = dt.now(self.registration_start.tzinfo or dt.utcnow().tzinfo)
        return (
            self.status == TournamentStatus.REGISTRATION and
            self.registration_start <= now <= self.registration_end
        )

    def can_join(self, user_id: int, user_rating: int) -> tuple[bool, str]:
        """
        Может ли пользователь зарегистрироваться на турнир.

        Возвращает: (можно, причина_если_нельзя)
        """
        if not self.is_registration_open():
            return False, "Регистрация закрыта"

        if user_rating < self.min_rating:
            return False, f"Рейтинг слишком низкий (минимум {self.min_rating})"

        if user_rating > self.max_rating:
            return False, f"Рейтинг слишком высокий (максимум {self.max_rating})"

        if len(self.participants) >= self.max_players:
            if any(p["user_id"] == user_id for p in self.waiting_list):
                return False, "Вы уже в листе ожидания"
            return False, "Турнир заполнен"

        if any(p["user_id"] == user_id for p in self.participants):
            return False, "Вы уже зарегистрированы"

        return True, "Можно присоединиться"

    def add_participant(self, user_id: int, seed: Optional[int] = None) -> bool:
        """
        Добавляет участника в список зарегистрированных.

        Возвращает True, если добавлен успешно.
        """
        if any(p["user_id"] == user_id for p in self.participants):
            return False

        participant = {
            "user_id": user_id,
            "checked_in": False,
            "seed": seed or 9999
        }

        self.participants.append(participant)
        return True

    def remove_participant(self, user_id: int) -> bool:
        """Удаляет участника из списка (до начала турнира)."""
        before = len(self.participants)
        self.participants = [p for p in self.participants if p["user_id"] != user_id]
        return len(self.participants) < before

    def check_in_participant(self, user_id: int) -> bool:
        """Подтверждает присутствие участника (чек-ин)."""
        for p in self.participants:
            if p["user_id"] == user_id:
                p["checked_in"] = True
                return True
        return False

    def initialize_bracket(self) -> None:
        """
        Создаёт пустую структуру сетки в зависимости от формата турнира.
        Вызывается после завершения регистрации.
        """
        if self.tournament_format == TournamentFormat.PLAYOFF_4:
            bracket_size = 4
        elif self.tournament_format == TournamentFormat.PLAYOFF_8:
            bracket_size = 8
        elif self.tournament_format == TournamentFormat.PLAYOFF_16:
            bracket_size = 16
        else:
            return

        bracket = {
            "size": bracket_size,
            "rounds": [],
            "matches": {}
        }

        import math
        num_rounds = int(math.log2(bracket_size)) if bracket_size > 0 else 0

        for round_num in range(1, num_rounds + 1):
            round_matches = []
            matches_in_round = bracket_size // (2 ** round_num)

            for match_num in range(1, matches_in_round + 1):
                match_id = f"{round_num}_{match_num}"
                round_matches.append(match_id)

                next_round = round_num + 1
                next_match_num = (match_num + 1) // 2
                next_match_id = f"{next_round}_{next_match_num}" if next_round <= num_rounds else None

                bracket["matches"][match_id] = {
                    "round": round_num,
                    "number": match_num,
                    "player1": None,
                    "player2": None,
                    "winner": None,
                    "next_match": next_match_id,
                    "match_data": None  # будет ссылка на Match.id
                }

            bracket["rounds"].append({
                "round": round_num,
                "name": self._get_round_name(round_num, num_rounds),
                "matches": round_matches
            })

        self.bracket = bracket

    def _get_round_name(self, round_num: int, total_rounds: int) -> str:
        """Возвращает красивое название раунда в зависимости от размера сетки."""
        if total_rounds == 2:   # 4 игрока
            names = {1: "Полуфинал", 2: "Финал"}
        elif total_rounds == 3: # 8 игроков
            names = {1: "Четвертьфинал", 2: "Полуфинал", 3: "Финал"}
        elif total_rounds == 4: # 16 игроков
            names = {1: "1/8 финала", 2: "Четвертьфинал", 3: "Полуфинал", 4: "Финал"}
        else:
            names = {
                1: "1/8 финала",
                2: "Четвертьфинал",
                3: "Полуфинал",
                4: "Финал"
            }

        return names.get(round_num, f"Раунд {round_num}")

    def seed_participants(self) -> None:
        """
        Распределяет подтвердивших участие игроков по сетке (посев).
        Вызывается после чек-ина.
        """
        if not self.bracket:
            return

        checked_in = [p for p in self.participants if p.get("checked_in")]
        checked_in.sort(key=lambda x: x.get("seed", 9999))

        bracket_size = self.bracket["size"]
        first_round_matches = bracket_size // 2

        for i in range(first_round_matches):
            match_id = f"1_{i + 1}"

            player1 = checked_in[i * 2]["user_id"] if i * 2 < len(checked_in) else None
            player2 = checked_in[i * 2 + 1]["user_id"] if i * 2 + 1 < len(checked_in) else None

            self.bracket["matches"][match_id]["player1"] = player1
            self.bracket["matches"][match_id]["player2"] = player2


class TournamentMatch(Base):
    """
    Связующая модель между турниром и конкретным матчем.

    Хранит:
    - позицию в турнирной сетке
    - ссылку на реальный матч (Match)
    - участников
    - победителя
    - статус завершения
    """

    __tablename__ = "tournament_matches"

    id = Column(Integer, primary_key=True)

    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    match_id      = Column(Integer, ForeignKey("matches.id"), nullable=True)

    # Позиция в сетке турнира
    bracket_position = Column(String(32), nullable=False)   # пример: "1_1", "2_3", "3_1"
    round_number     = Column(Integer, nullable=False)
    match_number     = Column(Integer, nullable=False)

    # Участники матча
    player1_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    player2_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Результат
    winner_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_walkover  = Column(Boolean, default=False)
    walkover_reason = Column(String(128), nullable=True)

    # Связь с следующим матчем
    next_match_id = Column(Integer, ForeignKey("tournament_matches.id"), nullable=True)

    # Статус
    is_completed = Column(Boolean, default=False)

    # Временные метки
    scheduled_time = Column(DateTime(timezone=True), nullable=True)
    started_at     = Column(DateTime(timezone=True), nullable=True)
    completed_at   = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    # Отношения
    tournament = relationship("Tournament", back_populates="tournament_matches")
    match      = relationship("Match")
    player1    = relationship("User", foreign_keys=[player1_id])
    player2    = relationship("User", foreign_keys=[player2_id])
    winner     = relationship("User", foreign_keys=[winner_id])

    next_match = relationship(
        "TournamentMatch",
        remote_side=[id],
        foreign_keys=[next_match_id],
        back_populates="previous_matches"
    )
    previous_matches = relationship(
        "TournamentMatch",
        back_populates="next_match",
        foreign_keys=[next_match_id]
    )

    def __repr__(self) -> str:
        return f"<TournamentMatch id={self.id} tournament={self.tournament_id} bracket={self.bracket_position}>"

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для API / отображения."""
        return {
            "id": self.id,
            "tournament_id": self.tournament_id,
            "bracket_position": self.bracket_position,
            "round_number": self.round_number,
            "match_number": self.match_number,
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "winner_id": self.winner_id,
            "is_completed": self.is_completed,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "match_id": self.match_id
        }


# ─── Обратные связи в User ───────────────────────────────────────────────

try:
    from models.user import User

    User.tournaments_created = relationship(
        "Tournament",
        foreign_keys="Tournament.created_by",
        back_populates="creator"
    )
    User.tournament_matches_as_player1 = relationship(
        "TournamentMatch",
        foreign_keys="TournamentMatch.player1_id",
        back_populates="player1"
    )
    User.tournament_matches_as_player2 = relationship(
        "TournamentMatch",
        foreign_keys="TournamentMatch.player2_id",
        back_populates="player2"
    )
except ImportError:
    pass