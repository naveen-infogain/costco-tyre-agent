"""
scripts/insert_265_60R18.py
---------------------------
Inserts 5 x 265/60R18 SUV tyres into:
  1. app/data/tyres.json  (JSON fallback — always updated)
  2. PostgreSQL products table (updated only if DB is reachable)

Run from project root:
    python scripts/insert_265_60R18.py
"""
from __future__ import annotations
import json, os, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# 5 tyres for size 265/60R18  (common SUV / light-truck fitment)
# ---------------------------------------------------------------------------
TYRES = [
    {
        "id": "LOCAL-265-60R18-001",
        "brand": "Michelin",
        "model": "LTX M/S2",
        "size": "265/60R18",
        "load_index": 110,
        "speed_rating": "H",
        "season": "all-season",
        "terrain": "highway",
        "price": 259.99,
        "member_price": 234.99,
        "tread_life_km": 100000,
        "wet_grip": "A",
        "noise_db": 70,
        "rating": 4.7,
        "review_count": 2340,
        "warranty_years": 5,
        "units_in_stock": 28,
        "warehouse_id": "W001",
        "active_promotion": "Save $30 on a set of 4",
        "description": (
            "Michelin LTX M/S2 is a premium all-season tyre for SUVs and light trucks. "
            "Delivers confident year-round traction, low road noise, and impressive tread life — "
            "ideal for highway driving and daily commuting."
        ),
        "compatible_vehicles": [
            "Toyota LandCruiser 2018-2024", "Ford Explorer 2018-2024",
            "Chevrolet Tahoe 2016-2024", "Nissan Patrol 2015-2024",
        ],
    },
    {
        "id": "LOCAL-265-60R18-002",
        "brand": "Bridgestone",
        "model": "Dueler H/P Sport",
        "size": "265/60R18",
        "load_index": 110,
        "speed_rating": "H",
        "season": "all-season",
        "terrain": "highway",
        "price": 239.99,
        "member_price": 214.99,
        "tread_life_km": 85000,
        "wet_grip": "A",
        "noise_db": 69,
        "rating": 4.5,
        "review_count": 1870,
        "warranty_years": 5,
        "units_in_stock": 20,
        "warehouse_id": "W002",
        "active_promotion": None,
        "description": (
            "Bridgestone Dueler H/P Sport combines sporty handling with everyday comfort for SUVs and 4WDs. "
            "Responsive steering, strong wet-road grip, and a quiet ride make it excellent for highway use."
        ),
        "compatible_vehicles": [
            "BMW X5 2018-2024", "Mercedes GLE 2018-2024",
            "Toyota Prado 2015-2024", "Mitsubishi Pajero Sport 2016-2024",
        ],
    },
    {
        "id": "LOCAL-265-60R18-003",
        "brand": "Goodyear",
        "model": "Wrangler HP All Weather",
        "size": "265/60R18",
        "load_index": 110,
        "speed_rating": "H",
        "season": "all-weather",
        "terrain": "all-terrain",
        "price": 219.99,
        "member_price": 194.99,
        "tread_life_km": 80000,
        "wet_grip": "A",
        "noise_db": 71,
        "rating": 4.4,
        "review_count": 1340,
        "warranty_years": 4,
        "units_in_stock": 16,
        "warehouse_id": "W003",
        "active_promotion": "Save $20 on a set of 4",
        "description": (
            "Goodyear Wrangler HP All Weather delivers all-terrain versatility with all-weather confidence. "
            "3-Peak Mountain Snowflake rated — ideal for SUVs that tackle city roads and weekend trails."
        ),
        "compatible_vehicles": [
            "Ford Everest 2018-2024", "Toyota Fortuner 2016-2024",
            "Isuzu MU-X 2015-2024", "Nissan Navara 2015-2024",
        ],
    },
    {
        "id": "LOCAL-265-60R18-004",
        "brand": "Continental",
        "model": "CrossContact LX20",
        "size": "265/60R18",
        "load_index": 110,
        "speed_rating": "H",
        "season": "all-season",
        "terrain": "highway",
        "price": 229.99,
        "member_price": 204.99,
        "tread_life_km": 90000,
        "wet_grip": "A",
        "noise_db": 68,
        "rating": 4.6,
        "review_count": 980,
        "warranty_years": 5,
        "units_in_stock": 12,
        "warehouse_id": "W001",
        "active_promotion": None,
        "description": (
            "Continental CrossContact LX20 combines long tread life with a comfortable, quiet ride. "
            "Excellent wet and dry handling with EcoPlus technology for improved fuel efficiency."
        ),
        "compatible_vehicles": [
            "Hyundai Santa Fe 2018-2024", "Kia Sorento 2018-2024",
            "Volkswagen Tiguan 2017-2024", "Skoda Kodiaq 2017-2024",
        ],
    },
    {
        "id": "LOCAL-265-60R18-005",
        "brand": "Pirelli",
        "model": "Scorpion Verde All Season",
        "size": "265/60R18",
        "load_index": 110,
        "speed_rating": "H",
        "season": "all-season",
        "terrain": "highway",
        "price": 249.99,
        "member_price": 224.99,
        "tread_life_km": 95000,
        "wet_grip": "A",
        "noise_db": 69,
        "rating": 4.8,
        "review_count": 760,
        "warranty_years": 5,
        "units_in_stock": 18,
        "warehouse_id": "W004",
        "active_promotion": "Save $25 on a set of 4",
        "description": (
            "Pirelli Scorpion Verde All Season is a premium SUV tyre engineered for low environmental impact "
            "without sacrificing performance. Outstanding grip, low rolling resistance, and a refined ride."
        ),
        "compatible_vehicles": [
            "Porsche Cayenne 2018-2024", "Audi Q7 2017-2024",
            "Land Rover Discovery 2017-2024", "Jeep Grand Cherokee 2016-2024",
        ],
    },
]


# ---------------------------------------------------------------------------
# 1. Update tyres.json
# ---------------------------------------------------------------------------
def update_json():
    path = Path(__file__).parent.parent / "app" / "data" / "tyres.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    existing_ids = {t["id"] for t in existing}

    added = 0
    for t in TYRES:
        entry = {
            "id": t["id"], "brand": t["brand"], "model": t["model"],
            "size": t["size"], "load_index": t["load_index"],
            "speed_rating": t["speed_rating"], "season": t["season"],
            "terrain": t["terrain"], "price": t["price"],
            "member_price": t["member_price"], "tread_life_km": t["tread_life_km"],
            "wet_grip": t["wet_grip"], "noise_db": t["noise_db"],
            "rating": t["rating"], "review_count": t["review_count"],
            "warranty_years": t["warranty_years"],
            "compatible_vehicles": t["compatible_vehicles"],
            "stock": {"warehouse_id": t["warehouse_id"], "qty": t["units_in_stock"]},
            "active_promotion": t["active_promotion"],
            "image_url": None,
            "description": t["description"],
        }
        if entry["id"] in existing_ids:
            existing = [entry if e["id"] == entry["id"] else e for e in existing]
            print(f"  JSON updated : {t['brand']} {t['model']}")
        else:
            existing.append(entry)
            added += 1
            print(f"  JSON added   : {t['brand']} {t['model']}")

    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"tyres.json saved — {added} new entries added\n")


# ---------------------------------------------------------------------------
# 2. Insert into PostgreSQL
# ---------------------------------------------------------------------------
def update_db():
    try:
        import psycopg2
        from psycopg2.extras import execute_batch
    except ImportError:
        print("psycopg2 not installed — skipping DB insert")
        return

    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 5432)),
            dbname=os.environ.get("DB_NAME", "costco_tyre"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", "postgres"),
        )
    except Exception as e:
        print(f"DB connection failed: {e}\nSkipping DB insert (JSON already updated).")
        return

    rows = []
    now  = datetime.utcnow()
    for t in TYRES:
        rows.append((
            t["id"],
            f"{t['brand']} {t['model']}",
            t["brand"], t["model"], t["size"],
            265, 60, 18,                   # width, aspect_ratio, rim_diameter
            t["price"], t["member_price"],
            t["units_in_stock"],
            t["description"], None,        # image_url
            True,                          # installation_included
            "SUV/Truck",                   # category
            t["season"], t["terrain"],
            t["load_index"], t["speed_rating"],
            t["wet_grip"], t["noise_db"],
            t["tread_life_km"], t["rating"],
            t["review_count"], t["warranty_years"],
            t["active_promotion"], t["warehouse_id"],
            now,
        ))

    with conn:
        with conn.cursor() as cur:
            execute_batch(cur, """
                INSERT INTO products
                    (sf_id, name, brand, model, size, width, aspect_ratio, rim_diameter,
                     price, member_price, units_in_stock, description, image_url,
                     installation_included, category, season, terrain, load_index,
                     speed_rating, wet_grip, noise_db, tread_life_km, rating,
                     review_count, warranty_years, active_promotion, warehouse_id, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (sf_id) DO UPDATE SET
                    units_in_stock   = EXCLUDED.units_in_stock,
                    member_price     = EXCLUDED.member_price,
                    rating           = EXCLUDED.rating,
                    review_count     = EXCLUDED.review_count,
                    active_promotion = EXCLUDED.active_promotion
            """, rows)

    conn.close()
    for t in TYRES:
        print(f"  DB inserted  : {t['brand']} {t['model']}")
    print(f"DB: {len(rows)} rows inserted/updated\n")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\nInserting {len(TYRES)} tyres of size 265/60R18...\n")
    update_json()
    update_db()
    print("Done.")
