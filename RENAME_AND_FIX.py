"""Скрипт для переименования папок и обновления импортов"""
import os
import shutil
import re
from pathlib import Path

def rename_folders():
    """Переименовать папки"""
    base_dir = Path(".")
    
    # Переименовать ml_service -> ml_service_old
    if (base_dir / "ml_service").exists() and not (base_dir / "ml_service_old").exists():
        print("Переименовываю ml_service -> ml_service_old...")
        shutil.move(str(base_dir / "ml_service"), str(base_dir / "ml_service_old"))
        print("✓ Готово")
    
    # Переименовать ml_service_new -> ml_service
    if (base_dir / "ml_service_new").exists():
        print("Переименовываю ml_service_new -> ml_service...")
        shutil.move(str(base_dir / "ml_service_new"), str(base_dir / "ml_service"))
        print("✓ Готово")

def update_imports():
    """Обновить все импорты с ml_service_new на ml_service"""
    base_dir = Path("ml_service")
    
    if not base_dir.exists():
        print("Папка ml_service не найдена! Сначала переименуйте папки.")
        return
    
    # Найти все Python файлы
    python_files = list(base_dir.rglob("*.py"))
    
    updated_count = 0
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Заменить импорты
            new_content = content.replace('ml_service_new', 'ml_service')
            
            if content != new_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                updated_count += 1
                print(f"Обновлен: {file_path}")
        except Exception as e:
            print(f"Ошибка при обработке {file_path}: {e}")
    
    print(f"\n✓ Обновлено файлов: {updated_count}")

if __name__ == "__main__":
    print("=" * 50)
    print("Переименование папок и обновление импортов")
    print("=" * 50)
    
    rename_folders()
    update_imports()
    
    print("\n" + "=" * 50)
    print("Готово! Теперь можно запускать проект.")
    print("=" * 50)

