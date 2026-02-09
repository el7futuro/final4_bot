# handlers/match.py
"""
Обработчики игрового процесса Final 4 с интеграцией BetTracker и BetValidator.
"""
import random
import logging
logger = logging.getLogger(__name__)
from sqlalchemy import select, and_, or_, func
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter

from sqlalchemy.orm import selectinload
from bot.config import BOT_TELEGRAM_ID
from models.user import User
from models.match import Match, MatchStatus, MatchType
from models.bet import Bet, BetType as ModelBetType, BetStatus
from models.bet_tracker import BetTracker, BetType
from services.game_manager import game_manager
from services.bet_validator import bet_validator
from bot.database import AsyncSessionLocal
from utils.emoji import EMOJI
import asyncio
from typing import Dict, List

router = Router(name="match")


# Состояния FSM для матча
class MatchStates:
    WAITING_FOR_BET = "waiting_for_bet"
    WAITING_FOR_CARD = "waiting_for_card"
    IN_MATCH = "in_match"
    SELECTING_EXTRA_TIME_PLAYERS = "selecting_extra_time_players"
    WAITING_FOR_SECOND_BET = "waiting_for_second_bet"


# handlers/match.py - исправленная функция match_type_vs_bot

from bot.config import BOT_TELEGRAM_ID  # Добавляем импорт
import random  # Для создания команды бота


@router.callback_query(F.data == "match_type_vs_bot")
async def match_type_vs_bot(callback: CallbackQuery, state: FSMContext):
    """Создание матча против бота - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    print(f"DEBUG: callback.from_user.id = {callback.from_user.id}")
    user_id = callback.from_user.id
    first_name = callback.from_user.first_name or "Игрок"

    # Динамический ID бота
    bot_telegram_id = callback.bot.id  # ← ИСПРАВЛЕНИЕ ЗДЕСЬ

    async with AsyncSessionLocal() as session:
        # 1. Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала зарегистрируйтесь через /start")
            return

        # 2. Находим или создаем пользователя-бота
        bot_result = await session.execute(
            select(User).where(User.telegram_id == bot_telegram_id)  # ← ИСПРАВЛЕНИЕ ЗДЕСЬ
        )
        bot_user = bot_result.scalar_one_or_none()

        if not bot_user:
            # Создаем пользователя-бота
            bot_user = User(
                telegram_id=bot_telegram_id,  # ← ИСПРАВЛЕНИЕ ЗДЕСЬ
                username='final4_bot',
                first_name='🤖 Бот'
            )
            session.add(bot_user)
            await session.flush()

        # ... остальной код без изменений ...

        # 3. Создаем стандартную команду игрока (16 футболистов)
        player_players = []

        # Вратарь (1)
        player_players.append({
            'id': 1,
            'position': 'GK',
            'name': f'{first_name} - Вратарь',
            'number': 1
        })

        # Защитники (5)
        for i in range(5):
            player_players.append({
                'id': 2 + i,
                'position': 'DF',
                'name': f'{first_name} - Защитник {i + 1}',
                'number': 2 + i
            })

        # Полузащитники (6)
        for i in range(6):
            player_players.append({
                'id': 7 + i,
                'position': 'MF',
                'name': f'{first_name} - Полузащитник {i + 1}',
                'number': 7 + i
            })

        # Нападающие (4)
        for i in range(4):
            player_players.append({
                'id': 13 + i,
                'position': 'FW',
                'name': f'{first_name} - Нападающий {i + 1}',
                'number': 13 + i
            })

        # 4. Создаем команду бота (16 футболистов)
        bot_players = []

        # Вратарь (1)
        bot_players.append({
            'id': 1,
            'position': 'GK',
            'name': '🤖 Бот-Вратарь',
            'number': 1
        })

        # Защитники (5)
        for i in range(5):
            bot_players.append({
                'id': 2 + i,
                'position': 'DF',
                'name': f'🤖 Бот-Защитник {i + 1}',
                'number': 2 + i
            })

        # Полузащитники (6)
        for i in range(6):
            bot_players.append({
                'id': 7 + i,
                'position': 'MF',
                'name': f'🤖 Бот-Полузащитник {i + 1}',
                'number': 7 + i
            })

        # Нападающие (4)
        for i in range(4):
            bot_players.append({
                'id': 13 + i,
                'position': 'FW',
                'name': f'🤖 Бот-Нападающий {i + 1}',
                'number': 13 + i
            })

        # 5. Создаем матч с ботом
        match = Match(
            player1_id=user.id,
            player2_id=bot_user.id,  # Используем реальный ID бота из БД
            player1_team_data={'players': player_players},
            player2_team_data={'players': bot_players},
            match_type=MatchType.VS_BOT,
            status=MatchStatus.CREATED,
            current_turn=1,
            bet_tracker=BetTracker()  # Инициализируем трекер
        )

        session.add(match)
        await session.commit()

        # 6. Показываем успешное создание
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

        # Сохраняем ID матча в состоянии
        await state.update_data(match_id=match.id)

@router.message(Command("play"))
async def command_play(message: Message):
    """Начать поиск матча"""
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        # Проверяем пользователя
        user = await session.get(User, user_id)
        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        # Используем GameManager для проверки возможности начала матча
        can_start, reason = await game_manager.can_start_match(session, user_id)
        if not can_start:
            await message.answer(f"❌ {reason}")
            return

        # Показываем меню выбора матча
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
    """Создание матча против случайного соперника"""
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        # Создаем матч
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

        # Запускаем поиск соперника в фоне
        asyncio.create_task(search_opponent(match.id, callback.bot))


@router.callback_query(F.data.startswith("start_match_"))
async def start_match(callback: CallbackQuery, state: FSMContext):
    """Начало матча"""
    match_id = int(callback.data.split("_")[2])
    telegram_id = callback.from_user.id  # Переименовываем для ясности

    async with AsyncSessionLocal() as session:
        # 1. Получаем пользователя из БД по telegram_id
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        # 2. Получаем матч
        match = await session.get(Match, match_id)

        if not match:
            await callback.answer("Матч не найден")
            return

        # 3. Проверяем участие пользователя в матче (используем user.id, а не telegram_id)
        if not match.is_player_in_match(user.id):  # user.id, а не telegram_id
            await callback.answer("Вы не участник этого матча")
            return

        if match.status != MatchStatus.CREATED:
            await callback.answer("Матч уже начат")
            return

        # 4. Начинаем матч
        match.status = MatchStatus.IN_PROGRESS
        match.started_at = func.now()
        match.current_player_turn = "player1"

        await session.commit()

        # 5. Сохраняем данные в состоянии
        await state.update_data(
            match_id=match_id,
            current_turn=1,
            bets_made=0,
            selected_player_id=None
        )
        await state.set_state(MatchStates.IN_MATCH)

        # 6. Показываем первый ход
        await show_turn(callback, state, match_id, 1)

    await callback.answer()


async def show_turn(callback: CallbackQuery, state: FSMContext, match_id: int, turn: int):
    """Показывает интерфейс хода с учетом ограничений"""
    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        telegram_id = callback.from_user.id  # ← ИЗМЕНЕНО: callback.from_user.id вместо message.from_user.id

        # 1. Получаем пользователя из БД
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.message.answer("Пользователь не найден")  # ← ИЗМЕНЕНО
            return

        user_db_id = user.id

        if not match or not match.is_player_in_match(user_db_id):
            await callback.message.answer("Ошибка доступа к матчу")  # ← ИЗМЕНЕНО
            return


        # Проверяем, ход ли игрока
        current_user_id = match.get_current_user_id()  # Этот метод возвращает id из users
        print(f"DEBUG: current_user_id = {current_user_id}, user_db_id = {user_db_id}")
        if current_user_id != user_db_id:  # Сравниваем с user_db_id
            text = f"""{EMOJI['wait']} <b>Ожидание хода соперника...</b>

Матч #{match.id}
Ход {turn}/11
Ходит: {get_player_name(match, current_user_id)}

{EMOJI['info']} Ждите, когда соперник сделает ход."""
            await message.answer(text, parse_mode='HTML')
            return

        # Ход игрока
        player_number = match.get_player_number(user_db_id)  # Используем user_db_id
        team_data = match.get_player_team_data(user_db_id)  # Используем user_db_id

        if not team_data:
            await message.answer("Ошибка: данные команды не найдены")
            return

        # Получаем доступных игроков через GameManager
        # GameManager.get_available_players тоже нужно исправить, но пока передаем user_db_id
        available_players = await game_manager.get_available_players(
            session, match_id, user_db_id  # Передаем user_db_id, а не telegram_id
        )

        if not available_players:
            # Нет доступных игроков - переходим к ДВ или завершаем
            await handle_no_available_players(callback.message, match, state)
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
Чет/нечет: {match.bet_tracker.get_remaining_even_odd()}/6 игроков"""

        # Показываем кнопки выбора игрока
        keyboard_buttons = []
        for player in available_players[:8]:  # Ограничиваем показ
            emoji = get_position_emoji(player.get('position', 'GK'))
            player_name = player.get('name', f"Игрок {player.get('id')}")
            player_number = player.get('number', '?')

            # Добавляем информацию о доступных ставках
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

        await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')  # ← ИЗМЕНЕНО


async def handle_no_available_players(message: Message, match: Match, state: FSMContext):
    """Обрабатывает ситуацию, когда нет доступных игроков"""
    if not match.is_extra_time and match.current_turn >= 11:
        # Завершаем основное время, переходим к ДВ
        text = f"""{EMOJI['clock']} <b>Основное время завершено!</b>

Матч #{match.id}
Основное время: 11 ходов

{EMOJI['info']} <b>Переходим к дополнительному времени!</b>
Теперь нужно выбрать 5 игроков из тех, кто не делал ставок в основном времени."""

        await state.set_state(MatchStates.SELECTING_EXTRA_TIME_PLAYERS)
        await state.update_data(
            extra_time_selected=[],
            selecting_for_match=match.id
        )

        # Показываем выбор игроков для ДВ
        await show_extra_time_selection(message, match.id, match.get_current_user_id())

    else:
        # Ошибка: должно быть доступно
        await message.answer("Ошибка: нет доступных игроков для хода. Обратитесь к администратору.")


@router.callback_query(F.data.startswith("select_player_"))
async def select_player(callback: CallbackQuery, state: FSMContext):
    """Выбор игрока для ставки с проверкой через BetValidator"""
    parts = callback.data.split("_")
    match_id = int(parts[2])
    player_id = int(parts[3])
    telegram_id = callback.from_user.id  # ← Переименовываем для ясности

    async with AsyncSessionLocal() as session:
        # 1. Получаем пользователя из БД
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        user_db_id = user.id  # ← Используем этот ID

        # 2. Получаем матч
        match = await session.get(Match, match_id)

        if not match or match.get_current_user_id() != user_db_id:  # ← Используем user_db_id
            await callback.answer("Сейчас не ваш ход")
            return

        # 3. Проверяем выбор игрока через GameManager (передаем user_db_id)
        is_valid, message = await game_manager.validate_player_selection(
            session, match_id, user_db_id, player_id  # ← Используем user_db_id
        )

        if not is_valid:
            await callback.answer(f"❌ {message}")
            return

        # 4. Получаем информацию об игроке ИЗ МАТЧА (а не из user.team_data)
        print(
            f"DEBUG select_player: user_db_id={user_db_id}, player1_id={match.player1_id}, "
            f"player2_id={match.player2_id}")
        team_data = match.get_player_team_data(user_db_id)  # ← Используем user_db_id

        print(f"DEBUG: team_data={team_data}")
        if not team_data:
            await callback.answer("Ошибка: данные команды не найдены")
            return

        team_players = team_data.get('players', [])
        player = next((p for p in team_players if p.get('id') == player_id), None)

        if not player:
            await callback.answer("Игрок не найден")
            return

        # 5. Сохраняем выбранного игрока в состоянии
        await state.update_data(
            selected_player_id=player_id,
            selected_player_position=player.get('position', 'GK'),
            selected_player_name=player.get('name', f"Игрок {player_id}"),
            current_bet_number=1  # Первая ставка
        )

        # 6. Показываем выбор типа ставки
        await show_bet_type_selection(callback.message, match, player)

    await callback.answer()

# В handlers/match.py, перед функцией extra_time_done добавьте:

@router.callback_query(F.data.startswith("select_extra_"))
async def select_extra_player(callback: CallbackQuery, state: FSMContext):
    """Выбор игрока для дополнительного времени"""
    parts = callback.data.split("_")
    match_id = int(parts[2])
    player_id = int(parts[3])
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        if not match or not match.is_player_in_match(user_id):
            await callback.answer("Ошибка доступа к матчу")
            return

        # Проверяем, что находимся в состоянии выбора ДВ
        current_state = await state.get_state()
        if current_state != MatchStates.SELECTING_EXTRA_TIME_PLAYERS:
            await callback.answer("Сейчас не время выбора игроков для ДВ")
            return

        # Получаем текущий список выбранных игроков
        state_data = await state.get_data()
        selected = state_data.get('extra_time_selected', [])

        # Проверяем, не выбран ли уже этот игрок
        if player_id in selected:
            # Убираем из выбранных
            selected.remove(player_id)
            action_emoji = "➖"
            action_text = "удален"
        else:
            # Проверяем, можно ли добавить (максимум 5)
            if len(selected) >= 5:
                await callback.answer("Можно выбрать только 5 игроков")
                return

            # Добавляем игрока
            selected.append(player_id)
            action_emoji = "➕"
            action_text = "выбран"

        # Обновляем состояние
        await state.update_data(extra_time_selected=selected)

        # Получаем информацию об игроке
        user = await session.get(User, user_id)
        player_name = f"Игрок #{player_id}"
        if user and user.team_data:
            import json
            team_data = json.loads(user.team_data) if isinstance(user.team_data, str) else user.team_data
            players = team_data.get('players', [])
            player = next((p for p in players if p.get('id') == player_id), None)
            if player:
                player_name = player.get('name', player_name)

        await callback.answer(f"{action_emoji} {player_name} {action_text} ({len(selected)}/5)")

        # Обновляем сообщение с новой клавиатурой
        try:
            await update_extra_time_keyboard(callback.message, match_id, user_id, selected)
        except Exception as e:
            logger.error(f"Error updating keyboard: {e}")
            await callback.answer("Ошибка обновления")


async def update_extra_time_keyboard(message: Message, match_id: int, user_id: int, selected: List[int]):
    """Обновляет клавиатуру выбора игроков ДВ"""
    async with AsyncSessionLocal() as session:
        # Получаем игроков для ДВ
        extra_players = await game_manager.get_extra_time_players(
            session, match_id, user_id
        )

        # Создаем новую клавиатуру
        keyboard_buttons = []

        for player in extra_players:
            emoji = get_position_emoji(player.get('position', 'GK'))
            player_name = player.get('name', f"Игрок {player.get('id')}")
            player_num = player.get('number', '?')

            # Проверяем, выбран ли игрок
            is_selected = player['id'] in selected
            prefix = "✅ " if is_selected else ""

            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{prefix}{emoji} {player_name} (#{player_num})",
                    callback_data=f"select_extra_{match_id}_{player['id']}"
                )
            ])

        # Кнопка готово с обновленным счетчиком
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['check']} Готово ({len(selected)}/5)",
                callback_data=f"extra_done_{match_id}"
            )
        ])

        # Кнопка отмены
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['cancel']} Отмена",
                callback_data=f"cancel_extra_{match_id}"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        # Обновляем только клавиатуру
        await message.edit_reply_markup(reply_markup=keyboard)


# Дальше продолжается существующий код extra_time_done...

@router.callback_query(F.data.startswith("extra_done_"))
async def extra_time_done(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора игроков для ДВ"""
    match_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        # Получаем матч
        match = await session.get(Match, match_id)
        if not match or not match.is_player_in_match(user_id):
            await callback.answer("Ошибка доступа к матчу")
            return

        # Получаем выбранных игроков из состояния
        state_data = await state.get_data()
        selected = state_data.get('extra_time_selected', [])

        # Проверяем количество
        if len(selected) != 5:
            await callback.answer(f"Нужно выбрать ровно 5 игроков (выбрано: {len(selected)})")
            return

        # Проверяем выбор через GameManager
        is_valid, message = await game_manager.validate_extra_time_selection(
            session, match_id, user_id, selected
        )

        if not is_valid:
            await callback.answer(f"❌ {message}")
            return

        # Сохраняем выбранных игроков в матч
        player_key = 'player1' if user_id == match.player1_id else 'player2'

        # Инициализируем словарь если нужно
        if not match.extra_time_players:
            match.extra_time_players = {}

        match.extra_time_players[player_key] = selected
        await session.commit()

        # Проверяем, выбрали ли оба игрока
        both_selected = (
                match.extra_time_players.get('player1') and
                match.extra_time_players.get('player2') and
                len(match.extra_time_players.get('player1', [])) == 5 and
                len(match.extra_time_players.get('player2', [])) == 5
        )

        if both_selected:
            # Оба игрока выбрали - начинаем ДВ
            # Определяем, чей ход начинать (тот, кто не начинал основной матч)
            if match.current_player_turn == "player1":
                match.current_player_turn = "player2"
            else:
                match.current_player_turn = "player1"

            # Обновляем трекер
            tracker = match.bet_tracker
            tracker.start_extra_time(selected)  # Используем выбор текущего игрока
            match.bet_tracker = tracker

            match.is_extra_time = True
            match.current_turn = 1  # Сбрасываем счетчик ходов для ДВ

            await session.commit()

            # Сбрасываем состояние
            await state.set_state(MatchStates.IN_MATCH)
            await state.update_data(extra_time_selected=[])

            # Уведомляем обоих игроков
            text = f"""{EMOJI['clock']} <b>Дополнительное время начато!</b>

Матч #{match.id}
Оба игрока выбрали по 5 запасных.

{EMOJI['rules']} <b>Правила ДВ:</b>
• Доступны те же типы ставок
• Максимум 1 ставка на гол на игрока"""

            await callback.message.edit_text(text, parse_mode='HTML')

            # Показываем первый ход ДВ
            current_user_id = match.get_current_user_id()
            if current_user_id == user_id:
                await show_turn(callback.message, state, match_id, 1)
            else:
                await callback.message.answer(
                    f"{EMOJI['wait']} Ожидание хода соперника...",
                    parse_mode='HTML'
                )

        else:
            # Ждем второго игрока
            opponent_id = match.player2_id if user_id == match.player1_id else match.player1_id
            opponent_name = get_player_name(match, opponent_id)

            text = f"""{EMOJI['check']} <b>Ваш выбор сохранен!</b>

Матч #{match.id}

"""

            await callback.message.edit_text(text, parse_mode='HTML')
            await state.set_state(None)  # Сбрасываем состояние, ждем второго игрока

        await callback.answer("Выбор сохранен!")



@router.callback_query(F.data.startswith("cancel_extra_"))
async def cancel_extra_selection(callback: CallbackQuery, state: FSMContext):
    """Отмена выбора игроков для ДВ"""
    match_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        if not match or not match.is_player_in_match(user_id):
            await callback.answer("Ошибка доступа")
            return

        # Сбрасываем состояние
        await state.clear()

        # Возвращаемся к просмотру матча
        text = f"""{EMOJI['cancel']} <b>Выбор игроков отменен</b>

Матч #{match.id}
Выбор игроков для дополнительного времени отменен.

{EMOJI['info']} Дополнительное время начнется, когда оба игрока выберут по 5 игроков."""

        await callback.message.edit_text(text, parse_mode='HTML')
        await callback.answer("Выбор отменен")


async def show_bet_type_selection(message: Message, match: Match, player: Dict):
    """Показывает выбор типа ставки с учетом ограничений"""
    player_id = player['id']
    position = player.get('position', 'GK')
    player_name = player.get('name', f"Игрок {player_id}")

    # Получаем доступные типы ставок через GameManager
    available_bets = await game_manager.get_available_bet_types(
        match, player_id, position, False  # Первая ставка
    )

    if not available_bets:
        await message.answer("❌ Нет доступных типов ставок для этого игрока")
        return

    text = f"""{EMOJI['bet']} <b>Выбор ставки (1/2)</b>

Игрок: {player_name} (#{player.get('number', '?')})
Позиция: {position}

{EMOJI['rules']} <b>Доступные ставки:</b>"""

    # Создаем кнопки - ИСПРАВЛЕННЫЙ КОД
    keyboard_buttons = []
    for bet_type_str, bet_name, values in available_bets:  # Изменено распаковку!
        # Для каждой ставки показываем возможные значения
        if bet_type_str == "even_odd":  # Используем строки, а не BetType
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"🔢 {bet_name} (чёт/нечёт)",
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
    """Выбор типа ставки"""
    parts = callback.data.split("_")

    # ИСПРАВЛЕНИЕ: Правильно извлекаем bet_type_str
    if len(parts) >= 5:
        match_id = int(parts[2])
        player_id = int(parts[3])
        bet_type_str = "_".join(parts[4:])  # Объединяем всё после player_id
    else:
        await callback.answer("❌ Ошибка в данных")
        return

    telegram_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        # 1. Получаем пользователя из БД
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        user_db_id = user.id  # ← Используем этот ID

        # 2. Получаем матч
        match = await session.get(Match, match_id)
        if not match:
            await callback.answer("Матч не найден")
            return

        # 3. Получаем данные из состояния
        state_data = await state.get_data()
        current_bet_number = state_data.get('current_bet_number', 1)

        # 4. Проверяем ставку через GameManager
        is_second_bet = (current_bet_number == 2)

        # 5. Получаем данные игрока ИЗ МАТЧА
        team_data = match.get_player_team_data(user_db_id)  # ← ИЗМЕНЕНО
        if not team_data:
            await callback.answer("Ошибка: данные команды не найдены")
            return

        team_players = team_data.get('players', [])  # ← ИЗМЕНЕНО
        player = next((p for p in team_players if p.get('id') == player_id), None)
        if not player:
            await callback.answer("Игрок не найден")
            return

        position = player.get('position', 'GK')

        # 6. Проверяем доступность типа ставки
        is_valid, message = await game_manager.validate_bet(
            match, player_id, position, bet_type_str, "", is_second_bet
        )

        if not is_valid:
            await callback.answer(f"❌ {message}")
            return

        # 7. Сохраняем тип ставки
        await state.update_data(
            selected_bet_type=bet_type_str,
            selected_player_id=player_id
        )

        # 8. Показываем выбор значения ставки
        await show_bet_value_selection(
            callback.message, match_id, bet_type_str, player, is_second_bet
        )

    await callback.answer()


async def show_bet_value_selection(message: Message, match_id: int, bet_type_str: str,
                                   player: Dict, is_second_bet: bool):
    """Показывает выбор значения ставки"""
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

    else:  # goal
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

    # Добавляем информацию о номере ставки
    bet_number_text = " (вторая ставка)" if is_second_bet else " (первая ставка)"
    text += f"\n\n{EMOJI['info']} Ставка #{1 if not is_second_bet else 2}{bet_number_text}"

    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data.startswith("bet_value_"))
async def process_bet(callback: CallbackQuery, state: FSMContext):
    """Обработка ставки с интеграцией BetTracker"""
    parts = callback.data.split("_")
    match_id = int(parts[2])
    bet_value = parts[3]

    telegram_id = callback.from_user.id  # ← Переименовываем
    state_data = await state.get_data()

    selected_player_id = state_data.get('selected_player_id')
    selected_player_position = state_data.get('selected_player_position')
    selected_bet_type = state_data.get('selected_bet_type')
    current_bet_number = state_data.get('current_bet_number', 1)

    async with AsyncSessionLocal() as session:
        # 1. Получаем пользователя из БД
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        user_db_id = user.id  # ← Используем этот ID

        # 2. Получаем матч
        match = await session.get(Match, match_id)

        if not match or match.get_current_user_id() != user_db_id:  # ← Используем user_db_id
            await callback.answer("Сейчас не ваш ход")
            return

        # 3. Проверяем ставку через GameManager (передаем user_db_id)
        is_second_bet = (current_bet_number == 2)
        is_valid, message = await game_manager.validate_bet(
            match, selected_player_id, selected_player_position,
            selected_bet_type, bet_value, is_second_bet
        )

        if not is_valid:
            await callback.answer(f"❌ {message}")
            return

        # 4. Преобразуем строку в BetType для BetTracker
        if selected_bet_type == "even_odd":
            bet_type_enum = BetType.EVEN_ODD
        elif selected_bet_type == "big_small":
            bet_type_enum = BetType.BIG_SMALL
        elif selected_bet_type == "goal":
            bet_type_enum = BetType.GOAL
        else:
            await callback.answer("Неизвестный тип ставки")
            return

        # 5. Обрабатываем ставку через GameManager (передаем user_db_id)
        success, result_message, bet_data = await game_manager.process_bet(
            session, match_id, user_db_id, selected_player_id, bet_type_enum, bet_value  # ← Используем user_db_id
        )

        if not success:
            await callback.answer(f"❌ {result_message}")
            return

        # 6. Бросок кубика
        dice_roll = random.randint(1, 6)

        # 7. Проверяем, выиграла ли ставка
        bet_won = check_bet(selected_bet_type, dice_roll, bet_value)

        # 8. Создаем запись о ставке
        bet = Bet(
            match_id=match_id,
            user_id=user_db_id,  # ← Используем user_db_id
            player_id=selected_player_id,
            bet_type=selected_bet_type,
            bet_value=bet_value,
            player_position=selected_player_position,
            dice_roll=dice_roll,
            bet_result=BetStatus.WON if bet_won else BetStatus.LOST,
            turn_number=match.current_turn,
            bet_order=current_bet_number
        )

        # 9. Рассчитываем полученные действия
        if bet_won:
            actions = calculate_actions(selected_player_position, selected_bet_type)
            bet.actions_gained = actions

            # Обновляем действия игрока в матче (используем user_db_id)
            match.update_player_actions(user_db_id, actions)  # ← Используем user_db_id

        session.add(bet)

        # 10. Обновляем счетчик ставок в состоянии
        bets_made = state_data.get('bets_made', 0) + 1
        await state.update_data(bets_made=bets_made)

        # 11. Если это первая ставка и можно сделать вторую, предлагаем вторую ставку
        if current_bet_number == 1:
            # Проверяем, можно ли сделать вторую ставку на этого же игрока
            tracker = match.bet_tracker
            available_second = tracker.get_available_bet_types(
                selected_player_id, selected_player_position, True
            )

            if available_second:
                # Можем сделать вторую ставку
                await state.update_data(current_bet_number=2)
                await show_bet_type_selection_second(
                    callback.message, match, selected_player_id, selected_player_position
                )
            else:
                # Вторую ставку сделать нельзя, завершаем ход
                await complete_turn(callback.message, match, state, dice_roll, bet_won)
        else:
            # Вторая ставка сделана, завершаем ход
            await complete_turn(callback.message, match, state, dice_roll, bet_won)

        await session.commit()

    await callback.answer()

async def show_bet_type_selection_second(message: Message, match: Match,
                                         player_id: int, position: str):
    """Показывает выбор второй ставки"""
    # Получаем доступные типы для второй ставки
    tracker = match.bet_tracker
    available_second = tracker.get_available_bet_types(player_id, position, True)

    if not available_second:
        return

    text = f"""{EMOJI['bet']} <b>Выбор второй ставки (2/2)</b>

Вы уже сделали первую ставку.
Теперь выберите вторую ставку (должна быть другого типа):

{EMOJI['info']} <b>Доступные типы для второй ставки:</b>"""

    keyboard_buttons = []
    for bet_type in available_second:  # bet_type здесь - объект BetType (не строка!)
        if bet_type == BetType.EVEN_ODD:  # Используем BetType enum
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="🔢 Чет/Нечет",
                    callback_data=f"bet_type_{match.id}_{player_id}_{bet_type.value}"  # .value!
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
    """Завершает ход и переключает на другого игрока"""
    state_data = await state.get_data()
    selected_player_position = state_data.get('selected_player_position')
    selected_bet_type = state_data.get('selected_bet_type')
    bet_value = state_data.get('bet_value', '')

    # Показываем результат
    await show_bet_result(
        message, match.id, dice_roll, bet_won,
        selected_player_position, selected_bet_type, bet_value
    )

    # Переключаем ход
    async with AsyncSessionLocal() as session:
        db_match = await session.get(Match, match.id)
        db_match.switch_turn()

        # Если переключились на первого игрока, увеличиваем номер хода
        if db_match.current_player_turn == "player1":
            db_match.current_turn += 1

            # Проверяем, не закончилось ли основное время
            if db_match.current_turn > 11 and not db_match.is_extra_time:
                # Начинаем дополнительное время
                await start_extra_time(message, db_match, state)
                return

        await session.commit()

        # Показываем следующий ход
        await show_turn(message, state, match.id, db_match.current_turn)


async def start_extra_time(message: Message, match: Match, state: FSMContext):
    """Начинает дополнительное время"""
    text = f"""{EMOJI['clock']} <b>Дополнительное время!</b>

Матч #{match.id}
Основное время завершено.

{EMOJI['rules']} <b>Правила ДВ:</b>
• Выберите 5 игроков, которые НЕ делали ставок в основном времени
• В ДВ доступны те же типы ставок
• Ходы продолжаются до победы"""

    await message.answer(text, parse_mode='HTML')

    # Начинаем выбор игроков для ДВ
    await state.set_state(MatchStates.SELECTING_EXTRA_TIME_PLAYERS)
    await state.update_data(
        extra_time_selected=[],
        selecting_for_match=match.id
    )

    # Показываем выбор игроков для ДВ
    await show_extra_time_selection(message, match.id, match.get_current_user_id())


async def show_extra_time_selection(message: Message, match_id: int, user_id: int):
    """Показывает выбор игроков для дополнительного времени"""
    async with AsyncSessionLocal() as session:
        # Получаем игроков для ДВ через GameManager
        extra_players = await game_manager.get_extra_time_players(
            session, match_id, user_id
        )

        if len(extra_players) < 5:
            text = f"""{EMOJI['warning']} <b>Недостаточно игроков для ДВ</b>

Нужно 5 игроков, которые не делали ставок в основном времени.
Доступно: {len(extra_players)}/{5}

{EMOJI['info']} Проверьте состав команды."""
            await message.answer(text, parse_mode='HTML')
            return

        text = f"""{EMOJI['clock']} <b>Выбор игроков для ДВ</b>

Выберите 5 игроков из доступных:
{len(extra_players)} игроков не делали ставок в основном времени.

{EMOJI['rules']} <b>Инструкция:</b>
• Нажмите на игроков, чтобы выбрать/отменить
• Нужно выбрать ровно 5 игроков
• После выбора нажмите "Готово"
• Можно отменить выбор кнопкой "Назад\""""

        # Создаем клавиатуру с игроками
        keyboard_buttons = []
        for player in extra_players:
            emoji = get_position_emoji(player.get('position', 'GK'))
            player_name = player.get('name', f"Игрок {player.get('id')}")
            player_num = player.get('number', '?')

            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} {player_name} (#{player_num})",
                    callback_data=f"select_extra_{match_id}_{player['id']}"
                )
            ])

        # Кнопка готово (пока 0/5)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['check']} Готово (0/5)",
                callback_data=f"extra_done_{match_id}"
            )
        ])

        # Кнопка отмены
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['back']} Назад",
                callback_data=f"cancel_extra_{match_id}"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

# Вспомогательные функции (остаются почти без изменений)

async def search_opponent(match_id: int, bot):
    """Поиск соперника для матча"""
    await asyncio.sleep(2)  # Имитация поиска

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)

        if not match or match.status != MatchStatus.WAITING:
            return

        # TODO: Реальная логика поиска соперника
        # Пока просто завершаем с ошибкой
        match.status = MatchStatus.CANCELLED
        await session.commit()

        # Уведомляем пользователя
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


def check_bet(bet_type: str, dice_roll: int, bet_value: str) -> bool:
    """Проверяет, выиграла ли ставка"""
    if bet_type == BetType.EVEN_ODD.value:
        is_even = dice_roll % 2 == 0
        return (bet_value == 'чет' and is_even) or (bet_value == 'нечет' and not is_even)

    elif bet_type == BetType.BIG_SMALL.value:
        is_less = dice_roll <= 3
        return (bet_value == 'меньше' and is_less) or (bet_value == 'больше' and not is_less)

    elif bet_type == BetType.GOAL.value:
        return str(dice_roll) == bet_value

    return False


def calculate_actions(position: str, bet_type: str) -> dict:
    """Рассчитывает полезные действия по правилам"""
    actions = {'goals': 0, 'passes': 0, 'defenses': 0}

    if position == 'GK' and bet_type == BetType.EVEN_ODD.value:
        actions['defenses'] = 3

    elif position == 'DF':
        if bet_type == BetType.EVEN_ODD.value:
            actions['defenses'] = 2
        elif bet_type == BetType.BIG_SMALL.value:
            actions['passes'] = 1
        elif bet_type == BetType.GOAL.value:
            actions['goals'] = 1

    elif position == 'MF':
        if bet_type == BetType.EVEN_ODD.value:
            actions['defenses'] = 1
        elif bet_type == BetType.BIG_SMALL.value:
            actions['passes'] = 2
        elif bet_type == BetType.GOAL.value:
            actions['goals'] = 1

    elif position == 'FW':
        if bet_type == BetType.BIG_SMALL.value:
            actions['passes'] = 1
        elif bet_type == BetType.GOAL.value:
            actions['goals'] = 1

    return actions


async def show_bet_result(message: Message, match_id: int, dice_roll: int,
                          bet_won: bool, position: str, bet_type: str, bet_value: str):
    """Показывает результат ставки"""
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
    """Возвращает имя игрока"""
    if player_id == match.player1_id:
        return "Игрок 1"
    elif player_id == match.player2_id:
        if match.match_type == MatchType.VS_BOT:
            return "Бот"
        else:
            return "Игрок 2"
    return "Неизвестный"


def get_position_emoji(position: str) -> str:
    """Возвращает emoji для позиции"""
    emojis = {
        'GK': '🥅',
        'DF': '🛡️',
        'MF': '⚡',
        'FW': '⚽'
    }
    return emojis.get(position, '👤')


def create_extra_time_keyboard(session, match_id: int, user_id: int,
                               selected_player_ids: List[int]) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора игроков ДВ"""
    # Это заглушка - в реальности нужно получать игроков из БД
    # Пока возвращаем простую клавиатуру

    keyboard_buttons = []

    # Кнопка готово с счетчиком
    keyboard_buttons.append([
        InlineKeyboardButton(
            text=f"{EMOJI['check']} Готово ({len(selected_player_ids)}/5)",
            callback_data=f"extra_done_{match_id}"
        )
    ])

    # Кнопка отмены
    keyboard_buttons.append([
        InlineKeyboardButton(
            text=f"{EMOJI['cancel']} Отмена",
            callback_data=f"cancel_extra_{match_id}"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


async def get_extra_time_players_for_keyboard(session, match_id: int, user_id: int) -> List[Dict]:
    """Возвращает игроков для отображения в клавиатуре ДВ"""
    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        if not match:
            return []

        user = await session.get(User, user_id)
        if not user or not user.team_data:
            return []

        # Получаем игроков через GameManager
        extra_players = await game_manager.get_extra_time_players(
            session, match_id, user_id
        )

        return extra_players

# Регистрация команд (остаются без изменений)
@router.message(Command("matches"))
async def command_matches(message: Message):
    """Список активных матчей"""
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
    """Детали матча по ID"""
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
Чет/нечет: {match.bet_tracker.get_even_odd_count()}/6 игроков"""

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
    """Показывает список матчей"""
    await callback.answer()
    await command_matches(callback.message)


@router.callback_query(F.data.startswith("continue_match_"))
async def continue_match_callback(callback: CallbackQuery, state: FSMContext):
    """Продолжение матча"""
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
    """Отмена матча"""
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


