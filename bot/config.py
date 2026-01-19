import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BotConfig:
    token: str
    admin_ids: list[int]


@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class RedisConfig:
    host: str
    port: int
    db: int
    password: Optional[str] = None


@dataclass
class Config:
    bot: BotConfig
    db: DatabaseConfig
    redis: RedisConfig


def load_config() -> Config:
    """Загрузка конфигурации из переменных окружения"""

    admin_ids = os.getenv('ADMIN_IDS', '').split(',')
    admin_ids = [int(id.strip()) for id in admin_ids if id.strip().isdigit()]

    return Config(
        bot=BotConfig(
            token=os.getenv('BOT_TOKEN', ''),
            admin_ids=admin_ids
        ),
        db=DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'final4_bot')
        ),
        redis=RedisConfig(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            password=os.getenv('REDIS_PASSWORD')
        )
    )