@echo off
REM Script to start frontend on Windows
echo ========================================
echo ML Service 0.9.1 - Frontend
echo ========================================
echo.

REM Change to script directory if called from elsewhere
cd /d "%~dp0"
cd frontend

REM Check node_modules
if not exist "node_modules" (
    echo Installing dependencies...
    call npm install --legacy-peer-deps
)

REM Create .env.local if it doesn't exist
if not exist ".env.local" (
    echo Creating .env.local file...
    (
        echo NEXT_PUBLIC_API_URL=http://localhost:8085
        echo NEXT_PUBLIC_WEBSOCKET_URL=ws://localhost:8085/ws
    ) > .env.local
)

REM Start dev server
echo Starting frontend dev server...
echo Frontend will be available at http://localhost:6565
call npm run dev

pause
