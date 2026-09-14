#!/usr/bin/env bash
# ==============================================================================
# ⚡ AeroCast-Now AI Pro: Unified Shutdown Script
# ==============================================================================
# Gracefully terminates Backend (FastAPI), Frontend (Vite), and Streamlit.
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$PROJECT_DIR/.pids"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}Stopping AeroCast-Now AI Pro services...${NC}"

# Function to kill process by port
kill_port() {
    local port=$1
    local name=$2
    local pids=$(lsof -ti :$port 2>/dev/null || ss -tulpn | grep ":$port " | grep -o 'pid=[0-9]*' | cut -d= -f2)
    if [ -n "$pids" ]; then
        echo -e "Stopping $name on port $port (PID: $pids)..."
        kill $pids 2>/dev/null || kill -9 $pids 2>/dev/null || true
        echo -e "${GREEN}✓ $name stopped.${NC}"
    else
        echo -e "${YELLOW}[i] No service found running on port $port ($name).${NC}"
    fi
}

# Stop from saved PID files if present
if [ -f "$PID_DIR/backend.pid" ]; then
    kill $(cat "$PID_DIR/backend.pid") 2>/dev/null || true
    rm -f "$PID_DIR/backend.pid"
fi
if [ -f "$PID_DIR/frontend.pid" ]; then
    kill $(cat "$PID_DIR/frontend.pid") 2>/dev/null || true
    rm -f "$PID_DIR/frontend.pid"
fi
if [ -f "$PID_DIR/streamlit.pid" ]; then
    kill $(cat "$PID_DIR/streamlit.pid") 2>/dev/null || true
    rm -f "$PID_DIR/streamlit.pid"
fi

# Fallback: kill by port
kill_port 8000 "FastAPI Backend"
kill_port 5173 "Vite Frontend"
kill_port 8501 "Streamlit Dashboard"

echo -e "\n${GREEN}✓ All AeroCast-Now AI Pro services stopped.${NC}"
