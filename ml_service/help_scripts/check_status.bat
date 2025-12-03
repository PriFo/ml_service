@echo off
REM Script to check service status
echo ========================================
echo ML Service 0.9.1 - Status Check
echo ========================================
echo.

echo Checking ports...
echo.

REM Check port 8085 (Backend)
netstat -an | findstr ":8085" >nul
if %errorlevel% == 0 (
    echo [OK] Backend listening on port 8085
) else (
    echo [ERROR] Backend NOT running on port 8085
)

REM Check port 6565 (Frontend)
netstat -an | findstr ":6565" >nul
if %errorlevel% == 0 (
    echo [OK] Frontend listening on port 6565
) else (
    echo [ERROR] Frontend NOT running on port 6565
)

echo.
echo Checking project structure...
echo.

if exist "backend\ml_service" (
    echo [OK] Folder backend\ml_service exists
) else (
    echo [ERROR] Folder backend\ml_service NOT found
    if exist "backend\ml_service_new" (
        echo [INFO] Found folder backend\ml_service_new - needs renaming
    )
)

if exist "backend\venv" (
    echo [OK] Backend virtual environment exists
) else (
    echo [WARNING] Backend virtual environment NOT found
)

if exist "frontend\node_modules" (
    echo [OK] Frontend node_modules exists
) else (
    echo [WARNING] Frontend node_modules NOT found
)

if exist ".env" (
    echo [OK] .env file exists
) else (
    echo [WARNING] .env file NOT found
)

echo.
echo Checking Python processes...
tasklist | findstr /i "python.exe" >nul
if %errorlevel% == 0 (
    echo [OK] Python processes running
    tasklist | findstr /i "python.exe"
) else (
    echo [ERROR] Python processes NOT found
)

echo.
echo Checking Node processes...
tasklist | findstr /i "node.exe" >nul
if %errorlevel% == 0 (
    echo [OK] Node processes running
    tasklist | findstr /i "node.exe"
) else (
    echo [ERROR] Node processes NOT found
)

echo.
echo ========================================
echo Status check completed
echo ========================================
echo.
echo If services are not running, use:
echo   START.bat - to start all services
echo   run_backend.bat - backend only
echo   run_frontend.bat - frontend only
echo.
pause
