#!/usr/bin/env bash
# =============================================================================
# TireAssist — Ubuntu Sandbox Deployment Script
# Run from the project root: bash deploy.sh
# =============================================================================
set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

ok()   { echo -e "${GREEN}✔ $1${RESET}"; }
warn() { echo -e "${YELLOW}⚠ $1${RESET}"; }
fail() { echo -e "${RED}✘ $1${RESET}"; exit 1; }
info() { echo -e "${BOLD}▶ $1${RESET}"; }

echo ""
echo -e "${BOLD}=============================================${RESET}"
echo -e "${BOLD}  TireAssist — Ubuntu Deployment${RESET}"
echo -e "${BOLD}=============================================${RESET}"
echo ""

# =============================================================================
# STEP 1 — Check prerequisites
# =============================================================================
info "Checking prerequisites..."

# Python 3.11+
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo $PY_VER | cut -d. -f1)
    PY_MINOR=$(echo $PY_VER | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        ok "Python $PY_VER"
    else
        warn "Python $PY_VER found — need 3.11+. Installing..."
        sudo apt-get update -qq
        sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
        sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
        ok "Python 3.11 installed"
    fi
else
    warn "Python3 not found. Installing..."
    sudo apt-get update -qq
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
    ok "Python 3.11 installed"
fi

# pip
if ! command -v pip3 &>/dev/null; then
    warn "pip not found. Installing..."
    sudo apt-get install -y python3-pip
fi
ok "pip $(pip3 --version | awk '{print $2}')"

# Node.js 18+
if command -v node &>/dev/null; then
    NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_VER" -ge 18 ]; then
        ok "Node.js $(node -v)"
    else
        warn "Node.js $(node -v) found — need 18+. Upgrading..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
        ok "Node.js $(node -v)"
    fi
else
    warn "Node.js not found. Installing Node 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
    ok "Node.js $(node -v)"
fi

# npm
ok "npm $(npm -v)"

# git
if ! command -v git &>/dev/null; then
    warn "git not found. Installing..."
    sudo apt-get install -y git
fi
ok "git $(git --version | awk '{print $3}')"

echo ""

# =============================================================================
# STEP 2 — Check .env file
# =============================================================================
info "Checking environment configuration..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        warn ".env created from .env.example — YOU MUST ADD YOUR API KEYS before the app will work"
        warn "Edit .env and add: ANTHROPIC_API_KEY=sk-ant-..."
    else
        fail ".env file missing and no .env.example found"
    fi
else
    ok ".env file exists"
fi

# Check required key
if grep -q "^ANTHROPIC_API_KEY=sk-ant-" .env; then
    ok "ANTHROPIC_API_KEY is set"
elif grep -q "^ANTHROPIC_API_KEY=" .env; then
    warn "ANTHROPIC_API_KEY is in .env but appears to be placeholder — app will fail at runtime"
else
    fail "ANTHROPIC_API_KEY not found in .env — required"
fi

# Optional keys
if grep -q "^ELEVENLABS_API_KEY=sk_" .env; then
    ok "ELEVENLABS_API_KEY set (voice enabled)"
else
    warn "ELEVENLABS_API_KEY not set — voice TTS disabled (chat still works)"
fi

if grep -q "^TWILIO_ACCOUNT_SID=AC" .env; then
    ok "TWILIO credentials set (WhatsApp enabled)"
else
    warn "TWILIO_* not set — WhatsApp booking message disabled (booking still works)"
fi

echo ""

# =============================================================================
# STEP 3 — Python virtual environment + dependencies
# =============================================================================
info "Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    ok "Virtual environment created at ./venv"
else
    ok "Virtual environment already exists"
fi

source venv/bin/activate
ok "Virtual environment activated"

info "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Python dependencies installed"

echo ""

# =============================================================================
# STEP 4 — Build React frontend
# =============================================================================
info "Building React frontend..."

cd frontend

if [ ! -d "node_modules" ]; then
    info "Installing npm packages..."
    npm install --silent
    ok "npm packages installed"
else
    ok "node_modules already present"
fi

npm run build --silent
ok "React build complete → frontend/dist/"

cd ..

echo ""

# =============================================================================
# STEP 5 — Verify build output
# =============================================================================
info "Verifying build output..."

if [ -f "frontend/dist/index.html" ]; then
    ok "frontend/dist/index.html exists"
else
    fail "React build failed — frontend/dist/index.html not found"
fi

echo ""

# =============================================================================
# STEP 6 — Start the server
# =============================================================================
info "Starting TireAssist backend on port 8000..."
echo ""
echo -e "${BOLD}  Access the app at:  http://$(hostname -I | awk '{print $1}'):8000${RESET}"
echo -e "${BOLD}  Health check:       http://$(hostname -I | awk '{print $1}'):8000/health${RESET}"
echo -e "${BOLD}  Dashboard:          http://$(hostname -I | awk '{print $1}'):8000/dashboard${RESET}"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
