"""
scripts/crm_to_json.py
----------------------
Converts CRM CSV data → app/data/tyres.json (60 tyres, all in-stock)
                      → app/data/users.json (50 users)

CRM records come first; synthetic extras pad up to the target counts.
Only tyres with qty > 0 are written — the search service never sees OOS rows.

Run:
    python scripts/crm_to_json.py
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CRM_DIR  = Path(__file__).parent.parent / "app" / "crm_data"
DATA_DIR = Path(__file__).parent.parent / "app" / "data"

PRODUCT_CSV    = CRM_DIR / "Costco_Product__c-4_8_2026.csv"
CONTACT_CSV    = CRM_DIR / "Contact-4_8_2026.csv"
ORDER_CSV      = CRM_DIR / "Costco_Order__c-4_8_2026.csv"
ORDER_ITEM_CSV = CRM_DIR / "Order_Item__c-4_8_2026.csv"

TARGET_TYRES = 100   # increased to fit Indian sizes
TARGET_USERS = 50

# ---------------------------------------------------------------------------
# CSV reader
# ---------------------------------------------------------------------------
def read_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append({k: (v.strip() if v else "") for k, v in row.items() if k != "_"})
    return rows

# ---------------------------------------------------------------------------
# Tyre synthetic helpers
# ---------------------------------------------------------------------------
_KNOWN_BRANDS = [
    "Michelin", "Bridgestone", "Pirelli", "Continental", "Goodyear",
    "Hankook", "Yokohama", "Cooper", "Dunlop", "Falken",
    "Firestone", "Kumho", "Toyo", "Nexen", "General", "BFGoodrich",
]
_PREMIUM = {"Michelin", "Bridgestone", "Continental", "Pirelli"}

# Extra synthetic tyre catalogue — used to pad from CRM count up to TARGET_TYRES
# Each entry: (brand, model, size, price, season, terrain, description_snippet)
_EXTRA_TYRES = [
    ("Michelin",     "Primacy 4",        "205/55R16", 189.99, "all-season", "highway",     "long-lasting all-season comfort"),
    ("Michelin",     "CrossClimate 2",   "225/50R17", 219.99, "all-season", "highway",     "all-weather performance and grip"),
    ("Michelin",     "Pilot Sport 4",    "245/40R18", 259.99, "summer",     "highway",     "high-performance sport driving"),
    ("Michelin",     "Alpin 6",          "195/65R15", 169.99, "winter",     "highway",     "winter snow and ice grip"),
    ("Bridgestone",  "Potenza Sport",    "235/45R18", 229.99, "summer",     "highway",     "sport performance summer tyre"),
    ("Bridgestone",  "Blizzak DM-V3",   "235/65R17", 199.99, "winter",     "all-terrain", "winter SUV snow traction"),
    ("Bridgestone",  "Ecopia EP500",     "195/60R16", 159.99, "all-season", "city",        "fuel efficient city commuting"),
    ("Bridgestone",  "Dueler AT",        "265/65R17", 219.99, "all-season", "all-terrain", "all-terrain SUV and truck tyre"),
    ("Continental",  "PremiumContact 6","215/55R17",  199.99, "all-season", "highway",     "premium comfort highway tyre"),
    ("Continental",  "WinterContact TS","205/60R16",  179.99, "winter",     "highway",     "winter safety on snow and ice"),
    ("Continental",  "CrossContact ATR","255/65R17",  239.99, "all-season", "all-terrain", "crossover all-terrain tyre"),
    ("Continental",  "SportContact 7",  "235/40R19",  279.99, "summer",     "highway",     "ultra high performance sport"),
    ("Pirelli",      "Cinturato P7",    "225/45R17",  209.99, "all-season", "highway",     "all-season touring comfort"),
    ("Pirelli",      "Scorpion Verde",  "235/60R18",  229.99, "all-season", "all-terrain", "SUV crossover all-season"),
    ("Pirelli",      "Winter Sottozero","205/55R16",  189.99, "winter",     "highway",     "winter performance on snow"),
    ("Goodyear",     "Eagle F1",        "225/45R18",  219.99, "summer",     "highway",     "sport summer high-performance"),
    ("Goodyear",     "Wrangler AT",     "265/70R17",  199.99, "all-season", "all-terrain", "off-road truck SUV tyre"),
    ("Goodyear",     "EfficientGrip",   "205/55R16",  169.99, "all-season", "highway",     "fuel efficient everyday highway"),
    ("Goodyear",     "Ultra Grip 9",    "195/65R15",  159.99, "winter",     "highway",     "winter safety grip on ice"),
    ("Hankook",      "Ventus S1 Evo3",  "235/45R18",  189.99, "summer",     "highway",     "ultra high performance summer"),
    ("Hankook",      "Kinergy GT",      "215/60R16",  149.99, "all-season", "highway",     "all-season grand touring"),
    ("Hankook",      "Dynapro ATM",     "265/65R17",  179.99, "all-season", "all-terrain", "all-terrain highway performance"),
    ("Yokohama",     "Advan Sport V107","245/45R18",  229.99, "summer",     "highway",     "performance summer sport tyre"),
    ("Yokohama",     "Geolandar AT G015","235/65R17", 189.99, "all-season", "all-terrain", "SUV all-terrain all-season"),
    ("Yokohama",     "BluEarth-GT",     "205/55R16",  159.99, "all-season", "highway",     "eco-friendly touring comfort"),
    ("Dunlop",       "Sport Maxx RT2",  "225/40R18",  199.99, "summer",     "highway",     "ultra high performance summer"),
    ("Dunlop",       "Grandtrek AT3",   "255/65R17",  189.99, "all-season", "all-terrain", "SUV truck all-terrain"),
    ("Falken",       "Azenis FK510",    "235/45R17",  169.99, "summer",     "highway",     "high performance summer sport"),
    ("Falken",       "Wildpeak AT3W",   "265/70R17",  179.99, "all-season", "all-terrain", "all-terrain off-road truck"),
    ("Cooper",       "CS5 Ultra Touring","215/55R17", 149.99, "all-season", "highway",     "grand touring all-season"),
    ("Toyo",         "Proxes Sport",    "225/45R18",  189.99, "summer",     "highway",     "sport summer performance"),
    ("Toyo",         "Open Country AT", "265/65R17",  199.99, "all-season", "all-terrain", "all-terrain open country SUV"),
    ("Kumho",        "Solus TA31",      "205/55R16",  129.99, "all-season", "highway",     "budget all-season highway value"),
    ("Nexen",        "N'Fera SU1",      "215/55R17",  139.99, "all-season", "highway",     "all-season touring value"),
    ("General",      "Altimax RT43",    "195/65R15",  119.99, "all-season", "highway",     "budget all-season everyday"),
    ("BFGoodrich",   "g-Force Comp 2",  "235/40R18",  199.99, "summer",     "highway",     "extreme sport performance summer"),
    ("BFGoodrich",   "All-Terrain T/A", "265/70R17",  209.99, "all-season", "all-terrain", "legendary off-road truck SUV"),
    ("Firestone",    "Destination LE3", "235/65R17",  169.99, "all-season", "highway",     "crossover SUV all-season touring"),
    ("Firestone",    "Champion Fuel Fighter","205/55R16",139.99,"all-season","highway",    "fuel economy city all-season"),
    ("Michelin",     "LTX M/S2",        "265/65R17",  239.99, "all-season", "all-terrain", "light truck SUV all-season"),
    ("Bridgestone",  "Turanza QuietTrack","215/55R17", 199.99, "all-season", "highway",    "ultra-quiet highway touring"),
    ("Continental",  "TrueContact Tour", "225/60R17",  179.99, "all-season", "highway",   "long-life touring all-season"),
    ("Pirelli",      "Powergy",         "215/60R16",  169.99, "all-season", "highway",     "sporty all-season highway"),
    ("Goodyear",     "Assurance WeatherReady","215/60R16",189.99,"all-season","highway",   "all-weather safety comfort"),
    ("Hankook",      "iON evo AS",      "235/50R19",  229.99, "all-season", "highway",     "EV optimised all-season"),
    ("Yokohama",     "Advan dB V553",   "205/60R16",  159.99, "all-season", "city",        "quiet comfortable city driving"),
    ("Michelin",     "Energy Saver+",   "185/65R15",  149.99, "all-season", "city",        "fuel efficient small car city"),
    ("Continental",  "EcoContact 6",    "185/65R15",  139.99, "all-season", "city",        "eco tyre for small hatchbacks"),
    ("Bridgestone",  "Enliten",         "195/65R15",  155.99, "all-season", "city",        "lightweight eco city commuter"),
]

# ---------------------------------------------------------------------------
# Indian market tyre catalogue
# Sizes mapped to top-selling Indian cars — covers hatchbacks → SUVs → trucks
# Format: (brand, model, size, price_inr_equiv, season, terrain, description)
# ---------------------------------------------------------------------------
_INDIA_TYRES = [
    # ── 165/65R14 — Celerio, Triber base ────────────────────────────────
    ("MRF",          "Zapper-C",         "165/65R14",  84.99,  "all-season", "city",        "lightweight city tyre for small hatchbacks"),
    ("CEAT",         "Milaze X3",        "165/65R14",  79.99,  "all-season", "city",        "smooth comfortable city tyre"),
    ("Apollo",       "Amazer 3G",        "165/65R14",  82.99,  "all-season", "city",        "reliable everyday city commuter tyre"),

    # ── 185/60R15 — Tigor, Aura ──────────────────────────────────────────
    ("MRF",          "ZV2K",             "185/60R15", 109.99,  "all-season", "city",        "compact sedan city comfort tyre"),
    ("CEAT",         "SecuraDrive",      "185/60R15", 104.99,  "all-season", "city",        "safe city tyre for compact sedans"),
    ("Apollo",       "Alnac 4G",         "185/60R15", 112.99,  "all-season", "city",        "all-season city highway tyre"),
    ("Bridgestone",  "B250",             "185/60R15", 119.99,  "all-season", "city",        "comfortable reliable sedan tyre"),

    # ── 185/70R15 — Tata Punch ───────────────────────────────────────────
    ("MRF",          "Wanderer",         "185/70R15", 114.99,  "all-season", "city",        "durable all-season tyre for Tata Punch"),
    ("CEAT",         "SecuraDrive",      "185/70R15", 109.99,  "all-season", "city",        "safe comfortable Punch city tyre"),
    ("Apollo",       "Amazer 4G Life",   "185/70R15", 119.99,  "all-season", "city",        "high mileage city tyre for Punch"),
    ("Bridgestone",  "B290",             "185/70R15", 124.99,  "all-season", "city",        "reliable everyday tyre for Tata Punch"),
    ("Goodyear",     "Assurance TripleMax","185/70R15",129.99, "all-season", "city",        "wet grip safety tyre for Punch"),

    # ── 195/80R15 — Maruti Jimny ─────────────────────────────────────────
    ("MRF",          "Monsoon M",        "195/80R15", 139.99,  "all-season", "all-terrain", "all-terrain off-road tyre for Jimny"),
    ("CEAT",         "Czar AT",          "195/80R15", 134.99,  "all-season", "all-terrain", "off-road all-terrain Jimny tyre"),
    ("Apollo",       "Apterra AT",       "195/80R15", 144.99,  "all-season", "all-terrain", "rugged all-terrain for Maruti Jimny"),
    ("BFGoodrich",   "All-Terrain T/A",  "195/80R15", 164.99,  "all-season", "all-terrain", "legendary off-road tyre for Jimny"),

    # ── 205/55R16 — Kushaq, Slavia, Virtus, Tata Altroz top ─────────────
    ("MRF",          "ZVTS",             "205/55R16", 149.99,  "all-season", "highway",     "sporty all-season tyre for Kushaq Slavia Virtus"),
    ("CEAT",         "SportDrive",       "205/55R16", 144.99,  "all-season", "highway",     "highway sport tyre for VW Skoda sedans"),
    ("Continental",  "PremiumContact 6", "205/55R16", 174.99,  "all-season", "highway",     "premium highway tyre for European hatchbacks"),
    ("Michelin",     "Primacy 4",        "205/55R16", 184.99,  "all-season", "highway",     "premium long-life highway touring tyre"),
    ("Bridgestone",  "Turanza T005",     "205/55R16", 169.99,  "all-season", "highway",     "quiet comfortable highway touring tyre"),
    ("Yokohama",     "BluEarth-GT AE51", "205/55R16", 159.99,  "all-season", "highway",     "eco-friendly grand touring all-season"),

    # ── 215/55R17 — Curvv, Innova Hycross, Verna top, Windsor ───────────
    ("MRF",          "ZVTS",             "215/55R17", 169.99,  "all-season", "highway",     "all-season highway tyre for Curvv and Hycross"),
    ("CEAT",         "SportDrive",       "215/55R17", 164.99,  "all-season", "highway",     "highway sport tyre for modern SUVs"),
    ("Apollo",       "Apterra HP2",      "215/55R17", 174.99,  "all-season", "highway",     "SUV highway comfort performance"),
    ("Michelin",     "Primacy 4",        "215/55R17", 194.99,  "all-season", "highway",     "premium highway tyre for modern SUVs"),
    ("Continental",  "PremiumContact 6", "215/55R17", 189.99,  "all-season", "highway",     "premium comfort SUV highway tyre"),

    # ── 215/75R15 — Mahindra Bolero ──────────────────────────────────────
    ("MRF",          "Monsoon M",        "215/75R15", 154.99,  "all-season", "all-terrain", "tough all-terrain tyre for Bolero"),
    ("CEAT",         "Czar AT",          "215/75R15", 149.99,  "all-season", "all-terrain", "off-road all-terrain Bolero tyre"),
    ("Apollo",       "Apterra AT",       "215/75R15", 159.99,  "all-season", "all-terrain", "rugged all-terrain for Mahindra Bolero"),

    # ── 165/80R13 — Alto, Kwid, S-Presso ────────────────────────────────
    ("MRF",          "Zapper-S",         "165/80R13",  89.99,  "all-season", "city",        "budget city tyre for small hatchbacks"),
    ("CEAT",         "Milaze X3",        "165/80R13",  84.99,  "all-season", "city",        "smooth quiet ride for mini cars"),
    ("Apollo",       "Amazer 3G Maxx",   "165/80R13",  79.99,  "all-season", "city",        "durable everyday city tyre"),

    # ── 175/65R14 — Grand i10, Tiago, Celerio ───────────────────────────
    ("MRF",          "Wanderer",         "175/65R14",  99.99,  "all-season", "city",        "reliable hatchback city commuter"),
    ("CEAT",         "SecuraDrive",      "175/65R14",  94.99,  "all-season", "city",        "safe and comfortable everyday tyre"),
    ("Bridgestone",  "Ecopia EP150",     "175/65R14", 109.99,  "all-season", "city",        "fuel efficient eco city tyre"),

    # ── 175/65R15 — WagonR, Exter, Ignis ────────────────────────────────
    ("MRF",          "ZV2K",             "175/65R15", 104.99,  "all-season", "city",        "comfortable compact city tyre"),
    ("CEAT",         "FuelSmarrt",       "175/65R15",  99.99,  "all-season", "city",        "low rolling resistance city tyre"),
    ("Apollo",       "Alnac 4G",         "175/65R15", 109.99,  "all-season", "city",        "smooth quiet city and highway tyre"),
    ("Goodyear",     "Assurance TripleMax","175/65R15",119.99, "all-season", "city",        "wet grip safety for city driving"),

    # ── 185/65R15 — Swift, Baleno, Dzire, Glanza ────────────────────────
    ("MRF",          "ZLX",              "185/65R15", 114.99,  "all-season", "highway",     "long life highway tyre for sedans and hatchbacks"),
    ("CEAT",         "Milaze",           "185/65R15", 109.99,  "all-season", "highway",     "comfortable highway touring tyre"),
    ("Apollo",       "Amazer 4G Life",   "185/65R15", 119.99,  "all-season", "highway",     "high mileage highway tyre"),
    ("Michelin",     "Energy XM2+",      "185/65R15", 134.99,  "all-season", "highway",     "fuel efficient premium highway tyre"),
    ("Bridgestone",  "B290",             "185/65R15", 124.99,  "all-season", "highway",     "reliable everyday highway comfort"),
    ("Continental",  "ContiEcoContact 5","185/65R15", 129.99,  "all-season", "highway",     "eco premium highway tyre"),
    ("Yokohama",     "Earth-1",          "185/65R15", 119.99,  "all-season", "highway",     "all-season touring with good wet grip"),

    # ── 195/65R15 — Ertiga, XL6, Rumion, Honda Amaze ───────────────────
    ("MRF",          "ZV2K",             "195/65R15", 129.99,  "all-season", "highway",     "MPV highway tyre with long tread life"),
    ("CEAT",         "SecuraDrive",      "195/65R15", 124.99,  "all-season", "highway",     "comfortable MPV highway tyre"),
    ("Apollo",       "Alnac 4GS",        "195/65R15", 134.99,  "all-season", "highway",     "sporty all-season highway tyre"),
    ("Michelin",     "Primacy 3",        "195/65R15", 149.99,  "all-season", "highway",     "premium comfort and safety highway"),

    # ── 185/55R16 — Honda City, Honda Amaze top, WR-V ───────────────────
    ("MRF",          "ZVTS",             "185/55R16", 134.99,  "all-season", "highway",     "sedan highway tyre with sporty feel"),
    ("CEAT",         "SportDrive",       "185/55R16", 129.99,  "all-season", "highway",     "sporty highway tyre for compact sedans"),
    ("Apollo",       "Aspire 4G",        "185/55R16", 139.99,  "all-season", "highway",     "stylish highway tyre for modern sedans"),
    ("Michelin",     "Pilot Street 2",   "185/55R16", 154.99,  "all-season", "highway",     "performance highway tyre"),

    # ── 195/55R16 — i20, Altroz, Ciaz, Verna ───────────────────────────
    ("MRF",          "ZVTS",             "195/55R16", 144.99,  "all-season", "highway",     "sporty hatchback highway tyre"),
    ("CEAT",         "SportDrive",       "195/55R16", 139.99,  "all-season", "highway",     "highway performance hatchback tyre"),
    ("Continental",  "PremiumContact 5", "195/55R16", 164.99,  "all-season", "highway",     "premium highway safety tyre"),
    ("Michelin",     "Primacy 4",        "195/55R16", 169.99,  "all-season", "highway",     "premium quiet all-season highway"),

    # ── 195/60R16 — Nexon, Sonet, Venue, Punch top, Magnite ────────────
    ("MRF",          "Wanderer Sport",   "195/60R16", 149.99,  "all-season", "highway",     "compact SUV highway tyre"),
    ("CEAT",         "SecuraDrive",      "195/60R16", 144.99,  "all-season", "highway",     "safe compact SUV all-season tyre"),
    ("Apollo",       "Apterra HP2",      "195/60R16", 154.99,  "all-season", "highway",     "compact SUV highway performance"),
    ("Bridgestone",  "Ecopia EP300",     "195/60R16", 159.99,  "all-season", "highway",     "eco fuel efficient compact SUV tyre"),
    ("Hankook",      "Kinergy Eco2",     "195/60R16", 149.99,  "all-season", "highway",     "fuel efficient compact SUV tyre"),

    # ── 215/60R16 — Creta, Seltos, Carens, Astor, XUV300, Fronx ────────
    ("MRF",          "Wanderer Sport",   "215/60R16", 164.99,  "all-season", "highway",     "mid-size SUV all-season highway tyre"),
    ("CEAT",         "CrossDrive",       "215/60R16", 159.99,  "all-season", "highway",     "crossover SUV all-season highway"),
    ("Apollo",       "Apterra HP2",      "215/60R16", 169.99,  "all-season", "highway",     "SUV highway comfort and performance"),
    ("Michelin",     "Latitude Tour HP", "215/60R16", 189.99,  "all-season", "highway",     "premium SUV highway comfort"),
    ("Bridgestone",  "Dueler H/P Sport", "215/60R16", 179.99,  "all-season", "highway",     "SUV highway sport comfort"),
    ("Continental",  "CrossContact LX2", "215/60R16", 184.99,  "all-season", "highway",     "crossover premium all-season"),
    ("Goodyear",     "Assurance Triplemax","215/60R16",169.99, "all-season", "highway",     "wet safety SUV all-season"),
    ("Yokohama",     "Geolandar CV G058","215/60R16", 174.99,  "all-season", "highway",     "crossover all-season versatile"),

    # ── 215/60R17 — Grand Vitara, Hyryder, Elevate, Compass India ───────
    ("MRF",          "Wanderer Sport",   "215/60R17", 174.99,  "all-season", "highway",     "mid SUV highway all-season tyre"),
    ("Apollo",       "Apterra AT2",      "215/60R17", 179.99,  "all-season", "all-terrain", "SUV all-terrain all-season"),
    ("Michelin",     "Latitude Sport 3", "215/60R17", 199.99,  "all-season", "highway",     "premium mid SUV sport highway"),
    ("Bridgestone",  "Dueler AT",        "215/60R17", 189.99,  "all-season", "all-terrain", "all-terrain mid-size SUV tyre"),

    # ── 235/60R18 — Harrier, Safari, Alcazar, Santa Fe ──────────────────
    ("MRF",          "Wanderer XL",      "235/60R18", 199.99,  "all-season", "highway",     "full-size SUV highway comfort"),
    ("CEAT",         "CrossDrive AT",    "235/60R18", 194.99,  "all-season", "all-terrain", "full SUV all-terrain capability"),
    ("Apollo",       "Apterra AT2",      "235/60R18", 204.99,  "all-season", "all-terrain", "full SUV all-terrain highway"),
    ("Michelin",     "Latitude X-Ice Xi3","235/60R18",219.99, "winter",     "all-terrain", "winter SUV snow and ice grip"),
    ("Goodyear",     "Wrangler HP",      "235/60R18", 209.99,  "all-season", "all-terrain", "SUV all-terrain highway sport"),

    # ── 235/55R18 — XUV700, Hector Plus ────────────────────────────────
    ("Apollo",       "Apterra HP2",      "235/55R18", 214.99,  "all-season", "highway",     "large SUV highway performance tyre"),
    ("Michelin",     "Latitude Tour HP", "235/55R18", 229.99,  "all-season", "highway",     "premium large SUV highway comfort"),
    ("Continental",  "CrossContact UHP", "235/55R18", 224.99,  "all-season", "highway",     "ultra high performance SUV"),

    # ── 255/65R17 — Scorpio N, Thar ─────────────────────────────────────
    ("MRF",          "Monsoon",          "255/65R17", 199.99,  "all-season", "all-terrain", "rugged off-road all-terrain SUV"),
    ("CEAT",         "Czar AT",          "255/65R17", 194.99,  "all-season", "all-terrain", "off-road all-terrain with highway comfort"),
    ("Apollo",       "Apterra AT",       "255/65R17", 204.99,  "all-season", "all-terrain", "all-terrain rugged off-road tyre"),
    ("BFGoodrich",   "All-Terrain T/A KO2","255/65R17",239.99,"all-season", "all-terrain", "legendary off-road all-terrain truck"),
    ("Goodyear",     "Wrangler AT SA+",  "255/65R17", 219.99,  "all-season", "all-terrain", "off-road wet terrain all-terrain"),
    ("Falken",       "Wildpeak AT3W",    "255/65R17", 209.99,  "all-season", "all-terrain", "all-terrain off-road truck SUV"),

    # ── 265/65R17 — Fortuner, Gloster ───────────────────────────────────
    ("MRF",          "Monsoon",          "265/65R17", 214.99,  "all-season", "all-terrain", "large SUV off-road all-terrain"),
    ("Apollo",       "Apterra AT2",      "265/65R17", 219.99,  "all-season", "all-terrain", "premium all-terrain large SUV"),
    ("Bridgestone",  "Dueler AT 693",    "265/65R17", 229.99,  "all-season", "all-terrain", "highway and off-road large SUV"),
    ("Michelin",     "Latitude Cross",   "265/65R17", 244.99,  "all-season", "all-terrain", "premium all-terrain performance"),
]

def _build_tyre_from_crm(row: dict) -> dict:
    """Build a tyre dict from a CRM product row."""
    rng   = random.Random(row["Id"])
    name  = row.get("Name", "")
    desc  = row.get("Description__c", "")
    brand = next((b for b in _KNOWN_BRANDS if name.lower().startswith(b.lower())), name.split()[0])
    model = name[len(brand):].strip() or name

    width = row.get("Width__c", "").strip()
    ratio = row.get("Aspect_ratio__c", "").strip()
    rim   = row.get("Rim_Diameter__c", "").strip()
    size  = f"{width}/{ratio}R{rim}" if (width and ratio and rim) else "205/55R16"

    price = float(row.get("Price__c") or 150)
    season  = "winter" if "winter" in desc.lower() else ("summer" if "sport" in desc.lower() else "all-season")
    terrain = "all-terrain" if "suv" in desc.lower() else ("city" if "city" in desc.lower() else "highway")

    return _make_tyre_dict(row["Id"], brand, model, size, price, season, terrain, desc, rng,
                           image_url=row.get("Image_Link__c") or None,
                           units=int(float(row.get("Units__c") or 0)))


def _build_tyre_synthetic(entry: tuple, idx: int) -> dict:
    """Build a tyre dict from a synthetic catalogue entry."""
    brand, model, size, price, season, terrain, desc = entry
    fake_id = f"SYN-{brand[:3].upper()}-{idx:04d}"
    rng = random.Random(fake_id)
    return _make_tyre_dict(fake_id, brand, model, size, price, season, terrain, desc, rng)


def _make_tyre_dict(tyre_id, brand, model, size, price, season, terrain, desc, rng,
                    image_url=None, units=0) -> dict:
    load_map = {"15": 89, "16": 91, "17": 94, "18": 97, "19": 99, "20": 102}
    rim = size.split("R")[-1] if "R" in size else "16"
    load_index   = load_map.get(rim, 91)
    speed_rating = "W" if season == "winter" else ("Y" if "sport" in desc.lower() else "V")
    wet_grip     = "A" if brand in _PREMIUM else rng.choice(["A", "B"])
    noise_db     = rng.randint(64, 73)
    tread_life   = round((int((price / 100) * 20000 + rng.randint(30000, 60000))) / 5000) * 5000
    rating       = round(rng.uniform(4.1, 4.9), 1)
    review_count = rng.randint(120, 2800)
    warranty_years = 5 if brand in _PREMIUM else rng.choice([3, 4, 5])
    member_price = round(price * rng.uniform(0.85, 0.92), 2)
    promos = [f"Save ${rng.randint(10,30)} on a set of 4", "Free installation on set of 4", ""]
    active_promo = rng.choice(promos) or None
    warehouse_id = f"W{rng.randint(1,5):03d}"
    # Always in-stock: CRM qty if > 0, else synthetic
    qty = units if units > 0 else rng.randint(8, 48)

    return {
        "id":                  tyre_id,
        "brand":               brand,
        "model":               model,
        "size":                size,
        "load_index":          load_index,
        "speed_rating":        speed_rating,
        "season":              season,
        "terrain":             terrain,
        "price":               price,
        "member_price":        member_price,
        "tread_life_km":       tread_life,
        "wet_grip":            wet_grip,
        "noise_db":            noise_db,
        "rating":              rating,
        "review_count":        review_count,
        "warranty_years":      warranty_years,
        "compatible_vehicles": [],
        "stock":               {"warehouse_id": warehouse_id, "qty": qty},
        "active_promotion":    active_promo,
        "image_url":           image_url,
        "description":         desc or None,
    }

# ---------------------------------------------------------------------------
# User synthetic helpers
# ---------------------------------------------------------------------------
_VEHICLES = [
    ("Honda","CR-V",2021),    ("Toyota","Camry",2020),   ("Ford","F-150",2022),
    ("Honda","Civic",2021),   ("Toyota","RAV4",2022),    ("Hyundai","Creta",2022),
    ("Kia","Seltos",2021),    ("BMW","3 Series",2020),   ("Maruti","Swift",2021),
    ("Tata","Nexon",2022),    ("Mahindra","Scorpio N",2022),("Volkswagen","Tiguan",2020),
    ("Chevrolet","Equinox",2021),("Nissan","Rogue",2021),("Subaru","Outback",2020),
    ("Hyundai","Venue",2022), ("Honda","Elevate",2023),  ("Tata","Punch",2022),
    ("Kia","Sonet",2021),     ("Toyota","Fortuner",2021),
]
_HABITS = [
    ["highway","daily commute"],["city","daily commute"],["highway","long drive"],
    ["city","weekend"],["off-road","highway"],["daily commute"],["highway"],
    ["city"],["highway","weekend"],["off-road","long drive"],
]
_TIERS = ["standard","standard","standard","gold","gold","executive"]
_CITIES = [
    ("Seattle","98101"),("Portland","97201"),("San Francisco","94105"),
    ("Los Angeles","90001"),("Phoenix","85001"),("Chicago","60601"),
    ("Houston","77001"),("Denver","80201"),("Austin","78701"),("Boston","02101"),
    ("Multnomah","97233"),("Dallas","75201"),("Atlanta","30301"),
]
_FIRST_NAMES = [
    "James","Robert","John","Michael","David","William","Richard","Joseph","Thomas","Charles",
    "Mary","Patricia","Jennifer","Linda","Barbara","Elizabeth","Susan","Jessica","Sarah","Karen",
    "Raj","Priya","Arjun","Anita","Vikram","Neha","Suresh","Kavya","Ravi","Deepa",
]
_LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Martinez","Wilson",
    "Anderson","Taylor","Thomas","Hernandez","Moore","Jackson","Martin","Lee","Perez","Thompson",
    "Kumar","Sharma","Patel","Singh","Reddy","Nair","Pillai","Iyer","Rao","Mehta",
]

def _build_user_from_crm(row: dict, idx: int, last_purchase) -> dict:
    rng     = random.Random(row["Id"])
    vehicle = _VEHICLES[rng.randint(0, len(_VEHICLES)-1)]
    habits  = _HABITS[rng.randint(0, len(_HABITS)-1)]
    tier    = _TIERS[rng.randint(0, len(_TIERS)-1)]
    city    = row.get("MailingCity") or row.get("MailingAddress.city") or "Seattle"
    zipcode = row.get("MailingPostalCode") or row.get("MailingAddress.postalCode") or "98101"
    name    = row.get("Name") or f"{row.get('FirstName','')} {row.get('LastName','')}".strip()
    return _make_user_dict(f"M{10000+idx+1}", name, tier, city, zipcode, vehicle, habits, last_purchase)


def _build_user_synthetic(idx: int, tyre_ids: list[str]) -> dict:
    rng     = random.Random(f"SYN-USER-{idx}")
    vehicle = _VEHICLES[rng.randint(0, len(_VEHICLES)-1)]
    habits  = _HABITS[rng.randint(0, len(_HABITS)-1)]
    tier    = _TIERS[rng.randint(0, len(_TIERS)-1)]
    city_zip = _CITIES[rng.randint(0, len(_CITIES)-1)]
    first   = _FIRST_NAMES[rng.randint(0, len(_FIRST_NAMES)-1)]
    last    = _LAST_NAMES[rng.randint(0, len(_LAST_NAMES)-1)]
    # ~60% chance of having a last purchase
    lp = None
    if tyre_ids and rng.random() < 0.6:
        lp = {
            "tyre_id": tyre_ids[rng.randint(0, len(tyre_ids)-1)],
            "date": f"202{rng.randint(3,5)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "mileage_at_purchase": rng.randint(10000, 80000),
        }
    return _make_user_dict(f"M{10000+idx+1}", f"{first} {last}", tier,
                           city_zip[0], city_zip[1], vehicle, habits, lp)


def _make_user_dict(member_id, name, tier, city, zipcode, vehicle, habits, last_purchase) -> dict:
    return {
        "member_id":       member_id,
        "name":            name,
        "membership_tier": tier,
        "location":        {"city": city, "zip": zipcode},
        "vehicle":         {"make": vehicle[0], "model": vehicle[1], "year": vehicle[2]},
        "driving_habits":  habits,
        "last_purchase":   last_purchase,
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Reading CRM CSVs …")

    # ── Last purchase lookup from orders ─────────────────────────────────
    last_purchase_by_contact: dict[str, dict] = {}
    try:
        orders = {r["Id"]: r for r in read_csv(ORDER_CSV)}
        for oi in read_csv(ORDER_ITEM_CSV):
            prod_id    = oi.get("Product__c","").strip()
            order      = orders.get(oi.get("Order__c",""))
            if not prod_id or not order:
                continue
            contact_id = order.get("Contact__c","").strip()
            if not contact_id:
                continue
            date = order.get("Order_Date__c","")
            existing = last_purchase_by_contact.get(contact_id)
            if not existing or date > existing["date"]:
                last_purchase_by_contact[contact_id] = {
                    "tyre_id": prod_id, "date": date, "mileage_at_purchase": 0
                }
        print(f"  Found last purchases for {len(last_purchase_by_contact)} contacts")
    except Exception as e:
        print(f"  Warning: last_purchase lookup failed ({e})")

    # ── Products: CRM + Western catalogue + India catalogue ──────────────
    crm_tyres = [_build_tyre_from_crm(r) for r in read_csv(PRODUCT_CSV)]
    # Ensure all CRM tyres have stock > 0
    for t in crm_tyres:
        if t["stock"]["qty"] == 0:
            t["stock"]["qty"] = random.Random(t["id"]).randint(8, 40)

    # All India tyres — always included regardless of TARGET_TYRES
    india_tyres = [_build_tyre_synthetic(e, i) for i, e in enumerate(_INDIA_TYRES)]

    # Pad remaining slots with Western catalogue extras
    already = len(crm_tyres) + len(india_tyres)
    need = max(0, TARGET_TYRES - already)
    western_tyres = [_build_tyre_synthetic(e, 1000 + i) for i, e in enumerate(_EXTRA_TYRES[:need])]

    tyres = crm_tyres + india_tyres + western_tyres
    print(f"  CRM: {len(crm_tyres)}  India: {len(india_tyres)}  Western: {len(western_tyres)}  =  {len(tyres)} total tyres")

    tyres_path = DATA_DIR / "tyres.json"
    tyres_path.write_text(json.dumps(tyres, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ Wrote {len(tyres)} tyres → {tyres_path}")

    # ── Contacts → 50 users ───────────────────────────────────────────────
    tyre_ids = [t["id"] for t in tyres]
    crm_contacts = read_csv(CONTACT_CSV)
    users = []
    for idx, row in enumerate(crm_contacts[:TARGET_USERS]):
        lp = last_purchase_by_contact.get(row["Id"])
        users.append(_build_user_from_crm(row, idx, lp))

    # Pad with synthetic users if CRM has fewer than 50
    for i in range(len(users), TARGET_USERS):
        users.append(_build_user_synthetic(i, tyre_ids))

    print(f"  CRM users: {min(len(crm_contacts), TARGET_USERS)}  +  synthetic: {max(0, TARGET_USERS - len(crm_contacts))}  =  {len(users)} total")

    users_path = DATA_DIR / "users.json"
    users_path.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ Wrote {len(users)} users → {users_path}")

    print("\nDone. Restart uvicorn — all data served from JSON.")

if __name__ == "__main__":
    main()
