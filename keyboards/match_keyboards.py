# keyboards/match_keyboards.py
"""
Клавиатуры для игрового процесса Final 4.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Optional, Tuple
from models.match import Match, MatchStatus
from models.team import Team
from utils.emoji import EMOJI


class MatchKeyboards:
    """Клавиатуры для матчей Final 4"""

    @staticmethod
    def get_main_menu() -> InlineKeyboardMarkup:
        """Главное меню матчей"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['vs']} Против соперника",
                        callback_data="match_type_vs_random"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['bot']} Против бота",
                        callback_data="match_type_vs_bot"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['tournament']} Турнир",
                        callback_data="match_type_tournament"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['list']} Мои матчи",
                        callback_data="show_matches"
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

    @staticmethod
    def get_bot_difficulty() -> InlineKeyboardMarkup:
        """Выбор сложности бота"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['easy']} Легкий",
                        callback_data="bot_difficulty_easy"
                    ),
                    InlineKeyboardButton(
                        text=f"{EMOJI['medium']} Средний",
                        callback_data="bot_difficulty_medium"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['hard']} Сложный",
                        callback_data="bot_difficulty_hard"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['back']} Назад",
                        callback_data="play_game"
                    )
                ]
            ]
        )

    @staticmethod
    def get_search_cancel(match_id: int) -> InlineKeyboardMarkup:
        """Отмена поиска соперника"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['cancel']} Отменить поиск",
                        callback_data=f"cancel_search_{match_id}"
                    )
                ]
            ]
        )

    @staticmethod
    def get_match_actions(match_id: int, can_start: bool = False) -> InlineKeyboardMarkup:
        """Действия с матчем"""
        buttons = []

        if can_start:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['play']} Начать матч",
                    callback_data=f"start_match_{match_id}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['cancel']} Отменить матч",
                callback_data=f"cancel_match_{match_id}"
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['back']} Назад",
                callback_data="show_matches"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_match_control(match_id: int, is_player_turn: bool) -> InlineKeyboardMarkup:
        """Управление матчем"""
        buttons = []

        if is_player_turn:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['dice']} Сделать ход",
                    callback_data=f"continue_match_{match_id}"
                )
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['wait']} Ожидание...",
                    callback_data="waiting"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['surrender']} Сдаться",
                callback_data=f"surrender_match_{match_id}"
            ),
            InlineKeyboardButton(
                text=f"{EMOJI['info']} Статистика",
                callback_data=f"match_stats_{match_id}"
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['back']} К списку матчей",
                callback_data="show_matches"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_player_selection(players: List[Dict], match_id: int) -> InlineKeyboardMarkup:
        """Выбор игрока для ставки"""
        buttons = []

        for player in players[:8]:  # Ограничиваем показ
            position = player.get('position', '')
            emoji = MatchKeyboards._get_position_emoji(position)

            buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} {player.get('name', 'Игрок')} (#{player.get('number', '?')})",
                    callback_data=f"select_player_{match_id}_{player.get('id', 0)}"
                )
            ])

        # Если игроков больше 8, добавляем пагинацию
        if len(players) > 8:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['left']} Назад",
                    callback_data=f"players_page_{match_id}_prev"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['right']} Вперед",
                    callback_data=f"players_page_{match_id}_next"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['cancel']} Отмена хода",
                callback_data=f"cancel_turn_{match_id}"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_bet_type_selection(match_id: int, player_id: int, available_bets: List[str]) -> InlineKeyboardMarkup:
        """Выбор типа ставки"""
        buttons = []

        bet_types = {
            'odd_even': (f"{EMOJI['defense']} Чет/Нечет", "отбития"),
            'less_more': (f"{EMOJI['pass']} Меньше/Больше", "передачи"),
            'exact': (f"{EMOJI['goal']} Точное число", "голы")
        }

        for bet_type in available_bets:
            if bet_type in bet_types:
                emoji_text, action = bet_types[bet_type]
                buttons.append([
                    InlineKeyboardButton(
                        text=emoji_text,
                        callback_data=f"select_bet_{match_id}_{player_id}_{bet_type}"
                    )
                ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['back']} Назад к игрокам",
                callback_data=f"back_to_players_{match_id}"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_odd_even_selection(match_id: int, player_id: int, bet_type: str) -> InlineKeyboardMarkup:
        """Выбор Чет/Нечет"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Чет (2, 4, 6)",
                        callback_data=f"bet_value_{match_id}_{player_id}_{bet_type}_чет"
                    ),
                    InlineKeyboardButton(
                        text="Нечет (1, 3, 5)",
                        callback_data=f"bet_value_{match_id}_{player_id}_{bet_type}_нечет"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['back']} Назад",
                        callback_data=f"back_to_bet_type_{match_id}_{player_id}"
                    )
                ]
            ]
        )

    @staticmethod
    def get_less_more_selection(match_id: int, player_id: int, bet_type: str) -> InlineKeyboardMarkup:
        """Выбор Меньше/Больше"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Меньше (1, 2, 3)",
                        callback_data=f"bet_value_{match_id}_{player_id}_{bet_type}_меньше"
                    ),
                    InlineKeyboardButton(
                        text="Больше (4, 5, 6)",
                        callback_data=f"bet_value_{match_id}_{player_id}_{bet_type}_больше"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['back']} Назад",
                        callback_data=f"back_to_bet_type_{match_id}_{player_id}"
                    )
                ]
            ]
        )

    @staticmethod
    def get_exact_number_selection(match_id: int, player_id: int, bet_type: str) -> InlineKeyboardMarkup:
        """Выбор точного числа"""
        buttons = []
        row = []

        for i in range(1, 7):
            row.append(InlineKeyboardButton(
                text=str(i),
                callback_data=f"bet_value_{match_id}_{player_id}_{bet_type}_{i}"
            ))

            if i % 3 == 0:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['back']} Назад",
                callback_data=f"back_to_bet_type_{match_id}_{player_id}"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_card_usage(card_instance_id: int, match_id: int) -> InlineKeyboardMarkup:
        """Использование карточки"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['card']} Использовать карточку",
                        callback_data=f"use_card_{match_id}_{card_instance_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['skip']} Пропустить",
                        callback_data=f"skip_card_{match_id}"
                    )
                ]
            ]
        )

    @staticmethod
    def get_card_target_selection(match_id: int, card_instance_id: int,
                                  available_targets: List[Dict]) -> InlineKeyboardMarkup:
        """Выбор цели для карточки"""
        buttons = []

        for target in available_targets[:6]:
            position = target.get('position', '')
            emoji = MatchKeyboards._get_position_emoji(position)

            buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} {target.get('name', 'Игрок')}",
                    callback_data=f"card_target_{match_id}_{card_instance_id}_{target.get('id', 0)}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['cancel']} Отмена",
                callback_data=f"cancel_card_{match_id}_{card_instance_id}"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_turn_result_actions(match_id: int, has_card: bool = False) -> InlineKeyboardMarkup:
        """Действия после хода"""
        buttons = []

        if has_card:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['card']} Посмотреть карточку",
                    callback_data=f"view_card_{match_id}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['continue']} Продолжить",
                callback_data=f"continue_after_turn_{match_id}"
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['stats']} Статистика матча",
                callback_data=f"match_stats_{match_id}"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_match_result_actions(match_id: int, is_rematch_possible: bool = True) -> InlineKeyboardMarkup:
        """Действия после завершения матча"""
        buttons = []

        if is_rematch_possible:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['rematch']} Реванш",
                    callback_data=f"rematch_{match_id}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['stats']} Детальная статистика",
                callback_data=f"detailed_stats_{match_id}"
            ),
            InlineKeyboardButton(
                text=f"{EMOJI['share']} Поделиться",
                callback_data=f"share_match_{match_id}"
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['play']} Новая игра",
                callback_data="play_game"
            ),
            InlineKeyboardButton(
                text=f"{EMOJI['menu']} Главное меню",
                callback_data="main_menu"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_surrender_confirmation(match_id: int) -> InlineKeyboardMarkup:
        """Подтверждение сдачи"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['yes']} Да, сдаюсь",
                        callback_data=f"confirm_surrender_{match_id}"
                    ),
                    InlineKeyboardButton(
                        text=f"{EMOJI['no']} Нет, продолжу",
                        callback_data=f"cancel_surrender_{match_id}"
                    )
                ]
            ]
        )

    @staticmethod
    def get_match_list(matches: List[Match], page: int = 0, has_more: bool = False) -> InlineKeyboardMarkup:
        """Список матчей с пагинацией"""
        buttons = []

        for match in matches:
            status_emoji = MatchKeyboards._get_match_status_emoji(match.status)

            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_emoji} Матч #{match.id}",
                    callback_data=f"match_detail_{match.id}"
                )
            ])

        # Пагинация
        pagination_buttons = []

        if page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text=f"{EMOJI['left']} Назад",
                    callback_data=f"matches_page_{page - 1}"
                )
            )

        if has_more:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text=f"{EMOJI['right']} Вперед",
                    callback_data=f"matches_page_{page + 1}"
                )
            )

        if pagination_buttons:
            buttons.append(pagination_buttons)

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['play']} Новый матч",
                callback_data="play_game"
            ),
            InlineKeyboardButton(
                text=f"{EMOJI['menu']} Главное меню",
                callback_data="main_menu"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_tournament_selection() -> InlineKeyboardMarkup:
        """Выбор типа турнира"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['tournament']} 4 участника",
                        callback_data="tournament_4"
                    ),
                    InlineKeyboardButton(
                        text=f"{EMOJI['tournament']} 8 участников",
                        callback_data="tournament_8"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['tournament']} 16 участников",
                        callback_data="tournament_16"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['list']} Активные турниры",
                        callback_data="active_tournaments"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['back']} Назад",
                        callback_data="play_game"
                    )
                ]
            ]
        )

    @staticmethod
    def get_tournament_registration(tournament_id: int, is_registered: bool = False) -> InlineKeyboardMarkup:
        """Регистрация на турнир"""
        buttons = []

        if not is_registered:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['register']} Зарегистрироваться",
                    callback_data=f"register_tournament_{tournament_id}"
                )
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['cancel']} Отменить регистрацию",
                    callback_data=f"unregister_tournament_{tournament_id}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['info']} Информация",
                callback_data=f"tournament_info_{tournament_id}"
            ),
            InlineKeyboardButton(
                text=f"{EMOJI['bracket']} Сетка",
                callback_data=f"tournament_bracket_{tournament_id}"
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['back']} Назад",
                callback_data="tournament_list"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def get_bet_rules_help() -> InlineKeyboardMarkup:
        """Помощь по правилам ставок"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['rules']} Подробные правила",
                        callback_data="detailed_rules"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['play']} Начать игру",
                        callback_data="play_game"
                    )
                ]
            ]
        )

    # Вспомогательные методы

    @staticmethod
    def _get_position_emoji(position: str) -> str:
        """Возвращает emoji для позиции"""
        emojis = {
            'GK': EMOJI.get('gk', '🥅'),
            'DF': EMOJI.get('df', '🛡️'),
            'MF': EMOJI.get('mf', '⚡'),
            'FW': EMOJI.get('fw', '⚽')
        }
        return emojis.get(position, '👤')

    @staticmethod
    def _get_match_status_emoji(status: MatchStatus) -> str:
        """Возвращает emoji для статуса матча"""
        emojis = {
            MatchStatus.CREATED: '📝',
            MatchStatus.WAITING: '🔍',
            MatchStatus.IN_PROGRESS: '⚽',
            MatchStatus.FINISHED: '🏁',
            MatchStatus.CANCELLED: '❌',
            MatchStatus.EXTRA_TIME: '⏰',
            MatchStatus.PENALTY: '🎯'
        }
        return emojis.get(status, '❓')

    @staticmethod
    def create_dynamic_keyboard(buttons_data: List[Tuple[str, str]],
                                rows: int = 2,
                                back_button: bool = True,
                                back_callback: str = "main_menu") -> InlineKeyboardMarkup:
        """Создает динамическую клавиатуру"""
        keyboard_buttons = []
        row = []

        for i, (text, callback_data) in enumerate(buttons_data):
            row.append(InlineKeyboardButton(text=text, callback_data=callback_data))

            if (i + 1) % rows == 0 or i == len(buttons_data) - 1:
                keyboard_buttons.append(row)
                row = []

        if back_button:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['back']} Назад",
                    callback_data=back_callback
                )
            ])

        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


# Быстрые функции для часто используемых клавиатур
def quick_match_actions(match_id: int) -> InlineKeyboardMarkup:
    """Быстрое создание клавиатуры действий матча"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['play']} Продолжить",
                    callback_data=f"continue_match_{match_id}"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['info']} Статистика",
                    callback_data=f"match_stats_{match_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['surrender']} Сдаться",
                    callback_data=f"surrender_match_{match_id}"
                )
            ]
        ]
    )


def quick_back_button(back_to: str = "main_menu") -> InlineKeyboardMarkup:
    """Простая кнопка 'Назад'"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['back']} Назад",
                    callback_data=back_to
                )
            ]
        ]
    )


def quick_yes_no(match_id: int, action: str) -> InlineKeyboardMarkup:
    """Клавиатура Да/Нет для подтверждения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['yes']} Да",
                    callback_data=f"confirm_{action}_{match_id}"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['no']} Нет",
                    callback_data=f"cancel_{action}_{match_id}"
                )
            ]
        ]
    )