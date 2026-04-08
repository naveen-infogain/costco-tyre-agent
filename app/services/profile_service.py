"""
Profile Service — loads member identity and purchase history.
Source priority: PostgreSQL (if configured) → users.json fallback.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from app.models.schemas import User, LastPurchase, Vehicle, UserLocation

log = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent.parent / "data" / "users.json"

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _user_from_db_row(row: tuple, columns: list[str]) -> User:
    """Convert a DB row (tuple) + column list into a User model."""
    d = dict(zip(columns, row))
    # Build nested objects
    vehicle = Vehicle(
        make=d.get("vehicle_make") or "Unknown",
        model=d.get("vehicle_model") or "Unknown",
        year=d.get("vehicle_year") or 2020,
    )
    location = UserLocation(
        city=d.get("mailing_city") or "",
        zip=d.get("mailing_postal_code") or "",
    )
    # last_purchase: look up from order_items joined to products
    # (populated separately via _get_last_purchase_db)
    habits = d.get("driving_habits") or ["highway", "daily commute"]
    if isinstance(habits, str):
        import ast
        try:
            habits = ast.literal_eval(habits)
        except Exception:
            habits = [habits]

    return User(
        member_id=d["member_id"],
        name=d.get("full_name") or f"{d.get('first_name','')} {d.get('last_name','')}".strip(),
        membership_tier=d.get("membership_tier") or "standard",
        location=location,
        vehicle=vehicle,
        driving_habits=habits,
        last_purchase=None,  # populated below
    )


def _get_last_purchase_db(conn, contact_sf_id: str) -> Optional[LastPurchase]:
    """Fetch the most recent completed order item for the contact."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT oi.product_sf_id, o.order_date
                FROM order_items oi
                JOIN orders o ON o.sf_id = oi.order_sf_id
                WHERE o.contact_sf_id = %s
                  AND oi.product_sf_id IS NOT NULL
                  AND oi.product_sf_id != ''
                ORDER BY o.order_date DESC
                LIMIT 1
            """, (contact_sf_id,))
            row = cur.fetchone()
            if row:
                return LastPurchase(
                    tyre_id=row[0],
                    date=str(row[1]),
                    mileage_at_purchase=0,
                )
    except Exception as e:
        log.debug("last_purchase DB query failed: %s", e)
    return None


def _get_member_db(member_id: str) -> Optional[User]:
    """Fetch a member from PostgreSQL by member_id."""
    try:
        from app.db.connection import get_conn, release_conn, db_available
        if not db_available():
            return None
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT sf_id, member_id, first_name, last_name, full_name, email, phone,
                           mailing_city, mailing_state, mailing_postal_code,
                           membership_tier, vehicle_make, vehicle_model, vehicle_year,
                           driving_habits
                    FROM contacts
                    WHERE member_id = %s
                """, (member_id,))
                cols = [c.name for c in cur.description]
                row = cur.fetchone()
                if not row:
                    return None
                user = _user_from_db_row(row, cols)
                d = dict(zip(cols, row))
                # Attach last purchase
                user.last_purchase = _get_last_purchase_db(conn, d["sf_id"])
                return user
        finally:
            release_conn(conn)
    except Exception as e:
        log.warning("DB get_member failed (%s) — falling back to JSON", e)
        return None


# ---------------------------------------------------------------------------
# JSON fallback
# ---------------------------------------------------------------------------

def _load_users() -> list[dict]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _get_member_json(member_id: str) -> Optional[User]:
    if not _DATA_PATH.exists():
        return None
    for raw in _load_users():
        if raw["member_id"] == member_id:
            return User(**raw)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_member(member_id: str) -> Optional[User]:
    """Return the User model for the given member_id. DB first, JSON fallback."""
    user = _get_member_db(member_id)
    if user is not None:
        return user
    return _get_member_json(member_id)


def get_last_purchased_tyre(member_id: str) -> Optional[LastPurchase]:
    user = get_member(member_id)
    if user and user.last_purchase:
        return user.last_purchase
    return None


def get_vehicle_history(member_id: str) -> list[Vehicle]:
    user = get_member(member_id)
    if user:
        return [user.vehicle]
    return []


def load_member_preferences(member_id: str) -> dict:
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
    return get_last_purchased_tyre(member_id) is not None
