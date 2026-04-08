"""
Recommendation Tools — LangChain @tool wrappers for tyre search, ranking,
and top-pick selection used by the Rec & Ranking Agent.
"""
from __future__ import annotations
import json
from typing import Optional
from langchain_core.tools import tool
from app.services import stock_service


@tool
def search_tyres(
    size: Optional[str] = None,
    season: Optional[str] = None,
    terrain: Optional[str] = None,
    max_price: Optional[float] = None,
    brand: Optional[str] = None,
) -> str:
    """
    Search the Costco tyre catalogue by criteria.
    Args:
        size: Tyre size string e.g. '205/55R16'
        season: 'all-season', 'winter', or 'summer'
        terrain: 'highway', 'city', or 'all-terrain'
        max_price: Maximum member price per tyre
        brand: Filter by brand name (e.g. 'Michelin')
    Returns JSON list of matching in-stock tyres sorted by rating.
    """
    results = stock_service.search_tyres(
        size=size, season=season, terrain=terrain,
        max_price=max_price, brand=brand, in_stock_only=True,
    )
    return json.dumps([t.model_dump() for t in results[:10]])


@tool
def get_tyre_details(tyre_id: str) -> str:
    """
    Get full details for a specific tyre by its ID.
    Used in Path A to fetch the member's previously purchased tyre.
    """
    tyre = stock_service.get_tyre_by_id(tyre_id)
    if not tyre:
        return json.dumps({"error": f"Tyre {tyre_id} not found"})
    return json.dumps(tyre.model_dump())


@tool
def rank_tyres(tyre_ids: list[str], ranking_signals: list[str]) -> str:
    """
    Rank a list of tyres by the given signals.
    ranking_signals can include: 'rating', 'value', 'tread_life', 'popularity', 'safety'
    Returns the tyre list re-ordered with rank scores attached.
    """
    tyres = []
    for tid in tyre_ids:
        t = stock_service.get_tyre_by_id(tid)
        if t:
            tyres.append(t)

    scored = []
    for t in tyres:
        score = 0.0
        if "rating" in ranking_signals:
            score += t.rating * 10
        if "value" in ranking_signals:
            # Value = tread_life per dollar (normalised)
            score += min(t.tread_life_km / t.member_price / 10, 10)
        if "tread_life" in ranking_signals:
            score += min(t.tread_life_km / 10000, 10)
        if "safety" in ranking_signals:
            wet_score = {"A": 3, "B": 2, "C": 1}.get(t.wet_grip, 0)
            speed_score = {"Y": 3, "W": 2, "V": 1, "H": 1}.get(t.speed_rating, 0)
            score += wet_score + speed_score
        if "popularity" in ranking_signals:
            score += min(t.review_count / 200, 5)
        scored.append({"tyre": t.model_dump(), "rank_score": round(score, 2)})

    scored.sort(key=lambda x: x["rank_score"], reverse=True)
    return json.dumps(scored)


@tool
def select_top_pick(ranked_tyres_json: str) -> str:
    """
    Select the #1 top pick from a ranked tyre list.
    Input: JSON string output from rank_tyres.
    Returns the top tyre with its rank score.
    """
    ranked = json.loads(ranked_tyres_json)
    if not ranked:
        return json.dumps({"error": "No tyres to rank"})
    return json.dumps(ranked[0])


@tool
def generate_punch_line(tyre_json: str) -> str:
    """
    Generate a bold, catchy one-liner for the Top Pick tyre.
    Input: JSON string of a tyre object.
    Returns a punch line string.
    """
    tyre = json.loads(tyre_json)
    brand = tyre.get("brand", "")
    model = tyre.get("model", "")
    tread = tyre.get("tread_life_km", 0)
    rating = tyre.get("rating", 0)
    wet = tyre.get("wet_grip", "")
    season = tyre.get("season", "")

    if rating >= 4.7 and wet == "A":
        return f"The {brand} {model} — top-rated grip meets {tread:,} km of confidence."
    elif tread >= 90000:
        return f"Go further with the {brand} {model} — {tread:,} km tread life, built to last."
    elif season == "winter":
        return f"Winter-ready from day one: the {brand} {model} grips where others slip."
    else:
        return f"Smart choice: the {brand} {model} delivers {rating}-star performance at member price."


@tool
def broaden_search(
    size: Optional[str] = None,
    season: Optional[str] = None,
    max_price: Optional[float] = None,
) -> str:
    """
    Broaden a tyre search when primary search returns 0 results.
    First relaxes terrain, then season. Returns best available alternatives.
    """
    results = stock_service.broaden_search(size=size, season=season, max_price=max_price)
    return json.dumps([t.model_dump() for t in results[:6]])


@tool
def handle_no_results() -> str:
    """
    Return a friendly no-results message and suggest restarting preference collection.
    Used when broaden_search also returns 0 results.
    """
    return json.dumps({
        "message": (
            "I couldn't find a match in our current catalogue for those exact requirements. "
            "Let's try a different approach — could you tell me your car's tyre size "
            "(you'll find it on the tyre sidewall or in your car manual)?"
        ),
        "action": "restart_collection",
    })
