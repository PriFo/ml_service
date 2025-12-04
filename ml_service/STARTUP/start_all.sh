#!/bin/bash
# Unified startup script for ML Service 0.9.1
# Shows logs from both backend and frontend in the same window
# Press 'r' + Enter to restart all services without closing terminal

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Global variables for process management
BACKEND_PID=""
FRONTEND_PID=""
BACKEND_LOG="/tmp/ml_service_backend_$$.log"
FRONTEND_LOG="/tmp/ml_service_frontend_$$.log"
RESTART_FLAG="/tmp/ml_service_restart_$$.flag"

# Cleanup function
cleanup() {
    echo -e "\n${RED}Stopping services...${NC}"
    stop_services
    rm -f "$BACKEND_LOG" "$FRONTEND_LOG" "$RESTART_FLAG"
    # Kill background processes
    kill "$INPUT_PID" "$LOG_PID" 2>/dev/null
    # Restore terminal
    stty echo icanon 2>/dev/null
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Function to stop services
stop_services() {
    # Stop backend
    if [ ! -z "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null
        wait "$BACKEND_PID" 2>/dev/null
    fi
    
    # Stop frontend
    if [ ! -z "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null
        wait "$FRONTEND_PID" 2>/dev/null
    fi
    
    # Kill any remaining Python processes running ml_service
    pkill -f "python.*ml_service" 2>/dev/null
    
    # Kill any remaining Node processes running next on port 6565
    lsof -ti:6565 2>/dev/null | xargs kill -9 2>/dev/null
    
    # Clean up log files
    rm -f "$BACKEND_LOG" "$FRONTEND_LOG"
    
    sleep 1
}

# Function to start services
start_services() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}ML Service 0.9.1 - Starting Services${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "${GREEN}Backend:  http://localhost:8085${NC}"
    echo -e "${GREEN}Frontend: http://localhost:6565${NC}"
    echo -e "${YELLOW}Type 'r' + Enter to restart services${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop services${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    
    # Stop existing services
    stop_services
    
    # Start backend
    cd "$PROJECT_ROOT/backend" || exit 1
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment and start backend
    source venv/bin/activate
    pip install --prefer-binary --upgrade -r requirements.txt >/dev/null 2>&1
    python -m ml_service > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    
    # Wait a bit before starting frontend
    sleep 3
    
    # Start frontend
    cd "$PROJECT_ROOT/frontend" || exit 1
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "Installing frontend dependencies..."
        npm install --legacy-peer-deps >/dev/null 2>&1
    fi
    
    # Start frontend
    npm run dev > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    
    echo -e "${GREEN}Services started!${NC}"
    echo -e "Backend PID: $BACKEND_PID"
    echo -e "Frontend PID: $FRONTEND_PID"
    echo ""
}

# Function to read user input in background (truly non-blocking)
read_input_background() {
    # Save terminal settings
    stty_save=$(stty -g)
    # Set terminal to raw mode for non-blocking input
    stty -echo -icanon time 0 min 0 2>/dev/null
    
    while true; do
        # Read one character with very short timeout
        char=$(dd bs=1 count=1 2>/dev/null)
        
        if [ "$char" = "r" ] || [ "$char" = "R" ]; then
            # Read next character to check for Enter
            next_char=$(dd bs=1 count=1 2>/dev/null)
            if [ -z "$next_char" ] || [ "$next_char" = $'\n' ] || [ "$next_char" = $'\r' ]; then
                # Enter pressed, set restart flag
                touch "$RESTART_FLAG"
            fi
        fi
        
        # Small sleep to prevent CPU spinning
        sleep 0.05
    done
    
    # Restore terminal (shouldn't reach here, but just in case)
    stty "$stty_save" 2>/dev/null
}

# Function to monitor and display logs
monitor_logs() {
    # Use tail to follow both log files
    tail -f -n +1 "$BACKEND_LOG" "$FRONTEND_LOG" 2>/dev/null | while IFS= read -r line; do
        # Determine source by checking which file the line came from
        if echo "$line" | grep -q "$BACKEND_LOG"; then
            # Remove the filename prefix
            log_line=$(echo "$line" | sed "s|^.*$BACKEND_LOG:||" | sed "s|^.*==>.*<==||")
            if [ ! -z "$log_line" ] && [ "$log_line" != "" ]; then
                echo -e "${YELLOW}[BACKEND]${NC} $log_line"
            fi
        elif echo "$line" | grep -q "$FRONTEND_LOG"; then
            log_line=$(echo "$line" | sed "s|^.*$FRONTEND_LOG:||" | sed "s|^.*==>.*<==||")
            if [ ! -z "$log_line" ] && [ "$log_line" != "" ]; then
                echo -e "${MAGENTA}[FRONTEND]${NC} $log_line"
            fi
        else
            # Try to determine by content patterns
            if echo "$line" | grep -qE "(uvicorn|FastAPI|ml_service|INFO|ERROR|WARNING|DEBUG|Started|Application startup)"; then
                echo -e "${YELLOW}[BACKEND]${NC} $line"
            elif echo "$line" | grep -qE "(next|webpack|ready|compiled|Local:.*6565|wait)"; then
                echo -e "${MAGENTA}[FRONTEND]${NC} $line"
            else
                # Default: show without prefix
                echo "$line"
            fi
        fi
    done
}

# Main execution
cd "$PROJECT_ROOT" || exit 1

# Check if we are in the correct directory
if [ ! -d "backend" ]; then
    echo -e "${RED}ERROR: Cannot find backend directory${NC}"
    echo "Expected structure: ml_service/backend and ml_service/frontend"
    echo "Current directory: $(pwd)"
    exit 1
fi

# Check and fix structure
if [ -d "backend/ml_service_new" ] && [ ! -d "backend/ml_service" ]; then
    echo "Fixing project structure..."
    mv "backend/ml_service_new" "backend/ml_service" || {
        echo -e "${RED}ERROR: Failed to rename folder${NC}"
        exit 1
    }
    echo "Structure fixed!"
    echo ""
fi

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    if [ -f ".env.example" ]; then
        cp ".env.example" ".env"
    elif [ -f "help_scripts/create_env.py" ]; then
        python3 help_scripts/create_env.py
    elif [ -f "create_env.py" ]; then
        python3 create_env.py
    fi
    echo ""
fi

# Start services
start_services

# Start input reader in background (reads from stdin without blocking logs)
# Redirect stdin from /dev/tty to avoid conflicts
read_input_background < /dev/tty &
INPUT_PID=$!

# Start log monitor in background
monitor_logs &
LOG_PID=$!

# Main loop - check for restart requests and service status
while true; do
    # Check for restart flag (non-blocking file check)
    if [ -f "$RESTART_FLAG" ]; then
        rm -f "$RESTART_FLAG"
        echo -e "\n${CYAN}Restart requested - Restarting services...${NC}\n"
        kill "$LOG_PID" 2>/dev/null
        wait "$LOG_PID" 2>/dev/null
        stop_services
        sleep 2
        start_services
        # Restart log monitor
        monitor_logs &
        LOG_PID=$!
    fi
    
    # Check if services are still running
    if [ ! -z "$BACKEND_PID" ] && ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        if [ ! -z "$FRONTEND_PID" ] && ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
            break
        fi
    fi
    
    sleep 0.1
done

# Cleanup
kill "$INPUT_PID" "$LOG_PID" 2>/dev/null
wait "$INPUT_PID" "$LOG_PID" 2>/dev/null

stop_services
rm -f "$BACKEND_LOG" "$FRONTEND_LOG" "$RESTART_FLAG"

echo -e "\n${RED}Services stopped.${NC}"
