#!/usr/bin/env bash
# ==============================================================================
# ⚡ AeroCast-Now AI Pro: Unified Startup Script
# ==============================================================================
# Starts both the FastAPI REST Backend (port 8000) and React Frontend (port 5173).
# Pass --streamlit to also launch the Streamlit Pro Dashboard (port 8501).
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/venv"
PID_DIR="$PROJECT_DIR/.pids"

mkdir -p "$PID_DIR"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================================${NC}"
echo -e "${CYAN}⚡ Starting AeroCast-Now AI Pro System${NC}"
echo -e "${BLUE}================================================================${NC}"

# 1. Check Virtual Environment
if [ -d "$VENV_DIR" ]; then
    PYTHON_BIN="$VENV_DIR/bin/python"
    UVICORN_BIN="$VENV_DIR/bin/uvicorn"
    STREAMLIT_BIN="$VENV_DIR/bin/streamlit"
else
    echo -e "${YELLOW}[!] venv not found at $VENV_DIR. Falling back to system python3.${NC}"
    PYTHON_BIN="$(which python3)"
    UVICORN_BIN="$(which uvicorn)"
    STREAMLIT_BIN="$(which streamlit)"
fi

# 2. Start Backend (FastAPI REST Server)
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 || ss -tulpn | grep -q ":8000 "; then
    echo -e "${YELLOW}[i] Backend already running on port 8000.${NC}"
else
    echo -e "${CYAN}[*] Starting FastAPI Backend on http://0.0.0.0:8000 ...${NC}"
    cd "$BACKEND_DIR"
    nohup "$PYTHON_BIN" -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload > "$PROJECT_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$PID_DIR/backend.pid"
    echo -e "${GREEN}[✓] Backend started (PID: $BACKEND_PID). Log: backend.log${NC}"
fi

# 3. Start Frontend (React + Vite)
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1 || ss -tulpn | grep -q ":5173 "; then
    echo -e "${YELLOW}[i] Frontend already running on port 5173.${NC}"
else
    echo -e "${CYAN}[*] Starting Vite Frontend on http://localhost:5173 ...${NC}"
    cd "$FRONTEND_DIR"
    nohup npm run dev -- --host 0.0.0.0 --port 5173 > "$PROJECT_DIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > "$PID_DIR/frontend.pid"
    echo -e "${GREEN}[✓] Frontend started (PID: $FRONTEND_PID). Log: frontend.log${NC}"
fi

# 4. Optional Streamlit Pro Meteorological Dashboard
if [[ "$*" == *"--streamlit"* ]]; then
    if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null 2>&1 || ss -tulpn | grep -q ":8501 "; then
        echo -e "${YELLOW}[i] Streamlit already running on port 8501.${NC}"
    else
        echo -e "${CYAN}[*] Starting Streamlit Dashboard on http://localhost:8501 ...${NC}"
        cd "$BACKEND_DIR"
        nohup "$STREAMLIT_BIN" run app.py --server.port 8501 --server.headless true > "$PROJECT_DIR/streamlit.log" 2>&1 &
        STREAMLIT_PID=$!
        echo "$STREAMLIT_PID" > "$PID_DIR/streamlit.pid"
        echo -e "${GREEN}[✓] Streamlit started (PID: $STREAMLIT_PID). Log: streamlit.log${NC}"
    fi
fi

# 5. Service Health Verification
echo -e "\n${CYAN}[*] Verifying services...${NC}"
sleep 2

# Check Backend Health
BACKEND_OK=0
for i in {1..10}; do
    if curl -s http://localhost:8000/api/health | grep -q "operational"; then
        BACKEND_OK=1
        break
    fi
    sleep 1
done

if [ $BACKEND_OK -eq 1 ]; then
    echo -e "  ${GREEN}✓ Backend REST API:${NC}      http://localhost:8000"
    echo -e "  ${GREEN}✓ Interactive API Docs:${NC}  http://localhost:8000/docs"
else
    echo -e "  ${YELLOW}! Backend is warming up... Check backend.log if issues persist.${NC}"
fi

# Check Frontend
if curl -s -I http://localhost:5173 | grep -q "200 OK"; then
    echo -e "  ${GREEN}✓ React 3D Web App:${NC}      http://localhost:5173"
else
    echo -e "  ${YELLOW}! Frontend is starting up... Check frontend.log.${NC}"
fi

if [[ "$*" == *"--streamlit"* ]]; then
    echo -e "  ${GREEN}✓ Streamlit Workbench:${NC}   http://localhost:8501"
fi

echo -e "\n${BLUE}================================================================${NC}"
echo -e "${GREEN}🎉 AeroCast-Now AI Pro is active!${NC}"
echo -e "To stop all services later, run: ${CYAN}./stop_all.sh${NC}"
echo -e "${BLUE}================================================================${NC}"
