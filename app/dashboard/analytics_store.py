"""
Analytics Store — in-memory aggregator for dashboard data.
Pre-seeded with v33 baseline from CLAUDE.md.
"""
from __future__ import annotations

# v33 baseline funnel (10,000 sessions)
_BASELINE_FUNNEL = [
    {"stage": "enter",    "visitors": 10000, "drop_rate": 0.0},
    {"stage": "browse",   "visitors": 8200,  "drop_rate": 18.0},
    {"stage": "detail",   "visitors": 6100,  "drop_rate": 25.6},
    {"stage": "cart",     "visitors": 4800,  "drop_rate": 21.3},
    {"stage": "pay",      "visitors": 4100,  "drop_rate": 14.6},
    {"stage": "book",     "visitors": 3700,  "drop_rate": 9.8},
    {"stage": "complete", "visitors": 3500,  "drop_rate": 5.4},
]

_IMPROVEMENT_LOG = [
    {"version": "v33", "agent": "Rec & Ranking", "change": "Popularity weight +8%",  "impact": "+3.2% pick rate",   "status": "deployed"},
    {"version": "v33", "agent": "Content",        "change": "Benefit-first messages", "impact": "+12% CTR",          "status": "deployed"},
    {"version": "v33", "agent": "Compare",        "change": "5 columns → 3 columns",  "impact": "+5% open rate",     "status": "deployed"},
    {"version": "v33", "agent": "Guardrail",      "change": "False positive fix",      "impact": "-40% false blocks", "status": "deployed"},
    {"version": "v33", "agent": "Rec & Ranking",  "change": "Safety weight for SUVs",  "impact": "testing",           "status": "ab_test"},
    {"version": "v33", "agent": "Appointment",    "change": "Morning slot bias",        "impact": "testing",           "status": "ab_test"},
    {"version": "v33", "agent": "Content",        "change": "Emoji-enhanced messages", "impact": "testing",           "status": "ab_test"},
    {"version": "v33", "agent": "Compare",        "change": "Bar charts vs numbers",   "impact": "testing",           "status": "ab_test"},
    {"version": "v34", "agent": "Guardrail",      "change": "Brand diversity enforcement", "impact": "queued",        "status": "queued"},
    {"version": "v34", "agent": "Rec & Ranking",  "change": "Tread warranty ranking",  "impact": "queued",            "status": "queued"},
    {"version": "v34", "agent": "Content",        "change": "Seasonal message variants","impact": "queued",           "status": "queued"},
]


def get_full_analytics() -> dict:
    """Return complete analytics payload for the dashboard."""
    from app.services.eval_service import get_scorecard, get_conversion_rate
    from app.services.dropoff_tracker import get_funnel_stats, get_drop_alerts

    # Merge live funnel stats with baseline (live stats start at 0 until sessions run)
    live_funnel = get_funnel_stats()
    live_enter = next((s["visitors"] for s in live_funnel if s["stage"] == "enter"), 0)

    funnel = _BASELINE_FUNNEL if live_enter == 0 else live_funnel

    return {
        "funnel": funnel,
        "conversion_rate": get_conversion_rate(),
        "scorecard": get_scorecard(),
        "drop_alerts": get_drop_alerts() if live_enter > 0 else _baseline_drop_alerts(),
        "improvements": _IMPROVEMENT_LOG,
        "summary": {
            "deployed_this_month": sum(1 for i in _IMPROVEMENT_LOG if i["status"] == "deployed"),
            "active_ab_tests": sum(1 for i in _IMPROVEMENT_LOG if i["status"] == "ab_test"),
            "queued_next_sprint": sum(1 for i in _IMPROVEMENT_LOG if i["status"] == "queued"),
        },
    }


def _baseline_drop_alerts() -> list[dict]:
    return [
        {"stage": "browse",   "current_rate": 18.0, "threshold": 15, "status": "warning"},
        {"stage": "detail",   "current_rate": 14.0, "threshold": 15, "status": "ok"},
        {"stage": "cart",     "current_rate": 13.0, "threshold": 15, "status": "ok"},
        {"stage": "pay",      "current_rate": 3.0,  "threshold": 5,  "status": "ok"},
        {"stage": "book",     "current_rate": 8.0,  "threshold": 10, "status": "ok"},
        {"stage": "complete", "current_rate": 5.4,  "threshold": 10, "status": "ok"},
    ]
