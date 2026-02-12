#!/bin/bash
# Script to start frontend on Linux/Mac

echo "========================================"
echo "ML Service 0.11.2 - Frontend"
echo "========================================"

cd frontend

# Check node_modules
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install --legacy-peer-deps
fi

# Create .env.local if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo "Creating .env.local file..."
    cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://localhost:8085
NEXT_PUBLIC_WEBSOCKET_URL=ws://localhost:8085/ws
EOF
fi

# Start dev server
echo "Starting frontend dev server..."
echo "Frontend will be available at http://localhost:6565"
npm run dev
