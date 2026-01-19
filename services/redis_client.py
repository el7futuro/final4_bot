# services/redis_service.py
import redis.asyncio as redis
from bot.config import load_config


class RedisService:
    def __init__(self):
        self.config = load_config()
        self.redis = None

    async def connect(self):
        """Подключиться к Redis"""
        if self.redis is None:
            self.redis = redis.Redis(
                host=self.config.redis.host,
                port=self.config.redis.port,
                db=self.config.redis.db,
                password=self.config.redis.password,
                decode_responses=True
            )
        return self.redis

    async def disconnect(self):
        """Отключиться от Redis"""
        if self.redis:
            await self.redis.close()
            self.redis = None

    async def get_client(self):
        """Получить Redis клиент"""
        return await self.connect()


# Синглтон экземпляр
redis_service = RedisService()


# Упрощенный интерфейс
async def get_redis():
    return await redis_service.get_client()


async def close_redis():
    await redis_service.disconnect()