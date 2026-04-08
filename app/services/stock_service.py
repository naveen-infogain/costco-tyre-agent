"""
Stock Filter Service — checks tyre availability per location, removes OOS entries,
and replaces them with the next best in-stock alternative.
Source priority: PostgreSQL (if configured) → tyres.json fallback.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from app.models.schemas import Tyre, TyreStock

log = logging.getLogger(__name__)
_DATA_PATH = Path(__file__).parent.parent / "data" / "tyres.json"


# ---------------------------------------------------------------------------
# DB loader
# ---------------------------------------------------------------------------

def _tyre_from_row(row: tuple, columns: list[str]) -> Tyre:
    """Convert a DB row into a Tyre model."""
    d = dict(zip(columns, row))
    stock = TyreStock(
        warehouse_id=d.get("warehouse_id") or "W001",
        qty=int(d.get("units_in_stock") or 0),
    )
    return Tyre(
        id=d["sf_id"],
        brand=d.get("brand") or "",
        model=d.get("model") or "",
        size=d.get("size") or "205/55R16",
        load_index=int(d.get("load_index") or 91),
        speed_rating=d.get("speed_rating") or "V",
        season=d.get("season") or "all-season",
        terrain=d.get("terrain") or "highway",
        price=float(d.get("price") or 0),
        member_price=float(d.get("member_price") or 0),
        tread_life_km=int(d.get("tread_life_km") or 60000),
        wet_grip=d.get("wet_grip") or "B",
        noise_db=int(d.get("noise_db") or 70),
        rating=float(d.get("rating") or 4.0),
        review_count=int(d.get("review_count") or 100),
        warranty_years=int(d.get("warranty_years") or 4),
        compatible_vehicles=[],
        stock=stock,
        active_promotion=d.get("active_promotion") or None,
        image_url=d.get("image_url") or None,
        description=d.get("description") or None,
    )


def _load_tyres_db() -> list[Tyre]:
    """Fetch all products from PostgreSQL."""
    try:
        from app.db.connection import get_conn, release_conn, db_available
        if not db_available():
            return []
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT sf_id, brand, model, size, load_index, speed_rating,
                           season, terrain, price, member_price, tread_life_km,
                           wet_grip, noise_db, rating, review_count, warranty_years,
                           units_in_stock, warehouse_id, active_promotion,
                           image_url, description
                    FROM products
                    WHERE units_in_stock > 0
                    ORDER BY rating DESC
                """)
                cols = [c.name for c in cur.description]
                return [_tyre_from_row(row, cols) for row in cur.fetchall()]
        finally:
            release_conn(conn)
    except Exception as e:
        log.warning("DB load_tyres failed (%s) — falling back to JSON", e)
        return []


# ---------------------------------------------------------------------------
# JSON fallback
# ---------------------------------------------------------------------------

def _load_tyres_json() -> list[Tyre]:
    if not _DATA_PATH.exists():
        return []
    with open(_DATA_PATH, encoding="utf-8") as f:
        return [Tyre(**t) for t in json.load(f)]


def _load_tyres() -> list[Tyre]:
    """DB first, JSON fallback."""
    tyres = _load_tyres_db()
    if tyres:
        return tyres
    return _load_tyres_json()


# ---------------------------------------------------------------------------
# Public API (unchanged signatures — drop-in replacement)
# ---------------------------------------------------------------------------

def get_all_tyres() -> list[Tyre]:
    return _load_tyres()


def get_tyre_by_id(tyre_id: str) -> Optional[Tyre]:
    """DB lookup by sf_id first, then full scan."""
    try:
        from app.db.connection import get_conn, release_conn, db_available
        if db_available():
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sf_id, brand, model, size, load_index, speed_rating,
                               season, terrain, price, member_price, tread_life_km,
                               wet_grip, noise_db, rating, review_count, warranty_years,
                               units_in_stock, warehouse_id, active_promotion,
                               image_url, description
                        FROM products WHERE sf_id = %s
                    """, (tyre_id,))
                    cols = [c.name for c in cur.description]
                    row = cur.fetchone()
                    if row:
                        return _tyre_from_row(row, cols)
            finally:
                release_conn(conn)
    except Exception as e:
        log.debug("get_tyre_by_id DB failed: %s", e)

    # JSON fallback
    for t in _load_tyres_json():
        if t.id == tyre_id:
            return t
    return None


def check_stock(tyre_ids: list[str], warehouse_id: Optional[str] = None) -> dict[str, bool]:
    tyres = {t.id: t for t in _load_tyres()}
    result: dict[str, bool] = {}
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
    if warehouse_id:
        return [t for t in tyres if t.stock.warehouse_id == warehouse_id and t.stock.qty > 0]
    return [t for t in tyres if t.stock.qty > 0]


def get_stock_badge(tyre: Tyre, locations: list[dict]) -> str:
    loc_map = {loc["id"]: loc["name"] for loc in locations}
    if tyre.stock.qty == 0:
        return "Out of stock"
    loc_name = loc_map.get(tyre.stock.warehouse_id, tyre.stock.warehouse_id)
    # Strip prefix robustly — handles any em-dash encoding variant
    import re as _re
    short_name = _re.split(r"Costco Tyre Centre\s*[—\-–]+\s*", loc_name, maxsplit=1)[-1].strip()
    return f"In stock at {short_name}"


def search_tyres(
    size: Optional[str] = None,
    season: Optional[str] = None,
    terrain: Optional[str] = None,
    max_price: Optional[float] = None,
    brand: Optional[str] = None,
    in_stock_only: bool = True,
) -> list[Tyre]:
    """
    Filter tyre catalogue by criteria. DB query when available for efficiency,
    otherwise in-memory filter on JSON data.
    """
    try:
        from app.db.connection import get_conn, release_conn, db_available
        if db_available():
            conn = get_conn()
            try:
                conditions = ["1=1"]
                params: list = []
                if in_stock_only:
                    conditions.append("units_in_stock > 0")
                if size:
                    conditions.append("size = %s")
                    params.append(size)
                if season:
                    conditions.append("season = %s")
                    params.append(season)
                if terrain:
                    conditions.append("terrain = %s")
                    params.append(terrain)
                if max_price:
                    conditions.append("member_price <= %s")
                    params.append(max_price)
                if brand:
                    conditions.append("LOWER(brand) = LOWER(%s)")
                    params.append(brand)

                with conn.cursor() as cur:
                    cur.execute(f"""
                        SELECT sf_id, brand, model, size, load_index, speed_rating,
                               season, terrain, price, member_price, tread_life_km,
                               wet_grip, noise_db, rating, review_count, warranty_years,
                               units_in_stock, warehouse_id, active_promotion,
                               image_url, description
                        FROM products
                        WHERE {' AND '.join(conditions)}
                        ORDER BY rating DESC
                    """, params)
                    cols = [c.name for c in cur.description]
                    db_results = [_tyre_from_row(row, cols) for row in cur.fetchall()]
                    if db_results:
                        return db_results
                    # DB returned 0 rows for this criteria — supplement from JSON
                    # (covers Indian-market tyres that exist in tyres.json but not in DB)
                    log.debug("search_tyres: DB returned 0 rows, supplementing from JSON")
            finally:
                release_conn(conn)
    except Exception as e:
        log.warning("search_tyres DB failed (%s) — falling back to JSON", e)

    # JSON fallback (also reached when DB returns 0 rows for the given criteria)
    tyres = _load_tyres_json()
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
    try:
        from app.db.connection import get_conn, release_conn, db_available
        if db_available():
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT size FROM products WHERE units_in_stock > 0 ORDER BY size"
                    )
                    db_sizes = [row[0] for row in cur.fetchall()]
            finally:
                release_conn(conn)
            # Merge with JSON sizes (covers Indian-market tyres not in DB)
            json_sizes = {t.size for t in filter_in_stock(_load_tyres_json())}
            return sorted(set(db_sizes) | json_sizes)
    except Exception as e:
        log.debug("get_available_sizes DB failed: %s", e)

    tyres = filter_in_stock(_load_tyres_json())
    return sorted({t.size for t in tyres})


def broaden_search(
    size: Optional[str] = None,
    season: Optional[str] = None,
    max_price: Optional[float] = None,
) -> list[Tyre]:
    results = search_tyres(size=size, season=season, max_price=max_price)
    if results:
        return results
    results = search_tyres(size=size, max_price=max_price)
    return results
