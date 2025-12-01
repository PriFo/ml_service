# Исправление структуры проекта

## Проблема

После переименования папок возникло несоответствие:
- Папка внутри `backend/` называется `ml_service_new`
- Но импорты в коде используют `ml_service`

## Решение

Нужно переименовать папку `backend/ml_service_new` → `backend/ml_service`

### Windows (PowerShell)
```powershell
cd ml_service\backend
Rename-Item -Path ml_service_new -NewName ml_service
```

### Linux/Mac
```bash
cd ml_service/backend
mv ml_service_new ml_service
```

### Python скрипт
```python
import shutil
from pathlib import Path

backend_dir = Path("ml_service/backend")
old_name = backend_dir / "ml_service_new"
new_name = backend_dir / "ml_service"

if old_name.exists() and not new_name.exists():
    shutil.move(str(old_name), str(new_name))
    print("✓ Папка переименована")
```

## После переименования

После переименования папки все должно работать, так как:
- Импорты уже используют `ml_service`
- `__main__.py` уже использует `ml_service.api.app:app`
- Все файлы уже обновлены

## Проверка

После переименования проверьте:
```bash
cd ml_service/backend
python -m ml_service
```

Должно запуститься без ошибок.

