@echo off
chcp 65001 >nul
echo ========================================
echo Генерация SSL сертификата для HTTPS
echo ========================================
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Ошибка: Python не найден в PATH
    echo Убедитесь, что Python установлен и добавлен в PATH
    pause
    exit /b 1
)

echo Генерация самоподписанного SSL сертификата...
echo.
python -m ml_service.core.generate_ssl_cert

echo.
pause

