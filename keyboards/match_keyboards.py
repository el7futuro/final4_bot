# handlers/start.py
"""
Обработчики команд старта и основного меню для Final 4.
"""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from sqlalchemy import func, select

from bot.database import AsyncSessionLocal
from models.user import User
from utils.db_helpers import get_user_with_team
from utils.emoji import EMOJI

router = Router(name="start")


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext):
    """
    Обработчик команды /start — регистрация/приветствие пользователя + главное меню.

    Очищает состояние FSM, регистрирует нового пользователя или обновляет
    последнего активного у существующего, показывает приветственный текст
    и основную клавиатуру.
    """
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # Новый пользователь
            user = User(
                telegram_id=user_id,
                username=username,
                first_name=first_name,
                last_name=message.from_user.last_name
            )
            session.add(user)
            await session.commit()

            welcome_text = f"""{EMOJI['welcome']} Добро пожаловать в FINAL 4, {first_name}!

{EMOJI['info']} <b>FINAL 4</b> — это стратегическая футбольная настольная игра, где вы выступаете в роли менеджера.

{EMOJI['rules']} <b>Основные правила:</b>
• Управляйте командой из 16 футболистов
• Делайте ставки на броски кубика
• Используйте карточки «Свисток»
• Соревнуйтесь с другими игроками

{EMOJI['play']} <b>Начните с создания команды!</b>

Используйте команду /team для создания своей команды из 16 футболистов."""
        else:
            # Существующий пользователь
            user.last_active = func.now()
            await session.commit()

            welcome_text = f"""{EMOJI['welcome']} С возвращением, {first_name}!

{EMOJI['stats']} <b>Ваша статистика:</b>
• Игр сыграно: {user.games_played}
• Побед: {user.games_won}
• Процент побед: {user.win_rate:.1f}%

{EMOJI['play']} <b>Что хотите сделать?</b>

Используйте команды:
/play — Начать новую игру
/matches — Мои матчи
/help — Правила игры"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['play']} Играть",
                    callback_data="play_game"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['help']} Помощь",
                    callback_data="show_help"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['profile']} Профиль",
                    callback_data="show_profile"
                ),
                InlineKeyboardButton(
                    text=f"{EMOJI['rules']} Правила",
                    callback_data="show_rules"
                )
            ]
        ]
    )

    await message.answer(
        welcome_text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@router.message(Command("help"))
async def command_help(message: Message):
    """
    Обработчик команды /help — список основных команд и краткая справка.
    """
    help_text = f"""{EMOJI['help']} <b>Помощь по командам:</b>

{EMOJI['play']} <b>Основные команды:</b>
/start — Главное меню
/help — Эта справка
/profile — Ваш профиль
/team — Управление командой
/play — Найти матч
/rules — Правила игры

{EMOJI['info']} <b>Как начать играть?</b>
1. Используйте /team для создания команды из 16 игроков
2. Используйте /play для поиска матча
3. Делайте ставки на броски кубика
4. Используйте карточки «Свисток» для влияния на игру

{EMOJI['rules']} <b>Типы ставок:</b>
• Чет/Нечет — даёт «отбития»
• 1-3/4-6 (Меньше/Больше) — даёт «передачи»
• Точное число — даёт «голы»

{EMOJI['card']} <b>Карточки «Свисток»:</b>
В колоде 40 карточек с различными эффектами.
Берите карточку после успешной ставки.

{EMOJI['support']} <b>Поддержка:</b>
По всем вопросам: @final4_support"""

    await message.answer(help_text, parse_mode='HTML')


@router.message(Command("rules"))
async def command_rules(message: Message):
    """
    Обработчик команды /rules — краткие правила игры + кнопки перехода.
    """
    rules_text = f"""{EMOJI['rules']} <b>Краткие правила FINAL 4:</b>

{EMOJI['target']} <b>Цель игры:</b>
Победить соперника, набрав больше очков за 4 раунда.

{EMOJI['team']} <b>Состав команды:</b>
• 1 вратарь (GK)
• 5 защитников (DF)
• 6 полузащитников (MF)
• 4 нападающих (FW)
Всего: 16 игроков

{EMOJI['formation']} <b>Допустимые формации:</b>
1-5-3-2, 1-5-2-3, 1-4-4-2, 1-4-3-3,
1-3-5-2, 1-3-4-3, 1-3-3-4

{EMOJI['dice']} <b>Ход игры:</b>
1. Менеджер делает ставки на футболистов
2. Бросается кубик (1-6)
3. При успешной ставке футболист получает действия
4. Берется карточка «Свисток»
5. Подсчитываются «отбития», «передачи» и «голы»

{EMOJI['card']} <b>Карточки «Свисток» (40 штук):</b>
• Хэт-трик, Дубль, Гол
• Автогол, ВАР, Офсайд
• Пенальти, Удаление, Предупреждение
• Фол, Потеря, Перехват, Отбор

{EMOJI['calc']} <b>Подсчет результата:</b>
• Из «отбитий» соперника вычитаем свои «передачи»
• Если «передач» >= «отбитий», все «голы» засчитываются
• Если «отбитий» больше, то на их уничтожение тратятся «голы»

{EMOJI['penalty']} <b>При ничьей:</b>
1. Дополнительное время (5 игроков)
2. Серия пенальти
3. Жребий"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['play']} Начать играть",
                    callback_data="play_game"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['help']} Подробная справка",
                    callback_data="detailed_rules"
                )
            ]
        ]
    )

    await message.answer(rules_text, reply_markup=keyboard, parse_mode='HTML')


@router.message(Command("profile"))
async def command_profile(message: Message):
    """
    Обработчик команды /profile — отображение профиля игрока.
    """
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        user, _ = await get_user_with_team(session, user_id)

        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        profile_text = f"""{EMOJI['profile']} <b>Профиль игрока</b>

{EMOJI['user']} <b>Игрок:</b> {user.first_name or 'Аноним'}
{EMOJI['id']} <b>ID:</b> {user.telegram_id}
{EMOJI['rating']} <b>Рейтинг ELO:</b> {user.rating}

{EMOJI['stats']} <b>Статистика:</b>
🎮 Сыграно: {user.games_played}
✅ Побед: {user.games_won}
📊 Процент побед: {user.win_rate:.1f}%

{EMOJI['time']} <b>Активность:</b>
🕒 Последняя активность: {user.last_active.strftime('%d.%m.%Y %H:%M')}"""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['play']} Играть",
                        callback_data="play_game"
                    )
                ]
            ]
        )

        await message.answer(profile_text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data == "show_profile")
async def show_profile_callback(callback: CallbackQuery):
    """
    Callback кнопки «Профиль» — вызывает отображение профиля.
    """
    await callback.answer()
    await command_profile(callback.message)


@router.callback_query(F.data == "show_help")
async def show_help_callback(callback: CallbackQuery):
    """
    Callback кнопки «Помощь» — вызывает справку по командам.
    """
    await callback.answer()
    await command_help(callback.message)


@router.callback_query(F.data == "show_rules")
async def show_rules_callback(callback: CallbackQuery):
    """
    Callback кнопки «Правила» — вызывает краткие правила.
    """
    await callback.answer()
    await command_rules(callback.message)


@router.callback_query(F.data == "detailed_rules")
async def detailed_rules_callback(callback: CallbackQuery):
    """
    Callback кнопки «Подробная справка» — полные правила игры.
    """
    rules_text = f"""{EMOJI['rules']} <b>ПОЛНЫЕ ПРАВИЛА FINAL 4</b>

{EMOJI['target']} <b>Цель игры:</b> Победить соперника.

{EMOJI['format']} <b>Форматы игры:</b>
1. Против случайного соперника
2. Против бота
3. Турнир плей-офф

{EMOJI['team']} <b>Состав команды:</b>
У каждого менеджера 16 футболистов:
• 1 вратарь (GK)
• 5 защитников (DF)
• 6 полузащитников (MF)
• 4 форварда (FW)

{EMOJI['formation']} <b>Допустимые формации:</b>
1-5-3-2, 1-5-2-3, 1-4-4-2, 1-4-3-3,
1-3-5-2, 1-3-4-3, 1-3-3-4

{EMOJI['dice']} <b>Полезные действия:</b>
При успешной ставке менеджера:
• Вратарь: 3 «отбития»
• Защитник: 2 «отбития» или 1 «передача»
• Полузащитник: 1 «отбитие» или 2 «передачи»
• Форвард: 1 «передача»

{EMOJI['bet']} <b>Ставка менеджера:</b>
Перед броском кубика менеджер делает 2 ставки на футболиста:
1. Чет/Нечет → «отбития»
2. 1-3/4-6 (Меньше/Больше) → «передачи»
3. Точное число → «гол»

{EMOJI['limit']} <b>Ограничения ставок:</b>
• Ставка на Чет/Нечет: только у 6 футболистов (включая вратаря)
• Ставка на Чет/Нечет у вратаря: обязательна
• Ставка на гол: 1 защитник, 3 полузащитника, 4 форварда

{EMOJI['card']} <b>Карточки «Свисток» (40 карт):</b>
• Хэт-Трик (1) — 3 гола
• Дубль (1) — 2 гола
• Гол (2) — 1 гол
• Автогол (1) — +1 гол сопернику
• ВАР (2) — отменяет карточку соперника
• Офсайд (2) — отменяет гол соперника
• Пенальти (2) — ставка на Больше/Меньше
• Удаление (2) — потеря всех действий
• Предупреждение (3) — потеря 1 действия
• Фол (6) — потеря «отбития»
• Потеря (6) — потеря «передачи»
• Перехват (6) — +1 «передача»
• Отбор (6) — +1 «отбитие»

{EMOJI['match']} <b>Ход матча:</b>
1. Первый бросает создатель игры
2. Первая ставка всегда на вратаря
3. Карточку берут сразу после успешной ставки
4. Все действия фиксируются

{EMOJI['calc']} <b>Подсчет голов:</b>
1. Берем «отбития» соперника
2. Вычитаем свои «передачи»
3. Если «передач» >= «отбитий» → все «голы» засчитываются
4. Если «отбитий» больше → тратим «голы» (1 гол = 2 отбития)

{EMOJI['example']} <b>Пример расчета:</b>
Команда 1: 2 Г, 6 П, 10 О
Команда 2: 3 Г, 7 П, 6 О

Голы Команды 1: 6о - 6п = 0о → 2 гола
Голы Команды 2: 10о - 7п = 3о → 3о/2 = 1.5 → 1 гол
Итог: 2:1

{EMOJI['extra']} <b>Дополнительное время:</b>
При ничьей назначается ДВ с 5 футболистами из запасных.

{EMOJI['penalty']} <b>Пенальти:</b>
Если ДВ не выявило победителя, проводится серия пенальти."""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['play']} Начать играть",
                    callback_data="play_game"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['back']} Назад",
                    callback_data="show_rules"
                )
            ]
        ]
    )

    await callback.message.edit_text(rules_text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data == "play_game")
async def play_game_callback(callback: CallbackQuery):
    """
    Callback кнопки «Играть» — показывает выбор типа матча.
    """
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала зарегистрируйтесь")
            return

        text = f"{EMOJI['play']} <b>Выберите тип игры:</b>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['vs']} Против случайного соперника",
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
                        callback_data="match_tournament"
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

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    """
    Callback кнопки «Назад» / «Главное меню» — возвращает в стартовое меню.
    """
    await callback.answer()
    await command_start(callback.message, state)