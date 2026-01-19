# utils/helpers.py (упрощенная версия)
"""
Критически важные вспомогательные функции.
"""

from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
import logging
import asyncio

logger = logging.getLogger(__name__)


async def send_large_message(
        message: Message | CallbackQuery,
        text: str,
        max_length: int = 4096,
        parse_mode: str = "HTML",
        reply_markup=None
) -> None:
    """Отправляет большое сообщение, разбивая его на части."""
    # ... реализация как выше

    return None

# Остальные функции можно убрать или реализовать по мере необходимости