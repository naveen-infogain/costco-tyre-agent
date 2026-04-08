"""
Drop-off Tracker — logs stage transitions, detects drop signals,
applies recovery rules, and feeds funnel analytics.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Optional

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# Funnel stages in order
# confirm_vehicle / collect_vehicle are pre-browse stages — not tracked in funnel
# (they add no meaningful drop signal; they resolve in 1-2 messages)
STAGES = ["enter", "browse", "detail", "cart", "pay", "book", "complete"]
_NON_FUNNEL_STAGES = {"confirm_vehicle", "collect_vehicle"}

# In-memory session activity log: {session_id: [{stage, timestamp}]}
_SESSION_LOG: dict[str, list[dict]] = {}

# Funnel aggregate counters
_FUNNEL: dict[str, int] = {s: 0 for s in STAGES}

# Drop alert thresholds (stage -> max acceptable drop rate %)
_DROP_THRESHOLDS = {
    "browse": 15,
    "detail": 25,
    "cart": 15,
    "pay": 15,
    "book": 5,
    "complete": 10,
}


def log_stage_transition(session_id: str, stage: str, context: Optional[dict] = None) -> None:
    """Record a stage transition for a session and update funnel counters."""
    if stage in _NON_FUNNEL_STAGES:
        return  # vehicle confirmation steps — not meaningful funnel stages
    if stage not in STAGES:
        return

    entry = {"stage": stage, "timestamp": time.time(), "context": context or {}}
    _SESSION_LOG.setdefault(session_id, []).append(entry)
    _FUNNEL[stage] = _FUNNEL.get(stage, 0) + 1

    log_file = _LOG_DIR / "funnel.json"
    all_logs: list = []
    if log_file.exists():
        try:
            all_logs = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            all_logs = []
    all_logs.append({"session_id": session_id, **entry})
    log_file.write_text(json.dumps(all_logs[-500:], indent=2), encoding="utf-8")  # keep last 500


def detect_drop(session_id: str) -> Optional[str]:
    """
    Analyse session activity to detect a drop signal.
    Returns a drop reason string or None if session is active.
    """
    history = _SESSION_LOG.get(session_id, [])
    if not history:
        return None

    now = time.time()
    last_event = history[-1]
    idle_secs = now - last_event["timestamp"]

    # Idle >2 minutes
    if idle_secs > 120:
        return "idle"

    # Back-navigation 3+ times (repeated browse/detail alternation)
    stages = [h["stage"] for h in history]
    back_nav_count = sum(
        1 for i in range(1, len(stages))
        if STAGES.index(stages[i]) < STAGES.index(stages[i - 1])
    )
    if back_nav_count >= 3:
        return "confused"

    # Too many refinement cycles (>3 browse entries)
    if stages.count("browse") > 3:
        return "overload"

    # Session duration > 8 min without reaching cart
    session_duration = now - history[0]["timestamp"]
    if session_duration > 480 and "cart" not in stages:
        return "too_long"

    return None


def apply_recovery_rule(drop_signal: str, session_context: dict) -> dict:
    """
    Map a drop signal to a recovery action for the UI.
    """
    rules = {
        "idle": {
            "action": "price_reminder",
            "message": f"Still deciding? Your member savings of ${session_context.get('savings', '0')} are waiting.",
        },
        "confused": {
            "action": "live_chat",
            "message": "Need help choosing? Chat with a tyre expert now.",
        },
        "overload": {
            "action": "simplify",
            "message": "Let us make it easy — here's our #1 pick for you.",
        },
        "too_long": {
            "action": "express_checkout",
            "message": "Short on time? Tap to go straight to checkout.",
        },
        "exit": {
            "action": "recovery_email",
            "message": "Recovery email scheduled in 1 hour.",
        },
    }
    return rules.get(drop_signal, {"action": "none", "message": ""})


def get_funnel_stats() -> list[dict]:
    """Return funnel stage counts as a list for the dashboard."""
    total = _FUNNEL.get("enter", 1) or 1
    stats = []
    for stage in STAGES:
        count = _FUNNEL.get(stage, 0)
        drop_rate = round((1 - count / total) * 100, 1) if total > 0 else 0.0
        stats.append({
            "stage": stage,
            "visitors": count,
            "drop_rate": drop_rate,
        })
    return stats


def get_drop_alerts() -> list[dict]:
    """Return drop-off alerts with threshold comparison for dashboard."""
    stats = get_funnel_stats()
    alerts = []
    for s in stats[1:]:  # skip 'enter'
        stage = s["stage"]
        threshold = _DROP_THRESHOLDS.get(stage, 20)
        alerts.append({
            "stage": stage,
            "current_rate": s["drop_rate"],
            "threshold": threshold,
            "status": "warning" if s["drop_rate"] > threshold else "ok",
        })
    return alerts
