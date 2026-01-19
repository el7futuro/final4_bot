# keyboards/main_menu.py
"""
Клавиатуры главного меню Final 4.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils.emoji import EMOJI


def get_main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['play']} Играть",
                    callback_data="play_game"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['team']} Моя команда",
                    callback_data="my_team"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['cards']} Мои карты",
                    callback_data="my_cards"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['stats']} Статистика",
                    callback_data="my_stats"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['leaderboard']} Рейтинг",
                    callback_data="leaderboard"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['rules']} Правила",
                    callback_data="rules"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['help']} Помощь",
                    callback_data="help"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['settings']} Настройки",
                    callback_data="settings"
                )
            ]
        ]
    )


def get_game_mode_kb() -> InlineKeyboardMarkup:
    """Выбор режима игры"""
    from keyboards.match_keyboards import MatchKeyboards
    return MatchKeyboards.get_main_menu()


def get_rules_kb() -> InlineKeyboardMarkup:
    """Клавиатура для правил"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['play']} Начать игру",
                    callback_data="play_game"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['back']} Назад в меню",
                    callback_data="main_menu"
                )
            ]
        ]
    )


def get_team_management_kb() -> InlineKeyboardMarkup:
    """Управление командой"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['edit']} Изменить состав",
                    callback_data="edit_team"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['formation']} Сменить формацию",
                    callback_data="change_formation"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['buy']} Купить игрока",
                    callback_data="buy_player"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['sell']} Продать игрока",
                    callback_data="sell_player"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['back']} Назад",
                    callback_data="main_menu"
                )
            ]
        ]
    )


def get_settings_kb() -> InlineKeyboardMarkup:
    """Настройки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['language']} Язык",
                    callback_data="change_language"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['notifications']} Уведомления",
                    callback_data="notifications"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['theme']} Тема",
                    callback_data="change_theme"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['sound']} Звуки",
                    callback_data="toggle_sounds"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['back']} Назад",
                    callback_data="main_menu"
                )
            ]
        ]
    )