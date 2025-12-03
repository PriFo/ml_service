@echo off
REM Quick frontend test
echo Testing Frontend...
echo.

cd frontend

if not exist "node_modules" (
    echo Installing dependencies...
    call npm install --legacy-peer-deps
)

echo.
echo Starting frontend for testing...
echo Press Ctrl+C to stop
echo.
call npm run dev
