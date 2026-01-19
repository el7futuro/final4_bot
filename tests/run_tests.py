# tests/run_tests.py
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_tests():
    """Запуск всех тестов"""
    print("=" * 60)
    print("ЗАПУСК ВСЕХ ТЕСТОВ ПРОЕКТА")
    print("=" * 60)

    results = {}

    # Тест 1: Конфигурация
    print("\n1. Тестирование конфигурации...")
    try:
        from tests.test_config import test_config_loading
        test_config_loading()
        results['config'] = "✅ УСПЕХ"
        print("   ✅ Успешно")
    except Exception as e:
        results['config'] = f"❌ ОШИБКА: {e}"
        print(f"   ❌ Ошибка: {e}")

    # Тест 2: Модели
    print("\n2. Тестирование моделей...")
    try:
        from tests.test_models import test_models_import
        test_models_import()
        results['models'] = "✅ УСПЕХ"
        print("   ✅ Успешно")
    except Exception as e:
        results['models'] = f"❌ ОШИБКА: {e}"
        print(f"   ❌ Ошибка: {e}")

    # Тест 3: База данных (асинхронный)
    print("\n3. Тестирование базы данных...")
    try:
        from tests.test_database import run_all_tests as run_db_tests
        db_success = asyncio.run(run_db_tests())
        results['database'] = "✅ УСПЕХ" if db_success else "❌ ОШИБКА"
        print("   ✅ Успешно" if db_success else "   ❌ Ошибка")
    except Exception as e:
        results['database'] = f"❌ ОШИБКА: {e}"
        print(f"   ❌ Ошибка: {e}")

    print("\n" + "=" * 60)
    print("СВОДКА РЕЗУЛЬТАТОВ:")
    print("=" * 60)

    for test_name, result in results.items():
        print(f"{test_name:15} : {result}")

    # Проверяем все ли тесты пройдены
    all_passed = all("✅" in result for result in results.values())

    if all_passed:
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        print("\nПроект готов к запуску.")
        print("Запустите бота: python -m bot.main")
        return True
    else:
        print("\n" + "=" * 60)
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        print("=" * 60)
        print("\nИсправьте ошибки перед запуском бота.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)