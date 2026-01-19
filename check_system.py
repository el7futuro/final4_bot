# check_system.py
import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def check_system():
    print("=" * 60)
    print("ПРОВЕРКА СИСТЕМЫ FINAL4 BOT")
    print("=" * 60)

    results = {}

    # 1. Проверка конфигурации
    print("\n1. Проверка конфигурации...")
    try:
        from bot.config import load_config
        config = load_config()
        print(f"   ✅ Конфигурация загружена")
        print(f"      Бот токен: {'ЕСТЬ' if config.bot.token else 'НЕТ!'}")
        print(f"      База данных: {config.db.database}")
        print(f"      Хост: {config.db.host}:{config.db.port}")
        results['config'] = True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        results['config'] = False

    # 2. Проверка моделей
    print("\n2. Проверка моделей...")
    try:
        from models.bet import Bet
        print(f"   ✅ Модель Bet загружена")

        # Комментируем проблемные импорты если нужно
        # from models.user import User
        # print(f"   ✅ Модель User загружена")

        # from models.match import Match
        # print(f"   ✅ Модель Match загружена")

        results['models'] = True
    except Exception as e:
        print(f"   ❌ Ошибка загрузки моделей: {e}")
        print(f"   Внимание на файл models/bet.py строка ~175")
        import traceback
        traceback.print_exc()
        results['models'] = False

    # 3. Проверка базы данных
    print("\n3. Проверка базы данных...")
    try:
        import asyncpg
        from bot.config import load_config

        config = load_config()
        conn = await asyncpg.connect(
            host=config.db.host,
            port=config.db.port,
            user=config.db.user,
            password=config.db.password,
            database=config.db.database
        )

        # Проверяем таблицы
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)

        print(f"   ✅ Подключение к PostgreSQL успешно")
        print(f"   ✅ Таблиц в базе: {len(tables)}")

        for table in tables:
            print(f"      - {table['tablename']}")

        await conn.close()
        results['database'] = True

    except Exception as e:
        print(f"   ❌ Ошибка подключения к БД: {e}")
        results['database'] = False

    # 4. Проверка зависимостей
    print("\n4. Проверка зависимостей...")
    try:
        import sqlalchemy
        print(f"   ✅ SQLAlchemy: {sqlalchemy.__version__}")

        import asyncpg
        print(f"   ✅ asyncpg установлен")

        results['dependencies'] = True
    except ImportError as e:
        print(f"   ❌ Отсутствует зависимость: {e}")
        results['dependencies'] = False

    # Вывод результатов
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ:")
    print("=" * 60)

    all_ok = True
    for test, passed in results.items():
        status = "✅ УСПЕХ" if passed else "❌ ОШИБКА"
        print(f"{test:15} : {status}")
        if not passed:
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ СИСТЕМА ГОТОВА К ЗАПУСКУ!")
        print("\nЗапустите бота командой:")
        print("python -m bot.main")
    else:
        print("❌ ТРЕБУЮТСЯ ИСПРАВЛЕНИЯ")
        print("\nОсновные проблемы:")
        if not results.get('config', False):
            print("- Проверьте файл .env (токен бота, пароль БД)")
        if not results.get('models', False):
            print("- Исправьте models/bet.py (строка ~175)")
        if not results.get('database', False):
            print("- Проверьте подключение к PostgreSQL")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(check_system())