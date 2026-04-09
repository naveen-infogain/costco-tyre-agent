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

ok()   { echo -e "${GREEN}✔${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET} $1"; }
fail() { echo -e "${RED}✘ $1${RESET}"; exit 1; }
info() { echo -e "${BOLD}▶ $1${RESET}"; }

# DB config — used throughout this script
DB_CONTAINER="tireassist-postgres"
DB_NAME="costco_tyre"
DB_USER="postgres"
DB_PASS="postgres"
DB_PORT="5432"

# App port — read from .env if set, else default 8080
APP_PORT=$(grep -E "^APP_PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
APP_PORT=${APP_PORT:-8080}

echo ""
echo -e "${BOLD}=============================================${RESET}"
echo -e "${BOLD}  TireAssist — Ubuntu Deployment${RESET}"
echo -e "${BOLD}=============================================${RESET}"
echo ""

# =============================================================================
# STEP 1 — Prerequisites
# =============================================================================
info "Step 1 — Checking prerequisites..."

# Python 3.11+
if command -v python3 &>/dev/null; then
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        ok "Python $PY_VER"
    else
        warn "Python $PY_VER found — installing 3.11..."
        sudo apt-get update -qq
        sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
        sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
    fi
else
    warn "Python3 not found — installing..."
    sudo apt-get update -qq
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
fi

if ! python3 -m venv --help &>/dev/null 2>&1; then
    sudo apt-get install -y python3.11-venv
fi
ok "Python $(python3 --version)"

# pip
if ! command -v pip3 &>/dev/null; then
    sudo apt-get install -y python3-pip
fi
ok "pip ready"

# Node.js 18+
if command -v node &>/dev/null; then
    NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_MAJOR" -lt 18 ]; then
        warn "Node.js $(node -v) too old — upgrading to Node 20..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
else
    warn "Node.js not found — installing Node 20..."
    sudo apt-get install -y curl
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
ok "Node.js $(node -v)"

# Docker
if ! command -v docker &>/dev/null; then
    fail "Docker not found. Install it: sudo apt install docker.io && sudo systemctl start docker"
fi
if ! docker info &>/dev/null 2>&1; then
    fail "Docker daemon not running. Start it: sudo systemctl start docker"
fi
ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"

echo ""

# =============================================================================
# STEP 2 — .env file
# =============================================================================
info "Step 2 — Environment configuration..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    warn ".env created from .env.example"
fi

# Check required key
if ! grep -q "^ANTHROPIC_API_KEY=sk-ant-" .env 2>/dev/null; then
    echo ""
    echo -e "${RED}ANTHROPIC_API_KEY is missing or not set in .env${RESET}"
    echo "  Open .env and add your key:  ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
    read -p "Press Enter after you've added it (or Ctrl+C to abort)..." _
fi

# Inject DB settings into .env (overwrite if already present)
update_env() {
    local key="$1" val="$2"
    if grep -q "^${key}=" .env 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${val}|" .env
    else
        echo "${key}=${val}" >> .env
    fi
}

update_env "DB_HOST"     "localhost"
update_env "DB_PORT"     "$DB_PORT"
update_env "DB_NAME"     "$DB_NAME"
update_env "DB_USER"     "$DB_USER"
update_env "DB_PASSWORD" "$DB_PASS"
update_env "APP_PORT"    "$APP_PORT"

ok ".env DB + port settings configured (APP_PORT=$APP_PORT)"
echo ""

# =============================================================================
# STEP 3 — PostgreSQL via Docker
# =============================================================================
info "Step 3 — Starting PostgreSQL in Docker..."

# If port 5432 is already taken, use 5433 and update .env
# Check app port is free
if ss -tuln 2>/dev/null | grep -q ":${APP_PORT} "; then
    warn "Port $APP_PORT is in use — trying $((APP_PORT+1))..."
    APP_PORT=$((APP_PORT+1))
    update_env "APP_PORT" "$APP_PORT"
    ok "Using port $APP_PORT instead"
else
    ok "App port $APP_PORT is free"
fi

if ss -tuln 2>/dev/null | grep -q ":5432 "; then
    warn "Port 5432 in use — using 5433 for Docker Postgres"
    DB_PORT="5433"
    update_env "DB_PORT" "5433"
fi

# Remove existing stopped container with same name (if any)
if docker ps -a --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    STATUS=$(docker inspect -f '{{.State.Status}}' "$DB_CONTAINER")
    if [ "$STATUS" = "running" ]; then
        ok "Postgres container '$DB_CONTAINER' already running"
    else
        warn "Removing stopped container '$DB_CONTAINER'..."
        docker rm "$DB_CONTAINER"
        STATUS="gone"
    fi
else
    STATUS="gone"
fi

if [ "$STATUS" != "running" ]; then
    docker run -d \
        --name "$DB_CONTAINER" \
        -e POSTGRES_USER="$DB_USER" \
        -e POSTGRES_PASSWORD="$DB_PASS" \
        -e POSTGRES_DB="$DB_NAME" \
        -p "${DB_PORT}:5432" \
        --restart unless-stopped \
        postgres:15-alpine
    ok "Postgres container started"
fi

# Wait until Postgres is ready to accept connections
info "Waiting for Postgres to be ready..."
RETRIES=20
until docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" -q 2>/dev/null; do
    RETRIES=$((RETRIES-1))
    if [ "$RETRIES" -eq 0 ]; then
        fail "Postgres did not become ready in time. Check: docker logs $DB_CONTAINER"
    fi
    sleep 1
done
ok "PostgreSQL is ready on port $DB_PORT"
echo ""

# =============================================================================
# STEP 4 — Python virtual environment + dependencies
# =============================================================================
info "Step 4 — Python virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    ok "Virtual environment created"
else
    ok "Virtual environment already exists"
fi

source venv/bin/activate

info "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Python packages installed"
echo ""

# =============================================================================
# STEP 5 — Initialise DB schema + load data
# =============================================================================
info "Step 5 — Initialising database schema and loading data..."

# Check if CRM CSV files exist
if [ -f "app/crm_data/Costco_Product__c-4_8_2026.csv" ]; then
    python scripts/init_db.py
    ok "Database schema created and CRM data loaded"
else
    warn "CRM CSV files not found in app/crm_data/ — running schema-only init"
    # Run just the CREATE TABLE part without the loaders
    python - <<'PYEOF'
import os, sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
import psycopg2

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
)
# Read schema SQL from init_db.py
import importlib.util, inspect
spec = importlib.util.spec_from_file_location("init_db", "scripts/init_db.py")
mod = importlib.util.load_from_spec(spec)
spec.loader.exec_module(mod)
with conn:
    with conn.cursor() as cur:
        cur.execute(mod.CREATE_SQL)
conn.close()
print("  Schema tables created successfully")
PYEOF
    ok "Database schema created (no CRM data — app will use JSON fallback)"
fi
echo ""

# =============================================================================
# STEP 6 — Build React frontend
# =============================================================================
info "Step 6 — Building React frontend..."

cd frontend
if [ ! -d "node_modules" ]; then
    npm install --silent
    ok "npm packages installed"
else
    ok "node_modules present"
fi
npm run build --silent
ok "React build → frontend/dist/"
cd ..

if [ ! -f "frontend/dist/index.html" ]; then
    fail "React build failed — frontend/dist/index.html not found"
fi
echo ""

# =============================================================================
# STEP 7 — Launch
# =============================================================================
HOST_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}${BOLD}=============================================${RESET}"
echo -e "${GREEN}${BOLD}  Deployment complete!${RESET}"
echo -e "${GREEN}${BOLD}=============================================${RESET}"
echo ""
echo -e "  App:        ${BOLD}http://${HOST_IP}:${APP_PORT}${RESET}"
echo -e "  Health:     http://${HOST_IP}:${APP_PORT}/health"
echo -e "  Dashboard:  http://${HOST_IP}:${APP_PORT}/dashboard"
echo -e "  Postgres:   localhost:${DB_PORT}  db=${DB_NAME}  user=${DB_USER}"
echo ""
echo "  Press Ctrl+C to stop the server."
echo ""

source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port "$APP_PORT" --workers 1
