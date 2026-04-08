"""
Profile Service — loads member identity and purchase history from users.json.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from app.models.schemas import User, LastPurchase, Vehicle

_DATA_PATH = Path(__file__).parent.parent / "data" / "users.json"

def _load_users() -> list[dict]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_member(member_id: str) -> Optional[User]:
    """Return the User model for the given member_id, or None if not found."""
    for raw in _load_users():
        if raw["member_id"] == member_id:
            return User(**raw)
    return None


def get_last_purchased_tyre(member_id: str) -> Optional[LastPurchase]:
    """Return the member's most recent tyre purchase, or None for new buyers."""
    user = get_member(member_id)
    if user and user.last_purchase:
        return user.last_purchase
    return None


def get_vehicle_history(member_id: str) -> list[Vehicle]:
    """Return all vehicles on record for the member (currently one per profile)."""
    user = get_member(member_id)
    if user:
        return [user.vehicle]
    return []


def load_member_preferences(member_id: str) -> dict:
    """Return driving habits, location, and tier for personalisation."""
    user = get_member(member_id)
    if not user:
        return {}
    return {
        "driving_habits": user.driving_habits,
        "location": user.location.model_dump(),
        "membership_tier": user.membership_tier,
        "vehicle": user.vehicle.model_dump(),
    }


def is_returning_buyer(member_id: str) -> bool:
    """True if the member has a prior tyre purchase on record."""
    return get_last_purchased_tyre(member_id) is not None
