"""
Profile Tools — LangChain @tool wrappers over profile_service.
"""
from __future__ import annotations
import json
from langchain_core.tools import tool
from app.services import profile_service


@tool
def load_member_session(member_id: str) -> str:
    """
    Load a Costco member's profile by their member ID.
    Returns member name, tier, vehicle, location, and purchase history as JSON.
    """
    user = profile_service.get_member(member_id)
    if not user:
        return json.dumps({"error": f"Member {member_id} not found. Please check the ID and try again."})
    return json.dumps(user.model_dump())


@tool
def detect_user_type(member_id: str) -> str:
    """
    Determine if a member is a returning buyer (has prior tyre purchase) or a new buyer.
    Returns JSON with user_type: 'returning' or 'new'.
    """
    is_returning = profile_service.is_returning_buyer(member_id)
    last = profile_service.get_last_purchased_tyre(member_id)
    return json.dumps({
        "user_type": "returning" if is_returning else "new",
        "last_purchase": last.model_dump() if last else None,
    })


@tool
def get_vehicle_history(member_id: str) -> str:
    """
    Retrieve all vehicles on record for a member.
    Returns a JSON list of vehicles (make, model, year).
    """
    vehicles = profile_service.get_vehicle_history(member_id)
    return json.dumps([v.model_dump() for v in vehicles])


@tool
def load_member_preferences(member_id: str) -> str:
    """
    Load a member's driving habits, location, vehicle, and membership tier.
    Used to personalise recommendations and content.
    """
    prefs = profile_service.load_member_preferences(member_id)
    return json.dumps(prefs)
