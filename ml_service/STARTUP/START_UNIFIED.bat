@echo off
REM Unified startup script for ML Service 0.9.1
REM Shows logs from both backend and frontend in the same window

echo ========================================
echo ML Service 0.9.1 - Unified Startup
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
        if exist "create_env.py" (
            python create_env.py
        )
    )
    echo.
)

REM Run PowerShell script
powershell -ExecutionPolicy Bypass -File "%~dp0start_unified.ps1"

pause
