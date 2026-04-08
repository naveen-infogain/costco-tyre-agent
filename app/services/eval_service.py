"""
Eval Service — feedback collector, agent scorecard, and improvement engine.
Pre-seeded with v33 baseline scores from CLAUDE.md.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Optional

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# v33 baseline scorecard (from CLAUDE.md)
_SCORECARD: dict[str, dict] = {
    "guardrail": {"agent": "Guardrail", "score": 86, "trend": 3, "status": "on_target"},
    "rec_ranking": {"agent": "Rec & Ranking", "score": 78, "trend": 4, "status": "on_target"},
    "compare": {"agent": "Compare", "score": 74, "trend": 4, "status": "on_target"},
    "content": {"agent": "Content", "score": 71, "trend": 8, "status": "on_target"},
    "appointment": {"agent": "Appointment", "score": 69, "trend": -2, "status": "under_review"},
    "orchestrator": {"agent": "Orchestrator", "score": 67, "trend": 5, "status": "on_target"},
}

_FEEDBACK_LOG: list[dict] = []

_IMPROVEMENT_LOG: list[dict] = [
    {"version": "v33", "agent": "Rec & Ranking", "change": "Popularity weight +8%", "impact": "+3.2% pick rate", "status": "deployed"},
    {"version": "v33", "agent": "Content", "change": "Benefit-first messages", "impact": "+12% CTR", "status": "deployed"},
    {"version": "v33", "agent": "Compare", "change": "5 columns → 3 columns", "impact": "+5% open rate", "status": "deployed"},
    {"version": "v33", "agent": "Guardrail", "change": "False positive fix", "impact": "-40% false blocks", "status": "deployed"},
    {"version": "v33", "agent": "Rec & Ranking", "change": "Safety weight increase for SUVs", "impact": "testing", "status": "ab_test"},
    {"version": "v33", "agent": "Appointment", "change": "Morning slot bias", "impact": "testing", "status": "ab_test"},
    {"version": "v33", "agent": "Content", "change": "Emoji-enhanced messages", "impact": "testing", "status": "ab_test"},
    {"version": "v33", "agent": "Compare", "change": "Bar charts vs numeric values", "impact": "testing", "status": "ab_test"},
    {"version": "v34", "agent": "Guardrail", "change": "Brand diversity enforcement", "impact": "queued", "status": "queued"},
    {"version": "v34", "agent": "Rec & Ranking", "change": "Tread warranty as ranking factor", "impact": "queued", "status": "queued"},
    {"version": "v34", "agent": "Content", "change": "Seasonal message variants", "impact": "queued", "status": "queued"},
]


def collect_feedback(
    session_id: str,
    agent: str,
    signal_type: str,
    signal: str,
    tyre_id: Optional[str] = None,
) -> None:
    """Record an implicit or explicit feedback signal."""
    entry = {
        "session_id": session_id,
        "agent": agent,
        "signal_type": signal_type,  # "implicit" | "explicit"
        "signal": signal,            # e.g. "pick_slot_1", "thumbs_up", "thumbs_down"
        "tyre_id": tyre_id,
        "timestamp": time.time(),
    }
    _FEEDBACK_LOG.append(entry)

    log_file = _LOG_DIR / "feedback.json"
    all_logs: list = []
    if log_file.exists():
        try:
            all_logs = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            all_logs = []
    all_logs.append(entry)
    log_file.write_text(json.dumps(all_logs[-1000:], indent=2), encoding="utf-8")


def update_scorecard(agent_key: str, delta: int) -> dict:
    """Adjust an agent's score by delta (e.g., +1 on positive feedback)."""
    if agent_key not in _SCORECARD:
        return {}
    _SCORECARD[agent_key]["score"] = max(0, min(100, _SCORECARD[agent_key]["score"] + delta))
    _SCORECARD[agent_key]["trend"] += delta
    return _SCORECARD[agent_key]


def get_scorecard() -> list[dict]:
    return list(_SCORECARD.values())


def get_improvement_log() -> list[dict]:
    return _IMPROVEMENT_LOG


def get_conversion_rate() -> float:
    """Mock conversion rate — 35.2% baseline as per v33."""
    return 35.2
