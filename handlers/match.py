# handlers/match.py
"""
Обработчики игрового процесса Final 4.
"""
import random
from sqlalchemy import select, and_, or_, func
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from models.user import User
from models.team import Team
from models.match import Match, MatchStatus, MatchType
from models.bet import Bet, BetType, BetStatus
from models.card import CardInstance, CardDeck
from core.game_engine import Final4GameEngine, BetType as EngineBetType
from core.bot_ai import Final4BotAI, BotDifficulty
from bot.database import AsyncSessionLocal
from utils.emoji import EMOJI
import asyncio

router = Router(name="match")


# Состояния FSM для матча
class MatchStates:
    WAITING_FOR_BET = "waiting_for_bet"
    WAITING_FOR_CARD = "waiting_for_card"
    IN_MATCH = "in_match"


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

        # Проверяем команду
        team = await session.get(Team, user_id)
        if not team:
            await message.answer("Сначала создайте команду через /team")
            return

        # Проверяем активный матч
        active_match = await session.execute(
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
            )
        )
        active_match = active_match.scalar_one_or_none()

        if active_match:
            await message.answer(
                f"⚽ У вас уже есть активный матч #{active_match.id}.\n"
                f"Используйте /match_{active_match.id} чтобы продолжить."
            )
            return

        # Показываем меню выбора матча
        text = f"""{EMOJI['play']} <b>Найти матч</b>

{EMOJI['team']} <b>Ваша команда:</b> {team.name}
{EMOJI['formation']} <b>Формация:</b> {team.formation}
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
            status=MatchStatus.WAITING
        )

        # Сохраняем данные команды
        team = await session.get(Team, user_id)
        match.player1_team_data = team.to_dict()
        match.player1_formation = team.formation

        session.add(match)
        await session.commit()

        text = f"""{EMOJI['search']} <b>Поиск соперника...</b>

Матч #{match.id}
Тип: Против случайного соперника
Ваша команда: {team.name}

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


@router.callback_query(F.data == "match_type_vs_bot")
async def match_type_vs_bot(callback: CallbackQuery, state: FSMContext):
    """Выбор сложности бота"""
    text = f"""{EMOJI['bot']} <b>Выберите сложность бота:</b>

1. {EMOJI['easy']} <b>Легкий</b>
   • Случайные ходы
   • Подходит для обучения

2. {EMOJI['medium']} <b>Средний</b>
   • Базовая стратегия
   • Следует правилам

3. {EMOJI['hard']} <b>Сложный</b>
   • Оптимальная стратегия
   • Для опытных игроков"""

    keyboard = InlineKeyboardMarkup(
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

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data.startswith("bot_difficulty_"))
async def create_bot_match(callback: CallbackQuery, state: FSMContext):
    """Создание матча против бота"""
    difficulty = callback.data.split("_")[2]  # easy, medium, hard
    user_id = callback.from_user.id

    difficulty_map = {
        'easy': BotDifficulty.EASY,
        'medium': BotDifficulty.MEDIUM,
        'hard': BotDifficulty.HARD
    }

    async with AsyncSessionLocal() as session:
        # Создаем матч
        match = Match(
            player1_id=user_id,
            match_type=MatchType.VS_BOT,
            status=MatchStatus.CREATED,
            bot_difficulty=difficulty_map[difficulty].value
        )

        # Сохраняем данные команды игрока
        team = await session.get(Team, user_id)
        match.player1_team_data = team.to_dict()
        match.player1_formation = team.formation

        # Создаем команду для бота
        bot_team = create_bot_team(difficulty)
        match.player2_team_data = bot_team
        match.player2_formation = bot_team['formation']

        # Устанавливаем бота как игрока 2
        match.player2_id = -1  # Специальный ID для бота

        session.add(match)
        await session.commit()

        # Сохраняем ID матча в состоянии
        await state.update_data(match_id=match.id)

        text = f"""{EMOJI['bot']} <b>Матч против бота создан!</b>

Матч #{match.id}
Сложность: {difficulty.capitalize()}
Ваша команда: {team.name}
Команда бота: {bot_team['name']}

{EMOJI['rules']} <b>Правила:</b>
• Первым ходит создатель матча
• У бота {difficulty_map[difficulty].value} уровень сложности
• Рейтинг не изменится"""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['play']} Начать матч",
                        callback_data=f"start_match_{match.id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['cancel']} Отменить",
                        callback_data=f"cancel_match_{match.id}"
                    )
                ]
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data.startswith("start_match_"))
async def start_match(callback: CallbackQuery, state: FSMContext):
    """Начало матча"""
    match_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)

        if not match:
            await callback.answer("Матч не найден")
            return

        if not match.is_player_in_match(user_id):
            await callback.answer("Вы не участник этого матча")
            return

        if match.status != MatchStatus.CREATED:
            await callback.answer("Матч уже начат")
            return

        # Начинаем матч
        match.status = MatchStatus.IN_PROGRESS
        match.started_at = func.now()
        match.current_player = match.player1_id  # Первым ходит создатель

        # Создаем колоду карточек для матча
        await create_card_deck_for_match(session, match_id)

        await session.commit()

        # Сохраняем данные в состоянии
        await state.update_data(
            match_id=match_id,
            current_turn=1,
            current_player=match.player1_id
        )
        await state.set_state(MatchStates.IN_MATCH)

        # Показываем первый ход
        await show_turn(callback.message, state, match_id, 1)

    await callback.answer()


async def show_turn(message: Message, state: FSMContext, match_id: int, turn: int):
    """Показывает интерфейс хода"""
    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        user_id = message.from_user.id

        if not match or not match.is_player_in_match(user_id):
            await message.answer("Ошибка доступа к матчу")
            return

        # Проверяем, ход ли игрока
        if match.current_player != user_id:
            text = f"""{EMOJI['wait']} <b>Ожидание хода соперника...</b>

Матч #{match.id}
Ход {turn}/4
Ходит: {get_player_name(match, match.current_player)}

{EMOJI['info']} Ждите, когда соперник сделает ход."""

            await message.answer(text, parse_mode='HTML')
            return

        # Ход игрока
        player_number = match.get_player_number(user_id)
        team_data = match.player1_team_data if player_number == 1 else match.player2_team_data

        text = f"""{EMOJI['dice']} <b>Ваш ход!</b>

Матч #{match.id}
Ход {turn}/4

{EMOJI['team']} <b>Ваша команда:</b> {team_data['name']}
{EMOJI['formation']} <b>Формация:</b> {team_data['formation']}

{EMOJI['rules']} <b>Правила хода:</b>
1. Выберите футболиста
2. Сделайте ставку
3. Бросьте кубик
4. Получите полезные действия
5. Возьмите карточку «Свисток» (если ставка сыграла)"""

        # Получаем доступных для хода игроков
        active_players = get_active_players(team_data)
        available_players = filter_available_players(active_players, turn, match, player_number)

        if not available_players:
            # Нет доступных игроков (невозможно по правилам)
            await message.answer("Ошибка: нет доступных игроков для хода")
            return

        # Показываем кнопки выбора игрока
        keyboard_buttons = []
        for player in available_players[:6]:  # Ограничиваем показ
            emoji = get_position_emoji(player['position'])
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} {player['name']} (#{player['number']})",
                    callback_data=f"select_player_{match_id}_{player['id']}"
                )
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data.startswith("select_player_"))
async def select_player(callback: CallbackQuery, state: FSMContext):
    """Выбор игрока для ставки"""
    parts = callback.data.split("_")
    match_id = int(parts[2])
    player_id = int(parts[3])

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        user_id = callback.from_user.id

        if not match or match.current_player != user_id:
            await callback.answer("Сейчас не ваш ход")
            return

        # Получаем информацию об игроке
        player_number = match.get_player_number(user_id)
        team_data = match.player1_team_data if player_number == 1 else match.player2_team_data

        player = None
        for p in team_data['players']:
            if p['id'] == player_id:
                player = p
                break

        if not player:
            await callback.answer("Игрок не найден")
            return

        # Сохраняем выбранного игрока в состоянии
        await state.update_data(
            selected_player_id=player_id,
            selected_player_position=player['position'],
            selected_player_name=player['name']
        )

        # Показываем выбор типа ставки
        await show_bet_type_selection(callback.message, match_id, player)

    await callback.answer()


async def show_bet_type_selection(message: Message, match_id: int, player: dict):
    """Показывает выбор типа ставки"""
    position = player['position']
    player_name = player['name']

    text = f"""{EMOJI['bet']} <b>Выбор ставки</b>

Игрок: {player_name} (#{player['number']})
Позиция: {position}

{EMOJI['rules']} <b>Доступные ставки:</b>"""

    # Определяем доступные ставки по правилам
    available_bets = []

    if position == 'GK':
        text += "\n• Чет/Нечет → 3 отбития"
        available_bets.append(('odd_even', 'Чет/Нечет', EMOJI['defense']))

    elif position == 'DF':
        text += "\n• Чет/Нечет → 2 отбития"
        text += "\n• Меньше/Больше → 1 передача"
        text += "\n• Точное число → 1 гол"
        available_bets.extend([
            ('odd_even', 'Чет/Нечет', EMOJI['defense']),
            ('less_more', 'Меньше/Больше', EMOJI['pass']),
            ('exact', 'Точное число', EMOJI['goal'])
        ])

    elif position == 'MF':
        text += "\n• Чет/Нечет → 1 отбитие"
        text += "\n• Меньше/Больше → 2 передачи"
        text += "\n• Точное число → 1 гол"
        available_bets.extend([
            ('odd_even', 'Чет/Нечет', EMOJI['defense']),
            ('less_more', 'Меньше/Больше', EMOJI['pass']),
            ('exact', 'Точное число', EMOJI['goal'])
        ])

    elif position == 'FW':
        text += "\n• Меньше/Больше → 1 передача"
        text += "\n• Точное число → 1 гол"
        available_bets.extend([
            ('less_more', 'Меньше/Больше', EMOJI['pass']),
            ('exact', 'Точное число', EMOJI['goal'])
        ])

    # Создаем кнопки
    keyboard_buttons = []
    for bet_type, bet_name, emoji in available_bets:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {bet_name}",
                callback_data=f"select_bet_{match_id}_{bet_type}"
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data.startswith("select_bet_"))
async def select_bet_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа ставки"""
    parts = callback.data.split("_")
    match_id = int(parts[2])
    bet_type = parts[3]  # odd_even, less_more, exact

    # Сохраняем тип ставки
    await state.update_data(selected_bet_type=bet_type)

    # Показываем выбор значения ставки
    await show_bet_value_selection(callback.message, match_id, bet_type)

    await callback.answer()


async def show_bet_value_selection(message: Message, match_id: int, bet_type: str):
    """Показывает выбор значения ставки"""
    if bet_type == 'odd_even':
        text = f"""{EMOJI['bet']} <b>Выберите значение:</b>

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

    elif bet_type == 'less_more':
        text = f"""{EMOJI['bet']} <b>Выберите значение:</b>

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

    else:  # exact
        text = f"""{EMOJI['bet']} <b>Выберите число:</b>

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

    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data.startswith("bet_value_"))
async def process_bet(callback: CallbackQuery, state: FSMContext):
    """Обработка ставки и бросок кубика"""
    parts = callback.data.split("_")
    match_id = int(parts[2])
    bet_value = parts[3]

    user_id = callback.from_user.id
    state_data = await state.get_data()

    selected_player_id = state_data.get('selected_player_id')
    selected_player_position = state_data.get('selected_player_position')
    selected_bet_type = state_data.get('selected_bet_type')

    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)

        if not match or match.current_player != user_id:
            await callback.answer("Сейчас не ваш ход")
            return

        # Бросок кубика
        import random
        dice_roll = random.randint(1, 6)

        # Проверяем ставку
        bet_won = check_bet(selected_bet_type, dice_roll, bet_value)

        # Создаем запись о ставке
        bet = Bet(
            match_id=match_id,
            user_id=user_id,
            player_id=selected_player_id,
            bet_type=selected_bet_type,
            bet_value=bet_value,
            player_position=selected_player_position,
            dice_roll=dice_roll,
            bet_result=BetStatus.WON if bet_won else BetStatus.LOST,
            turn_number=match.current_turn,
            bet_order=1  # TODO: считать порядок ставки
        )

        # Рассчитываем полученные действия
        if bet_won:
            actions = calculate_actions(selected_player_position, selected_bet_type)
            bet.actions_gained = actions

            # Обновляем действия игрока в матче
            player_number = match.get_player_number(user_id)
            if player_number == 1:
                current = match.player1_actions
                for key, value in actions.items():
                    current[key] += value
                match.player1_actions = current
            else:
                current = match.player2_actions
                for key, value in actions.items():
                    current[key] += value
                match.player2_actions = current

        session.add(bet)

        # Если ставка выиграла, берем карточку
        if bet_won:
            card = await draw_card(session, match_id)
            if card:
                # TODO: Обработка карточки
                pass

        # Передаем ход
        match.current_player = match.get_opponent_id(user_id)

        # Если оба игрока сделали по ставке, завершаем ход
        # TODO: Реализовать логику завершения хода

        await session.commit()

        # Показываем результат
        await show_bet_result(
            callback.message,
            match_id,
            dice_roll,
            bet_won,
            selected_player_position,
            selected_bet_type,
            bet_value
        )

    await callback.answer()


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


# Вспомогательные функции
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


def create_bot_team(difficulty: str) -> dict:
    """Создает команду для бота"""
    formations = ['1-4-4-2', '1-4-3-3', '1-5-3-2']

    return {
        'name': f'Бот ({difficulty.capitalize()})',
        'formation': random.choice(formations),
        'players': [
            # TODO: Создать полную команду из 16 игроков
        ]
    }


async def create_card_deck_for_match(session, match_id: int):
    """Создает колоду карточек для матча"""
    # TODO: Реализовать создание колоды из 40 карточек
    pass


def get_active_players(team_data: dict) -> list:
    """Возвращает активных игроков по формации"""
    formation = team_data['formation'].split('-')
    gk_needed = int(formation[0])
    df_needed = int(formation[1])
    mf_needed = int(formation[2])
    fw_needed = int(formation[3])

    active = []
    counts = {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}

    for player in team_data['players']:
        pos = player['position']
        if counts[pos] < {'GK': gk_needed, 'DF': df_needed,
                          'MF': mf_needed, 'FW': fw_needed}[pos]:
            active.append(player)
            counts[pos] += 1

    return active


def filter_available_players(players: list, turn: int, match, player_number: int) -> list:
    """Фильтрует игроков по правилам ставок"""
    # TODO: Реализовать полную логику фильтрации по правилам
    if turn == 1:
        # Первый ход - только вратарь
        return [p for p in players if p['position'] == 'GK']

    # Последующие ходы - все кроме вратаря
    return [p for p in players if p['position'] != 'GK']


def check_bet(bet_type: str, dice_roll: int, bet_value: str) -> bool:
    """Проверяет, выиграла ли ставка"""
    if bet_type == 'odd_even':
        is_even = dice_roll % 2 == 0
        return (bet_value == 'чет' and is_even) or (bet_value == 'нечет' and not is_even)

    elif bet_type == 'less_more':
        is_less = dice_roll <= 3
        return (bet_value == 'меньше' and is_less) or (bet_value == 'больше' and not is_less)

    elif bet_type == 'exact':
        return str(dice_roll) == bet_value

    return False


def calculate_actions(position: str, bet_type: str) -> dict:
    """Рассчитывает полезные действия по правилам"""
    actions = {'goals': 0, 'passes': 0, 'defenses': 0}

    if position == 'GK' and bet_type == 'odd_even':
        actions['defenses'] = 3

    elif position == 'DF':
        if bet_type == 'odd_even':
            actions['defenses'] = 2
        elif bet_type == 'less_more':
            actions['passes'] = 1
        elif bet_type == 'exact':
            actions['goals'] = 1

    elif position == 'MF':
        if bet_type == 'odd_even':
            actions['defenses'] = 1
        elif bet_type == 'less_more':
            actions['passes'] = 2
        elif bet_type == 'exact':
            actions['goals'] = 1

    elif position == 'FW':
        if bet_type == 'less_more':
            actions['passes'] = 1
        elif bet_type == 'exact':
            actions['goals'] = 1

    return actions


async def draw_card(session, match_id: int):
    """Вытягивает карточку из колоды"""
    # TODO: Реализовать вытягивание карточки
    return None


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


# Регистрация команд
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
Тип: {match.match_type.value}
Статус: {match.status.value}
Создан: {match.created_at.strftime('%d.%m.%Y %H:%M')}

{EMOJI['score']} <b>Счет:</b>
{match.player1_score} : {match.player2_score}

{EMOJI['turn']} <b>Ход:</b> {match.current_turn}/4
{EMOJI['player']} <b>Ходит:</b> {get_player_name(match, match.current_player)}"""

        keyboard_buttons = []

        if match.status == MatchStatus.CREATED:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{EMOJI['play']} Начать матч",
                    callback_data=f"start_match_{match.id}"
                )
            ])

        elif match.status == MatchStatus.IN_PROGRESS:
            if match.current_player == user_id:
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