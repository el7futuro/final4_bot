# handlers/start.py
"""
Обработчики команд старта и основного меню для Final 4.
"""

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func

from models.user import User
from models.team import Team
from bot.database import AsyncSessionLocal
from utils.emoji import EMOJI

router = Router(name="start")


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Регистрируем/обновляем пользователя
    async with AsyncSessionLocal() as session:
        # Получаем пользователя по telegram_id
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

            # Проверяем есть ли команда
            # Получаем team по id пользователя в БД
            if user:
                team = await session.get(Team, user.id)
            else:
                team = None

            if not team:
                welcome_text = f"""{EMOJI['welcome']} С возвращением, {first_name}!

У вас ещё нет команды. Для игры нужно создать команду из 16 футболистов.

{EMOJI['rules']} <b>Состав команды:</b>
• 1 вратарь (GK)
• 5 защитников (DF)
• 6 полузащитников (MF)
• 4 нападающих (FW)

Используйте команду /team для создания команды."""
            else:
                welcome_text = f"""{EMOJI['welcome']} С возвращением, {first_name}!

{EMOJI['stats']} <b>Ваша статистика:</b>
🏆 Рейтинг: {user.rating}

🎮 Сыграно матчей: {user.games_played}
✅ Побед: {user.games_won} ({user.win_rate:.1f}%)

{EMOJI['team']} <b>Команда:</b> {team.name}
{EMOJI['formation']} <b>Схема:</b> {team.formation}

{EMOJI['play']} Что будем делать?"""

    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{EMOJI['team']} Моя команда",
                    callback_data="show_team"
                ),
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

    # Отправляем приветственное сообщение
    await message.answer(
        welcome_text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@router.message(Command("help"))
async def command_help(message: Message):
    """Обработчик команды /help"""
    help_text = f"""{EMOJI['help']} <b>Помощь по командам:</b>

{EMOJI['play']} <b>Основные команды:</b>
/start - Главное меню
/help - Эта справка
/profile - Ваш профиль
/team - Управление командой
/play - Найти матч
/rules - Правила игры

{EMOJI['info']} <b>Как начать играть?</b>
1. Используйте /team для создания команды из 16 игроков
2. Используйте /play для поиска матча
3. Делайте ставки на броски кубика
4. Используйте карточки «Свисток» для влияния на игру

{EMOJI['rules']} <b>Типы ставок:</b>
• Чет/Нечет - даёт «отбития»
• 1-3/4-6 (Меньше/Больше) - даёт «передачи»
• Точное число - даёт «голы»

{EMOJI['card']} <b>Карточки «Свисток»:</b>
В колоде 40 карточек с различными эффектами.
Берите карточку после успешной ставки.

{EMOJI['support']} <b>Поддержка:</b>
По всем вопросам: @final4_support"""

    await message.answer(help_text, parse_mode='HTML')


@router.message(Command("rules"))
async def command_rules(message: Message):
    """Обработчик команды /rules (краткие правила)"""
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
    """Обработчик команды /profile"""
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        # Получаем пользователя по telegram_id
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

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
                        text=f"{EMOJI['team']} Моя команда",
                        callback_data="show_team"
                    ),
                    InlineKeyboardButton(
                        text=f"{EMOJI['play']} Играть",
                        callback_data="play_game"
                    )
                ]
            ]
        )

        await message.answer(profile_text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data == "show_team")
async def show_team_callback(callback_query):
    """Обработчик кнопки 'Моя команда'"""
    await callback_query.answer()
    await command_team(callback_query.message)


@router.message(Command("team"))
async def command_team(message: Message):
    """Обработчик команды /team"""
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        # Получаем пользователя по telegram_id
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Сначала зарегистрируйтесь через /start")
            return

        # Получаем team по id пользователя в БД
        if user:
            team = await session.get(Team, user.id)
        else:
            team = None

        if not team:
            # Команда не создана
            text = f"""{EMOJI['team']} <b>Создание команды</b>

У вас ещё нет команды. Для игры нужно создать команду из 16 футболистов.

{EMOJI['rules']} <b>Требования к команде:</b>
• 1 вратарь (GK)
• 5 защитников (DF)
• 6 полузащитников (MF)
• 4 нападающих (FW)

Всего должно быть 16 игроков."""

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{EMOJI['add']} Создать команду",
                            callback_data="create_team"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=f"{EMOJI['help']} Как играть?",
                            callback_data="show_help"
                        )
                    ]
                ]
            )
        else:
            # Показываем существующую команду
            counts = team.get_player_count()
            validation_result, validation_message = team.validate_team()

            text = f"""{EMOJI['team']} <b>Моя команда: {team.name}</b>

{EMOJI['gk']} Вратари: {counts['GK']}/1
{EMOJI['df']} Защитники: {counts['DF']}/5
{EMOJI['mf']} Полузащитники: {counts['MF']}/6
{EMOJI['fw']} Нападающие: {counts['FW']}/4

{EMOJI['formation']} <b>Текущая схема:</b> {team.formation}

{EMOJI['info']} Всего игроков: {sum(counts.values())}/16
{EMOJI['check']} {validation_message}"""

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{EMOJI['list']} Список игроков",
                            callback_data="list_players"
                        ),
                        InlineKeyboardButton(
                            text=f"{EMOJI['formation']} Сменить схему",
                            callback_data="change_formation"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=f"{EMOJI['play']} Играть с этой командой",
                            callback_data="play_game"
                        )
                    ]
                ]
            )

        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data == "create_team")
async def create_team_callback(callback_query):
    telegram_id  = callback_query.from_user.id

    async with AsyncSessionLocal() as session:
        # Получаем пользователя по telegram_id
        from sqlalchemy import select  # убедитесь что импорт есть
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id )
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback_query.answer("Ошибка: пользователь не найден")
            return

        # Проверяем, нет ли уже команды (по user.id, а не user_id!)
        existing_team = await session.get(Team, user.id)  # user.id - это id в БД
        # Получаем team по id пользователя в БД
        if user:
            team = await session.get(Team, user.id)
        else:
            team = None
        if existing_team:
            await callback_query.answer("У вас уже есть команда!")
            return

        # Создаём команду автоматически
        players = []

        # Вратарь
        players.append({
            'id': 1,
            'position': 'GK',
            'name': 'Вратарь',
            'number': 1,
            'skill': {'reflex': 80, 'positioning': 75, 'handling': 78}
        })

        # Защитники (5)
        for i in range(5):
            players.append({
                'id': 2 + i,
                'position': 'DF',
                'name': f'Защитник {i + 1}',
                'number': 2 + i,
                'skill': {'tackle': 75 + i * 2, 'positioning': 72 + i, 'speed': 70 - i}
            })

        # Полузащитники (6)
        for i in range(6):
            players.append({
                'id': 7 + i,
                'position': 'MF',
                'name': f'Полузащитник {i + 1}',
                'number': 7 + i,
                'skill': {'passing': 78 + i * 2, 'dribble': 75 + i, 'stamina': 80 - i}
            })

        # Нападающие (4)
        for i in range(4):
            players.append({
                'id': 13 + i,
                'position': 'FW',
                'name': f'Нападающий {i + 1}',
                'number': 13 + i,
                'skill': {'finishing': 82 + i * 3, 'pace': 80 + i, 'heading': 75 - i}
            })

        team = Team(
            user_id=user.id,  # ✅ ПРАВИЛЬНО: id пользователя в БД
            name=f"Команда {user.first_name or 'Игрока'}",
            players=players
        )
        session.add(team)
        await session.commit()

        await callback_query.answer("✅ Команда создана автоматически!")

        # Обновляем сообщение
        counts = team.get_player_count()
        validation_result, validation_message = team.validate_team()

        text = f"""{EMOJI['team']} <b>Моя команда: {team.name}</b>

{EMOJI['gk']} Вратари: {counts['GK']}/1
{EMOJI['df']} Защитники: {counts['DF']}/5
{EMOJI['mf']} Полузащитники: {counts['MF']}/6
{EMOJI['fw']} Нападающие: {counts['FW']}/4

{EMOJI['formation']} <b>Текущая схема:</b> {team.formation}

{EMOJI['info']} Всего игроков: {sum(counts.values())}/16
{EMOJI['check']} {validation_message}"""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['list']} Список игроков",
                        callback_data="list_players"
                    ),
                    InlineKeyboardButton(
                        text=f"{EMOJI['formation']} Сменить схему",
                        callback_data="change_formation"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['play']} Играть с этой командой",
                        callback_data="play_game"
                    )
                ]
            ]
        )

        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data == "list_players")
async def list_players_callback(callback_query):
    user_id = callback_query.from_user.id

    async with AsyncSessionLocal() as session:
        # Сначала получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback_query.answer("Пользователь не найден")
            return

        # Теперь получаем команду по user.id
        team = await session.get(Team, user.id)

        if not team:
            await callback_query.answer("У вас нет команды")
            return

        players_by_position = {
            'GK': [],
            'DF': [],
            'MF': [],
            'FW': []
        }

        for player in team.players:
            players_by_position[player['position']].append(player)

        text = f"{EMOJI['list']} <b>Состав команды «{team.name}»:</b>\n\n"

        # Вратари
        text += f"{EMOJI['gk']} <b>Вратари:</b>\n"
        for player in players_by_position['GK']:
            text += f"#{player['number']} {player['name']}\n"

        # Защитники
        text += f"\n{EMOJI['df']} <b>Защитники:</b>\n"
        for player in players_by_position['DF']:
            text += f"#{player['number']} {player['name']}\n"

        # Полузащитники
        text += f"\n{EMOJI['mf']} <b>Полузащитники:</b>\n"
        for player in players_by_position['MF']:
            text += f"#{player['number']} {player['name']}\n"

        # Нападающие
        text += f"\n{EMOJI['fw']} <b>Нападающие:</b>\n"
        for player in players_by_position['FW']:
            text += f"#{player['number']} {player['name']}\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['back']} Назад к команде",
                        callback_data="show_team"
                    )
                ]
            ]
        )

        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback_query.answer()


@router.callback_query(F.data == "change_formation")
async def change_formation_callback(callback_query):
    """Смена формации команды"""
    user_id = callback_query.from_user.id

    async with AsyncSessionLocal() as session:
        # Сначала получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback_query.answer("Пользователь не найден")
            return

        # Теперь получаем команду по user.id
        team = await session.get(Team, user.id)

        if not team:
            await callback_query.answer("У вас нет команды")
            return

        possible_formations = team.get_possible_formations()

        text = f"""{EMOJI['formation']} <b>Выбор формации</b>

Текущая формация: {team.formation}

{EMOJI['rules']} <b>Допустимые формации:</b>"""

        for formation in possible_formations:
            text += f"\n• {formation}"

        text += f"\n\n{EMOJI['info']} Выберите новую формацию:"

        # Создаем кнопки для формаций
        keyboard_buttons = []
        for formation in possible_formations:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{formation}",
                    callback_data=f"set_formation_{formation}"
                )
            ])

        # Добавляем кнопку "Назад"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{EMOJI['back']} Назад",
                callback_data="show_team"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback_query.answer()


@router.callback_query(F.data.startswith("set_formation_"))
async def set_formation_callback(callback_query):
    """Установка выбранной формации"""
    formation = callback_query.data.replace("set_formation_", "")
    user_id = callback_query.from_user.id

    async with AsyncSessionLocal() as session:
        # Сначала получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback_query.answer("Пользователь не найден")
            return

        # Теперь получаем команду по user.id
        team = await session.get(Team, user.id)

        if not team:
            await callback_query.answer("Ошибка: команда не найдена")
            return

        if team.set_formation(formation):
            await session.commit()
            await callback_query.answer(f"✅ Формация изменена на {formation}")

            # Возвращаем к информации о команде
            await show_team_callback(callback_query)
        else:
            await callback_query.answer("❌ Неверная формация")


@router.callback_query(F.data == "show_profile")
async def show_profile_callback(callback_query):
    """Обработчик кнопки 'Профиль'"""
    await callback_query.answer()
    await command_profile(callback_query.message)


@router.callback_query(F.data == "show_help")
async def show_help_callback(callback_query):
    """Обработчик кнопки 'Помощь'"""
    await callback_query.answer()
    await command_help(callback_query.message)


@router.callback_query(F.data == "show_rules")
async def show_rules_callback(callback_query):
    """Обработчик кнопки 'Правила'"""
    await callback_query.answer()
    await command_rules(callback_query.message)


@router.callback_query(F.data == "detailed_rules")
async def detailed_rules_callback(callback_query):
    """Подробные правила игры"""
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

    await callback_query.message.edit_text(rules_text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data == "play_game")
async def play_game_callback(callback_query):
    """Обработчик кнопки 'Играть'"""
    user_id = callback_query.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(

            select(User).where(User.telegram_id == user_id)

        )

        user = result.scalar_one_or_none()

        if not user:
            await callback_query.answer("Сначала зарегистрируйтесь")
            return

        # Получаем team по id пользователя в БД
        if user:
            team = await session.get(Team, user.id)
        else:
            team = None

        if not team:
            await callback_query.answer("Сначала создайте команду")
            return

        # Проверяем валидность команды
        is_valid, message = team.validate_team()
        if not is_valid:
            await callback_query.answer(f"Команда не готова: {message}")
            return

        text = f"""{EMOJI['play']} <b>Найти матч</b>

Ваша команда: {team.name}
Формация: {team.formation}

Выберите тип матча:"""

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['vs']} Против случайного соперника",
                        callback_data="match_vs_random"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{EMOJI['bot']} Против бота",
                        callback_data="match_vs_bot"
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

        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

    await callback_query.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback_query):
    """Возврат в главное меню"""
    await callback_query.answer()
    await command_start(callback_query.message, callback_query.bot)