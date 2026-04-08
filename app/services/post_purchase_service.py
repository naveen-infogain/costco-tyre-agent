"""
Post-Purchase Service — schedules reminders, satisfaction surveys,
profile write-backs, rotation cron alerts, and re-engagement triggers.
All actions are logged (mocked for demo; swap for real SMS/email APIs).
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)


def _append_log(filename: str, entry: dict) -> None:
    log_file = _LOG_DIR / filename
    entries: list = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
    entries.append(entry)
    log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def schedule_reminders(member_id: str, appointment_date: str, location_name: str, tyre_model: str) -> dict:
    """Schedule day-before SMS reminder and install-complete alert."""
    entry = {
        "type": "reminder_scheduled",
        "member_id": member_id,
        "appointment_date": appointment_date,
        "location": location_name,
        "tyre_model": tyre_model,
        "sms_day_before": True,
        "push_on_complete": True,
    }
    _append_log("post_purchase.json", entry)
    logger.info("Reminder scheduled for member %s on %s", member_id, appointment_date)
    return {"status": "scheduled", **entry}


def send_survey(member_id: str, order_id: str, delay_days: int = 30) -> dict:
    """Queue a satisfaction survey to be sent after installation."""
    entry = {
        "type": "survey_queued",
        "member_id": member_id,
        "order_id": order_id,
        "send_after_days": delay_days,
    }
    _append_log("post_purchase.json", entry)
    return {"status": "queued", **entry}


def write_review_to_profile(member_id: str, tyre_id: str, rating: int, review: str) -> dict:
    """Record member's post-purchase review back to their profile data."""
    entry = {
        "type": "review_written",
        "member_id": member_id,
        "tyre_id": tyre_id,
        "rating": rating,
        "review": review,
    }
    _append_log("post_purchase.json", entry)
    return {"status": "saved", **entry}


def schedule_rotation_reminder(member_id: str, tyre_id: str, current_mileage: int) -> dict:
    """Set a rotation reminder at current_mileage + 10,000 km."""
    next_rotation = current_mileage + 10000
    entry = {
        "type": "rotation_reminder",
        "member_id": member_id,
        "tyre_id": tyre_id,
        "remind_at_km": next_rotation,
    }
    _append_log("post_purchase.json", entry)
    return {"status": "scheduled", "remind_at_km": next_rotation}


def schedule_seasonal_swap_alert(member_id: str, season: str) -> dict:
    """Alert member when seasonal tyre swap is appropriate."""
    entry = {
        "type": "seasonal_swap_alert",
        "member_id": member_id,
        "season": season,
    }
    _append_log("post_purchase.json", entry)
    return {"status": "scheduled", **entry}


def schedule_re_engagement(member_id: str, tyre_id: str, tread_life_km: int, purchase_date: str) -> dict:
    """Re-engage member at predicted wear-out date."""
    entry = {
        "type": "re_engagement",
        "member_id": member_id,
        "tyre_id": tyre_id,
        "predicted_replacement_km": tread_life_km,
        "purchase_date": purchase_date,
    }
    _append_log("post_purchase.json", entry)
    return {"status": "scheduled", **entry}
