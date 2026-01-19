# services/__init__.py
"""
Сервисы для Final 4 Bot.
"""

from .redis_client import get_redis, close_redis
from .scheduler import scheduler


__all__ = [
    'get_redis',
    'close_redis',
]