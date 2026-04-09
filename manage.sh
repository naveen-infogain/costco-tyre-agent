#!/usr/bin/env bash
# =============================================================================
# TireAssist — App Manager (start / stop / restart / logs / status)
# Usage: sudo bash manage.sh [start|stop|restart|logs|status]
# =============================================================================

APP_PORT=$(grep -E "^APP_PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
APP_PORT=${APP_PORT:-8001}
PIDFILE="/tmp/tireassist.pid"
LOGFILE="/tmp/tireassist.log"
HOST_IP=$(hostname -I | awk '{print $1}')

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

ok()   { echo -e "${GREEN}✔${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET} $1"; }
fail() { echo -e "${RED}✘${RESET} $1"; }

start() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat $PIDFILE)" 2>/dev/null; then
        warn "Already running (PID $(cat $PIDFILE))"
        return
    fi

    echo -e "${BOLD}▶ Building frontend...${RESET}"
    cd frontend && npm run build --silent && cd ..
    ok "React build done"

    echo -e "${BOLD}▶ Starting TireAssist on port $APP_PORT...${RESET}"
    source venv/bin/activate
    nohup uvicorn app.main:app --host 0.0.0.0 --port "$APP_PORT" --workers 1 \
        > "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"

    sleep 2
    if kill -0 "$(cat $PIDFILE)" 2>/dev/null; then
        ok "TireAssist started (PID $(cat $PIDFILE))"
        echo ""
        echo -e "  App:        ${BOLD}http://${HOST_IP}:${APP_PORT}${RESET}"
        echo -e "  Health:     http://${HOST_IP}:${APP_PORT}/health"
        echo -e "  Dashboard:  http://${HOST_IP}:${APP_PORT}/dashboard"
        echo -e "  Logs:       sudo bash manage.sh logs"
    else
        fail "Failed to start — check logs: sudo bash manage.sh logs"
    fi
}

stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PIDFILE"
            ok "TireAssist stopped (PID $PID)"
        else
            warn "Process $PID not running — cleaning up pidfile"
            rm -f "$PIDFILE"
        fi
    else
        # fallback: kill by port
        fuser -k ${APP_PORT}/tcp 2>/dev/null && ok "Killed process on port $APP_PORT" || warn "Nothing running on port $APP_PORT"
    fi
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat $PIDFILE)" 2>/dev/null; then
        ok "Running (PID $(cat $PIDFILE)) → http://${HOST_IP}:${APP_PORT}"
    else
        warn "Not running"
    fi
}

logs() {
    if [ -f "$LOGFILE" ]; then
        tail -f "$LOGFILE"
    else
        warn "No log file found at $LOGFILE"
    fi
}

case "${1:-start}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    logs)    logs ;;
    status)  status ;;
    *)
        echo "Usage: sudo bash manage.sh [start|stop|restart|logs|status]"
        ;;
esac
