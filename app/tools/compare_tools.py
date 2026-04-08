"""
Compare Tools — LangChain @tool for generating side-by-side comparison cards.
"""
from __future__ import annotations
import json
from langchain_core.tools import tool
from app.services import stock_service


@tool
def generate_comparison_card(tyre_ids_json: str, member_context_json: str) -> str:
    """
    Generate a 3-column comparison card for up to 3 tyres.

    Args:
        tyre_ids_json: JSON list of tyre ID strings (2-3 IDs)
        member_context_json: JSON string with member context

    Returns a JSON comparison card with specs, AI pros/cons, and cost-per-km.
    """
    tyre_ids = json.loads(tyre_ids_json)
    ctx = json.loads(member_context_json)
    habits = ctx.get("driving_habits", [])

    tyres = []
    for tid in tyre_ids[:3]:
        t = stock_service.get_tyre_by_id(tid)
        if t:
            tyres.append(t)

    if not tyres:
        return json.dumps({"error": "No valid tyres found for comparison"})

    pros_cons: dict[str, dict] = {}
    cost_per_km: dict[str, float] = {}

    for t in tyres:
        cost_per_km[t.id] = round(t.member_price / t.tread_life_km * 1000, 3)  # $ per 1000km

        pros = []
        cons = []

        if t.rating >= 4.7:
            pros.append("Top-rated by members")
        if t.wet_grip == "A":
            pros.append("Excellent wet grip")
        if t.tread_life_km >= 80000:
            pros.append(f"Long tread life ({t.tread_life_km:,} km)")
        if t.noise_db <= 67:
            pros.append("Ultra-quiet ride")
        if t.member_price < 150:
            pros.append("Budget-friendly price")
        if t.warranty_years >= 5:
            pros.append(f"{t.warranty_years}-year warranty")

        if t.noise_db >= 73:
            cons.append("Higher road noise")
        if t.tread_life_km < 50000:
            cons.append("Shorter tread life — replace sooner")
        if t.member_price > 200:
            cons.append("Premium price point")
        if t.wet_grip == "C":
            cons.append("Average wet performance")
        if not pros:
            pros.append("Good all-round performance")

        pros_cons[t.id] = {"pros": pros[:3], "cons": cons[:2]}

    comparison = {
        "tyres": [t.model_dump() for t in tyres],
        "columns": [
            {
                "field": "member_price",
                "label": "Member Price",
                "values": {t.id: f"${t.member_price:.2f}" for t in tyres},
            },
            {
                "field": "tread_life_km",
                "label": "Tread Life",
                "values": {t.id: f"{t.tread_life_km:,} km" for t in tyres},
            },
            {
                "field": "noise_db",
                "label": "Road Noise",
                "values": {t.id: f"{t.noise_db} dB" for t in tyres},
            },
            {
                "field": "warranty_years",
                "label": "Warranty",
                "values": {t.id: f"{t.warranty_years} yrs" for t in tyres},
            },
            {
                "field": "wet_grip",
                "label": "Wet Grip",
                "values": {t.id: t.wet_grip for t in tyres},
            },
        ],
        "pros_cons": pros_cons,
        "cost_per_1000km": cost_per_km,
    }
    return json.dumps(comparison)
