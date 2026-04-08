"""
scripts/add_tyres_265_60R18.py
------------------------------
Inserts 4 x 265/60R18 SUV/truck tyres into:
  1. PostgreSQL products table (same schema as init_db.py)
  2. app/data/tyres.json (JSON fallback)

Run from project root:
    python scripts/add_tyres_265_60R18.py

Safe to re-run — uses ON CONFLICT DO UPDATE for DB, deduplicates by id for JSON.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 265/60R18 tyre catalogue — 4 entries covering different buyer profiles
# ---------------------------------------------------------------------------
TYRES_265_60R18 = [
    {
        "id":           "LOCAL-265-60R18-MIC-LTX",
        "brand":        "Michelin",
        "model":        "LTX M/S2",
        "size":         "265/60R18",
        "width":        265,
        "aspect_ratio": 60,
        "rim_diameter": 18,
        "load_index":   110,
        "speed_rating": "H",
        "season":       "all-season",
        "terrain":      "highway",
        "price":        259.99,
        "member_price": 234.99,
        "tread_life_km":  100000,
        "wet_grip":     "A",
        "noise_db":     70,
        "rating":       4.7,
        "review_count": 2340,
        "warranty_years": 5,
        "units_in_stock": 28,
        "warehouse_id": "W001",
        "active_promotion": "Save $30 on a set of 4",
        "description": (
            "Michelin LTX M/S2 is a premium all-season tyre engineered for SUVs and light trucks. "
            "Delivers confident year-round traction, low road noise, and impressive tread life — "
            "ideal for highway driving and daily commuting in a full-size SUV."
        ),
        "image_url": "",
        "installation_included": True,
        "category": "SUV/Truck",
        "compatible_vehicles": [
            "Toyota LandCruiser 2018-2024", "Ford Explorer 2018-2024",
            "Chevrolet Tahoe 2016-2024", "Nissan Patrol 2015-2024",
        ],
    },
    {
        "id":           "LOCAL-265-60R18-BRI-DUELER",
        "brand":        "Bridgestone",
        "model":        "Dueler H/P Sport",
        "size":         "265/60R18",
        "width":        265,
        "aspect_ratio": 60,
        "rim_diameter": 18,
        "load_index":   110,
        "speed_rating": "H",
        "season":       "all-season",
        "terrain":      "highway",
        "price":        239.99,
        "member_price": 214.99,
        "tread_life_km": 85000,
        "wet_grip":     "A",
        "noise_db":     69,
        "rating":       4.5,
        "review_count": 1870,
        "warranty_years": 5,
        "units_in_stock": 20,
        "warehouse_id": "W002",
        "active_promotion": None,
        "description": (
            "Bridgestone Dueler H/P Sport combines sporty handling with everyday comfort for SUVs and 4WDs. "
            "Responsive steering, strong wet-road grip, and a quiet ride make it an excellent choice "
            "for highway performance in larger vehicles."
        ),
        "image_url": "",
        "installation_included": True,
        "category": "SUV/Truck",
        "compatible_vehicles": [
            "BMW X5 2018-2024", "Mercedes GLE 2018-2024",
            "Toyota Prado 2015-2024", "Mitsubishi Pajero Sport 2016-2024",
        ],
    },
    {
        "id":           "LOCAL-265-60R18-GY-WRANGLER",
        "brand":        "Goodyear",
        "model":        "Wrangler HP All Weather",
        "size":         "265/60R18",
        "width":        265,
        "aspect_ratio": 60,
        "rim_diameter": 18,
        "load_index":   110,
        "speed_rating": "H",
        "season":       "all-weather",
        "terrain":      "all-terrain",
        "price":        219.99,
        "member_price": 194.99,
        "tread_life_km": 80000,
        "wet_grip":     "A",
        "noise_db":     71,
        "rating":       4.4,
        "review_count": 1340,
        "warranty_years": 4,
        "units_in_stock": 16,
        "warehouse_id": "W003",
        "active_promotion": "Save $20 on a set of 4",
        "description": (
            "Goodyear Wrangler HP All Weather delivers all-terrain versatility with all-weather confidence. "
            "Built for SUVs that tackle both city roads and weekend off-road adventures. "
            "3-Peak Mountain Snowflake rated for light snow traction."
        ),
        "image_url": "",
        "installation_included": True,
        "category": "SUV/Truck",
        "compatible_vehicles": [
            "Ford Everest 2018-2024", "Toyota Fortuner 2016-2024",
            "Isuzu MU-X 2015-2024", "Nissan Navara 2015-2024",
        ],
    },
    {
        "id":           "LOCAL-265-60R18-CON-CROSSCONTACT",
        "brand":        "Continental",
        "model":        "CrossContact LX20",
        "size":         "265/60R18",
        "width":        265,
        "aspect_ratio": 60,
        "rim_diameter": 18,
        "load_index":   110,
        "speed_rating": "H",
        "season":       "all-season",
        "terrain":      "highway",
        "price":        229.99,
        "member_price": 204.99,
        "tread_life_km": 90000,
        "wet_grip":     "A",
        "noise_db":     68,
        "rating":       4.6,
        "review_count": 980,
        "warranty_years": 5,
        "units_in_stock": 12,
        "warehouse_id": "W001",
        "active_promotion": None,
        "description": (
            "Continental CrossContact LX20 is a premium SUV tyre combining long tread life with "
            "a comfortable, quiet ride. Excellent wet and dry handling with EcoPlus technology "
            "for improved fuel efficiency — perfect for crossovers and SUVs."
        ),
        "image_url": "",
        "installation_included": True,
        "category": "SUV/Truck",
        "compatible_vehicles": [
            "Hyundai Santa Fe 2018-2024", "Kia Sorento 2018-2024",
            "Skoda Kodiaq 2017-2024", "Volkswagen Tiguan 2017-2024",
        ],
    },
]


# ---------------------------------------------------------------------------
# 1. Insert into PostgreSQL
# ---------------------------------------------------------------------------
def insert_into_db():
    try:
        import psycopg2
        from psycopg2.extras import execute_batch
    except ImportError:
        log.warning("psycopg2 not installed — skipping DB insert")
        return

    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 5432)),
            dbname=os.environ.get("DB_NAME", "costco_tyre"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", "postgres"),
        )
    except Exception as exc:
        log.warning("DB connection failed (%s) — skipping DB insert", exc)
        return

    rows = []
    now  = datetime.utcnow()
    for t in TYRES_265_60R18:
        rows.append((
            t["id"],                       # sf_id
            f"{t['brand']} {t['model']}",  # name
            t["brand"],
            t["model"],
            t["size"],
            t["width"],
            t["aspect_ratio"],
            t["rim_diameter"],
            t["price"],
            t["member_price"],
            t["units_in_stock"],
            t["description"],
            t["image_url"],
            t["installation_included"],
            t["category"],
            t["season"],
            t["terrain"],
            t["load_index"],
            t["speed_rating"],
            t["wet_grip"],
            t["noise_db"],
            t["tread_life_km"],
            t["rating"],
            t["review_count"],
            t["warranty_years"],
            t["active_promotion"],
            t["warehouse_id"],
            now,
        ))

    with conn:
        with conn.cursor() as cur:
            execute_batch(cur, """
                INSERT INTO products
                    (sf_id, name, brand, model, size, width, aspect_ratio, rim_diameter,
                     price, member_price, units_in_stock, description, image_url,
                     installation_included, category, season, terrain, load_index,
                     speed_rating, wet_grip, noise_db, tread_life_km, rating, review_count,
                     warranty_years, active_promotion, warehouse_id, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (sf_id) DO UPDATE SET
                    units_in_stock = EXCLUDED.units_in_stock,
                    member_price   = EXCLUDED.member_price,
                    rating         = EXCLUDED.rating,
                    review_count   = EXCLUDED.review_count,
                    active_promotion = EXCLUDED.active_promotion
            """, rows)
    conn.close()
    log.info("DB: inserted/updated %d tyres (265/60R18)", len(rows))


# ---------------------------------------------------------------------------
# 2. Add to tyres.json (JSON fallback)
# ---------------------------------------------------------------------------
def insert_into_json():
    json_path = Path(__file__).parent.parent / "app" / "data" / "tyres.json"
    existing  = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else []

    existing_ids = {t["id"] for t in existing}
    added = 0
    for t in TYRES_265_60R18:
        entry = {
            "id":           t["id"],
            "brand":        t["brand"],
            "model":        t["model"],
            "size":         t["size"],
            "load_index":   t["load_index"],
            "speed_rating": t["speed_rating"],
            "season":       t["season"],
            "terrain":      t["terrain"],
            "price":        t["price"],
            "member_price": t["member_price"],
            "tread_life_km": t["tread_life_km"],
            "wet_grip":     t["wet_grip"],
            "noise_db":     t["noise_db"],
            "rating":       t["rating"],
            "review_count": t["review_count"],
            "warranty_years": t["warranty_years"],
            "compatible_vehicles": t["compatible_vehicles"],
            "stock": {
                "warehouse_id": t["warehouse_id"],
                "qty":          t["units_in_stock"],
            },
            "active_promotion": t["active_promotion"],
            "image_url":    t["image_url"],
            "description":  t["description"],
        }
        if entry["id"] in existing_ids:
            # Update in place
            existing = [entry if e["id"] == entry["id"] else e for e in existing]
            log.info("JSON: updated  %s %s", t["brand"], t["model"])
        else:
            existing.append(entry)
            added += 1
            log.info("JSON: added    %s %s", t["brand"], t["model"])

    json_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("JSON: saved %s (added %d new entries)", json_path, added)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log.info("Adding 265/60R18 tyres (%d entries)…", len(TYRES_265_60R18))
    insert_into_db()
    insert_into_json()
    log.info("Done.")
