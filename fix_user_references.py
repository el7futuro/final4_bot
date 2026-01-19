# fix_user_references.py
from pathlib import Path

file_path = Path("handlers/start.py")
content = file_path.read_text(encoding="utf-8")

# 1. Исправляем change_formation_callback
old_change_formation = '''@router.callback_query(F.data == "change_formation")
async def change_formation_callback(callback_query):
    """Смена формации команды"""
    user_id = callback_query.from_user.id

    async with AsyncSessionLocal() as session:
        # Получаем team по id пользователя в БД
        if user:
            team = await session.get(Team, user.id)
        else:
            team = None

        if not team:
            await callback_query.answer("У вас нет команды")
            return'''

new_change_formation = '''@router.callback_query(F.data == "change_formation")
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
            return'''

content = content.replace(old_change_formation, new_change_formation)

# 2. Исправляем set_formation_callback
old_set_formation = '''@router.callback_query(F.data.startswith("set_formation_"))
async def set_formation_callback(callback_query):
    """Установка выбранной формации"""
    formation = callback_query.data.replace("set_formation_", "")
    user_id = callback_query.from_user.id

    async with AsyncSessionLocal() as session:
        # Получаем team по id пользователя в БД
        if user:
            team = await session.get(Team, user.id)
        else:
            team = None

        if not team:
            await callback_query.answer("Ошибка: команда не найдена")
            return'''

new_set_formation = '''@router.callback_query(F.data.startswith("set_formation_"))
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
            return'''

content = content.replace(old_set_formation, new_set_formation)

# 3. Убираем дублирование в list_players_callback
content = content.replace(
    '''# Теперь получаем команду по user.id
        team = await session.get(Team, user.id)
        if user:
            team = await session.get(Team, user.id)
        else:
            team = None''',
    '''# Теперь получаем команду по user.id
        team = await session.get(Team, user.id)'''
)

# 4. Убираем лишние импорты select внутри функций
# У вас есть "from sqlalchemy import select" внутри некоторых функций
# Это лишнее, так как select уже импортирован в начале файла
content = content.replace(
    '        from sqlalchemy import select\n\n        # Получаем пользователя по telegram_id',
    '        # Получаем пользователя по telegram_id'
)

file_path.write_text(content, encoding="utf-8")
print("Файл исправлен!")