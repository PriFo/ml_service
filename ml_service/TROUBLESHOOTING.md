# Решение проблем с подключением

## Проблема: "localhost отказано в подключении"

### Шаг 1: Проверка статуса сервисов

Запустите скрипт проверки:
```powershell
.\check_status.bat
```

Или проверьте вручную:
```powershell
# Проверка портов
netstat -an | findstr ":8085"  # Backend
netstat -an | findstr ":6565"  # Frontend

# Проверка процессов
tasklist | findstr python.exe
tasklist | findstr node.exe
```

### Шаг 2: Проверка окон сервисов

После запуска `START.bat` должны открыться **2 окна**:
1. **"ML Service Backend"** - окно с логами backend
2. **"ML Service Frontend"** - окно с логами frontend

**Если окна не открылись:**
- Проверьте, нет ли ошибок в скрипте
- Запустите сервисы по отдельности

### Шаг 3: Запуск сервисов по отдельности

#### Backend (в отдельном терминале):
```powershell
cd ml_service\backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m ml_service
```

**Ожидаемый вывод:**
```
ML Service 0.9.1 started
API available at http://0.0.0.0:8085
INFO:     Uvicorn running on http://0.0.0.0:8085
```

**Если есть ошибки:**
- Проверьте, что `.env` файл существует
- Проверьте, что все зависимости установлены
- Проверьте структуру папок (`backend\ml_service` должна существовать)

#### Frontend (в отдельном терминале):
```powershell
cd ml_service\frontend
npm install --legacy-peer-deps
npm run dev
```

**Ожидаемый вывод:**
```
- ready started server on 0.0.0.0:6565
- Local: http://localhost:6565
```

### Шаг 4: Проверка подключения

#### Backend:
Откройте в браузере: http://localhost:8085/health

**Ожидаемый ответ:**
```json
{
  "status": "healthy",
  "version": "0.9.1",
  "timestamp": "..."
}
```

#### Frontend:
Open in browser: http://localhost:6565

**Ожидаемый результат:** Откроется интерфейс ML Service

### Шаг 5: Частые проблемы

#### Проблема: "Модуль ml_service не найден"

**Решение:**
```powershell
cd ml_service\backend
# Убедитесь что папка называется ml_service (не ml_service_new)
dir
# Если есть ml_service_new, переименуйте:
Rename-Item ml_service_new ml_service
```

#### Проблема: "Порт уже занят"

**Решение:**
```powershell
# Найти процесс на порту 8085
netstat -ano | findstr :8085
# Убить процесс (замените PID на реальный)
taskkill /PID <PID> /F

# Или измените порт в .env
ML_SERVICE_PORT=8086
```

#### Проблема: "Ошибка при установке зависимостей"

**Backend:**
```powershell
cd ml_service\backend
.\venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Frontend:**
```powershell
cd ml_service\frontend
Remove-Item -Recurse -Force node_modules
npm install --legacy-peer-deps
```

#### Проблема: "База данных не создается"

**Решение:**
```powershell
cd ml_service\backend
.\venv\Scripts\activate
python -c "from ml_service.db.migrations import run_migrations; run_migrations()"
```

### Шаг 6: Логи и отладка

#### Просмотр логов Backend:
Откройте окно "ML Service Backend" и проверьте вывод

#### Просмотр логов Frontend:
Откройте окно "ML Service Frontend" и проверьте вывод

#### Проверка .env файла:
```powershell
# Убедитесь что файл существует
if (Test-Path .env) { Get-Content .env } else { echo ".env не найден" }
```

### Шаг 7: Полный перезапуск

Если ничего не помогает:

```powershell
# 1. Остановите все процессы
taskkill /F /IM python.exe
taskkill /F /IM node.exe

# 2. Удалите виртуальное окружение и пересоздайте
cd ml_service\backend
Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# 3. Удалите node_modules и переустановите
cd ..\frontend
Remove-Item -Recurse -Force node_modules
npm install --legacy-peer-deps

# 4. Запустите заново
cd ..
.\START.bat
```

## Контакты для помощи

Если проблема не решена:
1. Проверьте логи в окнах сервисов
2. Запустите `check_status.bat` и пришлите вывод
3. Проверьте версии Python (должен быть 3.10+) и Node.js (должен быть 18+)

