#!/usr/bin/env bash
# =============================================================================
# TireAssist — DB connection checker + port auto-fix
# Run: sudo bash check_db.sh
# =============================================================================

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

ok()   { echo -e "${GREEN}✔${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET} $1"; }
fail() { echo -e "${RED}✘${RESET} $1"; }
info() { echo -e "${BOLD}▶ $1${RESET}"; }

echo ""
echo -e "${BOLD}TireAssist — DB Connection Check${RESET}"
echo "================================="
echo ""

# ── Step 1: Show running Postgres containers ─────────────────────────────────
info "Running Postgres containers:"
sudo docker ps --filter "ancestor=postgres" --format "  Name: {{.Names}}  Ports: {{.Ports}}" 2>/dev/null
sudo docker ps --filter "name=postgres" --format "  Name: {{.Names}}  Ports: {{.Ports}}" 2>/dev/null
sudo docker ps --filter "name=tireassist" --format "  Name: {{.Names}}  Ports: {{.Ports}}" 2>/dev/null
echo ""

# ── Step 2: Auto-detect host port from running container ─────────────────────
info "Auto-detecting Postgres port..."

DETECTED_PORT=$(sudo docker ps --format "{{.Ports}}" 2>/dev/null \
    | grep -oP '0\.0\.0\.0:\K[0-9]+(?=->5432)' \
    | head -1)

if [ -z "$DETECTED_PORT" ]; then
    warn "Could not auto-detect port from docker ps"
    DETECTED_PORT=$(grep -E "^DB_PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
    warn "Using DB_PORT from .env: $DETECTED_PORT"
else
    ok "Postgres container is on host port: $DETECTED_PORT"
fi

# ── Step 3: Compare with .env ─────────────────────────────────────────────────
ENV_PORT=$(grep -E "^DB_PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
ENV_HOST=$(grep -E "^DB_HOST=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
ENV_NAME=$(grep -E "^DB_NAME=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
ENV_USER=$(grep -E "^DB_USER=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
ENV_PASS=$(grep -E "^DB_PASSWORD=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')

echo ""
info "Current .env DB settings:"
echo "  DB_HOST=$ENV_HOST"
echo "  DB_PORT=$ENV_PORT"
echo "  DB_NAME=$ENV_NAME"
echo "  DB_USER=$ENV_USER"
echo ""

if [ "$DETECTED_PORT" != "$ENV_PORT" ] && [ -n "$DETECTED_PORT" ]; then
    warn "Port mismatch! Container is on $DETECTED_PORT but .env has $ENV_PORT"
    echo ""
    read -p "  Auto-fix DB_PORT in .env to $DETECTED_PORT? [Y/n]: " CONFIRM
    CONFIRM=${CONFIRM:-Y}
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        sed -i "s|^DB_PORT=.*|DB_PORT=$DETECTED_PORT|" .env
        ENV_PORT="$DETECTED_PORT"
        ok "DB_PORT updated to $DETECTED_PORT in .env"
    fi
else
    ok "DB_PORT in .env matches container ($ENV_PORT)"
fi

echo ""

# ── Step 4: Test actual connection ────────────────────────────────────────────
info "Testing connection to ${ENV_HOST}:${ENV_PORT}/${ENV_NAME}..."

source venv/bin/activate 2>/dev/null || true

python3 - <<PYEOF
import sys, os
from dotenv import load_dotenv
load_dotenv()
try:
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "costco_tyre"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        connect_timeout=5,
    )
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
    tables = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products") if tables > 0 else None
    products = cur.fetchone()[0] if tables > 0 else 0
    conn.close()
    print(f"  OK  Connected successfully")
    print(f"  OK  Tables in DB: {tables}")
    print(f"  OK  Products rows: {products}")
    sys.exit(0)
except Exception as e:
    print(f"  FAIL  {e}")
    sys.exit(1)
PYEOF

DB_STATUS=$?
echo ""

# ── Step 5: Summary + next step ───────────────────────────────────────────────
echo "================================="
if [ $DB_STATUS -eq 0 ]; then
    echo -e "${GREEN}${BOLD}DB connection OK — ready to deploy!${RESET}"
    echo ""
    echo "  Run:  sudo bash deploy1.sh"
else
    echo -e "${RED}${BOLD}DB connection failed — check above errors${RESET}"
    echo ""
    echo "  Common fixes:"
    echo "  1. Wrong port → this script auto-fixes it, then re-run"
    echo "  2. Container stopped → sudo docker start tireassist-postgres"
    echo "  3. Wrong DB name → check: sudo docker exec tireassist-postgres psql -U postgres -l"
fi
echo ""
