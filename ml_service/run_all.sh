#!/bin/bash
# Script to start backend and frontend simultaneously on Linux/Mac

echo "========================================"
echo "ML Service 0.9.1 - Starting all services"
echo "========================================"

# Cleanup function on exit
cleanup() {
    echo "Stopping services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# Start backend in background
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt
python -m ml_service &
BACKEND_PID=$!
cd ..

# Small delay
sleep 3

# Start frontend in background
cd frontend
if [ ! -d "node_modules" ]; then
    npm install --legacy-peer-deps
fi
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Backend started on http://localhost:8085 (PID: $BACKEND_PID)"
echo "Frontend started on http://localhost:6565 (PID: $FRONTEND_PID)"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait
wait
