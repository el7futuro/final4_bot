# fix_all.py
import re
from pathlib import Path


file_path = Path("handlers/start.py")
content = file_path.read_text(encoding="utf-8")

# 1. Добавляем select в импорт
if "from sqlalchemy import select" not in content:
    content = content.replace(
        "from sqlalchemy import func",
        "from sqlalchemy import select, func"
    )

# 2. Исправляем ВСЕ session.get(User, user_id)
content = re.sub(
    r'(\s+)user = await session\.get\(User, user_id\)',
    r'\1result = await session.execute(\n\1    select(User).where(User.telegram_id == user_id)\n\1)\n\1user = result.scalar_one_or_none()',
    content
)

# 3. Исправляем ВСЕ team запросы (сложнее, нужно контекст)
lines = content.split('\n')
new_lines = []
i = 0

while i < len(lines):
    line = lines[i]

    # Если находим team = await session.get(Team, user_id)
    if 'team = await session.get(Team, user_id)' in line:
        indent = line[:len(line) - len(line.lstrip())]

        # Проверяем, есть ли user выше в коде
        # Ищем ближайший user выше в том же блоке
        new_lines.append(f"{indent}# Получаем team по id пользователя в БД")
        new_lines.append(f"{indent}if user:")
        new_lines.append(f"{indent}    team = await session.get(Team, user.id)")
        new_lines.append(f"{indent}else:")
        new_lines.append(f"{indent}    team = None")
    else:
        new_lines.append(line)

    i += 1

content = '\n'.join(new_lines)

# Сохраняем
file_path.write_text(content, encoding="utf-8")
print("Файл исправлен!")