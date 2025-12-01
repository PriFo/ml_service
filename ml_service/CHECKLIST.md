# Чеклист готовности проекта

## ✅ Выполнено

### Backend
- [x] Структура проекта создана
- [x] Core компоненты (config, security, GPU detector, scheduler)
- [x] Database (models, repositories, migrations)
- [x] ML Engine (model, feature_store, drift_detector, validators)
- [x] API endpoints (train, predict, quality, models, alerts, drift)
- [x] WebSocket для real-time updates
- [x] Unit тесты (pytest, coverage > 80%)
- [x] Requirements.txt с зависимостями

### Frontend
- [x] Структура Next.js 15 + React 19
- [x] State management (Context API + useReducer)
- [x] API client (Fetch API)
- [x] WebSocket client
- [x] Theme manager (light/dark/system)
- [x] Cookie consent (GDPR)
- [x] Компоненты (Dashboard, AlertBanner, ThemeToggle, ModelSelector, CookieConsent)
- [x] CSS-first animations
- [x] Unit тесты (Jest)
- [x] Package.json с зависимостями

### Инфраструктура
- [x] Dockerfile для backend
- [x] Dockerfile для frontend
- [x] docker-compose.yml
- [x] Скрипты запуска (run_backend.bat/sh, run_frontend.bat/sh, run_all.bat/sh)
- [x] .env.example
- [x] .gitignore
- [x] README.md
- [x] Документация

## ⚠️ Требует внимания

### После переименования папок
1. [ ] Переименовать `ml_service` -> `ml_service_old`
2. [ ] Переименовать `ml_service_new` -> `ml_service`
3. [ ] Обновить все импорты с `ml_service_new` на `ml_service`
4. [ ] Обновить пути в скриптах запуска
5. [ ] Обновить пути в docker-compose.yml

### Перед запуском
1. [ ] Создать `.env` файл из `.env.example`
2. [ ] Установить `ML_ADMIN_API_TOKEN` (минимум 32 символа)
3. [ ] Проверить пути к БД и артефактам
4. [ ] Установить зависимости (backend: `pip install -r requirements.txt`, frontend: `npm install`)

### Тестирование
1. [ ] Запустить backend тесты: `cd backend && pytest`
2. [ ] Запустить frontend тесты: `cd frontend && npm test`
3. [ ] Проверить работу API: `curl http://localhost:8085/health`
4. [ ] Проверить работу frontend: открыть http://localhost:6565

## 🔍 Известные проблемы

### Backend
- [ ] В `repositories.py` используется `parse_date` из `dateutil` - нужно убедиться что библиотека установлена
- [ ] В `routes.py` есть импорт `from ml_service_new.db.models import Model` внутри функции - нужно вынести наверх
- [ ] WebSocket endpoint требует аутентификации - нужно проверить

### Frontend
- [ ] CookieConsent компонент может не отображаться если consent уже установлен
- [ ] WebSocket может не переподключаться при потере соединения

## 📝 Рекомендации

1. **Перед первым запуском:**
   - Прочитайте `RENAME_INSTRUCTIONS.md` для переименования папок
   - Создайте `.env` файл с правильными настройками
   - Установите все зависимости

2. **Для разработки:**
   - Используйте `run_all.bat` или `run_all.sh` для запуска всех сервисов
   - Backend будет на http://localhost:8085
   - Frontend будет на http://localhost:6565

3. **Для production:**
   - Используйте Docker: `docker-compose up --build`
   - Настройте переменные окружения в `.env`
   - Проверьте безопасность токенов

