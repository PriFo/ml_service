@echo off
REM Helper script to install dependencies with proper wheel handling
echo Upgrading pip...
python -m pip install --upgrade pip setuptools wheel

echo.
echo Installing dependencies with preference for precompiled wheels...
pip install --prefer-binary --upgrade -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo WARNING: Some packages failed to install with precompiled wheels.
    echo Attempting to install remaining packages...
    pip install -r requirements.txt
)

echo.
echo Dependency installation completed.

