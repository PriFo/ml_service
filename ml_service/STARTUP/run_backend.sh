#!/bin/bash
# Script to start backend on Linux/Mac

echo "========================================"
echo "ML Service 0.11.2 - Backend"
echo "========================================"

cd backend

# Check virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f "../.env" ]; then
    echo "Creating .env file..."
    if [ -f "../.env.example" ]; then
        cp ../.env.example ../.env
    else
        echo "Creating .env from template..."
        if [ -f "../help_scripts/create_env.py" ]; then
            python3 ../help_scripts/create_env.py
        elif [ -f "../create_env.py" ]; then
            python3 ../create_env.py
        else
            echo "WARNING: create_env.py not found!"
        fi
    fi
    echo "WARNING: Edit .env file with your settings!"
    echo "Especially important to set ML_ADMIN_API_TOKEN!"
    read -p "Press Enter to continue..."
fi

# Start server
echo "Starting backend server..."
echo "API will be available at http://localhost:8085"
python -m ml_service
