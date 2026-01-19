# fix_references.py
from pathlib import Path
import re

file_path = Path("handlers/start.py")
content = file_path.read_text(encoding="utf-8")

# 1. Исправляем create_team_callback
content = re.sub(
    r'async def create_team_callback\(callback_query\):\s*\n\s*user_id = callback_query\.from_user\.id\s*\n\s*async with AsyncSessionLocal\(\) as session:\s*\n\s*user = await session\.get\(User, user_id\)',
    '''async def create_team_callback(callback_query):
    user_id = callback_query.from_user.id

    async with AsyncSessionLocal() as session:
        # Получаем пользователя по telegram_id
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()''',
    content
)

# 2. Исправляем проверку existing_team
content = re.sub(
    r'existing_team = await session\.get\(Team, user_id\)',
    'if user:\n                existing_team = await session.get(Team, user.id)\n            else:\n                existing_team = None',
    content
)

# 3. Исправляем list_players_callback
content = re.sub(
    r'async def list_players_callback\(callback_query\):\s*\n\s*user_id = callback_query\.from_user\.id\s*\n\s*async with AsyncSessionLocal\(\) as session:\s*\n\s*team = await session\.get\(Team, user_id\)',
    '''async def list_players_callback(callback_query):
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
        team = await session.get(Team, user.id)''',
    content
)

# 4. Исправляем change_formation_callback
content = re.sub(
    r'async def change_formation_callback\(callback_query\):\s*\n\s*user_id = callback_query\.from_user\.id\s*\n\s*async with AsyncSessionLocal\(\) as session:\s*\n\s*team = await session\.get\(Team, user_id\)',
    '''async def change_formation_callback(callback_query):
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
        team = await session.get(Team, user.id)''',
    content
)

file_path.write_text(content, encoding="utf-8")
print("Файл исправлен!")