@echo off
REM Script to start backend on Windows
echo ========================================
echo ML Service 0.11.2 - Backend
echo ========================================
echo.

REM Change to script directory if called from elsewhere
cd /d "%~dp0"
cd backend

REM Check virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
echo Upgrading pip, setuptools, and wheel...
python -m pip install --upgrade pip setuptools wheel
echo.
echo Installing dependencies (preferring precompiled wheels)...
echo This may take several minutes for packages that need to build from source...
pip install --prefer-binary --upgrade -r requirements.txt --timeout=300
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to install dependencies!
    echo Please check the error messages above.
    pause
    exit /b 1
)
echo.
echo Dependencies installed successfully!

REM Create .env if it doesn't exist
if not exist "..\.env" (
    echo Creating .env file...
    if exist "..\.env.example" (
        copy ..\.env.example ..\.env
    ) else (
        echo Creating .env from template...
        if exist "..\help_scripts\create_env.py" (
            python ..\help_scripts\create_env.py
        ) else (
            if exist "..\create_env.py" (
                python ..\create_env.py
            ) else (
                echo WARNING: create_env.py not found!
            )
        )
    )
    echo WARNING: Edit .env file with your settings!
    echo Especially important to set ML_ADMIN_API_TOKEN!
    pause
)

REM Start server
echo Starting backend server...
echo API will be available at http://localhost:8085
python -m ml_service

pause
