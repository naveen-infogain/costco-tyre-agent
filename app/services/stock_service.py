"""
Stock Filter Service — checks tyre availability per location, removes OOS entries,
and replaces them with the next best in-stock alternative.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from app.models.schemas import Tyre, TyreStock

_DATA_PATH = Path(__file__).parent.parent / "data" / "tyres.json"


def _load_tyres() -> list[Tyre]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return [Tyre(**t) for t in json.load(f)]


def get_all_tyres() -> list[Tyre]:
    return _load_tyres()


def get_tyre_by_id(tyre_id: str) -> Optional[Tyre]:
    for t in _load_tyres():
        if t.id == tyre_id:
            return t
    return None


def check_stock(tyre_ids: list[str], warehouse_id: Optional[str] = None) -> dict[str, bool]:
    """
    Returns {tyre_id: in_stock} for each requested ID.
    If warehouse_id is given, checks that specific warehouse; otherwise any stock counts.
    """
    result: dict[str, bool] = {}
    tyres = {t.id: t for t in _load_tyres()}
    for tid in tyre_ids:
        tyre = tyres.get(tid)
        if not tyre:
            result[tid] = False
        elif warehouse_id:
            result[tid] = (tyre.stock.warehouse_id == warehouse_id and tyre.stock.qty > 0)
        else:
            result[tid] = tyre.stock.qty > 0
    return result


def filter_in_stock(tyres: list[Tyre], warehouse_id: Optional[str] = None) -> list[Tyre]:
    """Remove out-of-stock tyres from a list."""
    if warehouse_id:
        return [t for t in tyres if t.stock.warehouse_id == warehouse_id and t.stock.qty > 0]
    return [t for t in tyres if t.stock.qty > 0]


def get_stock_badge(tyre: Tyre, locations: list[dict]) -> str:
    """Return a human-readable stock badge for display."""
    loc_map = {loc["id"]: loc["name"] for loc in locations}
    if tyre.stock.qty == 0:
        return "❌ Out of stock"
    loc_name = loc_map.get(tyre.stock.warehouse_id, tyre.stock.warehouse_id)
    short_name = loc_name.replace("Costco Tyre Centre — ", "")
    return f"✅ In stock at {short_name}"


def search_tyres(
    size: Optional[str] = None,
    season: Optional[str] = None,
    terrain: Optional[str] = None,
    max_price: Optional[float] = None,
    brand: Optional[str] = None,
    in_stock_only: bool = True,
) -> list[Tyre]:
    """
    Filter tyre catalogue by criteria. Returns matching tyres sorted by rating desc.
    """
    tyres = _load_tyres()

    if size:
        tyres = [t for t in tyres if t.size == size]
    if season:
        tyres = [t for t in tyres if t.season == season]
    if terrain:
        tyres = [t for t in tyres if t.terrain == terrain]
    if max_price:
        tyres = [t for t in tyres if t.member_price <= max_price]
    if brand:
        tyres = [t for t in tyres if t.brand.lower() == brand.lower()]
    if in_stock_only:
        tyres = filter_in_stock(tyres)

    return sorted(tyres, key=lambda t: t.rating, reverse=True)


def get_available_sizes() -> list[str]:
    """Return all distinct tyre sizes currently in stock, sorted."""
    tyres = filter_in_stock(_load_tyres())
    return sorted({t.size for t in tyres})


def broaden_search(
    size: Optional[str] = None,
    season: Optional[str] = None,
    max_price: Optional[float] = None,
) -> list[Tyre]:
    """Relax terrain first, then season, to find alternatives when primary search fails."""
    # Relax terrain — keep size + season
    results = search_tyres(size=size, season=season, max_price=max_price)
    if results:
        return results

    # Relax season too — only size constraint
    results = search_tyres(size=size, max_price=max_price)
    return results
