@echo off
REM Unified startup script for ML Service 0.9.1
REM Combines functionality of START and START_UNIFIED
REM Shows logs from both backend and frontend in the same window
REM Press Ctrl+R to restart all services without closing terminal

echo ========================================
echo ML Service 0.9.1 - Unified Startup
echo ========================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Go to project root (one level up from STARTUP)
cd /d ".."

REM Check if we are in the correct directory
if not exist "backend" (
    echo ERROR: Cannot find backend directory
    echo Expected structure: ml_service/backend and ml_service/frontend
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Check and fix structure
if exist "backend\ml_service_new" (
    if not exist "backend\ml_service" (
        echo Fixing project structure...
        ren "backend\ml_service_new" "ml_service"
        if errorlevel 1 (
            echo ERROR: Failed to rename folder
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
    ) else (
        if exist "help_scripts\create_env.py" (
            python help_scripts\create_env.py
        ) else (
            if exist "create_env.py" (
                python create_env.py
            )
        )
    )
    echo.
)

REM Run PowerShell script (from STARTUP directory)
powershell -ExecutionPolicy Bypass -File "%~dp0start_all.ps1"

pause

