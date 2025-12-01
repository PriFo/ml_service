@echo off
chcp 65001 >nul
echo Инициализация Git репозитория...

git init
if %errorlevel% neq 0 (
    echo Ошибка: Git не установлен или не найден в PATH
    echo Пожалуйста, установите Git с https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Добавление файлов в staging...
git add .

echo Создание начального коммита...
git commit -m "Initial commit: ML Service project"

echo.
echo Git репозиторий успешно инициализирован!
echo.
echo Для создания репозитория на GitHub выполните одну из следующих команд:
echo.
echo 1. Если у вас установлен GitHub CLI (gh):
echo    gh repo create ml_service --public --source=. --remote=origin --push
echo.
echo 2. Или создайте репозиторий вручную на GitHub.com и выполните:
echo    git remote add origin https://github.com/YOUR_USERNAME/ml_service.git
echo    git branch -M main
echo    git push -u origin main
echo.
pause

