# Инструкция по переименованию папок

## Автоматическое переименование

### Windows (PowerShell)
```powershell
# Переименовать старую папку
Rename-Item -Path ml_service -NewName ml_service_old

# Переименовать новую папку
Rename-Item -Path ml_service_new -NewName ml_service
```

### Linux/Mac (Bash)
```bash
# Переименовать старую папку
mv ml_service ml_service_old

# Переименовать новую папку
mv ml_service_new ml_service
```

### Python скрипт
```bash
python rename_folders.py
```

## После переименования

После переименования `ml_service_new` -> `ml_service` нужно обновить импорты в коде:

1. Все файлы в `backend/ml_service_new/` содержат импорты вида:
   ```python
   from ml_service_new.xxx import yyy
   ```

2. После переименования папки структура изменится на:
   ```
   backend/
     ml_service/  # <- переименовано из ml_service_new
       api/
       core/
       ...
   ```

3. Нужно обновить все импорты с `ml_service_new` на `ml_service`:
   ```python
   # Было:
   from ml_service_new.xxx import yyy
   
   # Стало:
   from ml_service.xxx import yyy
   ```

4. Также обновить в `__main__.py`:
   ```python
   # Было:
   uvicorn.run("ml_service_new.api.app:app", ...)
   
   # Стало:
   uvicorn.run("ml_service.api.app:app", ...)
   ```

## Автоматическое обновление импортов

Можно использовать поиск и замену во всех файлах:
- Найти: `ml_service_new`
- Заменить: `ml_service`

Или использовать sed (Linux/Mac):
```bash
find backend/ml_service -name "*.py" -exec sed -i 's/ml_service_new/ml_service/g' {} +
```

