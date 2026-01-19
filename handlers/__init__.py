# handlers/__init__.py
"""
Обработчики команд для Final 4 Bot.
"""

from .start import router as start_router
from .match import router as match_router

__all__ = [
    'start_router',
    'match_router'
]