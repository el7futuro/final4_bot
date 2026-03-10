# handlers/match.py
"""
Обработчики игрового процесса Final 4 с интеграцией BetTracker и BetValidator.
"""

import asyncio
import json
import logging
import random
from typing import Dict, List

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.handlers import message
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from bot.config import BOT_TELEGRAM_ID
from bot.database import AsyncSessionLocal
from core import Final4BotAI
from core.game_utils import calculate_actions
from models.bet import Bet, BetStatus, BetType as ModelBetType
from models.bet_tracker import BetTracker, BetType
from models.match import Match, MatchStatus, MatchType
from models.user import User
from services.bet_validator import bet_validator
from services.game_manager import game_manager
from utils.emoji import EMOJI

logger = logging.getLogger(__name__)

router = Router(name="match")


class MatchStates:
    """
    Состояния Finite State Machine для управления игровым процессом матча.

    Эти константы используются в FSMContext для контроля этапов:
    - ожидание ставки
    - выбор карточки
    - активный матч
    - выбор игроков для дополнительного времени
    - ожидание второй ставки
    """
    WAITING_FOR_BET = "waiting_for_bet"
    WAITING_FOR_CARD = "waiting_for_card"
    IN_MATCH = "in_match"

    WAITING_FOR_SECOND_BET = "waiting_for_second_bet"


@router.callback_query(F.data == "match_type_vs_bot")
async def match_type_vs_bot(callback: CallbackQuery, state: FSMContext):
    """
    Создание матча против бота.

    Получает пользователя, создаёт (при необходимости) пользователя-бота,
    генерирует стандартные команды по 16 игроков для обоих,
    создаёт запись Match с типом VS_BOT и показывает клавиатуру начала игры.
    """
    print(f"DEBUG: callback.from_user.id = {callback.from_user.id}")
    user_id = callback.from_user.id
    first_name = callback.from_user.first_name or "Игрок"

    bot_telegram_id = callback.bot.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала зарегистрируйтесь через /start")
            return

        bot_result = await session.execute(
            select(User).where(User.telegram_id == bot_telegram_id)
        )
        bot_user = bot_result.scalar_one_or_none()

        if not bot_user:
            bot_user = User(
                telegram_id=bot_telegram_id,
                username='final4_bot',
                first_name='🤖 Бот'
            )
            session.add(bot_user)
            await session.flush()

        player_players = []

        player_players.append({
            'id': 1,
            'position': 'GK',
            'name': f'{first_name} - Вратарь',
            'number': 1
        })

        for i in range(5):
            player_players.append({
                'id': 2 + i,
                'position': 'DF',
                'name': f'{first_name} - Защитник {i + 1}',
                'number': 2 + i
            })

        for i in range(6):
            player_players.append({
                'id': 7 + i,
                'position': 'MF',
                'name': f'{first_name} - Полузащитник {i + 1}',
                'number': 7 + i
            })

        for i in range(4):
            player_players.append({
                'id': 13 + i,
                'position': 'FW',
                'name': f'{first_name} - Нападающий {i + 1}',
                'number': 13 + i
            })

        bot_players = []

        bot_players.append({
            'id': 1,
            'position': 'GK',
            'name': '🤖 Бот-Вратарь',
            'number': 1
        })

        for i in range(5):
            bot_players.append({
                'id': 2 + i,
                'position': 'DF',
                'name': f'🤖 Бот-Защитник {i + 1}',
                'number': 2 + i
            })

        for i in range(6):
            bot_players.append({
                'id': 7 + i,
                'position': 'MF',
                'name': f'🤖 Бот-Полузащитник {i + 1}',
                'number': 7 + i
            })

        for i in range(4):
            bot_players.append({
                'id': 13 + i,
                'position': 'FW',
                'name': f'🤖 Бот-Нападающий {i + 1}',
                'number': 13 + i
            })

        match = Match(
            player1_id=user.id,
            player2_id=bot_user.id,
            player1_team_data={'players': player_players},
            player2_team_data={'players': bot_players},
            match_type=MatchType.VS_BOT,
            status=MatchStatus.CREATED,
            current_turn=1,
            bet_tracker=BetTracker()
        )

        session.add(match)
        await session.commit()

        text = f"""🎮 <b>Матч против бота создан!</b>

ID матча: <code>{match.id}</code>
Соперник: 🤖 Бот
Статус: Ожидание первого хода
Ход: 1/11

<b>Первый ход:</b> выберите вратаря и сделайте ставку на чет/нечет."""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎯 Начать первый ход",
                        callback_data=f"start_match_{match.id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📊 Посмотреть матч",
                        callback_data=f"view_match_{match.id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="play_game"
                    )
                ]
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await callback.answer()

        await state.update_data(match_id=match.id)


@router.message(Command("play"))
async def command_play(message: Message):
    """
    Команда /play — показывает меню выбора типа матча.

    Проверяет пользователя через GameManager и выводит кнопки:
    против случайного соперника, против бота, турнир.
    """
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        can_start, reason = await game_manager.can_start_match(session, user_id)
        if not can_start:
            await message.answer(f"❌ {reason}")
            return

        text = f"""{EMOJI['play']} <b>Найти матч</b>

{EMOJI['rating']} <b>Ваш рейтинг:</b> {user.rating}

{EMOJI['vs']} <b>Выберите тип матча:</b>

1. {EMOJI['vs']} <b>Против случайного соперника</b>
   • Рейтинговый матч
   • Подбор по рейтингу
   • Награда: +{user.rating // 10} очков рейтинга

2. {EMOJI['bot']} <b>Против бота</b>
   • Тренировка
   • Без риска для рейтинга
   • 3 уровня сложности

3. {EMOJI['tournament']} <b>Турнир</b>
   • Плей-офф на 4/8/16 игроков
   • Призовой фонд
   • Только для опытных"""

        keyboard = InlineKeyboardMarkup(
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
                        text=f"{EMOJI['back']} Назад",
                        callback_data="main_menu"
                    )
                ]
            ]
        )

        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data == "match_type_vs_random")
async def match_type_vs_random(callback: CallbackQuery, state: FSMContext):
    """
    Создание матча против случайного соперника.

    Создаёт запись Match со статусом WAITING и запускает фоновый поиск соперника.
    """
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        match = Match(
            player1_id=user_id,
            match_type=MatchType.VS_RANDOM,
            status=MatchStatus.WAITING.value
        )

        session.add(match)
        await session.commit()

        text = f"""{EMOJI['search']} <b>Поиск соперника...</b>

Матч #{match.id}
Тип: Против случайного соперника

Ищем соперника с похожим рейтингом...
Это может занять 1-5 минут.

{EMOJI['info']} Вы можете отменить поиск в любое время."""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['cancel']} Отменить поиск",
                        callback_data=f"cancel_search_{match.id}"
                    )
                ]
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await callback.answer()

        asyncio.create_task(search_opponent(match.id, callback.bot))


@router.callback_query(F.data.startswith("start_match_"))
async def start_match(callback: CallbackQuery, state: FSMContext):
    """
    Начало матча (переход из CREATED в IN_PROGRESS).

    Устанавливает статус, текущего игрока, сохраняет данные в FSM
    и вызывает show_turn для первого хода.
    """
    match_id = int(callback.data.split("_")[2])
    telegram_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        match = await session.get(Match, match_id)

        if not match:
            await callback.answer("Матч не найден")
            return

        if not match.is_player_in_match(user.id):
            await callback.answer("Вы не участник этого матча")
            return

        if match.status != MatchStatus.CREATED:
            await callback.answer("Матч уже начат")
            return

        match.status = MatchStatus.IN_PROGRESS
        match.started_at = func.now()
        match.current_player_turn = "player1"

        await session.commit()

        await state.update_data(
            match_id=match_id,
            current_turn=1,
            bets_made=0,
            selected_player_id=None
        )
        await state.set_state(MatchStates.IN_MATCH)

        await show_turn(callback, state, match_id, 1)

    await callback.answer()


async def show_turn(callback: CallbackQuery, state: FSMContext, match_id: int, turn: int):
    """
    Отображение интерфейса текущего хода игрока.

    Получает доступных игроков через GameManager, формирует текст и клавиатуру.
    Если нет доступных игроков — вызывает обработку дополнительного времени.
    """
    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        telegram_id = callback.from_user.id

        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await message.answer("Пользователь не найден")
            return

        user_db_id = user.id

        if not match or not match.is_player_in_match(user_db_id):
            await message.answer("Ошибка доступа к матчу")
            return

        current_user_id = match.get_current_user_id()
        print(f"DEBUG: current_user_id = {current_user_id}, user_db_id = {user_db_id}")
        if current_user_id != user_db_id:
            text = f"""{EMOJI['wait']} <b>Ожидание хода соперника...</b>

Матч #{match.id}
Ход {turn}/11
Ходит: {get_player_name(match, current_user_id)}

{EMOJI['info']} Ждите, когда соперник сделает ход."""
            await message.answer(text, parse_mode='HTML')
            return

        player_number = match.get_player_number(user_db_id)
        team_data = match.get_player_team_data(user_db_id)

        if not team_data:
            await message.answer("Ошибка: данные команды не найдены")
            return

        available_players = await game_manager.get_available_players(
            session, match_id, user_db_id
        )

        if not available_players:
            await handle_no_available_players(message, match, state)
            return

        text = f"""{EMOJI['dice']} <b>Ваш ход!</b>

Матч #{match.id}
Ход {turn}/11



{EMOJI['rules']} <b>Правила хода:</b>
• Выберите футболиста из доступных
• Сделайте первую ставку
• Сделайте вторую ставку (если возможно)
• Бросьте кубик
• Получите полезные действия
• Возьмите карточку «Свисток» (если ставка сыграла)

{EMOJI['info']} <b>Статус квот:</b>
Голы: DF ({match.bet_tracker.get_goal_quota_left('DF')}/1), 
      MF ({match.bet_tracker.get_goal_quota_left('MF')}/3), 
      FW ({match.bet_tracker.get_goal_quota_left('FW')}/4)
Чет/нечет: {match.bet_tracker.get_remaining_EVEN_ODD()}/6 игроков"""

        keyboard_buttons = []
        for player in available_players[:8]:
            emoji = get_position_emoji(player.get('position', 'GK'))
            player_name = player.get('name', f"Игрок {player.get('id')}")
            player_number = player.get('number', '?')

            available_types = match.bet_tracker.get_available_bet_types(
                player['id'], player.get('position', 'GK'), False
            )
            bets_info = f" ({len(available_types)} ставок)"

            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} {player_name} (#{player_number}){bets_info}",
                    callback_data=f"select_player_{match_id}_{player['id']}"
                )
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')


async def handle_no_available_players(message: Message, match: Match, state: FSMContext):
    """
    Обработка ситуации, когда нет доступных игроков для хода.
    """
    # Проверяем, что основное время завершено (11+ ходов)
    if not match.is_extra_time and match.current_turn >= 11:

        # Проверяем счет через game_manager
        from services.game_manager import game_manager

        async with AsyncSessionLocal() as session:
            _, _, result_data = await game_manager.check_match_completion(session, match)

            if result_data and result_data["action"] == "extra_time":
                # Ничья - автоматически начинаем ДВ
                await start_extra_time_auto(message, match, state)
                return
            elif result_data and result_data["action"] == "finish":
                # Уже есть победитель - завершаем
                await game_manager.process_match_completion(session, match, result_data)

                # Отправляем результат
                result_text = game_manager.format_match_result(result_data)
                await message.answer(result_text, parse_mode='HTML')

                await state.clear()
                return

    # Если не подходит под условия - ошибка
    await message.answer("Ошибка: нет доступных игроков для хода. Обратитесь к администратору.")
@router.callback_query(F.data.startswith("select_player_"))
async def select_player(callback: CallbackQuery, state: FSMContext):
    """
    Выбор игрока для ставки.

    Проверяет валидность через GameManager, сохраняет выбранного игрока в состоянии
    и вызывает выбор типа ставки.
    """
    parts = callback.data.split("_")
    match_id = int(parts[2])
    player_id = int(parts[3])
    telegram_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        user_db_id = user.id

        match = await session.get(Match, match_id)

        if not match or match.get_current_user_id() != user_db_id:
            await callback.answer("Сейчас не ваш ход")
            return

        is_valid, message_text = await game_manager.validate_player_selection(
            session, match_id, user_db_id, player_id
        )

        if not is_valid:
            await callback.answer(f"❌ {message_text}")
            return

        team_data = match.get_player_team_data(user_db_id)

        if not team_data:
            await callback.answer("Ошибка: данные команды не найдены")
            return

        team_players = team_data.get('players', [])
        player = next((p for p in team_players if p.get('id') == player_id), None)

        if not player:
            await callback.answer("Игрок не найден")
            return

        await state.update_data(
            selected_player_id=player_id,
            selected_player_position=player.get('position', 'GK'),
            selected_player_name=player.get('name', f"Игрок {player_id}"),
            current_bet_number=1
        )

        await show_bet_type_selection(callback.message, match, player)

    await callback.answer()




async def show_bet_type_selection(message: Message, match: Match, player: Dict):
    """
    Показ выбора типа первой ставки для выбранного игрока.

    Использует GameManager для получения доступных типов ставок.
    """
    player_id = player['id']
    position = player.get('position', 'GK')
    player_name = player.get('name', f"Игрок {player_id}")

    available_bets = await game_manager.get_available_bet_types(
        match, player_id, position, False
    )

    if not available_bets:
        await message.answer("❌ Нет доступных типов ставок для этого игрока")
        return

    text = f"""{EMOJI['bet']} <b>Выбор ставки (1/2)</b>

Игрок: {player_name} (#{player.get('number', '?')})
Позиция: {position}

{EMOJI['rules']} <b>Доступные ставки:</b>"""

    keyboard_buttons = []
    for bet_type_str, bet_name, values in available_bets:
        if bet_type_str == "EVEN_ODD":
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"🔢 {bet_name} (чет/нечет)",
                    callback_data=f"bet_type_{match.id}_{player_id}_{bet_type_str}"
                )
            ])
        elif bet_type_str == "big_small":
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"📊 {bet_name} (больше/меньше)",
                    callback_data=f"bet_type_{match.id}_{player_id}_{bet_type_str}"
                )
            ])
        elif bet_type_str == "goal":
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"⚽ {bet_name} (точное число)",
                    callback_data=f"bet_type_{match.id}_{player_id}_{bet_type_str}"
                )
            ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data.startswith("bet_type_"))
async def select_bet_type(callback: CallbackQuery, state: FSMContext):
    """
    Выбор типа ставки (первая или вторая).

    Валидирует через GameManager и переходит к выбору значения ставки.
    """
    parts = callback.data.split("_")

    if len(parts) >= 5:
        match_id = int(parts[2])
        player_id = int(parts[3])
        bet_type_str = "_".join(parts[4:])
    else:
        await callback.answer("❌ Ошибка в данных")
        return

    telegram_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        user_db_id = user.id

        match = await session.get(Match, match_id)
        if not match:
            await callback.answer("Матч не найден")
            return

        state_data = await state.get_data()
        current_bet_number = state_data.get('current_bet_number', 1)

        is_second_bet = (current_bet_number == 2)

        team_data = match.get_player_team_data(user_db_id)
        if not team_data:
            await callback.answer("Ошибка: данные команды не найдены")
            return

        team_players = team_data.get('players', [])
        player = next((p for p in team_players if p.get('id') == player_id), None)
        if not player:
            await callback.answer("Игрок не найден")
            return

        position = player.get('position', 'GK')

        is_valid, message_text = await game_manager.validate_bet(
            match, player_id, position, bet_type_str, "", is_second_bet
        )

        if not is_valid:
            await callback.answer(f"❌ {message_text}")
            return

        await state.update_data(
            selected_bet_type=bet_type_str,
            selected_player_id=player_id
        )

        await show_bet_value_selection(
            callback.message, match_id, bet_type_str, player, is_second_bet
        )

    await callback.answer()


async def show_bet_value_selection(message: Message, match_id: int, bet_type_str: str,
                                   player: Dict, is_second_bet: bool):
    """
    Показ выбора конкретного значения ставки (чет/нечет, больше/меньше, точное число).
    """
    player_name = player.get('name', f"Игрок {player['id']}")

    if bet_type_str == BetType.EVEN_ODD.value:
        text = f"""{EMOJI['bet']} <b>Выберите значение:</b>

Игрок: {player_name}
Ставка: Чет/Нечет

• Чет (2, 4, 6) → шанс 50%
• Нечет (1, 3, 5) → шанс 50%"""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Чет",
                        callback_data=f"bet_value_{match_id}_чет"
                    ),
                    InlineKeyboardButton(
                        text="Нечет",
                        callback_data=f"bet_value_{match_id}_нечет"
                    )
                ]
            ]
        )

    elif bet_type_str == BetType.BIG_SMALL.value:
        text = f"""{EMOJI['bet']} <b>Выберите значение:</b>

Игрок: {player_name}
Ставка: Больше/Меньше

• Меньше (1, 2, 3) → шанс 50%
• Больше (4, 5, 6) → шанс 50%"""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Меньше",
                        callback_data=f"bet_value_{match_id}_меньше"
                    ),
                    InlineKeyboardButton(
                        text="Больше",
                        callback_data=f"bet_value_{match_id}_больше"
                    )
                ]
            ]
        )

    else:
        text = f"""{EMOJI['bet']} <b>Выберите число:</b>

Игрок: {player_name}
Ставка: Точное число (гол)

Угадайте число на кубике (1-6)
Шанс: 1 из 6 (16.7%)"""

        keyboard_buttons = []
        row = []
        for i in range(1, 7):
            row.append(InlineKeyboardButton(
                text=str(i),
                callback_data=f"bet_value_{match_id}_{i}"
            ))
            if i % 3 == 0:
                keyboard_buttons.append(row)
                row = []
        if row:
            keyboard_buttons.append(row)

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    bet_number_text = " (вторая ставка)" if is_second_bet else " (первая ставка)"
    text += f"\n\n{EMOJI['info']} Ставка #{1 if not is_second_bet else 2}{bet_number_text}"

    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data.startswith("bet_value_"))
async def process_bet(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбранного значения ставки.

    Сохраняет ставку в Bet, обновляет used_players и current_on_field,
    показывает клавиатуру подтверждения хода.
    """
    parts = callback.data.split("_")
    match_id = int(parts[2])
    bet_value = parts[3]

    telegram_id = callback.from_user.id
    state_data = await state.get_data()

    selected_player_id = state_data.get('selected_player_id')
    selected_player_position = state_data.get('selected_player_position')
    selected_bet_type = state_data.get('selected_bet_type')
    current_bet_number = state_data.get('current_bet_number', 1)

    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if not user:
            await callback.answer("Пользователь не найден")
            return

        user_db_id = user.id

        match = await session.get(Match, match_id)
        team_data = match.get_player_team_data(user_db_id)
        if not team_data:
            await callback.answer("Ошибка: данные команды не найдены")
            return

        player = next(
            (p for p in team_data.get('players', []) if p.get('id') == selected_player_id),
            None
        )
        if not player:
            await callback.answer("Игрок не найден в команде")
            return

        selected_player_name = player.get('name', f"Игрок {selected_player_id}")
        if not match or match.get_current_user_id() != user_db_id:
            await callback.answer("Сейчас не ваш ход")
            return

        is_second_bet = (current_bet_number == 2)
        is_valid, message_text = await game_manager.validate_bet(
            match, selected_player_id, selected_player_position,
            selected_bet_type, bet_value, is_second_bet
        )
        if not is_valid:
            await callback.answer(f"❌ {message_text}")
            return

        if selected_bet_type == "EVEN_ODD":
            bet_type_enum = BetType.EVEN_ODD
        elif selected_bet_type == "big_small":
            bet_type_enum = BetType.BIG_SMALL
        elif selected_bet_type == "goal":
            bet_type_enum = BetType.GOAL
        else:
            await callback.answer("Неизвестный тип ставки")
            return

        success, result_message, bet_data = await game_manager.process_bet(
            session, match_id, user_db_id, selected_player_id, bet_type_enum, bet_value
        )
        if not success:
            await callback.answer(f"❌ {result_message}")
            return

        bet = Bet(
            match_id=match_id,
            user_id=user_db_id,
            player_id=selected_player_id,
            bet_type=bet_type_enum,
            bet_value=bet_value,
            player_position=selected_player_position,
            dice_roll=None,
            bet_result=BetStatus.PENDING,
            actions_gained=None,
            turn_number=match.current_turn,
            bet_order=current_bet_number
        )

        current_field = match.current_on_field or {'DF': 0, 'MF': 0, 'FW': 0}
        current_field[selected_player_position] = current_field.get(selected_player_position, 0) + 1
        match.current_on_field = current_field

        if match.used_players is None:
            match.used_players = []
        match.used_players.append(selected_player_id)

        session.add(bet)

        bets_made = state_data.get('bets_made', 0) + 1
        await state.update_data(bets_made=bets_made)

        await session.commit()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Отменить / Изменить ставку",
                        callback_data=f"cancel_bet_{match_id}_{selected_player_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Подтвердить ход и ждать соперника",
                        callback_data=f"confirm_turn_{match_id}"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            f"Ставка принята на {selected_player_name} ({selected_player_position}).\n"
            "Можно отменить или подтвердить ход.",
            reply_markup=keyboard
        )

        await callback.answer("Ставка сохранена")


@router.callback_query(F.data.startswith("confirm_turn_"))
async def confirm_turn(callback: CallbackQuery):
    """
    Подтверждение хода игрока и запуск хода бота (для матчей VS_BOT).
    """
    match_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        if not match or match.current_player_turn != "player1":
            await callback.answer("Не ваш ход")
            return

        match.current_player_turn = "player2"
        await session.commit()


        bot_instance = Final4BotAI
        await bot_instance.make_bot_turn(match, session)

        await callback.message.edit_text(
            "Ваш ход подтверждён. Соперник сделал ставку и бросил кубик.\n"
            "Итоги хода уже показаны выше."
        )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_bet_"))
async def cancel_bet(callback: CallbackQuery):
    """
    Отмена последней ставки.
    """
    match_id = int(callback.data.split("_")[2])
    player_id = int(callback.data.split("_")[3])
    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        await session.commit()
        await callback.message.edit_text("Ставка отменена. Выберите заново.")
    await callback.answer()


async def show_bet_type_selection_second(message: Message, match: Match,
                                         player_id: int, position: str):
    """
    Показ выбора второй ставки (если применимо).
    """
    tracker = match.bet_tracker
    available_second = tracker.get_available_bet_types(player_id, position, True)

    if not available_second:
        return

    text = f"""{EMOJI['bet']} <b>Выбор второй ставки (2/2)</b>

Вы уже сделали первую ставку.
Теперь выберите вторую ставку (должна быть другого типа):

{EMOJI['info']} <b>Доступные типы для второй ставки:</b>"""

    keyboard_buttons = []
    for bet_type in available_second:
        if bet_type == BetType.EVEN_ODD:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="🔢 Чет/Нечет",
                    callback_data=f"bet_type_{match.id}_{player_id}_{bet_type.value}"
                )
            ])
        elif bet_type == BetType.BIG_SMALL:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="📊 Больше/Меньше",
                    callback_data=f"bet_type_{match.id}_{player_id}_{bet_type.value}"
                )
            ])
        elif bet_type == BetType.GOAL:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="⚽ Точное число (гол)",
                    callback_data=f"bet_type_{match.id}_{player_id}_{bet_type.value}"
                )
            ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


async def complete_turn(message: Message, match: Match, state: FSMContext,
                        dice_roll: int, bet_won: bool):
    """
    Завершение хода после броска кубика.
    """
    state_data = await state.get_data()
    selected_player_position = state_data.get('selected_player_position')
    selected_bet_type = state_data.get('selected_bet_type')
    bet_value = state_data.get('bet_value', '')

    await show_bet_result(
        message, match.id, dice_roll, bet_won,
        selected_player_position, selected_bet_type, bet_value
    )

    async with AsyncSessionLocal() as session:
        db_match = await session.get(Match, match.id)
        db_match.switch_turn()

        # ... остальная логика обновления ...

        # Проверяем, не закончилось ли основное время
        if db_match.current_turn > 11 and not db_match.is_extra_time:
            # Проверяем счет через game_manager
            from services.game_manager import game_manager

            is_completed, _, result_data = await game_manager.check_match_completion(session, db_match)

            if result_data and result_data["action"] == "extra_time":
                # Ничья - переходим в ДВ
                await session.commit()
                await start_extra_time_auto(message, db_match, state)
                return
            elif result_data and result_data["action"] == "finish":
                # Матч завершен
                await game_manager.process_match_completion(session, db_match, result_data)

                # Отправляем результат
                result_text = game_manager.format_match_result(result_data)
                await message.answer(result_text, parse_mode='HTML')

                await state.clear()
                return

        await session.commit()

async def start_extra_time(message: Message, match: Match, state: FSMContext):
    """
    Переход к дополнительному времени (вызов выбора игроков).
    """
    text = f"""{EMOJI['clock']} <b>Дополнительное время!</b>

Матч #{match.id}
Основное время завершено.

{EMOJI['rules']} <b>Правила ДВ:</b>
• Выберите 5 игроков, которые НЕ делали ставок в основном времени
• В ДВ доступны те же типы ставок
• Ходы продолжаются до победы"""

    await message.answer(text, parse_mode='HTML')

    await state.set_state(MatchStates.SELECTING_EXTRA_TIME_PLAYERS)
    await state.update_data(
        extra_time_selected=[],
        selecting_for_match=match.id
    )




async def search_opponent(match_id: int, bot):
    """
    Фоновая задача поиска соперника (заглушка).
    """
    await asyncio.sleep(2)

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)

        if not match or match.status != MatchStatus.WAITING:
            return

        match.status = MatchStatus.CANCELLED
        await session.commit()

        try:
            await bot.send_message(
                match.player1_id,
                f"{EMOJI['cancel']} <b>Поиск соперника отменен</b>\n\n"
                f"Не удалось найти соперника за отведенное время.\n"
                f"Попробуйте создать матч против бота.",
                parse_mode='HTML'
            )
        except:
            pass


async def show_bet_result(message: Message, match_id: int, dice_roll: int,
                          bet_won: bool, position: str, bet_type: str, bet_value: str):
    """
    Отображение результата ставки и полученных действий.
    """
    result_emoji = "✅" if bet_won else "❌"
    result_text = "Выиграна" if bet_won else "Проиграна"

    text = f"""{result_emoji} <b>Результат ставки</b>

🎲 Выпало: {dice_roll}
🎯 Ставка: {bet_value}
📊 Результат: {result_text}

{get_position_emoji(position)} {position}"""

    if bet_won:
        actions = calculate_actions(position, bet_type)
        action_text = []

        if actions.get('goals', 0) > 0:
            action_text.append(f"{EMOJI['goal']} +{actions['goals']} гол")
        if actions.get('passes', 0) > 0:
            action_text.append(f"{EMOJI['pass']} +{actions['passes']} передача")
        if actions.get('defenses', 0) > 0:
            action_text.append(f"{EMOJI['defense']} +{actions['defenses']} отбитие")

        if action_text:
            text += f"\n\n{EMOJI['gift']} <b>Получено:</b>\n" + "\n".join(action_text)

        text += f"\n\n{EMOJI['card']} <b>Вы получили карточку «Свисток»!</b>"

    await message.answer(text, parse_mode='HTML')


def get_player_name(match, player_id: int) -> str:
    """
    Возвращает имя игрока для отображения в сообщениях.
    """
    if player_id == match.player1_id:
        return "Игрок 1"
    elif player_id == match.player2_id:
        if match.match_type == MatchType.VS_BOT:
            return "Бот"
        else:
            return "Игрок 2"
    return "Неизвестный"


def get_position_emoji(position: str) -> str:
    """
    Возвращает эмодзи для позиции футболиста.
    """
    emojis = {
        'GK': '🥅',
        'DF': '🛡️',
        'MF': '⚡',
        'FW': '⚽'
    }
    return emojis.get(position, '👤')


@router.message(Command("matches"))
async def command_matches(message: Message):
    """
    Команда /matches — список активных матчей пользователя.
    """
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        matches = await session.execute(
            select(Match).where(
                or_(
                    Match.player1_id == user_id,
                    Match.player2_id == user_id
                ),
                Match.status.in_([
                    MatchStatus.CREATED,
                    MatchStatus.WAITING,
                    MatchStatus.IN_PROGRESS
                ])
            ).order_by(Match.created_at.desc()).limit(5)
        )
        matches = matches.scalars().all()

        if not matches:
            await message.answer(
                f"{EMOJI['list']} <b>Нет активных матчей</b>\n\n"
                f"Используйте /play чтобы начать новый матч.",
                parse_mode='HTML'
            )
            return

        text = f"{EMOJI['list']} <b>Ваши активные матчи:</b>\n\n"

        for match in matches:
            status_emoji = {
                MatchStatus.CREATED: '📝',
                MatchStatus.WAITING: '🔍',
                MatchStatus.IN_PROGRESS: '⚽'
            }.get(match.status, '❓')

            opponent = "Бот" if match.match_type == MatchType.VS_BOT else "Соперник"

            text += (
                f"{status_emoji} <b>Матч #{match.id}</b>\n"
                f"Тип: {opponent}\n"
                f"Статус: {match.status.value}\n"
                f"Создан: {match.created_at.strftime('%d.%m %H:%M')}\n"
                f"/match_{match.id}\n\n"
            )

        await message.answer(text, parse_mode='HTML')


@router.message(lambda message: message.text and message.text.startswith('/match_'))
async def command_match_detail(message: Message):
    """
    Команда /match_123 — детальная информация о конкретном матче.
    """
    try:
        match_id = int(message.text.split('_')[1])
    except (IndexError, ValueError):
        await message.answer("Неверный формат команды. Используйте /match_123")
        return

    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)

        if not match or not match.is_player_in_match(user_id):
            await message.answer("Матч не найден или у вас нет доступа")
            return

        text = f"""{EMOJI['match']} <b>Матч #{match.id}</b>

{EMOJI['vs']} <b>Участники:</b>
• {get_player_name(match, match.player1_id)}
• {get_player_name(match, match.player2_id)}

{EMOJI['info']} <b>Информация:</b>
Тип: {match.match_type}
Статус: {match.status.value}
Создан: {match.created_at.strftime('%d.%m.%Y %H:%M')}

{EMOJI['score']} <b>Счет:</b>
{match.player1_score} : {match.player2_score}

{EMOJI['turn']} <b>Ход:</b> {match.current_turn}/{'∞' if match.is_extra_time else '11'}
{EMOJI['player']} <b>Ходит:</b> {get_player_name(match, match.get_current_user_id())}

{EMOJI['stats']} <b>Статистика квот:</b>
Голы: DF ({match.bet_tracker.get_goal_quota_used('DF')}/1), 
      MF ({match.bet_tracker.get_goal_quota_used('MF')}/3), 
      FW ({match.bet_tracker.get_goal_quota_used('FW')}/4)
Чет/нечет: {match.bet_tracker.get_EVEN_ODD_count()}/6 игроков"""

        keyboard_buttons = []

        if match.status == MatchStatus.CREATED:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['play']} Начать матч",
                    callback_data=f"start_match_{match.id}"
                )
            ])

        elif match.status == MatchStatus.IN_PROGRESS:
            if match.get_current_user_id() == user_id:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{EMOJI['dice']} Сделать ход",
                        callback_data=f"continue_match_{match.id}"
                    )
                ])
            else:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{EMOJI['wait']} Ожидание хода соперника",
                        callback_data="waiting"
                    )
                ])

        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['back']} Назад к списку",
                callback_data="show_matches"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data == "show_matches")
async def show_matches_callback(callback: CallbackQuery):
    """
    Callback для возврата к списку матчей.
    """
    await callback.answer()
    await command_matches(callback.message)


@router.callback_query(F.data.startswith("continue_match_"))
async def continue_match_callback(callback: CallbackQuery, state: FSMContext):
    """
    Продолжение активного матча (вызов show_turn).
    """
    match_id = int(callback.data.split("_")[2])

    await state.update_data(match_id=match_id)
    await state.set_state(MatchStates.IN_MATCH)

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        if match:
            await show_turn(callback.message, state, match_id, match.current_turn)

    await callback.answer()


@router.callback_query(F.data.startswith("cancel_match_"))
async def cancel_match_callback(callback: CallbackQuery):
    """
    Отмена матча (только для статусов CREATED / WAITING).
    """
    match_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)

        if match and match.status in [MatchStatus.CREATED, MatchStatus.WAITING]:
            match.status = MatchStatus.CANCELLED
            await session.commit()

            await callback.answer("Матч отменен")
            await callback.message.edit_text(
                f"{EMOJI['cancel']} <b>Матч #{match_id} отменен</b>",
                parse_mode='HTML'
            )
        else:
            await callback.answer("Нельзя отменить этот матч")


async def start_extra_time_auto(message: Message, match: Match, state: FSMContext):
    """
    Автоматический старт дополнительного времени.
    ДВ начинается сразу, используются 5 неиспользованных игроков.
    """
    # Получаем ID обоих игроков
    player1_id = match.player1_id
    player2_id = match.player2_id

    # Получаем данные команд
    team1_data = match.player1_team_data
    team2_data = match.player2_team_data

    # Находим неиспользованных игроков (кто не в used_players)
    used_players = set(match.used_players or [])

    # Для каждого игрока находим его 5 запасных
    player1_subs = []
    if team1_data and 'players' in team1_data:
        for player in team1_data['players']:
            if player.get('id') not in used_players:
                player1_subs.append(player.get('id'))
                if len(player1_subs) == 5:
                    break

    player2_subs = []
    if team2_data and 'players' in team2_data:
        for player in team2_data['players']:
            if player.get('id') not in used_players:
                player2_subs.append(player.get('id'))
                if len(player2_subs) == 5:
                    break

    # Обновляем матч через game_manager
    async with AsyncSessionLocal() as session:
        match_db = await session.get(Match, match.id)

        # Устанавливаем ДВ через метод модели
        match_db.start_extra_time(player1_subs, player2_subs)

        # Сбрасываем счетчик ходов и переключаем ход
        match_db.current_turn = 1
        match_db.current_player_turn = "player1"
        match_db.is_extra_time = True

        # Обновляем BetTracker
        tracker = match_db.bet_tracker
        tracker.start_extra_time(player1_subs + player2_subs)  # передаем общий список
        match_db.bet_tracker = tracker

        await session.commit()

    # Уведомляем игроков
    text = f"""⏰ <b>Дополнительное время!</b>

Матч #{match.id}
Основное время завершилось ничьей.

⚡ <b>Автоматически выбраны запасные игроки:</b>
• Каждая команда использует 5 игроков, не игравших в основном времени
• Ходы продолжаются до победы
• Счетчик ходов сброшен до 1

{EMOJI['dice']} Сейчас ход: {get_player_name(match, match.get_current_user_id())}"""

    await message.answer(text, parse_mode='HTML')

    # Если сейчас ход текущего пользователя - показываем интерфейс
    if match.get_current_user_id() == message.from_user.id:
        await show_turn(message, state, match.id, 1)