@echo off
REM Main startup script for ML Service 0.9.1
REM Usage: double-click this file or run START.bat

echo ========================================
echo ML Service 0.9.1 - Starting all services
echo ========================================
echo.

REM Check if we are in the correct directory
if not exist "backend" (
    echo ERROR: Run this script from the project root ml_service/
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Check and fix structure
if exist "backend\ml_service_new" (
    if not exist "backend\ml_service" (
        echo Fixing project structure...
        echo Renaming backend\ml_service_new -^> backend\ml_service
        ren "backend\ml_service_new" "ml_service"
        if errorlevel 1 (
            echo ERROR: Failed to rename folder
            echo Rename manually: backend\ml_service_new -^> backend\ml_service
            pause
            exit /b 1
        )
        echo Structure fixed!
        echo.
    )
)

REM Create .env if it doesn't exist
if not exist ".env" (
    echo Creating .env file...
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo .env created from .env.example
    ) else (
        if exist "create_env.py" (
            python create_env.py
        ) else (
            echo WARNING: .env.example not found, create .env manually
        )
    )
    echo.
)

REM Start backend in separate window using run_backend.bat
echo Starting Backend...
start "ML Service Backend" cmd /k "cd /d %~dp0 && call run_backend.bat"

REM Small delay for backend startup
timeout /t 5 /nobreak >nul

REM Start frontend in separate window using run_frontend.bat
echo Starting Frontend...
start "ML Service Frontend" cmd /k "cd /d %~dp0 && call run_frontend.bat"

echo.
echo ========================================
echo Services started!
echo ========================================
echo Backend:  http://localhost:8085
echo Frontend: http://localhost:6565
echo.
echo To stop services, close the service windows
echo ========================================
pause
