# utils/helpers.py
"""
Критически важные вспомогательные функции для работы с Telegram.
"""

from typing import Union

from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

import logging
import asyncio

logger = logging.getLogger(__name__)


async def send_large_message(
    message: Union[Message, CallbackQuery],
    text: str,
    max_length: int = 4096,
    parse_mode: str = "HTML",
    reply_markup=None
) -> None:
    """
    Отправляет большое сообщение, автоматически разбивая его на части,
    если длина превышает Telegram-лимит (по умолчанию 4096 символов).

    Args:
        message: объект Message или CallbackQuery, от которого будем отвечать/редактировать
        text: текст сообщения (может быть очень длинным)
        max_length: максимальная длина одной части (по умолчанию 4096)
        parse_mode: режим парсинга ("HTML", "MarkdownV2", None)
        reply_markup: клавиатура (InlineKeyboardMarkup или ReplyKeyboardMarkup)
    """
    # Если это CallbackQuery — получаем message объект
    if isinstance(message, CallbackQuery):
        target = message.message
    else:
        target = message

    if len(text) <= max_length:
        # Если текст короткий — отправляем одним сообщением
        try:
            await target.answer(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except TelegramBadRequest as e:
            logger.warning(f"Ошибка отправки сообщения: {e}")
        return

    # Разбиваем длинный текст на части
    parts = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) <= max_length:
            current += line
        else:
            if current:
                parts.append(current)
            current = line
            # Если одна строка длиннее лимита — разбиваем жёстко
            while len(current) > max_length:
                parts.append(current[:max_length])
                current = current[max_length:]

    if current:
        parts.append(current)

    # Отправляем каждую часть
    for i, part in enumerate(parts, 1):
        try:
            await target.answer(
                text=f"{part}\n\n({i}/{len(parts)})",
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            # Небольшая задержка, чтобы не попасть в лимиты Telegram
            await asyncio.sleep(0.3)
        except TelegramBadRequest as e:
            logger.warning(f"Ошибка отправки части {i}/{len(parts)}: {e}")
        except Exception as e:
            logger.error(f"Критическая ошибка при отправке части {i}: {e}")
            break