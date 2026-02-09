# test_bot.py
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def test_bot():
    print("=" * 60)
    print("Тестирование компонентов бота")
    print("=" * 60)

    try:
        # 1. Проверка конфигурации
        from bot.config import load_config
        config = load_config()

        print("✅ Конфигурация загружена")
        print(f"   Бот токен: {'установлен' if config.bot.token else 'НЕ УСТАНОВЛЕН!'}")
        print(f"   Админы: {config.bot.admin_ids}")

        if not config.bot.token:
            print("\n❌ Токен бота не установлен!")
            print("Добавьте BOT_TOKEN=ваш_токен в .env файл")
            return False

        # 2. Проверка базы данных
        from bot.database import check_db_connection
        if await check_db_connection():
            print("✅ База данных доступна")
        else:
            print("❌ Проблемы с базой данных")
            return False

        # 3. Проверка моделей
        try:
            from models.user import User

            from models.match import Match
            print("✅ Модели загружены")
        except Exception as e:
            print(f"❌ Ошибка загрузки моделей: {e}")
            return False

        print("\n" + "=" * 60)
        print("✅ ВСЕ КОМПОНЕНТЫ ГОТОВЫ!")
        print("=" * 60)

        print("\nТеперь можете запустить бота командой:")
        print("python -m bot.main")

        return True

    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("\nУстановите зависимости:")
        print("pip install aiogram sqlalchemy asyncpg python-dotenv")
        return False

    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_bot())