# models/tournament.py
"""
Модель турниров для Final 4.
"""

from sqlalchemy import Column, Integer, String, JSON, DateTime, func, ForeignKey, Enum, Boolean, Float, Text
from sqlalchemy.orm import relationship
import enum
from models.base import Base


class TournamentStatus(enum.Enum):
    """Статусы турнира"""
    REGISTRATION = "registration"  # Регистрация участников
    CHECKIN = "checkin"  # Подтверждение участников
    IN_PROGRESS = "in_progress"  # Идет
    FINISHED = "finished"  # Завершен
    CANCELLED = "cancelled"  # Отменен


class TournamentType(enum.Enum):
    """Типы турниров"""
    SINGLE_ELIMINATION = "single"  # Олимпийская система (проиграл - вылетел)
    DOUBLE_ELIMINATION = "double"  # Двойная система выбывания
    SWISS = "swiss"  # Швейцарская система
    ROUND_ROBIN = "round_robin"  # Круговая система


class TournamentFormat(enum.Enum):
    """Форматы турнира"""
    PLAYOFF_4 = "playoff_4"  # 4 участника
    PLAYOFF_8 = "playoff_8"  # 8 участников
    PLAYOFF_16 = "playoff_16"  # 16 участников


class Tournament(Base):
    __tablename__ = 'tournaments'

    id = Column(Integer, primary_key=True)

    # Основная информация
    name = Column(String(128), nullable=False)
    description = Column(Text)
    tournament_type = Column(Enum(TournamentType), nullable=False, default=TournamentType.SINGLE_ELIMINATION)
    tournament_format = Column(Enum(TournamentFormat), nullable=False, default=TournamentFormat.PLAYOFF_8)
    status = Column(Enum(TournamentStatus), nullable=False, default=TournamentStatus.REGISTRATION)

    # Настройки
    max_players = Column(Integer, nullable=False)  # Максимальное количество участников
    entry_fee = Column(Integer, default=0)  # Взнос за участие
    prize_pool = Column(Integer, default=0)  # Призовой фонд
    min_rating = Column(Integer, default=0)  # Минимальный рейтинг для участия
    max_rating = Column(Integer, default=9999)  # Максимальный рейтинг для участия

    # Расписание
    registration_start = Column(DateTime(timezone=True), nullable=False)
    registration_end = Column(DateTime(timezone=True), nullable=False)
    tournament_start = Column(DateTime(timezone=True), nullable=False)
    estimated_end = Column(DateTime(timezone=True))

    # Призовые места (в процентах от призового фонда)
    prize_distribution = Column(JSON, default={
        '1': 50.0,  # 1 место - 50%
        '2': 30.0,  # 2 место - 30%
        '3': 20.0  # 3 место - 20%
    })

    # Сетка турнира
    bracket = Column(JSON, default=dict)  # Структура сетки
    current_round = Column(Integer, default=1)  # Текущий раунд

    # Участники
    participants = Column(JSON, default=list)  # Список участников [{'user_id': X, 'checked_in': bool}]
    waiting_list = Column(JSON, default=list)  # Лист ожидания

    # Результаты
    winner_id = Column(Integer, ForeignKey('users.id'))
    second_place_id = Column(Integer, ForeignKey('users.id'))
    third_place_id = Column(Integer, ForeignKey('users.id'))
    final_standings = Column(JSON, default=list)  # Финальные места

    # Создатель турнира
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Время
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))

    # Связи
    creator = relationship("User", foreign_keys=[created_by])
    winner = relationship("User", foreign_keys=[winner_id])
    second_place = relationship("User", foreign_keys=[second_place_id])
    third_place = relationship("User", foreign_keys=[third_place_id])
    tournament_matches = relationship("TournamentMatch", back_populates="tournament", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tournament(id={self.id}, name='{self.name}', status={self.status.value})>"

    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.tournament_type.value,
            'format': self.tournament_format.value,
            'status': self.status.value,
            'max_players': self.max_players,
            'current_players': len(self.participants),
            'entry_fee': self.entry_fee,
            'prize_pool': self.prize_pool,
            'current_round': self.current_round,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'registration_end': self.registration_end.isoformat() if self.registration_end else None,
            'tournament_start': self.tournament_start.isoformat() if self.tournament_start else None
        }

    def is_registration_open(self) -> bool:
        """Открыта ли регистрация"""
        from datetime import datetime
        now = datetime.now(self.registration_start.tzinfo)
        return (self.status == TournamentStatus.REGISTRATION and
                self.registration_start <= now <= self.registration_end)

    def can_join(self, user_id: int, user_rating: int) -> tuple[bool, str]:
        """Может ли пользователь присоединиться к турниру"""
        # Проверяем, открыта ли регистрация
        if not self.is_registration_open():
            return False, "Регистрация закрыта"

        # Проверяем рейтинг
        if user_rating < self.min_rating:
            return False, f"Рейтинг слишком низкий (минимум {self.min_rating})"
        if user_rating > self.max_rating:
            return False, f"Рейтинг слишком высокий (максимум {self.max_rating})"

        # Проверяем, есть ли уже место
        if len(self.participants) >= self.max_players:
            # Проверяем лист ожидания
            if any(p['user_id'] == user_id for p in self.waiting_list):
                return False, "Вы уже в листе ожидания"
            return False, "Турнир заполнен"

        # Проверяем, не зарегистрирован ли уже
        if any(p['user_id'] == user_id for p in self.participants):
            return False, "Вы уже зарегистрированы"

        return True, "Можно присоединиться"

    def add_participant(self, user_id: int):
        """Добавляет участника"""
        if len(self.participants) < self.max_players:
            self.participants.append({
                'user_id': user_id,
                'checked_in': False,
                'join_date': func.now(),
                'seed': len(self.participants) + 1  # Посев
            })
        else:
            # Добавляем в лист ожидания
            self.waiting_list.append({
                'user_id': user_id,
                'join_date': func.now(),
                'position': len(self.waiting_list) + 1
            })

    def remove_participant(self, user_id: int):
        """Удаляет участника"""
        self.participants = [p for p in self.participants if p['user_id'] != user_id]
        self.waiting_list = [p for p in self.waiting_list if p['user_id'] != user_id]

    def check_in_participant(self, user_id: int):
        """Подтверждает участие"""
        for participant in self.participants:
            if participant['user_id'] == user_id:
                participant['checked_in'] = True
                break

    def generate_bracket(self):
        """Генерирует сетку турнира"""
        if self.tournament_type != TournamentType.SINGLE_ELIMINATION:
            # Для других типов нужна своя логика
            return

        checked_in = [p for p in self.participants if p['checked_in']]
        num_players = len(checked_in)

        # Определяем ближайшую степень двойки
        import math
        bracket_size = 2 ** math.ceil(math.log2(num_players)) if num_players > 0 else 0

        # Создаем пустую сетку
        bracket = {
            'size': bracket_size,
            'rounds': [],
            'matches': {}
        }

        # Определяем количество раундов
        num_rounds = int(math.log2(bracket_size)) if bracket_size > 0 else 0

        for round_num in range(1, num_rounds + 1):
            round_matches = []
            matches_in_round = bracket_size // (2 ** round_num)

            for match_num in range(1, matches_in_round + 1):
                match_id = f"{round_num}_{match_num}"
                round_matches.append(match_id)

                # Определяем следующий матч
                next_round = round_num + 1
                next_match_num = (match_num + 1) // 2
                next_match_id = f"{next_round}_{next_match_num}" if next_round <= num_rounds else None

                bracket['matches'][match_id] = {
                    'round': round_num,
                    'number': match_num,
                    'player1': None,
                    'player2': None,
                    'winner': None,
                    'next_match': next_match_id,
                    'match_data': None  # ID реального матча
                }

            bracket['rounds'].append({
                'round': round_num,
                'name': self._get_round_name(round_num, num_rounds),
                'matches': round_matches
            })

        self.bracket = bracket

    def _get_round_name(self, round_num: int, total_rounds: int) -> str:
        """Возвращает название раунда"""
        round_names = {
            1: '1/8 финала',
            2: '1/4 финала',
            3: '1/2 финала',
            4: 'Финал'
        }

        # Для сеток разного размера
        if total_rounds == 2:  # 4 участника
            names = {1: '1/2 финала', 2: 'Финал'}
        elif total_rounds == 3:  # 8 участников
            names = {1: '1/4 финала', 2: '1/2 финала', 3: 'Финал'}
        elif total_rounds == 4:  # 16 участников
            names = {1: '1/8 финала', 2: '1/4 финала', 3: '1/2 финала', 4: 'Финал'}
        else:
            names = round_names

        return names.get(round_num, f"Раунд {round_num}")

    def seed_participants(self):
        """Распределяет участников по сетке"""
        if not self.bracket:
            return

        checked_in = [p for p in self.participants if p['checked_in']]
        checked_in.sort(key=lambda x: x.get('seed', 999))

        # Для олимпийской системы используем стандартное распределение
        bracket_size = self.bracket['size']
        matches_first_round = bracket_size // 2

        for i in range(matches_first_round):
            match_id = f"1_{i + 1}"

            if i * 2 < len(checked_in):
                player1 = checked_in[i * 2]['user_id']
            else:
                player1 = None  # Автоматический проход

            if i * 2 + 1 < len(checked_in):
                player2 = checked_in[i * 2 + 1]['user_id']
            else:
                player2 = None  # Автоматический проход

            self.bracket['matches'][match_id]['player1'] = player1
            self.bracket['matches'][match_id]['player2'] = player2


class TournamentMatch(Base):
    __tablename__ = 'tournament_matches'

    id = Column(Integer, primary_key=True)

    # Связи
    tournament_id = Column(Integer, ForeignKey('tournaments.id'), nullable=False)
    match_id = Column(Integer, ForeignKey('matches.id'))  # Ссылка на реальный матч

    # Позиция в сетке
    bracket_position = Column(String(32), nullable=False)  # "1_1", "1_2", "2_1", etc.
    round_number = Column(Integer, nullable=False)
    match_number = Column(Integer, nullable=False)

    # Участники
    player1_id = Column(Integer, ForeignKey('users.id'))
    player2_id = Column(Integer, ForeignKey('users.id'))

    # Результат
    winner_id = Column(Integer, ForeignKey('users.id'))
    is_walkover = Column(Boolean, default=False)  # Техническая победа
    walkover_reason = Column(String(128))

    # Следующий матч в сетке
    next_match_id = Column(Integer, ForeignKey('tournament_matches.id'))

    # Статус
    is_completed = Column(Boolean, default=False)

    # Время
    scheduled_time = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    tournament = relationship("Tournament", back_populates="tournament_matches")
    match = relationship("Match")
    player1 = relationship("User", foreign_keys=[player1_id])
    player2 = relationship("User", foreign_keys=[player2_id])
    winner = relationship("User", foreign_keys=[winner_id])
    next_match = relationship("TournamentMatch", remote_side=[id], foreign_keys=[next_match_id],
                              back_populates="previous_matches")
    previous_matches = relationship("TournamentMatch", back_populates="next_match",
                                    foreign_keys=[next_match_id])

    def __repr__(self):
        return f"<TournamentMatch(id={self.id}, tournament={self.tournament_id}, bracket={self.bracket_position})>"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'tournament_id': self.tournament_id,
            'bracket_position': self.bracket_position,
            'round_number': self.round_number,
            'match_number': self.match_number,
            'player1_id': self.player1_id,
            'player2_id': self.player2_id,
            'winner_id': self.winner_id,
            'is_completed': self.is_completed,
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'match_id': self.match_id
        }


# Обратная связь для User
try:
    from models.user import User

    User.tournaments_created = relationship("Tournament", foreign_keys="Tournament.created_by",
                                            back_populates="creator")
    User.tournament_matches_as_player1 = relationship("TournamentMatch", foreign_keys="TournamentMatch.player1_id",
                                                      back_populates="player1")
    User.tournament_matches_as_player2 = relationship("TournamentMatch", foreign_keys="TournamentMatch.player2_id",
                                                      back_populates="player2")
except:
    pass