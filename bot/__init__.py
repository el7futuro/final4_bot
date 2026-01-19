# bot/__init__.py
"""
Основной модуль бота Final 4.
"""

from .config import load_config, Config, BotConfig, DatabaseConfig, RedisConfig
from .database import init_db, get_session, close_db, engine, AsyncSessionLocal, Base
from .main import main
from .middleware import DatabaseMiddleware, ThrottlingMiddleware

__all__ = [
    # config.py
    'load_config',
    'Config',
    'BotConfig',
    'DatabaseConfig',
    'RedisConfig',

    # database.py
    'init_db',
    'get_session',
    'close_db',
    'engine',
    'AsyncSessionLocal',
    'Base',

    # main.py
    'main',

    # middleware.py
    'DatabaseMiddleware',
    'ThrottlingMiddleware'
]

__version__ = '1.0.0'
__author__ = 'Final 4 Team'