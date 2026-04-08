"""
Content Tools — LangChain @tool for generating personalised messages per tyre slot.
"""
from __future__ import annotations
import json
from langchain_core.tools import tool


@tool
def generate_personalised_msg(tyre_json: str, member_context_json: str, slot_type: str) -> str:
    """
    Generate a personalised message for a tyre recommendation slot.

    Args:
        tyre_json: JSON string of the Tyre object
        member_context_json: JSON string with member preferences (driving_habits, tier, vehicle, location)
        slot_type: One of 'best_repurchase', 'best_upgrade', 'most_popular',
                   'top_pick', 'runner_up', 'budget_alt'

    Returns a personalised message string for display in the recommendation card.
    """
    tyre = json.loads(tyre_json)
    ctx = json.loads(member_context_json)

    brand = tyre.get("brand", "")
    model = tyre.get("model", "")
    member_price = tyre.get("member_price", 0)
    tread = tyre.get("tread_life_km", 0)
    rating = tyre.get("rating", 0)
    promo = tyre.get("active_promotion") or ""
    habits = ctx.get("driving_habits", [])
    tier = ctx.get("membership_tier", "standard")
    vehicle = ctx.get("vehicle", {})
    city = ctx.get("location", {}).get("city", "your area")

    vehicle_str = f"{vehicle.get('make', '')} {vehicle.get('model', '')}"
    habit_str = " and ".join(habits[:2]) if habits else "everyday driving"

    tier_suffix = {
        "executive": "As an Executive member, you're getting our best member pricing.",
        "gold": "Your Gold membership saves you on every set.",
        "standard": "Great value at your member price.",
    }.get(tier, "")

    noise_db = tyre.get("noise_db", 99)
    quiet_note = "whisper-quiet on the highway" if noise_db < 68 else ("smooth and refined" if noise_db < 72 else "")

    messages = {
        "best_repurchase": (
            f"You went with these last time — and for good reason. "
            f"The {brand} {model} delivered for your {vehicle_str}, "
            f"and at ${member_price:.0f}/tyre it still gives you {tread:,} km of reliable tread. "
            f"{tier_suffix} {promo}"
        ).strip(),

        "best_upgrade": (
            f"If your last set did the job, this one will impress you. "
            f"The {brand} {model} steps it up with {rating}★ ratings and stronger wet grip — "
            f"{'exactly what you need for ' + habit_str if habit_str else 'a real step forward'}. "
            f"{tier_suffix}"
        ).strip(),

        "most_popular": (
            f"This is what {vehicle_str} drivers in {city} keep coming back to. "
            f"The {brand} {model} holds a {rating}★ rating from {tyre.get('review_count', 0):,} real members — "
            f"that kind of trust is hard to argue with. {promo}"
        ).strip(),

        "top_pick": (
            f"For {habit_str} in a {vehicle_str}, this is the one I'd go with. "
            f"The {brand} {model} hits {rating}★, runs {tread:,} km, "
            f"{'and is ' + quiet_note + ' — ' if quiet_note else 'and at '}"
            f"${member_price:.0f}/tyre it's genuinely great value. {promo}"
        ).strip(),

        "runner_up": (
            f"Worth a serious look too — the {brand} {model} at ${member_price:.0f}/tyre "
            f"gives you {tread:,} km of tread "
            f"{'and a ' + quiet_note + ' feel' if quiet_note else ''}. "
            f"A solid choice if you want something a little different for {habit_str}."
        ).strip(),

        "budget_alt": (
            f"Don't overlook this one. The {brand} {model} at ${member_price:.0f}/tyre "
            f"stretches {tread:,} km — that's some of the best cost-per-km on the list. "
            f"Smart value without cutting corners on safety. {promo}"
        ).strip(),
    }

    return messages.get(slot_type, f"The {brand} {model} — {rating}★ rated at ${member_price:.0f}/tyre.")
