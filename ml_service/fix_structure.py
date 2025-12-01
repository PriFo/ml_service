"""Скрипт для исправления структуры проекта"""
import shutil
from pathlib import Path

def fix_structure():
    """Переименовать backend/ml_service_new -> backend/ml_service"""
    backend_dir = Path("backend")
    old_name = backend_dir / "ml_service_new"
    new_name = backend_dir / "ml_service"
    
    if not backend_dir.exists():
        print("❌ Папка backend не найдена!")
        print("   Запустите скрипт из корня проекта ml_service/")
        return False
    
    if not old_name.exists():
        if new_name.exists():
            print("✓ Структура уже исправлена (папка ml_service существует)")
            return True
        else:
            print("❌ Папка ml_service_new не найдена в backend/")
            return False
    
    if new_name.exists():
        print("⚠️  Папка ml_service уже существует!")
        print("   Удалите одну из папок вручную")
        return False
    
    print("Переименовываю backend/ml_service_new -> backend/ml_service...")
    try:
        shutil.move(str(old_name), str(new_name))
        print("✓ Папка успешно переименована")
        return True
    except Exception as e:
        print(f"❌ Ошибка при переименовании: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Исправление структуры проекта")
    print("=" * 50)
    
    success = fix_structure()
    
    if success:
        print("\n" + "=" * 50)
        print("✓ Структура исправлена!")
        print("Теперь можно запускать проект:")
        print("  Windows: run_all.bat")
        print("  Linux/Mac: ./run_all.sh")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("❌ Не удалось исправить структуру")
        print("Проверьте структуру папок вручную")
        print("=" * 50)

