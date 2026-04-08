"""
scripts/init_db.py
------------------
One-time setup script: creates all PostgreSQL tables and loads CRM CSV data.

Tasks covered:
  Task 2 — Insert CRM CSV data into PostgreSQL
  Task 3 — Generate synthetic fields for data missing from CRM
            (season, terrain, rating, member_price, vehicle, membership_tier, etc.)

Run once (idempotent — safe to re-run):
    python scripts/init_db.py

Requires .env with DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD set.
"""
from __future__ import annotations

import csv
import hashlib
import logging
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

# Make sure app package is importable from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_batch

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CRM_DIR = Path(__file__).parent.parent / "app" / "crm_data"

PRODUCT_CSV     = CRM_DIR / "Costco_Product__c-4_8_2026.csv"
CONTACT_CSV     = CRM_DIR / "Contact-4_8_2026.csv"
ORDER_CSV       = CRM_DIR / "Costco_Order__c-4_8_2026.csv"
ORDER_ITEM_CSV  = CRM_DIR / "Order_Item__c-4_8_2026.csv"
TRANSACTION_CSV = CRM_DIR / "Transaction__c-4_8_2026.csv"
CART_CSV        = CRM_DIR / "Costco_Cart__c-4_8_2026.csv"
CART_ITEM_CSV   = CRM_DIR / "Cart_Item__c-4_8_2026.csv"
ENGAGEMENT_CSV  = CRM_DIR / "Engagement__c-4_8_2026.csv"

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------
def get_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "costco_tyre"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
    )

# ---------------------------------------------------------------------------
# CSV reader — strips the Salesforce [Type] prefix in the first column
# ---------------------------------------------------------------------------
def read_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Remove the Salesforce "[ObjectType]" marker column
            clean = {k: (v.strip() if v else "") for k, v in row.items() if k != "_"}
            rows.append(clean)
    return rows

# ---------------------------------------------------------------------------
# Synthetic data helpers — Task 3
# ---------------------------------------------------------------------------

_KNOWN_BRANDS = [
    "Michelin", "Bridgestone", "Pirelli", "Continental", "Goodyear",
    "Hankook", "Yokohama", "Cooper", "Dunlop", "Falken", "BFGoodrich",
    "Firestone", "Kumho", "Toyo", "Nexen", "General",
]

def _extract_brand(name: str) -> tuple[str, str]:
    """Split 'Michelin Defender T+H' → ('Michelin', 'Defender T+H')."""
    for brand in _KNOWN_BRANDS:
        if name.lower().startswith(brand.lower()):
            model = name[len(brand):].strip()
            return brand, model or name
    # fallback: first word is brand
    parts = name.split(None, 1)
    return parts[0], parts[1] if len(parts) > 1 else parts[0]


def _infer_season(description: str) -> str:
    d = description.lower()
    if any(k in d for k in ["winter", "snow", "ice", "cold weather"]):
        return "winter"
    if any(k in d for k in ["summer", "performance", "sport", "high-performance"]):
        return "summer"
    return "all-season"


def _infer_terrain(description: str, name: str) -> str:
    text = (description + " " + name).lower()
    if any(k in text for k in ["off-road", "all-terrain", "mud", "truck", "suv", "4x4"]):
        return "all-terrain"
    if any(k in text for k in ["city", "urban", "commute"]):
        return "city"
    return "highway"


def _synthetic_product_fields(row: dict) -> dict:
    """Generate realistic values for fields missing from the CRM product record."""
    rng = random.Random(row["Id"])  # deterministic per product

    price = float(row.get("Price__c") or 0) or 150.0
    units = int(row.get("Units__c") or 0)
    desc  = row.get("Description__c", "")
    name  = row.get("Name", "")

    brand, model = _extract_brand(name)

    # Tyre size: Width/Aspect_ratioRRim_Diameter
    width  = row.get("Width__c", "").strip()
    ratio  = row.get("Aspect_ratio__c", "").strip()
    rim    = row.get("Rim_Diameter__c", "").strip()
    size   = f"{width}/{ratio}R{rim}" if width and ratio and rim else "205/55R16"

    # Member price ≈ 85–92% of retail
    member_price = round(price * rng.uniform(0.85, 0.92), 2)

    # Season & terrain inferred from description
    season  = _infer_season(desc)
    terrain = _infer_terrain(desc, name)

    # Load index: based on rim diameter
    load_map = {"13": 82, "14": 85, "15": 89, "16": 91, "17": 94, "18": 97,
                "19": 99, "20": 102, "21": 105}
    load_index = load_map.get(rim, 91)

    # Speed rating: based on season/type
    speed_rating = "W" if season == "winter" else ("Y" if "performance" in desc.lower() else "V")

    # Wet grip A/B/C — premium brands → A, others → B
    premium = {"Michelin", "Bridgestone", "Continental", "Pirelli"}
    wet_grip = "A" if brand in premium else rng.choice(["A", "B"])

    # Noise dB 64–73
    noise_db = rng.randint(64, 73)

    # Tread life: longer for higher price
    tread_life = int((price / 100) * 20000 + rng.randint(30000, 60000))
    tread_life = round(tread_life / 5000) * 5000  # round to 5k

    # Rating 4.1–4.9
    rating = round(rng.uniform(4.1, 4.9), 1)

    # Review count: correlated with units sold
    review_count = rng.randint(max(50, units * 5), max(200, units * 20))

    # Warranty
    warranty_years = 5 if brand in premium else rng.choice([3, 4, 5])

    # Promotion
    promos = [
        f"Save ${rng.randint(10,30)} on a set of 4",
        "Free installation on set of 4",
        "Member exclusive pricing",
        "",  # no promotion
    ]
    active_promo = rng.choice(promos)

    # Warehouse — distribute across 5 warehouses
    warehouse_id = f"W{rng.randint(1,5):03d}"

    return {
        "brand": brand,
        "model": model,
        "size": size,
        "width": int(width) if width.isdigit() else None,
        "aspect_ratio": int(ratio) if ratio.isdigit() else None,
        "rim_diameter": int(rim) if rim.isdigit() else None,
        "member_price": member_price,
        "season": season,
        "terrain": terrain,
        "load_index": load_index,
        "speed_rating": speed_rating,
        "wet_grip": wet_grip,
        "noise_db": noise_db,
        "tread_life_km": tread_life,
        "rating": rating,
        "review_count": review_count,
        "warranty_years": warranty_years,
        "active_promotion": active_promo,
        "warehouse_id": warehouse_id,
    }


_VEHICLES = [
    ("Honda", "CR-V", 2021), ("Toyota", "Camry", 2020), ("Ford", "F-150", 2022),
    ("Honda", "Civic", 2021), ("Toyota", "RAV4", 2022), ("Hyundai", "Creta", 2022),
    ("Kia", "Seltos", 2021), ("BMW", "3 Series", 2020), ("Maruti", "Swift", 2021),
    ("Tata", "Nexon", 2022), ("Mahindra", "Scorpio N", 2022), ("Volkswagen", "Tiguan", 2020),
    ("Chevrolet", "Equinox", 2021), ("Nissan", "Rogue", 2021), ("Subaru", "Outback", 2020),
]

_HABITS = [
    ["highway", "daily commute"],
    ["city", "daily commute"],
    ["highway", "long drive"],
    ["city", "weekend"],
    ["off-road", "highway"],
    ["daily commute"],
    ["highway"],
]

_TIERS = ["standard", "standard", "standard", "gold", "gold", "executive"]


def _synthetic_contact_fields(sf_id: str, idx: int) -> dict:
    """Generate deterministic synthetic fields for a contact."""
    rng = random.Random(sf_id)
    vehicle = _VEHICLES[rng.randint(0, len(_VEHICLES) - 1)]
    habits  = _HABITS[rng.randint(0, len(_HABITS) - 1)]
    tier    = _TIERS[rng.randint(0, len(_TIERS) - 1)]
    member_id = f"M{10000 + idx + 1}"
    return {
        "member_id": member_id,
        "membership_tier": tier,
        "vehicle_make": vehicle[0],
        "vehicle_model": vehicle[1],
        "vehicle_year": vehicle[2],
        "driving_habits": habits,
    }

# ---------------------------------------------------------------------------
# DDL — create all tables
# ---------------------------------------------------------------------------
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS products (
    sf_id               VARCHAR PRIMARY KEY,
    name                VARCHAR NOT NULL,
    brand               VARCHAR NOT NULL,
    model               VARCHAR NOT NULL,
    size                VARCHAR NOT NULL,
    width               INTEGER,
    aspect_ratio        INTEGER,
    rim_diameter        INTEGER,
    price               NUMERIC(10,2),
    member_price        NUMERIC(10,2),
    units_in_stock      INTEGER DEFAULT 0,
    description         TEXT,
    image_url           VARCHAR,
    installation_included BOOLEAN DEFAULT FALSE,
    category            VARCHAR,
    season              VARCHAR DEFAULT 'all-season',
    terrain             VARCHAR DEFAULT 'highway',
    load_index          INTEGER,
    speed_rating        VARCHAR,
    wet_grip            VARCHAR,
    noise_db            INTEGER,
    tread_life_km       INTEGER,
    rating              NUMERIC(3,1),
    review_count        INTEGER,
    warranty_years      INTEGER,
    active_promotion    TEXT,
    warehouse_id        VARCHAR DEFAULT 'W001',
    created_at          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    sf_id               VARCHAR PRIMARY KEY,
    member_id           VARCHAR UNIQUE NOT NULL,
    first_name          VARCHAR,
    last_name           VARCHAR,
    full_name           VARCHAR,
    email               VARCHAR,
    phone               VARCHAR,
    mailing_street      VARCHAR,
    mailing_city        VARCHAR,
    mailing_state       VARCHAR,
    mailing_postal_code VARCHAR,
    username            VARCHAR,
    password            VARCHAR,
    membership_tier     VARCHAR DEFAULT 'standard',
    vehicle_make        VARCHAR,
    vehicle_model       VARCHAR,
    vehicle_year        INTEGER,
    driving_habits      TEXT[],
    created_at          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    sf_id               VARCHAR PRIMARY KEY,
    name                VARCHAR,
    contact_sf_id       VARCHAR REFERENCES contacts(sf_id) ON DELETE SET NULL,
    order_date          DATE,
    status              VARCHAR,
    total_amount        NUMERIC(10,2),
    created_at          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    sf_id               VARCHAR PRIMARY KEY,
    name                VARCHAR,
    order_sf_id         VARCHAR REFERENCES orders(sf_id) ON DELETE CASCADE,
    product_sf_id       VARCHAR REFERENCES products(sf_id) ON DELETE SET NULL,
    quantity            INTEGER,
    status              VARCHAR,
    total_amount        NUMERIC(10,2),
    created_at          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    sf_id               VARCHAR PRIMARY KEY,
    name                VARCHAR,
    contact_sf_id       VARCHAR REFERENCES contacts(sf_id) ON DELETE SET NULL,
    order_sf_id         VARCHAR REFERENCES orders(sf_id) ON DELETE SET NULL,
    payment_method      VARCHAR,
    status              VARCHAR,
    total_amount        NUMERIC(10,2),
    transaction_datetime TIMESTAMP,
    created_at          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS carts (
    sf_id               VARCHAR PRIMARY KEY,
    name                VARCHAR,
    contact_sf_id       VARCHAR REFERENCES contacts(sf_id) ON DELETE SET NULL,
    cart_date           DATE,
    total_amount        NUMERIC(10,2),
    created_at          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cart_items (
    sf_id               VARCHAR PRIMARY KEY,
    name                VARCHAR,
    cart_sf_id          VARCHAR REFERENCES carts(sf_id) ON DELETE CASCADE,
    product_sf_id       VARCHAR REFERENCES products(sf_id) ON DELETE SET NULL,
    quantity            INTEGER,
    total_price         NUMERIC(10,2),
    created_at          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS engagements (
    sf_id               VARCHAR PRIMARY KEY,
    name                VARCHAR,
    contact_sf_id       VARCHAR REFERENCES contacts(sf_id) ON DELETE SET NULL,
    campaign_name       VARCHAR,
    category            VARCHAR,
    coupon_code         VARCHAR,
    description         TEXT,
    product_sf_id       VARCHAR REFERENCES products(sf_id) ON DELETE SET NULL,
    search_term         VARCHAR,
    engagement_timestamp TIMESTAMP,
    website_action      VARCHAR,
    created_at          TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ts(val: str):
    """Parse Salesforce timestamp → datetime or None."""
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("+0000", "+00:00").replace("Z", "+00:00"))
    except ValueError:
        return None

def _date(val: str):
    """Parse YYYY-MM-DD date → date or None."""
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except ValueError:
        return None

def _float(val: str):
    try:
        return float(val) if val else None
    except ValueError:
        return None

def _int(val: str):
    try:
        return int(float(val)) if val else None
    except ValueError:
        return None

def _bool(val: str) -> bool:
    return str(val).lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_products(cur) -> None:
    rows = read_csv(PRODUCT_CSV)
    log.info("Loading %d products …", len(rows))
    data = []
    for row in rows:
        syn = _synthetic_product_fields(row)
        data.append((
            row["Id"],
            row.get("Name", ""),
            syn["brand"],
            syn["model"],
            syn["size"],
            syn["width"],
            syn["aspect_ratio"],
            syn["rim_diameter"],
            _float(row.get("Price__c")),
            syn["member_price"],
            _int(row.get("Units__c")),
            row.get("Description__c", ""),
            row.get("Image_Link__c", ""),
            _bool(row.get("Installation_Included__c")),
            row.get("Category__c", "Tire"),
            syn["season"],
            syn["terrain"],
            syn["load_index"],
            syn["speed_rating"],
            syn["wet_grip"],
            syn["noise_db"],
            syn["tread_life_km"],
            syn["rating"],
            syn["review_count"],
            syn["warranty_years"],
            syn["active_promotion"],
            syn["warehouse_id"],
            _ts(row.get("CreatedDate")),
        ))
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
            rating         = EXCLUDED.rating
    """, data)
    log.info("  ✓ %d products inserted/updated", len(data))


def load_contacts(cur) -> None:
    rows = read_csv(CONTACT_CSV)
    log.info("Loading %d contacts …", len(rows))
    data = []
    for idx, row in enumerate(rows):
        syn = _synthetic_contact_fields(row["Id"], idx)
        data.append((
            row["Id"],
            syn["member_id"],
            row.get("FirstName", ""),
            row.get("LastName", ""),
            row.get("Name", ""),
            row.get("Email", ""),
            row.get("Phone", ""),
            row.get("MailingStreet", ""),
            row.get("MailingCity", ""),
            row.get("MailingState", ""),
            row.get("MailingPostalCode", ""),
            row.get("Username__c", ""),
            row.get("Password__c", ""),
            syn["membership_tier"],
            syn["vehicle_make"],
            syn["vehicle_model"],
            syn["vehicle_year"],
            syn["driving_habits"],
            _ts(row.get("CreatedDate")),
        ))
    execute_batch(cur, """
        INSERT INTO contacts
            (sf_id, member_id, first_name, last_name, full_name, email, phone,
             mailing_street, mailing_city, mailing_state, mailing_postal_code,
             username, password, membership_tier, vehicle_make, vehicle_model,
             vehicle_year, driving_habits, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (sf_id) DO NOTHING
    """, data)
    log.info("  ✓ %d contacts inserted", len(data))


def load_orders(cur) -> None:
    rows = read_csv(ORDER_CSV)
    log.info("Loading %d orders …", len(rows))
    data = [
        (row["Id"], row.get("Name"), row.get("Contact__c") or None,
         _date(row.get("Order_Date__c")), row.get("Status__c"),
         _float(row.get("Total_Order_Amount__c")), _ts(row.get("CreatedDate")))
        for row in rows
    ]
    execute_batch(cur, """
        INSERT INTO orders (sf_id, name, contact_sf_id, order_date, status, total_amount, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (sf_id) DO NOTHING
    """, data)
    log.info("  ✓ %d orders inserted", len(data))


def load_order_items(cur) -> None:
    rows = read_csv(ORDER_ITEM_CSV)
    log.info("Loading %d order items …", len(rows))
    data = [
        (row["Id"], row.get("Name"), row.get("Order__c") or None,
         row.get("Product__c") or None, _int(row.get("Quantity__c")),
         row.get("Status__c"), _float(row.get("Total_Product_Amount__c")),
         _ts(row.get("CreatedDate")))
        for row in rows
    ]
    execute_batch(cur, """
        INSERT INTO order_items (sf_id, name, order_sf_id, product_sf_id, quantity, status, total_amount, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (sf_id) DO NOTHING
    """, data)
    log.info("  ✓ %d order items inserted", len(data))


def load_transactions(cur) -> None:
    rows = read_csv(TRANSACTION_CSV)
    log.info("Loading %d transactions …", len(rows))
    data = [
        (row["Id"], row.get("Name"), row.get("Contact__c") or None,
         row.get("Order__c") or None, row.get("Payment_Method__c"),
         row.get("Status__c"), _float(row.get("Total_Amount__c")),
         _ts(row.get("Transaction_Date_time__c")), _ts(row.get("CreatedDate")))
        for row in rows
    ]
    execute_batch(cur, """
        INSERT INTO transactions
            (sf_id, name, contact_sf_id, order_sf_id, payment_method, status,
             total_amount, transaction_datetime, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (sf_id) DO NOTHING
    """, data)
    log.info("  ✓ %d transactions inserted", len(data))


def load_carts(cur) -> None:
    rows = read_csv(CART_CSV)
    log.info("Loading %d carts …", len(rows))
    data = [
        (row["Id"], row.get("Name"), row.get("Contact__c") or None,
         _date(row.get("Date__c")), _float(row.get("Total_Cart_Amount__c")),
         _ts(row.get("CreatedDate")))
        for row in rows
    ]
    execute_batch(cur, """
        INSERT INTO carts (sf_id, name, contact_sf_id, cart_date, total_amount, created_at)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (sf_id) DO NOTHING
    """, data)
    log.info("  ✓ %d carts inserted", len(data))


def load_cart_items(cur) -> None:
    rows = read_csv(CART_ITEM_CSV)
    log.info("Loading %d cart items …", len(rows))
    data = [
        (row["Id"], row.get("Name"), row.get("Cart__c") or None,
         row.get("Product__c") or None, _int(row.get("Quantity__c")),
         _float(row.get("Total_Price__c")), _ts(row.get("CreatedDate")))
        for row in rows
    ]
    execute_batch(cur, """
        INSERT INTO cart_items (sf_id, name, cart_sf_id, product_sf_id, quantity, total_price, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (sf_id) DO NOTHING
    """, data)
    log.info("  ✓ %d cart items inserted", len(data))


def load_engagements(cur) -> None:
    rows = read_csv(ENGAGEMENT_CSV)
    log.info("Loading %d engagements …", len(rows))
    data = [
        (row["Id"], row.get("Name"), row.get("Contact__c") or None,
         row.get("Campaign_Name__c"), row.get("Category__c"),
         row.get("Coupon_Code__c"), row.get("Description__c"),
         row.get("Product__c") or None, row.get("Search_Term__c"),
         _ts(row.get("Timestamp__c")), row.get("Website_Action__c"),
         _ts(row.get("CreatedDate")))
        for row in rows
    ]
    execute_batch(cur, """
        INSERT INTO engagements
            (sf_id, name, contact_sf_id, campaign_name, category, coupon_code,
             description, product_sf_id, search_term, engagement_timestamp,
             website_action, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (sf_id) DO NOTHING
    """, data)
    log.info("  ✓ %d engagements inserted", len(data))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log.info("Connecting to PostgreSQL …")
    try:
        conn = get_connection()
    except Exception as e:
        log.error("Cannot connect: %s", e)
        log.error("Check DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD in .env")
        sys.exit(1)

    with conn:
        with conn.cursor() as cur:
            log.info("Creating tables …")
            cur.execute(CREATE_SQL)

            # Insert order matters for FK constraints
            load_products(cur)
            load_contacts(cur)
            load_orders(cur)
            load_order_items(cur)
            load_transactions(cur)
            load_carts(cur)
            load_cart_items(cur)
            load_engagements(cur)

    conn.close()
    log.info("Done. Database is ready — set DATABASE_URL and restart the app.")


if __name__ == "__main__":
    main()
