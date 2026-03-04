# core/game_engine.py
"""
Основной движок игры Final 4.

Этот модуль является фасадом (центральной точкой входа) для всей игровой логики.
Он объединяет компоненты из других модулей и предоставляет их для использования
в handlers, сервисах и других частях бота.

Не содержит собственной логики — только импорты и (при необходимости) обёртки.
"""

from typing import Dict, List, Tuple, Optional, Any
import random

from aiogram.types import CallbackQuery

# Импортируем модели и перечисления из engine_classes
from .engine_classes import (
    Final4GameEngine,
    BetType,
    BetStatus,
    CardType,
    Base,
    Bet
)

# Импортируем асинхронную сессию для работы с БД
from bot import AsyncSessionLocal

# Импортируем компоненты для бросков кубика и расчёта действий
from .dice import DiceManager, ActionCalculator, DiceRoll

# Импортируем калькулятор матча (расчёт счёта по действиям)
from .match_calculator import MatchCalculator, MatchResult

# Импортируем логику дополнительного времени и пенальти
from .extra_time import ExtraTimeManager, PenaltyShootout

# Импортируем ИИ бота (для матчей против бота)
from .bot_ai import Final4BotAI, BotDifficulty


# Если в будущем здесь появится обёртка или общая логика — её можно добавить
# Пока модуль остаётся фасадом для удобного импорта в других частях бота

# Пример использования (в handlers или сервисах):
#
# from core.game_engine import Final4GameEngine, DiceManager, MatchCalculator
#
# engine = Final4GameEngine()
# dice_manager = DiceManager()
# match_calculator = MatchCalculator()





