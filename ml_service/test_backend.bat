@echo off
REM Quick backend test
echo Testing Backend...
echo.

cd backend

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Checking dependencies...
pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting backend for testing...
echo Press Ctrl+C to stop
echo.
python -m ml_service
