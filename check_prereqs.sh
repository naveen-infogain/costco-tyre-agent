#!/usr/bin/env bash
# =============================================================================
# TireAssist — Prerequisites Checker
# Run this FIRST on your Ubuntu sandbox to see what needs installing.
# Does NOT install anything — read-only check.
# Usage: bash check_prereqs.sh
# =============================================================================

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

ok()   { echo -e "  ${GREEN}✔${RESET}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${RESET}  $1"; }
fail() { echo -e "  ${RED}✘${RESET}  $1"; }

echo ""
echo -e "${BOLD}TireAssist — Prerequisites Check${RESET}"
echo "================================="
echo ""

ISSUES=0

# ── Python ──────────────────────────────────────────────────────────────────
echo -e "${BOLD}Python${RESET}"
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        ok "Python $PY_VER  (need 3.11+)"
    else
        fail "Python $PY_VER  — need 3.11+  →  sudo apt install python3.11"
        ISSUES=$((ISSUES+1))
    fi
else
    fail "Python3 not found  →  sudo apt install python3.11"
    ISSUES=$((ISSUES+1))
fi

if command -v pip3 &>/dev/null; then
    ok "pip $(pip3 --version | awk '{print $2}')"
else
    fail "pip not found  →  sudo apt install python3-pip"
    ISSUES=$((ISSUES+1))
fi

if python3 -m venv --help &>/dev/null 2>&1; then
    ok "python3-venv available"
else
    fail "python3-venv missing  →  sudo apt install python3.11-venv"
    ISSUES=$((ISSUES+1))
fi
echo ""

# ── Node.js / npm ────────────────────────────────────────────────────────────
echo -e "${BOLD}Node.js / npm${RESET}"
if command -v node &>/dev/null; then
    NODE_VER=$(node -v)
    NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        ok "Node.js $NODE_VER  (need 18+)"
    else
        fail "Node.js $NODE_VER — need 18+  →  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash - && sudo apt install nodejs"
        ISSUES=$((ISSUES+1))
    fi
else
    fail "Node.js not found  →  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash - && sudo apt install nodejs"
    ISSUES=$((ISSUES+1))
fi

if command -v npm &>/dev/null; then
    ok "npm $(npm -v)"
else
    fail "npm not found (installed with Node.js)"
    ISSUES=$((ISSUES+1))
fi
echo ""

# ── Git ──────────────────────────────────────────────────────────────────────
echo -e "${BOLD}Git${RESET}"
if command -v git &>/dev/null; then
    ok "git $(git --version | awk '{print $3}')"
else
    warn "git not found  →  sudo apt install git  (needed to clone repo)"
fi
echo ""

# ── .env file ────────────────────────────────────────────────────────────────
echo -e "${BOLD}.env Configuration${RESET}"
if [ -f ".env" ]; then
    ok ".env file exists"
    if grep -q "^ANTHROPIC_API_KEY=sk-ant-" .env; then
        ok "ANTHROPIC_API_KEY is set  ← required"
    else
        fail "ANTHROPIC_API_KEY missing or not set  ← app won't start without this"
        ISSUES=$((ISSUES+1))
    fi
    if grep -q "^ELEVENLABS_API_KEY=sk_" .env; then
        ok "ELEVENLABS_API_KEY set  (voice enabled)"
    else
        warn "ELEVENLABS_API_KEY not set  →  voice TTS disabled, chat still works"
    fi
    if grep -q "^TWILIO_ACCOUNT_SID=AC" .env; then
        ok "TWILIO credentials set  (WhatsApp enabled)"
    else
        warn "TWILIO_* not set  →  WhatsApp message disabled, booking still works"
    fi
    if grep -q "^ARIZE_API_KEY=." .env; then
        ok "ARIZE_API_KEY set  (observability enabled)"
    else
        warn "ARIZE_API_KEY not set  →  tracing disabled, app still works"
    fi
else
    fail ".env file missing  →  cp .env.example .env  then add ANTHROPIC_API_KEY"
    ISSUES=$((ISSUES+1))
fi
echo ""

# ── Ports ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}Ports${RESET}"
if command -v ss &>/dev/null; then
    if ss -tuln | grep -q ":8000 "; then
        warn "Port 8000 is already in use — stop the existing process before deploying"
    else
        ok "Port 8000 is free"
    fi
else
    warn "ss not available — can't check port 8000"
fi
echo ""

# ── Summary ──────────────────────────────────────────────────────────────────
echo "================================="
if [ "$ISSUES" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}All checks passed — ready to deploy!${RESET}"
    echo ""
    echo "  Run:  bash deploy.sh"
else
    echo -e "${RED}${BOLD}$ISSUES issue(s) found — fix them then run: bash deploy.sh${RESET}"
fi
echo ""
