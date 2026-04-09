#!/usr/bin/env bash
# =============================================================================
# TireAssist — Quick Redeploy (assumes Docker + Postgres already running)
# Run from project root: sudo bash deploy1.sh
# =============================================================================
set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"

ok()   { echo -e "${GREEN}✔${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET} $1"; }
info() { echo -e "${BOLD}▶ $1${RESET}"; }

APP_PORT=$(grep -E "^APP_PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
APP_PORT=${APP_PORT:-8001}

echo ""
echo -e "${BOLD}=============================================${RESET}"
echo -e "${BOLD}  TireAssist — Redeploy${RESET}"
echo -e "${BOLD}=============================================${RESET}"
echo ""

# =============================================================================
# STEP 1 — Kill existing server on APP_PORT
# =============================================================================
info "Step 1 — Freeing port $APP_PORT..."
fuser -k ${APP_PORT}/tcp 2>/dev/null && ok "Port $APP_PORT freed" || ok "Port $APP_PORT was already free"

# =============================================================================
# STEP 2 — Pull latest code
# =============================================================================
info "Step 2 — Pulling latest code..."
git pull
ok "Code up to date"

# =============================================================================
# STEP 3 — Install/update Python dependencies
# =============================================================================
info "Step 3 — Python dependencies..."
source venv/bin/activate
pip install -r requirements.txt -q
ok "Python packages up to date"

# =============================================================================
# STEP 4 — Build React frontend
# =============================================================================
info "Step 4 — Building React frontend..."
cd frontend
npm install --silent
npm run build --silent
cd ..
ok "React build → frontend/dist/"

# =============================================================================
# STEP 5 — Start server
# =============================================================================
HOST_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}${BOLD}=============================================${RESET}"
echo -e "${GREEN}${BOLD}  Ready!${RESET}"
echo -e "${GREEN}${BOLD}=============================================${RESET}"
echo ""
echo -e "  App:        ${BOLD}http://${HOST_IP}:${APP_PORT}${RESET}"
echo -e "  Health:     http://${HOST_IP}:${APP_PORT}/health"
echo -e "  Dashboard:  http://${HOST_IP}:${APP_PORT}/dashboard"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port "$APP_PORT" --workers 1
