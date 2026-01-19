from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from bot.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
import time


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для инъекции сессии БД"""

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        async for session in get_session():
            data['session'] = session
            return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware для защиты от флуда"""

    def __init__(self, limit: float = 0.5):
        self.limit = limit
        self.last_time = {}
        super().__init__()

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:

        user_id = event.from_user.id
        current_time = time.time()

        if user_id in self.last_time:
            time_passed = current_time - self.last_time[user_id]
            if time_passed < self.limit:
                # Слишком частые запросы
                if isinstance(event, Message):
                    await event.answer("⚠️ Слишком много запросов! Подождите немного.")
                return

        self.last_time[user_id] = current_time
        return await handler(event, data)