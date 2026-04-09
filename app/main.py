"""
Module: main.py
Purpose: FastAPI entry point — routes all HTTP requests through the pipeline
Layer: main

Dependencies:
  - langchain_anthropic: ChatAnthropic LLM for response text generation
  - app.services.*: Pure Python services (profile, stock, cart, payment, etc.)
  - app.tools.*: LangChain @tool wrappers used inside _build_recommendation_cards()
  - app.agents.guardrail_agent: Runs 5 safety checks on every response (no LLM)
  - app.dashboard.dashboard: FastAPI router mounted at /dashboard

Architecture:
  Every /chat request follows a deterministic pipeline — no ReAct agent loop.
  Intent is detected with regex. Python handles all data operations.
  The LLM is called EXACTLY ONCE per message (in _llm_respond()) for text only.
  GuardrailAgent runs AFTER the LLM call using pure Python checks (zero LLM calls).

Production notes:
  Env vars required:
    ANTHROPIC_API_KEY  — mandatory; app will refuse to call the LLM without it
    ELEVENLABS_API_KEY — optional; voice TTS disabled if absent
    APP_ENV            — "dev" (default) | "prod" (tightens CORS)
    LOG_LEVEL          — "INFO" (default) | "DEBUG" | "WARNING"

  Start command (dev):
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

  Start command (prod):
    APP_ENV=prod uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000

  Health check:
    GET http://localhost:8000/health → {"status": "ok", "version": "0.33.0"}

  Session state is in-memory — resets on server restart (by design for demo).
  Swap point: replace SESSION_STORE / CHAT_HISTORY dicts with Redis for prod.

Endpoints:
  GET  /              → chat UI  (app/static/index.html)
  POST /chat          → main pipeline (1 LLM call per message)
  POST /feedback      → thumbs up/down signals → eval_service scorecard
  POST /voice/tts     → ElevenLabs TTS stream (requires ELEVENLABS_API_KEY)
  GET  /voice/status  → {"enabled": bool} — UI uses this to show/hide mic button
  GET  /health        → {"status": "ok", "version": "...", "active_sessions": N}
  GET  /dashboard     → analytics dashboard UI
  GET  /dashboard/api → live analytics JSON (funnel, scorecard, alerts)
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Arize observability — traces every LLM call + LangChain tool invocation
# Optional: app runs normally without it if keys are absent.
# ---------------------------------------------------------------------------

def _setup_arize() -> bool:
    """
    Initialise Arize OpenTelemetry tracing for LangChain.

    Reads ARIZE_SPACE_ID and ARIZE_API_KEY from environment.
    Returns True if tracing was set up, False if keys are missing.

    What gets traced automatically:
      - Every ChatAnthropic LLM call (input tokens, output tokens, latency, model)
      - Every @tool invocation (generate_personalised_msg, generate_punch_line, etc.)
      - Every LangChain agent run (if ReAct agents are activated)

    Custom spans added manually:
      - /chat pipeline span (intent, stage, session_id, member_id)
      - /image-analyse span (scenario, car_make, tyre_size)
    """
    space_id = os.environ.get("ARIZE_SPACE_ID")
    api_key  = os.environ.get("ARIZE_API_KEY")

    if not space_id or not api_key:
        logger.info("Arize: ARIZE_SPACE_ID or ARIZE_API_KEY not set — tracing disabled")
        return False

    try:
        from arize.otel import register
        from openinference.instrumentation.langchain import LangChainInstrumentor

        # Register sends traces to Arize cloud via OTLP/gRPC
        register(
            space_id=space_id,
            api_key=api_key,
            project_name=os.environ.get("ARIZE_PROJECT_NAME", "costco-tyre-agent"),
        )

        # Auto-instrument all LangChain / LangGraph calls
        LangChainInstrumentor().instrument()

        logger.info("Arize: tracing enabled → project=%s", os.environ.get("ARIZE_PROJECT_NAME", "costco-tyre-agent"))
        return True

    except ImportError:
        logger.warning(
            "Arize: packages not installed — run: "
            "pip install arize-otel openinference-instrumentation-langchain"
        )
        return False
    except Exception as exc:
        logger.warning("Arize: setup failed (%s) — tracing disabled", exc)
        return False


_ARIZE_ENABLED = _setup_arize()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Costco Tyre Agent", version="0.33.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if os.environ.get("APP_ENV", "dev") == "dev" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# React build output — served when `npm run build` has been run.
# In dev mode (npm run dev on :5173) this folder may not exist — that's fine.
_REACT_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _REACT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_REACT_DIST / "assets")), name="react-assets")

# ---------------------------------------------------------------------------
# Lazy LLM — single shared ChatAnthropic instance
# ---------------------------------------------------------------------------

_llm = None

def get_llm():
    global _llm
    if _llm is None:
        from langchain_anthropic import ChatAnthropic
        _llm = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            temperature=0,
            max_tokens=1024,
        )
    return _llm

# Guardrail (no LLM)
_guardrail = None

def get_guardrail():
    global _guardrail
    if _guardrail is None:
        from app.agents.guardrail_agent import GuardrailAgent
        _guardrail = GuardrailAgent()
    return _guardrail

# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------

from app.models.schemas import SessionState

SESSION_STORE: dict[str, SessionState] = {}
# Conversation history per session: list of {role, content}
CHAT_HISTORY: dict[str, list[dict]] = {}

def get_session(session_id: str) -> SessionState:
    if session_id not in SESSION_STORE:
        SESSION_STORE[session_id] = SessionState(
            session_id=session_id,
            last_active=time.time(),
        )
    SESSION_STORE[session_id].last_active = time.time()
    return SESSION_STORE[session_id]

def get_history(session_id: str) -> list[dict]:
    return CHAT_HISTORY.setdefault(session_id, [])

def add_to_history(session_id: str, role: str, content: str):
    history = get_history(session_id)
    history.append({"role": role, "content": content})
    # Keep last 10 turns (20 messages)
    CHAT_HISTORY[session_id] = history[-20:]

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str
    message: str

class FeedbackRequest(BaseModel):
    session_id: str
    signal: str

class ImageAnalyseRequest(BaseModel):
    session_id: str
    image_data: str   # base64-encoded image bytes (no data URI prefix)
    image_type: str   # e.g. "image/jpeg" | "image/png" | "image/webp"
    tyre_id: Optional[str] = None
    agent: str = "rec_ranking"

class TTSRequest(BaseModel):
    text: str
    session_id: Optional[str] = None

# ---------------------------------------------------------------------------
# Make → known models map (used for chips AND LLM prompt hints)
# Keys are lowercased make names. Add new makes here and they flow everywhere.
# ---------------------------------------------------------------------------
_MAKE_MODELS: dict[str, list[str]] = {
    # Indian market
    "maruti suzuki": ["Swift", "Baleno", "Brezza", "Ertiga", "Grand Vitara", "WagonR", "Fronx", "Ignis"],
    "maruti":        ["Swift", "Baleno", "Brezza", "Ertiga", "Grand Vitara", "WagonR", "Fronx"],
    "tata":          ["Nexon", "Punch", "Harrier", "Safari", "Altroz", "Curvv", "Tigor"],
    "mahindra":      ["Scorpio N", "XUV700", "XUV300", "Thar", "Bolero", "XUV400", "3XO"],
    "hyundai":       ["Creta", "Venue", "i20", "Alcazar", "Verna", "Exter", "Tucson"],
    "kia":           ["Seltos", "Sonet", "Carens", "EV6", "EV9"],
    "renault":       ["Kwid", "Kiger", "Duster", "Triber"],
    "nissan":        ["Magnite", "Rogue", "Altima", "X-Trail"],
    # Chinese/EV brands (growing in India & globally)
    "byd":           ["Atto 3", "Seal", "Dolphin", "Sealion 6", "Atto 2", "Sea Lion 7"],
    "mg":            ["Hector", "Astor", "ZS EV", "Gloster", "Windsor", "Comet"],
    "ola":           ["S1 Pro", "S1 Air", "S1 X"],
    # Japanese
    "toyota":        ["Fortuner", "Innova Crysta", "Hyryder", "Camry", "RAV4", "Urban Cruiser"],
    "honda":         ["City", "Amaze", "Elevate", "CR-V", "Civic", "WR-V"],
    "suzuki":        ["Swift", "Baleno", "Vitara", "Jimny", "S-Cross"],
    "mazda":         ["CX-5", "CX-30", "Mazda3", "MX-5"],
    "subaru":        ["Outback", "Forester", "Crosstrek", "Impreza"],
    # Korean
    "genesis":       ["GV80", "GV70", "G80", "GV60"],
    # European
    "volkswagen":    ["Taigun", "Virtus", "Tiguan", "Polo", "Golf", "Passat"],
    "skoda":         ["Kushaq", "Slavia", "Octavia", "Kodiaq", "Superb"],
    "bmw":           ["3 Series", "5 Series", "X1", "X3", "X5", "iX"],
    "mercedes":      ["C-Class", "E-Class", "GLC", "GLE", "A-Class"],
    "audi":          ["A4", "A6", "Q3", "Q5", "Q7", "e-tron"],
    "volvo":         ["XC40", "XC60", "XC90", "S60"],
    "peugeot":       ["208", "2008", "3008", "508"],
    # American
    "ford":          ["EcoSport", "Endeavour", "F-150", "Mustang", "Bronco", "Explorer"],
    "chevrolet":     ["Colorado", "Silverado", "Equinox", "Trailblazer"],
    "jeep":          ["Compass", "Wrangler", "Grand Cherokee", "Meridian"],
}


# ---------------------------------------------------------------------------
# Vehicle → default tyre size map
# ---------------------------------------------------------------------------

# Most common OEM tyre sizes by model name (lowercase substring match).
# Covers the top ~60 models sold in North America. Year-specific overrides
# are handled separately in _infer_size_from_text() for generation changes.
_VEHICLE_SIZE_MAP = {
    # Honda
    "cr-v": "235/65R17", "cr v": "235/65R17", "crv": "235/65R17",
    "civic": "215/55R16",
    "accord": "225/50R17",
    "pilot": "245/60R18",
    "odyssey": "235/60R18",
    "hr-v": "215/60R16", "hrv": "215/60R16",
    "passport": "245/60R18",
    "ridgeline": "245/60R18",
    # Toyota
    "camry": "235/45R18",
    "rav4": "235/65R17", "rav 4": "235/65R17",
    "corolla": "205/55R16",
    "highlander": "245/60R20",
    "tacoma": "265/70R16",
    "tundra": "275/65R18",
    "4runner": "265/70R16",
    "prius": "195/65R15",
    "sienna": "235/60R18",
    "venza": "235/50R20",
    "sequoia": "275/55R20",
    # Ford
    "f-150": "265/70R17", "f150": "265/70R17",
    "escape": "235/50R18",
    "explorer": "255/50R20",
    "mustang": "235/50R18",
    "edge": "235/55R19",
    "bronco": "265/70R17",
    "ranger": "265/70R17",
    "expedition": "275/55R20",
    # Chevrolet / GMC
    "equinox": "225/65R17",
    "silverado": "265/70R17",
    "malibu": "225/50R17",
    "traverse": "255/65R18",
    "tahoe": "275/55R20",
    "suburban": "275/55R20",
    "colorado": "265/70R16",
    "blazer": "235/50R20",
    "terrain": "225/60R17",
    "yukon": "275/55R20",
    # BMW
    "3 series": "225/45R18", "3series": "225/45R18",
    "5 series": "245/45R18", "5series": "245/45R18",
    "x3": "245/50R19",
    "x5": "255/55R19",
    "x1": "225/50R18",
    "x7": "275/45R21",
    # Mercedes-Benz
    "c-class": "225/45R17", "c class": "225/45R17",
    "e-class": "245/45R18", "e class": "245/45R18",
    "glc": "235/55R19",
    "gle": "255/55R19",
    "gla": "225/45R18",
    # Nissan
    "rogue": "225/65R17",
    "altima": "235/45R18",
    "sentra": "205/55R16",
    "pathfinder": "265/60R18",
    "frontier": "265/70R16",
    "murano": "235/55R20",
    "kicks": "205/60R16",
    "armada": "275/60R20",
    # Kia
    "sorento": "235/65R17",
    "sportage": "235/55R18",
    "telluride": "265/45R20",
    "soul": "205/55R16",
    "forte": "205/55R16",
    "carnival": "235/55R19",
    "stinger": "225/40R19",
    # Hyundai
    "tucson": "235/65R17",
    "santa fe": "235/60R18", "santafe": "235/60R18",
    "elantra": "205/55R16",
    "sonata": "215/55R17",
    "palisade": "245/60R20",
    "ioniq": "215/55R17",
    "venue": "205/60R16",
    # Subaru
    "outback": "225/60R18",
    "forester": "225/60R17",
    "crosstrek": "225/60R17",
    "impreza": "205/55R16",
    "ascent": "245/60R20",
    "wrx": "235/45R17",
    # Volkswagen
    "jetta": "205/55R16",
    "tiguan": "215/65R17",
    "passat": "215/55R17",
    "atlas": "255/50R20",
    "golf": "205/55R16",
    # Audi
    "a4": "235/40R18",
    "a6": "245/45R18",
    "q5": "235/55R19",
    "q7": "255/55R19",
    "q3": "215/65R17",
    # Jeep
    "cherokee": "225/60R17",
    "grand cherokee": "265/60R18", "grand_cherokee": "265/60R18",
    "wrangler": "245/75R17",
    "compass": "215/60R17",
    "gladiator": "255/70R18",
    # Tesla
    "model 3": "235/45R18", "model3": "235/45R18",
    "model y": "255/45R19", "modely": "255/45R19",
    "model s": "245/45R19", "models": "245/45R19",
    "model x": "265/45R20", "modelx": "265/45R20",
    # Dodge / Ram / Chrysler
    "ram 1500": "275/60R20", "ram1500": "275/60R20",
    "durango": "265/50R20",
    "charger": "235/55R19",
    "challenger": "235/55R19",
    "pacifica": "235/65R17",
    # Lexus
    "rx": "235/55R20",
    "es": "215/55R17",
    "nx": "225/60R18",
    # Mazda
    "cx-5": "225/65R17", "cx5": "225/65R17",
    "cx-9": "255/50R20", "cx9": "255/50R20",
    "mazda3": "215/45R18",
    "mazda6": "225/55R17",

    # ── Indian market ────────────────────────────────────────────────────

    # Maruti Suzuki
    "swift": "185/65R15",
    "baleno": "185/65R15",
    "dzire": "185/65R15",
    "alto": "165/80R13",
    "wagonr": "175/60R15", "wagon r": "175/60R15",
    "ertiga": "195/65R15",
    "xl6": "195/65R15",
    "brezza": "215/60R16", "vitara brezza": "215/60R16",
    "s-cross": "215/60R16", "s cross": "215/60R16",
    "ciaz": "195/55R16",
    "celerio": "165/65R14",
    "ignis": "175/65R15",
    "grand vitara": "215/60R17",
    "jimny": "195/80R15",
    "fronx": "195/60R16",
    "invicto": "225/55R17",

    # Hyundai India
    "grand i10": "175/65R14", "i10": "175/65R14",
    "i20": "195/55R16",
    "creta": "215/60R16",
    "venue": "195/60R16",
    "alcazar": "215/60R17",
    "verna": "195/55R16",
    "aura": "185/65R15",
    "exter": "175/65R15",

    # Tata Motors
    "nexon": "195/60R16",
    "punch": "185/70R15",     # base/mid variants; top variant is 195/60R16
    "harrier": "235/60R18",
    "safari": "235/60R18",
    "altroz": "195/55R16",
    "tiago": "175/65R14",
    "tigor": "185/60R15",
    "curvv": "215/55R17",
    "avinya": "215/55R17",

    # Mahindra
    "scorpio n": "255/65R17", "scorpio-n": "255/65R17",
    "scorpio classic": "235/70R16",
    "scorpio": "235/70R16",
    "xuv700": "235/55R18", "xuv 700": "235/55R18",
    "xuv400": "215/60R16", "xuv 400": "215/60R16",
    "xuv300": "215/60R16", "xuv 300": "215/60R16",
    "xuv3xo": "215/60R16", "xuv 3xo": "215/60R16", "3xo": "215/60R16",
    "thar": "255/65R16",
    "bolero": "215/75R15",
    "be 6e": "235/50R20", "be6e": "235/50R20",
    "xev 9e": "255/45R20", "xev9e": "255/45R20",

    # Kia India
    "seltos": "215/60R16",
    "sonet": "195/60R16",
    "carens": "215/60R16",
    "ev6": "235/55R19",

    # Toyota India
    "fortuner": "265/65R17",
    "innova crysta": "215/65R16", "crysta": "215/65R16",
    "innova hycross": "225/55R17", "hycross": "225/55R17",
    "hyryder": "215/60R17",
    "glanza": "185/65R15",
    "rumion": "185/65R15",

    # Honda India
    "amaze": "185/55R16",
    "elevate": "215/60R16",
    "city": "185/55R16",       # Honda City (not Kansas City)

    # MG Motor
    "hector": "215/60R17",
    "astor": "215/60R16",
    "zs ev": "215/55R17", "zsev": "215/55R17",
    "gloster": "265/60R18",
    "windsor": "215/55R17",
    "comet": "155/70R13",

    # Skoda India
    "kushaq": "205/55R16",
    "slavia": "205/55R16",

    # Volkswagen India
    "taigun": "215/50R17",
    "virtus": "205/55R16",

    # Renault India
    "kwid": "165/80R13",
    "kiger": "195/60R16",
    "duster": "215/65R16",

    # Nissan India
    "magnite": "195/60R16",

    # Jeep India
    "meridian": "235/65R17",
    "compass": "215/60R17",    # India-spec Compass
}

# Vehicle class fallback — used when model not found in map.
# Inferred from keywords in the model name or make.
_CLASS_SIZE_DEFAULTS = {
    "truck":        "265/70R17",   # pickup trucks
    "suv":          "235/65R17",   # mid/full-size SUVs
    "compact_suv":  "215/60R16",   # Indian sub-4m SUVs (Nexon, Venue, Sonet)
    "van":          "235/65R17",   # minivans / MPVs
    "sedan":        "205/55R16",   # standard sedans
    "compact":      "185/65R15",   # hatchbacks / small cars (Indian market default)
    "minicar":      "165/80R13",   # entry-level (Alto, Kwid)
    "sport":        "225/45R17",   # sport/performance
}
_CLASS_KEYWORDS = {
    "truck":       ["truck", "pickup", "1500", "f-150", "f150", "silverado", "tundra", "tacoma", "ranger", "frontier", "ridgeline", "bolero"],
    "suv":         ["suv", "crossover", "4runner", "explorer", "pilot", "highlander", "pathfinder", "expedition", "tahoe", "suburban", "yukon", "sequoia", "palisade", "telluride", "atlas", "ascent", "fortuner", "harrier", "safari", "gloster", "scorpio", "xuv700"],
    "compact_suv": ["compact suv", "sub4", "sub-4", "microsuv", "micro suv"],
    "van":         ["van", "minivan", "odyssey", "sienna", "pacifica", "carnival", "ertiga", "xl6", "rumion"],
    "sport":       ["sport", "coupe", "mustang", "stinger", "wrx", "challenger", "charger"],
    "minicar":     ["minicar", "mini car", "entry", "kwid", "alto", "comet"],
    "compact":     ["compact", "hatch", "hatchback", "fit", "yaris", "fiesta", "spark", "accent", "rio", "swift", "baleno", "i20", "altroz", "tiago", "punch", "celerio", "ignis", "glanza"],
}

# ---------------------------------------------------------------------------
# Model-name → make lookup (for multilingual messages where only model is said)
# e.g. "nexon per jata hun" → make=Tata, model=Nexon
# ---------------------------------------------------------------------------
_KNOWN_MODEL_MAKES: dict[str, str] = {
    # Tata
    "nexon": "Tata", "punch": "Tata", "harrier": "Tata", "safari": "Tata",
    "altroz": "Tata", "curvv": "Tata", "tigor": "Tata", "tiago": "Tata",
    # Mahindra
    "scorpio": "Mahindra", "thar": "Mahindra", "xuv700": "Mahindra",
    "xuv300": "Mahindra", "xuv400": "Mahindra", "bolero": "Mahindra",
    "3xo": "Mahindra",
    # Hyundai
    "creta": "Hyundai", "venue": "Hyundai", "i20": "Hyundai", "verna": "Hyundai",
    "alcazar": "Hyundai", "exter": "Hyundai", "tucson": "Hyundai",
    # Kia
    "sonet": "Kia", "seltos": "Kia", "carens": "Kia",
    # Maruti Suzuki
    "swift": "Maruti Suzuki", "baleno": "Maruti Suzuki", "brezza": "Maruti Suzuki",
    "ertiga": "Maruti Suzuki", "fronx": "Maruti Suzuki", "ignis": "Maruti Suzuki",
    "wagonr": "Maruti Suzuki", "wagon r": "Maruti Suzuki",
    "grand vitara": "Maruti Suzuki", "vitara": "Maruti Suzuki",
    # Honda
    "city": "Honda", "amaze": "Honda", "elevate": "Honda",
    "cr-v": "Honda", "crv": "Honda", "civic": "Honda",
    # Toyota
    "innova": "Toyota", "fortuner": "Toyota", "camry": "Toyota",
    "corolla": "Toyota", "hyryder": "Toyota", "urban cruiser": "Toyota",
    # MG
    "hector": "MG", "astor": "MG", "gloster": "MG", "comet": "MG",
    # Skoda
    "slavia": "Skoda", "kushaq": "Skoda", "octavia": "Skoda", "superb": "Skoda",
    # Renault
    "kwid": "Renault", "kiger": "Renault", "triber": "Renault",
    # Volkswagen
    "taigun": "Volkswagen", "virtus": "Volkswagen", "polo": "Volkswagen",
    # Nissan
    "magnite": "Nissan",
}

# Compiled regex matching any known model name — used in multilingual intent detection.
# Sorted longest-first so "grand vitara" matches before "grand" etc.
_MODEL_NAMES_RE = re.compile(
    r"(?<![a-z])(" + "|".join(
        re.escape(k) for k in sorted(
            (k for k in _VEHICLE_SIZE_MAP if not k[0].isdigit() and len(k) >= 3),
            key=len, reverse=True,
        )
    ) + r")(?![a-z])",
    re.IGNORECASE,
)


def _infer_size(vehicle) -> Optional[str]:
    """Look up OEM tyre size from vehicle model name, with class-based fallback."""
    return _infer_size_from_text(f"{vehicle.make} {vehicle.model}")


def _infer_size_from_text(text: str) -> Optional[str]:
    """
    Infer tyre size from any free-text car description.

    Tries exact map match first, then vehicle-class keywords as fallback.
    Returns None only when the text contains no recognisable vehicle info.

    Args:
        text: Any string containing a car make/model (e.g. 'Honda CR-V', 'my new SUV').

    Returns:
        Tyre size string (e.g. '235/65R17') or None.
    """
    lower = text.lower()

    # 1. Direct map lookup
    for pattern, size in _VEHICLE_SIZE_MAP.items():
        if pattern in lower:
            return size

    # 2. Vehicle class keyword fallback
    for cls, keywords in _CLASS_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return _CLASS_SIZE_DEFAULTS[cls]

    # 3. Make-based guess: luxury → sport size, otherwise sedan default
    luxury_makes = {"bmw", "mercedes", "audi", "lexus", "porsche", "infiniti", "acura", "cadillac", "lincoln", "volvo", "genesis"}
    if any(m in lower for m in luxury_makes):
        return "225/45R17"

    return None


def _infer_terrain(habits: list[str]) -> str:
    habits_lower = " ".join(habits).lower()
    if "off-road" in habits_lower or "all-terrain" in habits_lower:
        return "all-terrain"
    if "city" in habits_lower:
        return "city"
    return "highway"


def _detect_terrain_from_msg(msg: str) -> Optional[str]:
    """
    Extract an explicit terrain preference from a user message.
    Returns None if no terrain signal found — caller keeps the habit-inferred value.
    """
    m = msg.lower()

    # Famous mountain / rough-road destinations → all-terrain
    _mountain_destinations = [
        "ladakh", "leh", "manali", "spiti", "rohtang", "zanskar", "pangong",
        "coorg", "ooty", "munnar", "shimla", "mussoorie", "nainital", "kedarnath",
        "badrinath", "char dham", "valley of flowers", "chopta",
        "himalayas", "himalayan", "western ghats", "eastern ghats",
        "sahyadri", "aravalli",
        "srinagar", "kashmir", "jammu", "gulmarg", "pahalgam", "sonamarg",
        "kargil", "vaishno devi",
        # Northeast — rough + very wet roads
        "assam", "kaziranga", "majuli", "meghalaya", "cherrapunji", "shillong",
        "sikkim", "gangtok", "arunachal", "tawang", "manipur", "nagaland",
        "mizoram", "tripura", "northeast",
    ]
    if any(d in m for d in _mountain_destinations):
        return "all-terrain"

    if any(k in m for k in ["off-road", "offroad", "off road", "mud", "trail", "4x4", "4wd", "rough", "jungle", "mountain", "hills", "ghats"]):
        return "all-terrain"
    # Major city destinations → highway driving
    _highway_destinations = [
        "mumbai", "delhi", "bangalore", "bengaluru", "chennai", "hyderabad",
        "pune", "kolkata", "jaipur", "ahmedabad", "surat", "agra", "varanasi",
        "amritsar", "lucknow", "chandigarh", "bhopal", "indore", "nagpur",
    ]
    if any(d in m for d in _highway_destinations):
        return "highway"
    if any(k in m for k in ["highway", "motorway", "freeway", "long drive", "intercity", "expressway", "road trip", "trip", "travel", "journey"]):
        return "highway"
    if any(k in m for k in ["city", "urban", "town", "commute", "traffic", "stop and go"]):
        return "city"
    return None


# ---------------------------------------------------------------------------
# Price / quality intent detection
# ---------------------------------------------------------------------------

# Intent → (sort_key, slot_labels, slot_types)
# sort_key: lambda applied to tyre objects before picking top 3
_PRICE_INTENT_CONFIG: dict[str, dict] = {
    "budget": {
        "sort": lambda t: t.member_price,          # cheapest first
        "reverse": False,
        "labels": ["Best Value", "Budget Pick", "Most Affordable"],
        "types":  ["budget_alt", "budget_alt", "budget_alt"],
        "punch_slot": 0,
    },
    "premium": {
        "sort": lambda t: (-t.rating, t.member_price),  # highest rating first, then price desc
        "reverse": False,
        "labels": ["Premium Pick", "Top Performer", "Runner-up"],
        "types":  ["top_pick", "runner_up", "budget_alt"],
        "punch_slot": 0,
    },
    "performance": {
        "sort": lambda t: (-t.rating, t.noise_db),   # highest rating, lowest noise
        "reverse": False,
        "labels": ["Best Performance", "High Grip", "Runner-up"],
        "types":  ["top_pick", "runner_up", "budget_alt"],
        "punch_slot": 0,
    },
    "safety": {
        "sort": lambda t: (0 if t.wet_grip == "A" else 1 if t.wet_grip == "B" else 2, -t.rating),
        "reverse": False,
        "labels": ["Safest Pick", "High Wet Grip", "Runner-up"],
        "types":  ["top_pick", "runner_up", "budget_alt"],
        "punch_slot": 0,
    },
    "longevity": {
        "sort": lambda t: -t.tread_life_km,         # longest tread life first
        "reverse": False,
        "labels": ["Longest Lasting", "Best Durability", "Runner-up"],
        "types":  ["top_pick", "runner_up", "budget_alt"],
        "punch_slot": 0,
    },
    "value": {
        # Best tread life per rupee/dollar spent
        "sort": lambda t: -(t.tread_life_km / t.member_price) if t.member_price > 0 else 0,
        "reverse": False,
        "labels": ["Best Value for Money", "Smart Choice", "Budget Alt"],
        "types":  ["top_pick", "runner_up", "budget_alt"],
        "punch_slot": 0,
    },
}

def _extract_price_limit(msg: str) -> Optional[float]:
    """
    Extract an explicit price ceiling from the message in any language.

    Handles patterns like:
      English:  "less than $130", "under 150", "below $200", "max $120", "no more than 140"
      Hindi:    "130 se kam", "130 rupaye se kam", "150 se neeche", "zyada se zyada 130"
      Telugu:   "130 kante takkuva", "130 lopala"
      Numbers:  bare "$130", "130 dollars" when combined with a qualifier word

    Returns the float price limit or None if no price constraint found.
    """
    m = msg.lower()

    # Pattern: qualifier word + optional $ + number (e.g. "under $130", "less than 150")
    _UNDER_RE = re.compile(
        r"(?:"
        r"under|below|less\s+than|cheaper\s+than|no\s+more\s+than|max(?:imum)?|"
        r"within|up\s+to|at\s+most|not\s+more\s+than|"
        # Hindi
        r"se\s+kam|se\s+neeche|se\s+sasta|zyada\s+se\s+zyada|itne\s+mein|"
        r"itna\s+budget|budget\s+hai|ke\s+andar|ke\s+neeche|tak\s+ke|"
        # Telugu
        r"kante\s+takkuva|lopala|kante\s+takkuva\s+ga"
        r")"
        r"\s*[\$₹£€]?\s*(\d{2,5}(?:[.,]\d{1,2})?)",
        re.IGNORECASE,
    )

    # Pattern: number + qualifier (e.g. "130 se kam", "$130 budget", "130 max")
    _NUM_FIRST_RE = re.compile(
        r"[\$₹£€]?\s*(\d{2,5}(?:[.,]\d{1,2})?)\s*"
        r"(?:se\s+kam|se\s+neeche|se\s+sasta|max|maximum|or\s+less|and\s+below|budget|tak|"
        r"kante\s+takkuva|lopala)",
        re.IGNORECASE,
    )

    # Pattern: "more cheaper", "more affordable" — these imply budget intent but no number
    # (handled by _detect_price_intent returning "budget", not here)

    for pattern in (_UNDER_RE, _NUM_FIRST_RE):
        match = pattern.search(m)
        if match:
            raw = match.group(1).replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                pass
    return None


def _detect_price_intent(msg: str) -> str:
    """
    Detect what kind of tyre the user is looking for from their message.

    Returns one of: budget | premium | performance | safety | longevity | value | none
    'none' means no specific intent — use default rating-based ranking.
    """
    m = msg.lower()

    # Budget / cheap signals — English + Hindi + Telugu + "more cheaper" patterns
    if re.search(
        r"\bcheap\b|\bbudget\b|\baffordabl\b|\beconom\b|\blow.?price\b|\binexpensiv\b|"
        r"\bmore\s+cheap\b|\bmore\s+affordabl\b|\bcheaper\b|\bsomething\s+cheaper\b|"
        r"\bless\s+expensiv\b|\bless\s+pric\b|\bcost\s+less\b|"
        r"\bsaasta\b|\bsasti\b|\bsasta\b|\bkam\s+price\b|\bkam\s+daam\b|"
        r"\bsastaa\b|\bless\s+expen\b|\bdon.t\s+want\s+to\s+spend\b|"
        r"\btight\s+budget\b|\bon\s+a\s+budget\b|\bwithout\s+breaking\b|"
        # Hindi cheap/price
        r"\bsasta\b|\bsaste\b|\bsasti\b|\bkam\s+keemat\b|\bsastay\b|\bkam\s+paise\b|"
        r"\bkam\s+mein\b|\bthoda\s+kam\b|\bkam\s+ka\b|"
        # Telugu
        r"\btakkuva\s+dharam\b|\btakkuva\b.*\bdharamb|\bcheepa\b|\bless\s+cost\b",
        m,
    ):
        return "budget"

    # Premium / best quality signals
    if re.search(
        r"\bpremium\b|\bbest\s+quality\b|\btop\s+quality\b|\bhigh.?end\b|\bluxury\b|"
        r"\bspare\s+no\s+expense\b|\bbest\s+available\b|\bno\s+compromise\b|"
        r"\bbehtar\b|\bsabse\s+accha\b|\bbadhiya\b|\bkamaal\b",
        m,
    ):
        return "premium"

    # Performance / grip / sporty signals
    if re.search(
        r"\bperformance\b|\bgrip\b|\bsporty\b|\bfast\b|\bhandling\b|\bcornering\b|"
        r"\bhigh.?speed\b|\bsport\b|\btrack\b|\baggressive\b|\bresponsiv\b",
        m,
    ):
        return "performance"

    # Safety / wet / monsoon signals
    if re.search(
        r"\bsafe\b|\bsafety\b|\bwet\b|\brain\b|\bmonsoon\b|\bslippery\b|\bbraking\b|"
        r"\bsurakh\b|\bsecure\b|\bsurakshit\b",
        m,
    ):
        return "safety"

    # Long lasting / durable
    if re.search(
        r"\blong.?last\b|\bdurabl\b|\blong\s+life\b|\btyre\s+life\b|\blong\s+mileage\b|"
        r"\bzyada\s+chal\b|\bzyadaa\s+km\b|\bkitne\s+km\b|\btikau\b",
        m,
    ):
        return "longevity"

    # Value for money
    if re.search(
        r"\bvalue\s+for\s+money\b|\bbest\s+deal\b|\bworth\b|\bgood\s+deal\b|"
        r"\bpaisa\s+vasool\b|\bpaisa\b.*\bvasool\b",
        m,
    ):
        return "value"

    return "none"


# ---------------------------------------------------------------------------
# Language & tone detection
# ---------------------------------------------------------------------------

# Language-specific word markers — most distinctive words per language.
# Order matters: more specific languages checked before broader ones.
_LANG_MARKERS: dict[str, set[str]] = {
    "Telugu": {
        "ledu", "avunu", "nenu", "meeru", "cheppu", "baaga", "velthanu",
        "vere", "enti", "chala", "ikkade", "akkade", "anni", "pedda", "chinna",
        "enduku", "emiti", "kavali", "cheyyandi", "cheyyi", "veltunnanu",
    },
    "Tamil": {
        "enna", "epdi", "sollu", "ponga", "vaanga", "konjam", "romba",
        "nalla", "aama", "illai", "nandri", "vanakkam", "seri",
    },
    "Kannada": {
        "yenu", "bega", "swamy", "yaake", "hogi", "banni", "nodri",
        "chennagide", "gottilla", "helu", "sigatte",
    },
    "Malayalam": {
        "alle", "undo", "mone", "mol", "enthanu", "sheriyano",
        "nokku", "varo", "parayoo", "adipoli",
    },
    "Bengali": {
        "kemon", "achho", "bhalo", "dada", "didi", "bolo", "jano",
        "amake", "apnake", "bolun",
    },
    "Marathi": {
        "aahe", "bagh", "mala", "tumhi", "sangto", "kara", "yeto",
        "nako", "hote", "aala",
    },
    "Hindi": {
        "yaar", "bhai", "haan", "nahi", "nahin", "kya", "acha", "accha", "theek",
        "bolo", "karo", "leke", "lekar", "gaadi", "chalte", "jaana", "milega",
        "arre", "arrey", "abhi", "bas", "ekdum", "bilkul", "sahi",
        "dekho", "bata", "kaafi", "thoda", "jaldi", "suno", "chal", "chalo",
        "jata", "jati", "jaunga", "jayenge", "hun", "hoon", "raha", "rahi",
        "wala", "wali", "mujhe", "humko", "aapko", "tyre", "chahiye",
    },
}

# All regional markers flattened — used to catch "non-English" quickly
_ALL_REGIONAL: set[str] = {w for words in _LANG_MARKERS.values() for w in words}

# Additional casual English signals (not language-specific)
_CASUAL_EN_MARKERS = re.compile(r"\blol\b|\bhaha\b|\bomg\b|gonna|wanna|gotta|lemme|\btbh\b|lmao|bruh")

# Morphological suffix patterns — catches conjugated verb forms that word-lists miss.
# Telugu is agglutinative: "velthunnanu" = "velthu" (go) + "unnanu" (I am).
# These patterns fire ONLY when no word-list match is found first.
_MORPH_PATTERNS: list[tuple[str, str]] = [
    # Telugu verb suffixes: -unnanu, -unna, -tanu, -thanu, -andi, -ante, -atu
    ("Telugu",   r"\w{3,}(unnanu|unna|thunnanu|tunna|tanu|thanu|andi|ante|atu)\b"),
    # Tamil verb suffixes: -ndaan, -raan, -vaan, -ren, -rom, -reen, -kkum
    ("Tamil",    r"\w{3,}(ndaan|raan|vaan|ren\b|rom\b|reen|kkum)\b"),
    # Kannada verb suffixes: -enu, -iru, -ide, -alli, -iinda
    ("Kannada",  r"\w{3,}(enu\b|iru\b|ide\b|alli\b|iinda)\b"),
    # Malayalam verb suffixes: -unnu, -um, -aan, -aal
    ("Malayalam",r"\w{4,}(unnu|unu\b|aan\b|aal\b)\b"),
    # Hindi verb patterns: raha/rahi + hu/hoon, jata/jati + hun, lekar/leke
    ("Hindi",    r"\b(ja|aa|kar|de|le|ho)\s+(raha|rahi)\s+(hu|hoon|hai)\b"),
    ("Hindi",    r"\b(raha|rahi)\s+(hu|hoon)\b"),
    ("Hindi",    r"\b(jata|jati|jaata|jaati)\s+(hun|hoon|hai)\b"),
    ("Hindi",    r"\b(le|leke|lekar)\s+\w+"),
]


def _detect_language(msg: str) -> str:
    """
    Detect the primary language of a user message.

    Two-pass detection:
      Pass 1 — word-list match (exact words, fast)
      Pass 2 — morphological suffix patterns (catches conjugated forms)

    Returns one of: Telugu | Tamil | Kannada | Malayalam | Bengali | Marathi |
                    Hindi | casual_en | English

    Caller stores result in session.preferences['language'] so it persists.

    Args:
        msg: Raw user message.

    Returns:
        Language label string.
    """
    m = msg.lower()
    words = set(re.split(r"\W+", m))

    # Pass 1: exact word markers (fastest path)
    for lang, markers in _LANG_MARKERS.items():
        if words & markers:
            return lang

    # Pass 2: morphological suffix patterns (catches verb conjugations)
    for lang, pattern in _MORPH_PATTERNS:
        if re.search(pattern, m):
            return lang

    if _CASUAL_EN_MARKERS.search(m):
        return "casual_en"
    if len(msg.split()) <= 5 and msg and not msg[0].isupper():
        return "casual_en"
    return "English"


def _detect_tone(msg: str) -> str:
    """Legacy tone label — derived from language for backwards compatibility."""
    lang = _detect_language(msg)
    if lang in ("Hindi", "Telugu", "Tamil", "Kannada", "Malayalam", "Bengali", "Marathi"):
        return "hinglish"
    if lang == "casual_en":
        return "casual"
    return "formal"


# LLM language instruction — appended to system prompt so Claude replies in the
# same language as the user. Technical terms (tyre size, brand, price) stay in English.
_LANG_INSTRUCTION: dict[str, str] = {
    "Telugu": (
        "The user is writing in Telugu. Reply entirely in Telugu. "
        "Keep tyre sizes (e.g. 235/65R17), brand names, and prices in English. "
        "Be warm and conversational, like a knowledgeable friend."
    ),
    "Tamil": (
        "The user is writing in Tamil. Reply entirely in Tamil. "
        "Keep tyre sizes, brand names, and prices in English."
    ),
    "Kannada": (
        "The user is writing in Kannada. Reply entirely in Kannada. "
        "Keep tyre sizes, brand names, and prices in English."
    ),
    "Malayalam": (
        "The user is writing in Malayalam. Reply entirely in Malayalam. "
        "Keep tyre sizes, brand names, and prices in English."
    ),
    "Bengali": (
        "The user is writing in Bengali. Reply entirely in Bengali. "
        "Keep tyre sizes, brand names, and prices in English."
    ),
    "Marathi": (
        "The user is writing in Marathi. Reply entirely in Marathi. "
        "Keep tyre sizes, brand names, and prices in English."
    ),
    "Hindi": (
        "The user is communicating in Hindi or Hinglish. "
        "Reply in Hinglish — mix Hindi naturally into English sentences. "
        "Use words like yaar, boss, chalo, sahi where they feel natural. "
        "Keep it short and punchy. Never be stiff or over-formal."
    ),
    "casual_en": (
        "The user is speaking casually. Match their energy — "
        "be conversational, light, and punchy. No corporate language."
    ),
    "English": "",  # default persona already handles this
}

# Hardcoded vehicle question templates — used when language is English/casual only.
# For all other languages the context_then_vehicle handler calls LLM directly.
_VEHICLE_Q: dict[str, str] = {
    "Hindi":    "{opener} **{year} {make} {model}** leke jaaoge, ya koi aur gaadi?",
    "casual_en": "{opener} Rolling in your **{year} {make} {model}**, or different wheels?",
    "English":  "{opener} Are you taking your **{year} {make} {model}**, or a different vehicle?",
}
_VEHICLE_Q_NO_CAR: dict[str, str] = {
    "Hindi":    "{opener} Konsi gaadi ke liye tyres chahiye?",
    "casual_en": "{opener} Which car are we sorting tyres for?",
    "English":  "{opener} Which car are you shopping tyres for?",
}


# Destination-to-label map for friendly response text
_DESTINATION_LABELS = {
    # Mountain / rough terrain
    "ladakh":    ("Ladakh",       "all-terrain", "Those mountain passes need serious grip"),
    "leh":       ("Leh-Ladakh",   "all-terrain", "High altitude, rough roads — tyres matter a lot here"),
    "manali":    ("Manali",       "all-terrain", "Rohtang and beyond — you'll want all-terrain tyres"),
    "spiti":     ("Spiti Valley", "all-terrain", "One of the toughest drives in India — right tyre is key"),
    "coorg":     ("Coorg",        "all-terrain", "Those winding ghats need good grip"),
    "ooty":      ("Ooty",         "all-terrain", "Ghat roads — all-terrain is the smart call"),
    "munnar":    ("Munnar",       "all-terrain", "Beautiful drive, but those ghats deserve proper tyres"),
    "shimla":    ("Shimla",       "all-terrain", "Hill roads can get tricky, especially in season"),
    "mussoorie": ("Mussoorie",    "all-terrain", "Mountain roads — grip and stability matter here"),
    "nainital":  ("Nainital",     "all-terrain", "Winding hill roads — you'll want confident tyres"),
    "kedarnath": ("Kedarnath",    "all-terrain", "Tough mountain terrain — all-terrain is the way to go"),
    "goa":       ("Goa",          "highway",     "Long highway drive down to Goa — comfort and mileage matter"),
    "lonavala":  ("Lonavala",     "all-terrain", "Ghats can get slippery — good wet grip is important"),
    "mahabaleshwar": ("Mahabaleshwar", "all-terrain", "Hill station roads — solid grip is a must"),
    # Kashmir / J&K — mountain + snow risk
    "srinagar":  ("Srinagar",    "all-terrain", "Beautiful drive but mountain roads and snow risk — grip matters a lot"),
    "kashmir":   ("Kashmir",     "all-terrain", "Mountain terrain, possible snow — all-terrain tyres are the right call"),
    "jammu":     ("Jammu",       "all-terrain", "Jammu-Srinagar highway has some serious mountain stretches"),
    "gulmarg":   ("Gulmarg",     "all-terrain", "Snow-covered roads — you'll need serious all-terrain grip"),
    "pahalgam":  ("Pahalgam",    "all-terrain", "Mountain valley roads — all-terrain with good wet grip"),
    "sonamarg":  ("Sonamarg",    "all-terrain", "High altitude snow roads — all-terrain is non-negotiable"),
    "kargil":    ("Kargil",      "all-terrain", "Tough high-altitude terrain — you need the most durable tyres"),
    "vaishno devi": ("Vaishno Devi", "all-terrain", "Mountain roads up to Katra — solid grip is essential"),
    # Northeast India — mix of highway + rough/wet roads, high rainfall
    "assam":        ("Assam",            "all-terrain", "Roads can get rough and very wet — wet grip A-rating is a must"),
    "kaziranga":    ("Kaziranga",         "all-terrain", "Approach roads get muddy — all-terrain with strong wet grip"),
    "majuli":       ("Majuli",            "all-terrain", "River island roads are rough and waterlogged in season"),
    "meghalaya":    ("Meghalaya",         "all-terrain", "One of the wettest regions on earth — wet grip is non-negotiable"),
    "cherrapunji":  ("Cherrapunji",       "all-terrain", "Wettest place in India — wet grip A-rating is essential"),
    "shillong":     ("Shillong",          "all-terrain", "Hill roads + heavy rain — all-terrain with great wet grip"),
    "sikkim":       ("Sikkim",            "all-terrain", "Mountain roads with heavy rainfall — all-terrain is the right call"),
    "gangtok":      ("Gangtok",           "all-terrain", "Steep hill roads, wet most of the year — all-terrain is key"),
    "arunachal":    ("Arunachal Pradesh", "all-terrain", "Remote mountain roads — durability and grip both matter"),
    "tawang":       ("Tawang",            "all-terrain", "High altitude, rough and wet roads — you need serious all-terrain"),
    "manipur":      ("Manipur",           "all-terrain", "Hilly terrain with wet roads — all-terrain and wet grip matter"),
    "nagaland":     ("Nagaland",          "all-terrain", "Hilly roads, heavy rainfall — all-terrain tyres are the smart pick"),
    "mizoram":      ("Mizoram",           "all-terrain", "Steep hilly roads with lots of rain — all-terrain is a must"),
    # Highway / city destinations
    "mumbai":    ("Mumbai",   "highway", "Long highway run — you'll want something comfortable and fuel-efficient"),
    "delhi":     ("Delhi",    "highway", "Delhi highways are fast — durability and highway comfort matter"),
    "bangalore": ("Bangalore","highway", "Bangalore roads can be rough — a good all-rounder works well"),
    "bengaluru": ("Bangalore","highway", "Bangalore roads can be rough — a good all-rounder works well"),
    "chennai":   ("Chennai",  "highway", "Long expressway stretch — highway tyres will serve you well"),
    "hyderabad": ("Hyderabad","highway", "Decent highways all the way — comfort and mileage are the priority"),
    "pune":      ("Pune",     "highway", "Expressway run — smooth highway tyres are the right pick"),
    "kolkata":   ("Kolkata",  "highway", "Long drive — highway comfort and durability is what you need"),
    "jaipur":    ("Jaipur",   "highway", "NH48 is a solid highway — good mileage tyres will shine here"),
    "ahmedabad": ("Ahmedabad","highway", "Long expressway stretch — highway tyres are perfect"),
    "surat":     ("Surat",    "highway", "Expressway all the way — highway comfort is key"),
    "agra":      ("Agra",     "highway", "Yamuna Expressway is smooth — great for highway tyres"),
    "varanasi":  ("Varanasi", "highway", "Long drive — durability and highway comfort matter"),
    "amritsar":  ("Amritsar", "highway", "GT Road classic — highway tyres built for the long haul"),
    # South India — coastal + ghat mix
    "kerala":    ("Kerala",       "all-terrain", "Ghats, coastal roads, and heavy rain — wet grip and durability both matter"),
    "kochi":     ("Kochi",        "all-terrain", "Coastal city with monsoon-prone roads — wet grip is key"),
    "thrissur":  ("Thrissur",     "all-terrain", "Kerala roads — good wet grip and handling are a must"),
    "thiruvananthapuram": ("Thiruvananthapuram", "all-terrain", "Kerala roads — wet grip and comfort for the long drive"),
    "trivandrum": ("Thiruvananthapuram", "all-terrain", "Kerala roads — wet grip and comfort for the long drive"),
    "kozhikode": ("Kozhikode",    "all-terrain", "Malabar coast roads with rain — all-terrain with strong wet grip"),
    "calicut":   ("Kozhikode",    "all-terrain", "Malabar coast roads with rain — all-terrain with strong wet grip"),
    "pondicherry": ("Pondicherry","highway",     "Coastal expressway — highway tyres for a comfortable ride"),
    "puducherry": ("Pondicherry", "highway",     "Coastal expressway — highway tyres for a comfortable ride"),
    "madurai":   ("Madurai",      "highway",     "Long expressway drive — highway comfort tyres will do great"),
    "coimbatore": ("Coimbatore",  "highway",     "Good highways out of Coimbatore — highway tyres are the right pick"),
    "vizag":     ("Visakhapatnam","highway",     "Coastal highway — comfortable highway tyres are ideal"),
    "visakhapatnam": ("Visakhapatnam", "highway","Coastal highway — comfortable highway tyres are ideal"),
    "vijayawada": ("Vijayawada",  "highway",     "NH16 is a strong highway — good mileage tyres will serve you well"),
    "tirupati":  ("Tirupati",     "all-terrain", "Ghat road to the temple — all-terrain with good wet grip"),
}


# Climates where winter tyres are genuinely relevant (heavy snow/ice)
_WINTER_CITIES = {"Minneapolis", "Chicago", "Denver", "Boston", "Montreal", "Toronto"}

def _detect_season(city: str = "") -> str:
    """
    Auto-detect the appropriate tyre season from the current calendar month and member city.

    Logic:
      - Winter months (Dec–Feb) in a cold/snowy city → "winter"
      - Summer months (Jun–Aug) → "summer" (performance/summer tyres)
      - Everything else → "all-season"
      - Mild-climate cities (SF, LA, Phoenix, Seattle, Portland) → always "all-season"

    Args:
        city: Member's city name from their profile location. Used to skip winter
              recommendations for mild climates even in cold months.

    Returns:
        "winter" | "summer" | "all-season"
    """
    from datetime import datetime as _dt
    month = _dt.now().month

    # Mild-climate cities never need winter tyres
    mild_cities = {"San Francisco", "Los Angeles", "Phoenix", "Seattle", "Portland"}
    if city in mild_cities:
        if month in (6, 7, 8):
            return "summer"
        return "all-season"

    # Winter months in a cold/snowy city
    if month in (12, 1, 2) and city in _WINTER_CITIES:
        return "winter"

    # Summer months — performance/summer tyres relevant
    if month in (6, 7, 8):
        return "summer"

    # Spring / autumn — all-season is the safe default
    return "all-season"

# ---------------------------------------------------------------------------
# Smart slot suggestion — uses member history + habits to rank slots
# ---------------------------------------------------------------------------

def _suggest_smart_slots(user, location_id: str, n: int = 3) -> list[dict]:
    """
    Return the best N available appointment slots ranked by the member's likely schedule.

    Ranking signals (in priority order):
      1. Day-of-week preference — inferred from last_purchase.date (weekend vs weekday buyer)
      2. Commuter flag — "daily commute" habit → prefer Saturday morning over weekday slots
      3. Morning preference — earlier slots have shorter wait times (from predict_wait_times logic)

    Looks 7 days ahead so weekend slots are always reachable even mid-week.

    Args:
        user:        Member User object (needs driving_habits + last_purchase).
        location_id: Warehouse ID to check availability for.
        n:           Number of slots to return.

    Returns:
        List of slot dicts with keys: slot_id, date, time, available, estimated_duration_mins,
        plus 'why' — a short human-readable reason for the suggestion.
    """
    from app.tools.appointment_tools import get_available_slots
    from datetime import datetime as _dt

    # Fetch 7 days so we catch at least one weekend
    all_slots = json.loads(get_available_slots.invoke({"location_id": location_id, "days_ahead": 7}))
    available = [s for s in all_slots if s["available"]]

    # --- Infer day preference from last purchase ---
    preferred_weekend = False
    if user and user.last_purchase:
        try:
            purchase_weekday = _dt.strptime(str(user.last_purchase.date), "%Y-%m-%d").weekday()
            preferred_weekend = purchase_weekday >= 5  # 5=Sat, 6=Sun
        except (ValueError, AttributeError):
            pass

    # Daily commuters are busy on weekdays — prefer Saturday even if not a weekend shopper
    is_commuter = user and any(
        h.lower() in ("daily commute", "city", "commute") for h in (user.driving_habits or [])
    )
    if is_commuter:
        preferred_weekend = True

    def slot_score(s: dict) -> tuple:
        day = _dt.strptime(s["date"], "%Y-%m-%d").weekday()  # 0=Mon … 6=Sun
        is_weekend = day >= 5
        hour = int(s["time"].split(":")[0])

        # Lower = better
        day_match = 0 if (is_weekend == preferred_weekend) else 1
        morning_bonus = 0 if hour < 11 else (1 if hour < 14 else 2)
        return (day_match, s["date"], morning_bonus, s["time"])

    ranked = sorted(available, key=slot_score)[:n]

    # Attach a short human-readable "why" label to each slot
    for s in ranked:
        day = _dt.strptime(s["date"], "%Y-%m-%d").weekday()
        hour = int(s["time"].split(":")[0])
        day_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day]
        time_label = "morning" if hour < 11 else ("afternoon" if hour >= 14 else "midday")
        s["why"] = f"{day_name} {time_label} — {'less busy' if hour < 11 else 'convenient time'}"

    return ranked


# ---------------------------------------------------------------------------
# Core pipeline — deterministic (no LLM)
# ---------------------------------------------------------------------------

def _build_recommendation_cards(session: SessionState, user) -> list[dict]:
    """Build tyre recommendation cards using Python services only — zero LLM calls."""
    from app.services.stock_service import search_tyres, get_tyre_by_id, get_stock_badge
    from app.tools.content_tools import generate_personalised_msg
    from app.tools.recommendation_tools import generate_punch_line

    locs_path = Path(__file__).parent / "data" / "locations.json"
    locs = json.loads(locs_path.read_text(encoding="utf-8")) if locs_path.exists() else []
    member_ctx = json.dumps({
        "driving_habits": user.driving_habits,
        "location": user.location.model_dump(),
        "membership_tier": user.membership_tier,
        "vehicle": user.vehicle.model_dump(),
    })

    # Auto-detect season from current date + member city — never ask the member
    city = user.location.city if user.location else ""
    season = _detect_season(city)
    # terrain: explicit override from message > driving_habits inference
    terrain = session.preferences.get("override_terrain") or _infer_terrain(user.driving_habits)
    # max_price: explicit price ceiling from user message ("less than $130", "130 se kam")
    max_price: Optional[float] = session.preferences.get("max_price")

    cards = []

    # ── Path A: returning buyer ──────────────────────────────────────────
    if session.user_path == "A" and user.last_purchase:
        last_tyre = get_tyre_by_id(user.last_purchase.tyre_id)
        size = last_tyre.size if last_tyre else _infer_size(user.vehicle)

        # Search with auto-detected season; broaden progressively until we have 3+ options
        results = search_tyres(size=size, season=season, terrain=terrain, max_price=max_price, in_stock_only=True)
        if len(results) < 3:
            _extra = search_tyres(size=size, season="all-season", terrain=terrain, max_price=max_price, in_stock_only=True)
            _seen = {t.id for t in results}
            results += [t for t in _extra if t.id not in _seen]
        if len(results) < 3:
            _extra = search_tyres(size=size, max_price=max_price, in_stock_only=True)
            _seen = {t.id for t in results}
            results += [t for t in _extra if t.id not in _seen]
        # If price filter yields nothing, relax it so we don't show empty results
        if not results and max_price:
            results = search_tyres(size=size, season=season, terrain=terrain, in_stock_only=True)

        # Slot 1: Best Repurchase (same tyre if in stock)
        repurchase = last_tyre if (last_tyre and last_tyre.stock.qty > 0) else None
        alternatives = [t for t in results if not repurchase or t.id != repurchase.id]
        # Slot 2: Best Upgrade (highest rating among alternatives)
        upgrade = alternatives[0] if alternatives else None
        # Slot 3: Most Popular (most reviews)
        popular_pool = [t for t in alternatives if not upgrade or t.id != upgrade.id]
        popular = max(popular_pool, key=lambda t: t.review_count) if popular_pool else None

        slots = [
            (repurchase or upgrade, "Best Repurchase", "best_repurchase"),
            (upgrade, "Best Upgrade", "best_upgrade"),
            (popular, "Most Popular", "most_popular"),
        ]
        for tyre, tag, slot_type in slots:
            if not tyre:
                continue
            msg = generate_personalised_msg.invoke({
                "tyre_json": json.dumps(tyre.model_dump()),
                "member_context_json": member_ctx,
                "slot_type": slot_type,
            })
            punch = None
            if slot_type == "best_upgrade":
                punch = generate_punch_line.invoke({"tyre_json": json.dumps(tyre.model_dump())})
            cards.append({
                "tyre": tyre.model_dump(),
                "slot_tag": tag,
                "personalised_msg": msg,
                "stock_badge": get_stock_badge(tyre, locs),
                "punch_line": punch,
            })

    # ── Path B: new buyer ────────────────────────────────────────────────
    else:
        size = session.preferences.get("override_tyre_size") or _infer_size(user.vehicle)

        # Search with auto-detected season + inferred terrain; broaden progressively until we have 3+
        results = search_tyres(size=size, season=season, terrain=terrain, max_price=max_price, in_stock_only=True)
        if len(results) < 3:
            _extra = search_tyres(size=size, season="all-season", terrain=terrain, max_price=max_price, in_stock_only=True)
            _seen = {t.id for t in results}
            results += [t for t in _extra if t.id not in _seen]
        if len(results) < 3:
            _extra = search_tyres(size=size, max_price=max_price, in_stock_only=True)
            _seen = {t.id for t in results}
            results += [t for t in _extra if t.id not in _seen]
        # If price filter yields nothing, relax it (show what we have, warn in response)
        if not results and max_price:
            results = search_tyres(size=size, season=season, terrain=terrain, in_stock_only=True)
            session.preferences["price_filter_relaxed"] = True
        if not results:
            results = search_tyres(in_stock_only=True)

        # ── Apply user intent-based ranking ──────────────────────────────
        # If the user expressed a price/quality intent (budget, premium, safety, etc.)
        # sort results by that signal rather than default rating-descending.
        intent = session.preferences.get("ranking_intent", "none")
        intent_cfg = _PRICE_INTENT_CONFIG.get(intent)

        if intent_cfg:
            sorted_results = sorted(results, key=intent_cfg["sort"])
        else:
            # Default: highest rating first
            sorted_results = sorted(results, key=lambda x: x.rating, reverse=True)

        # Enforce brand diversity across top 3 (regardless of intent)
        seen_brands: set[str] = set()
        diverse: list = []
        for t in sorted_results:
            if t.brand not in seen_brands or len(diverse) < 3:
                diverse.append(t)
                seen_brands.add(t.brand)
            if len(diverse) == 3:
                break

        # Build slot labels from intent config (or fallback defaults)
        if intent_cfg:
            labels = intent_cfg["labels"]
            types  = intent_cfg["types"]
            punch_slot = intent_cfg["punch_slot"]
        else:
            labels = ["Top Pick", "Runner-up", "Budget Alt"]
            types  = ["top_pick", "runner_up", "budget_alt"]
            punch_slot = 0

        slot_defs = []
        for i, tyre in enumerate(diverse[:3]):
            is_top = (i == punch_slot)
            slot_defs.append((tyre, labels[i], types[i], is_top))

        # If intent is NOT budget, still append cheapest option as Budget Alt when slot 3 is empty
        if len(slot_defs) < 3 and intent != "budget":
            _used_ids = {s[0].id for s in slot_defs}
            _budget_pool = sorted([t for t in results if t.id not in _used_ids], key=lambda t: t.member_price)
            if _budget_pool:
                slot_defs.append((_budget_pool[0], "Budget Alt", "budget_alt", False))

        for tyre, tag, slot_type, is_top in slot_defs:
            msg = generate_personalised_msg.invoke({
                "tyre_json": json.dumps(tyre.model_dump()),
                "member_context_json": member_ctx,
                "slot_type": slot_type,
            })
            punch = None
            if is_top:
                punch = generate_punch_line.invoke({"tyre_json": json.dumps(tyre.model_dump())})
            cards.append({
                "tyre": tyre.model_dump(),
                "slot_tag": tag,
                "personalised_msg": msg,
                "stock_badge": get_stock_badge(tyre, locs),
                "punch_line": punch,
            })

    return cards

# ---------------------------------------------------------------------------
# Shared personality — prepended to every stage system prompt
# ---------------------------------------------------------------------------

_PERSONA = (
    "You are Alex, a real person at Costco who genuinely loves helping members find the right tyres. "
    "You text the way a knowledgeable friend would — casual, warm, and direct. "

    # ── Tone & language rules ──────────────────────────────────────────────
    "Always use contractions: I'll, you're, that's, it's, we've, don't, can't, won't. "
    "Never write 'I am' when you can write 'I'm'. Never write 'you are' when you can write 'you're'. "
    "Use the member's first name naturally — once per reply, not every sentence. "
    "React like a human: 'Nice!', 'Oh, good choice.', 'Yeah, that one's solid.' — "
    "brief, genuine reactions before getting to the point. "
    "Use natural pauses with commas: 'So, based on your Camry...' not 'Based on your Camry'. "
    "Occasionally start with 'So,', 'Well,', 'Right,', or 'Actually,' to sound human. "
    "Use 'and' and 'but' at the start of sentences when it flows naturally. "

    # ── What to avoid ──────────────────────────────────────────────────────
    "NEVER sound like a press release, FAQ, or customer-service script. "
    "NEVER use phrases like: 'Certainly!', 'Absolutely!', 'Great question!', "
    "'I'd be happy to', 'As your tyre advisor', 'rest assured', 'please note'. "
    "NEVER use corporate filler. If you can cut a word, cut it. "
    "NEVER repeat information the UI already shows on the card. "
    "NEVER ask for info you already have — name, city, vehicle are all in the profile. "

    # ── Structure ──────────────────────────────────────────────────────────
    "Keep replies short: 1–2 sentences max unless context demands more. "
    "The cards and UI handle the details — your job is the human connection. "
    "Reference their specific situation — vehicle, city, driving habits, tier — "
    "to make the reply feel personal, not copy-pasted."
)

# ---------------------------------------------------------------------------
# Single LLM call — generate conversational response text
# ---------------------------------------------------------------------------

def _llm_respond(session_id: str, system: str, user_msg: str) -> str:
    """
    Make a single LLM call and return the response text.

    This is the ONLY place in the pipeline where the LLM is called.
    All data work (search, rank, stock, cart) happens before this function.
    The LLM's sole job here is to write a short, friendly conversational reply.

    Args:
        session_id: Current session ID — used to retrieve conversation history.
        system:     System prompt scoped to the current pipeline stage (2-4 sentences).
                    Changes per stage (login / select / cart / payment / booking).
        user_msg:   Context string assembled by the pipeline, not the raw user message.
                    Contains member name, vehicle, cards shown, prices, etc.

    Returns:
        Response text from Claude. Empty string on API error.

    Side effects:
        Reads from CHAT_HISTORY[session_id] (last 8 messages = last 4 turns).
        Does NOT write to history — caller (chat endpoint) writes after guardrail.
    """
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    # Append language instruction so LLM replies in the same language as the user
    session = SESSION_STORE.get(session_id)
    if session:
        lang = session.preferences.get("language", "English")
        lang_hint = _LANG_INSTRUCTION.get(lang, "")
        if lang_hint:
            system = f"{system}\n\n{lang_hint}"

    history = get_history(session_id)
    messages = [SystemMessage(content=system)]
    for h in history[-8:]:  # last 4 turns (8 messages = user + assistant pairs)
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        else:
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_msg))

    # ── External API Call ────────────────────────────────────────────────────
    # Service:    Anthropic Claude  (claude-sonnet-4-6)
    # Endpoint:   POST https://api.anthropic.com/v1/messages
    # Auth:       ANTHROPIC_API_KEY (required in .env — app will error without it)
    # Params:     max_tokens=1024, temperature=0 (deterministic; set in get_llm())
    # Rate limit: ~60 req/min on Tier 1 — back off on HTTP 429
    # Latency:    ~800ms p50 / ~2s p99  (sonnet-4-6 as of 2025)
    # Cost:       ~$0.003 per call (1K input + 1K output tokens, Sonnet pricing)
    # Context:    System prompt + up to 8 history messages + 1 context message
    # Fallback:   Returns user-friendly message on 529/429/network errors
    try:
        result = get_llm().invoke(messages)
        return result.content
    except Exception as e:
        err = str(e).lower()
        if "overloaded" in err or "529" in err:
            logger.warning("Anthropic API overloaded (529) — returning fallback")
            return "I'm having a bit of a moment — the AI service is overloaded right now. Give it a few seconds and try again."
        if "429" in err or "rate" in err:
            logger.warning("Anthropic API rate limited (429)")
            return "Too many requests right now — please try again in a moment."
        logger.error(f"LLM call failed: {e}")
        return "Something went wrong on my end. Please try again."

# ---------------------------------------------------------------------------
# Pipeline intent detection (pure Python — no LLM)
# ---------------------------------------------------------------------------

def _detect_intent(msg: str, session: SessionState) -> str:
    """
    3-tier intent router.

    Tier 1 — Global rules  : patterns that fire from ANY stage.
    Tier 2 — Stage rules   : existing stage-gated logic (context-sensitive).
    Tier 3 — LLM classifier: called only when Tiers 1+2 produce no match.
                             Returns a single label — no explanation, minimal latency.

    Returns one of:
      login | context_then_vehicle | same_vehicle | new_vehicle | new_vehicle_detail |
      select_tyre | compare | add_cart | confirm_pay | cancel | book_slot | general
    """
    m = msg.lower().strip()

    # ── Tier 1 — Global rules (stage-independent) ────────────────────────────
    # These patterns are strong enough to override whatever stage we're in.

    # Member ID — always login regardless of stage
    if re.match(r"^m\d{4,6}$", m):
        return "login"

    # Explicit corrections/apologies always mean the user is updating context.
    # Must be Tier 1 so "my bad im travelling to Assam" never hits same_vehicle.
    if re.search(r"\bmy bad\b|actually[,!]|\bsorry\b|i meant|i mean,|oops\b|\bcorrection\b", m):
        return "context_then_vehicle"

    # Hard action intents — these are unambiguous from any stage
    if re.search(r"\badd to cart\b|add.to.cart", m):
        return "add_cart"
    if re.search(r"\bcompar|side.by.side|\bvs\b|\bversus\b", m):
        return "compare"
    if re.search(r"\bbook\b|\bschedule\b|\bappointment\b|\binstall\b|\bslot\b", m):
        return "book_slot"
    if re.search(r"\bcancel\b|\bgo back\b|\bstart over\b|\brestart\b", m):
        return "cancel"

    # ── Tier 1.5 — Multilingual vehicle detection (global, pre-cart stages only) ──
    # If a known car brand or model name appears in the message, and we are not
    # deep into checkout, treat it as a vehicle specification regardless of
    # language context (English, Hindi, Telugu, Tamil, Kannada, etc.).
    _VEHICLE_STAGES = {"confirm_vehicle", "collect_vehicle", "browse", "greet", None, ""}
    if session.stage in _VEHICLE_STAGES:
        if re.search(r"\d{3}/\d{2}R\d{2}", msg, re.IGNORECASE):
            return "new_vehicle_detail"
        if re.search(
            r"\b(honda|toyota|ford|bmw|mercedes|audi|kia|hyundai|nissan|chevrolet|"
            r"subaru|mazda|volkswagen|maruti|suzuki|tata|mahindra|mg|skoda|renault|"
            r"citroen|isuzu|jeep|dodge|tesla|lexus|acura|infiniti)\b",
            m,
        ):
            return "new_vehicle_detail"
        if _MODEL_NAMES_RE.search(m):
            return "new_vehicle_detail"

    # ── Tier 2 — Stage-sensitive rules ───────────────────────────────────────
    # Context matters here — same word means different things in different stages.

    # When cart is confirmed, "yes" / "sure" / "go ahead" mean "confirm payment" not add-to-cart
    if session.stage == "cart":
        if re.search(r"^yes\b|^yeah\b|^yep\b|^sure\b|^ok\b|^okay\b|^go ahead\b|^proceed\b|^confirm\b|^pay\b|^sounds good\b", m):
            return "confirm_pay"

    if session.stage == "confirm_vehicle":
        # ── SAME VEHICLE — checked FIRST.
        # English/Hindi: "same", "yes", "haan", "wahi gaadi"
        # Telugu: "avunu" (yes), "unna vehicle" (existing vehicle),
        #         "tesuku" (will take/taking), "ikkade unna" (the one here)
        # Tamil:  "aama" (yes), "athey" (same one)
        # Kannada: "houdu" (yes), "adey" (same)
        if re.search(
            r"\bsame\b|wahi\s+gaadi|same\s+(hi|le|wali|car|gaadi)|"
            r"^yes\b|^yeah\b|^yep\b|^haan\b|^han\b|that one|existing|keep it|current|"
            # Telugu affirmations and "existing vehicle" phrases
            r"\bavunu\b|\bunna\s+vehicle\b|\bunna\s+car\b|\bunna\s+gaadi\b|"
            r"\btesuku\b|\bikkade\s+unna\b|ade\s+(vehicle|car|gaadi)|"
            # Tamil
            r"\baama\b|\bathey\b|\bathey\s+(vehicle|car)\b|"
            # Kannada
            r"\bhoudu\b|\badey\s+(vehicle|car|gaadi)\b",
            m
        ):
            return "same_vehicle"
        # "my <vehicle>" — negative lookahead excludes correction fillers
        if re.search(r"\bmy (?!bad\b|mistake\b|oops\b|fault\b)\w+", m):
            return "same_vehicle"

        # ── CAR BRAND / MODEL / TYRE SIZE — check FIRST so multilingual messages
        # like "Nahin main Kerala nexon per jata hun" are caught before destination context.
        if re.search(r"\d{3}/\d{2}R\d{2}", msg, re.IGNORECASE):
            return "new_vehicle_detail"
        if re.search(r"\b(honda|toyota|ford|bmw|mercedes|audi|kia|hyundai|nissan|chevrolet|"
                     r"subaru|mazda|volkswagen|maruti|tata|mahindra|mg|skoda|renault)\b", m):
            return "new_vehicle_detail"
        # Model name only (no brand) — covers "nexon", "creta", "swift" in any language context
        if _MODEL_NAMES_RE.search(m):
            return "new_vehicle_detail"
        # Different vehicle signals — includes Hindi negation "nahin/nahi"
        if re.search(
            r"\bnew\b|^no\b|differ|just got|bought|have a|got a|switched|changed|"
            r"\bnahin\b|\bnahi\b|\bnope\b|\balag\b|\bdusri\b|\bdusra\b",
            m,
        ):
            return "new_vehicle"
        # ── TRIP / DESTINATION CONTEXT — only when no car brand/model detected above
        # Includes Hindi travel phrases, Indian cities, and Indian states.
        if re.search(
            r"road trip|long drive|travel|journey|trip to|going to|heading to|"
            r"off.road|highway|monsoon|\brain\b|winter|city driv|daily|"
            # Hindi / Hinglish travel phrases
            r"ja raha|ja rahi|jaana|safar|nikal raha|nikal rahi|chal raha|jaa raha|"
            r"jata hun|jati hun|jaunga|jayenge|nikalna|travel kar|drive kar|"
            # Major Indian cities
            r"\bmumbai\b|\bbombay\b|\bdelhi\b|\bbangalore\b|\bbengaluru\b|\bchennai\b|"
            r"\bhyderabad\b|\bpune\b|\bkolkata\b|\bjaipur\b|\bahmedabad\b|"
            r"\bsurat\b|\bchandigarh\b|\bindore\b|\bnagpur\b|\blucknow\b|"
            r"\bgoa\b|\bkochi\b|\bvishakapatnam\b|\bvizag\b|"
            # Indian states — destination context
            r"\bkerala\b|\bgujarat\b|\brajasthan\b|\bmaharashtra\b|\bkarnataka\b|"
            r"\btamil\s*nadu\b|\bandhra\b|\btelangana\b|\bpunjab\b|\bharyana\b|"
            r"\bup\b|\buttar\s*pradesh\b|\bmp\b|\bmadya\s*pradesh\b|\bassam\b|"
            r"\bwest\s*bengal\b|\bodisha\b|\bjharkhand\b|\bchhattisgarh\b",
            m
        ):
            return "context_then_vehicle"

    if session.stage == "collect_vehicle":
        return "new_vehicle_detail"

    # These fire anywhere except when stage rules already matched above
    if re.search(r"add.to.cart|checkout|\bbuy\b|\bpurchase\b|\bproceed\b", m):
        return "add_cart"
    if re.search(r"view details|select this|i.ll take|choose|i.ll go with|i want this", m):
        return "select_tyre"
    if re.search(r"\bconfirm\b|pay now|complete.*order|place order|confirm.*pay|pay.*confirm|let'?s pay|yes.*pay|go ahead.*pay|proceed.*pay", m):
        return "confirm_pay"
    if re.search(r"\bpick\b|\bchoose\b|\bselect\b|\bwant\b|go with", m):
        return "select_tyre"
    if re.search(r"\bcancel\b|\bback\b|\bchange\b", m):
        return "cancel"

    # ── Tier 3 — LLM classifier (only when Tiers 1+2 give no match) ─────────
    # Cheap single-turn call: no history, tiny prompt, returns one label only.
    return _llm_classify_intent(msg, session)


# ---------------------------------------------------------------------------
# Tier 3 — LLM intent classifier (fallback only)
# ---------------------------------------------------------------------------

_INTENT_OPTIONS = (
    "login | context_then_vehicle | same_vehicle | new_vehicle | new_vehicle_detail | "
    "select_tyre | compare | add_cart | confirm_pay | cancel | book_slot | general"
)


def _llm_classify_intent(msg: str, session: SessionState) -> str:
    """
    Classify intent with a single LLM call when rule-based routing fails.

    Called only from Tier 3 of _detect_intent — never directly.
    No conversation history is sent — just message + stage + known options.
    Returns one label from _INTENT_OPTIONS, defaults to 'general' on error.

    Args:
        msg:     Raw user message.
        session: Current session (provides stage and last known context).

    Returns:
        One of the intent label strings.

    # ── External API Call ────────────────────────────────────────────────────
    # Service:    Anthropic Claude  (claude-sonnet-4-6)
    # Endpoint:   POST https://api.anthropic.com/v1/messages
    # Auth:       ANTHROPIC_API_KEY (required in .env)
    # Params:     max_tokens=10, temperature=0  (single label response)
    # Rate limit: ~60 req/min on Tier 1
    # Latency:    ~200ms (tiny output — single word)
    # Fallback:   Returns "general" on any error
    # ────────────────────────────────────────────────────────────────────────
    """
    stage = session.stage or "unknown"
    system = (
        f"You are an intent classifier for a tyre shopping assistant. "
        f"Current conversation stage: '{stage}'. "
        f"Classify the user message into EXACTLY ONE of these labels: {_INTENT_OPTIONS}. "
        f"IMPORTANT: If the message mentions a car brand or model (e.g. Tata Nexon, Creta, Swift, "
        f"Honda City) in ANY language (Hindi, Telugu, Tamil, Kannada, Hinglish, etc.), "
        f"classify as 'new_vehicle_detail'. "
        f"Reply with the label only — no explanation, no punctuation."
    )
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        result = get_llm().invoke([
            SystemMessage(content=system),
            HumanMessage(content=msg),
        ])
        label = result.content.strip().lower().split()[0].rstrip(".,!")
        _valid = {l.strip() for l in _INTENT_OPTIONS.split("|")}
        if label in _valid:
            logger.debug("LLM classifier → %s (msg: %r, stage: %s)", label, msg[:40], stage)
            return label
    except Exception as e:
        logger.warning("LLM classifier failed (%s) — defaulting to 'general'", e)
    return "general"


def _parse_vehicle_from_msg(msg: str) -> Optional[dict]:
    """
    Extract vehicle make, model, and year from a free-text message.

    Recognises patterns like:
      "Honda CR-V 2023", "2022 Toyota Camry", "Ford F-150"

    Returns:
        Dict with keys make, model, year (int or None), or None if no match.

    Example:
        _parse_vehicle_from_msg("I just got a Honda CR-V 2023")
        # {"make": "Honda", "model": "CR-V", "year": 2023}
    """
    makes = {
        # North America
        "honda": "Honda", "toyota": "Toyota", "ford": "Ford", "bmw": "BMW",
        "mercedes": "Mercedes-Benz", "audi": "Audi", "kia": "Kia",
        "hyundai": "Hyundai", "nissan": "Nissan", "chevrolet": "Chevrolet",
        "chevy": "Chevrolet", "subaru": "Subaru", "mazda": "Mazda",
        "volkswagen": "Volkswagen", "vw": "Volkswagen", "lexus": "Lexus",
        "jeep": "Jeep", "dodge": "Dodge", "ram": "Ram", "gmc": "GMC",
        "tesla": "Tesla", "acura": "Acura", "infiniti": "Infiniti",
        # India
        "maruti": "Maruti Suzuki", "suzuki": "Maruti Suzuki",
        "tata": "Tata", "mahindra": "Mahindra",
        "mg": "MG", "skoda": "Skoda", "renault": "Renault",
        "citroen": "Citroën", "isuzu": "Isuzu",
    }
    m = msg.lower()
    make = None
    make_key_found = None
    for key, canonical in makes.items():
        if re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", m):
            make = canonical
            make_key_found = key
            break

    # Extract year (4-digit number between 2000–2030)
    year_match = re.search(r"\b(20[0-2]\d)\b", msg)
    year = int(year_match.group(1)) if year_match else None

    if make and make_key_found:
        # Extract model — words after the make name, before the year
        make_pos = m.find(make_key_found)
        after_make = msg[make_pos + len(make_key_found):].strip()
        # Remove year from model string
        model_raw = re.sub(r"\b20[0-2]\d\b", "", after_make).strip(" -,.")
        # Truncate at the first filler word — handles multilingual context like
        # "nexon kosam choosthunanu" → stop at "kosam" → "nexon"
        # "nexon lo velthanu" → stop at "lo" → "nexon"
        _MULTILANG_FILLERS = re.compile(
            r"\b(kosam|kosamu|lo\b|ki\b|tho\b|toh\b|loki|nunchi|velthanu|"
            r"choosthunanu|veltunna|chestunanu|"          # Telugu
            r"mein|se\b|ko\b|ka\b|ke\b|per\b|par\b|leke|lekar|wala|wali|"
            r"hai\b|hun\b|hoon\b|jata|jati|jaunga|jayenge|"  # Hindi
            r"\bon\b|\bin\b|\bwith\b|\bfor\b|\bthe\b|\ban\b|\bmy\b|"
            r"\bgoing\b|\bheading\b|\btravelling\b|\bdriving\b)\b",
            re.IGNORECASE,
        )
        filler_match = _MULTILANG_FILLERS.search(model_raw)
        if filler_match:
            model_raw = model_raw[:filler_match.start()].strip(" -,.")
        model = model_raw.split(",")[0].strip() if model_raw else "Unknown"
        # Validate: if model is empty or looks like a sentence, use model-name regex fallback
        if not model or len(model.split()) > 3:
            model_m = _MODEL_NAMES_RE.search(msg)
            if model_m:
                model = model_m.group(1).title()
        return {"make": make, "model": model or "Unknown", "year": year}

    # ── Model-only fallback: "nexon per jata hun", "my creta", "in seltos" ──
    # Handles multilingual messages where the make brand is omitted.
    model_match = _MODEL_NAMES_RE.search(m)
    if model_match:
        found_model = model_match.group(1).lower()
        inferred_make = _KNOWN_MODEL_MAKES.get(found_model)
        if inferred_make:
            return {
                "make": inferred_make,
                "model": found_model.title(),
                "year": year,
            }

    return None


def _extract_tyre_id_from_msg(msg: str, session: SessionState) -> Optional[str]:
    """Pull a tyre ID from the message, or return the first card from session."""
    match = re.search(r"[A-Z]{2,5}-[A-Z0-9]{2,8}-\d{5}R\d{2}", msg.upper())
    if match:
        return match.group()
    # Fall back to first card stored in session preferences
    first = session.preferences.get("last_cards_ids", [])
    return first[0] if first else None


# ---------------------------------------------------------------------------
# Chat route — full pipeline
# ---------------------------------------------------------------------------

@app.post("/chat")
async def chat(req: ChatRequest):
    session = get_session(req.session_id)
    msg = req.message.strip()

    from app.services.dropoff_tracker import log_stage_transition, detect_drop, apply_recovery_rule
    from app.services.eval_service import collect_feedback
    from app.services.profile_service import get_member, is_returning_buyer

    log_stage_transition(req.session_id, session.stage)
    drop_signal = detect_drop(req.session_id)
    add_to_history(req.session_id, "user", msg)

    intent = _detect_intent(msg, session)

    # ── Arize: annotate span with pipeline metadata ───────────────────────
    # LangChainInstrumentor auto-creates spans for LLM calls.
    # We enrich the parent /chat span with business-level attributes so Arize
    # dashboards can filter by intent, stage, member, language, and ranking intent.
    if _ARIZE_ENABLED:
        try:
            from opentelemetry import trace as _otel_trace
            _span = _otel_trace.get_current_span()
            _span.set_attribute("chat.session_id",      req.session_id)
            _span.set_attribute("chat.member_id",       session.member_id or "")
            _span.set_attribute("chat.stage",           session.stage or "")
            _span.set_attribute("chat.intent",          intent)
            _span.set_attribute("chat.user_path",       session.user_path or "")
            _span.set_attribute("chat.language",        session.preferences.get("language", "English"))
            _span.set_attribute("chat.ranking_intent",  session.preferences.get("ranking_intent", "none"))
        except Exception:
            pass  # Never let tracing break the request

    # Detect and persist language — updates on every message so it adapts.
    # Priority: once a non-English language is detected it sticks for the session.
    detected_lang = _detect_language(msg)
    existing_lang = session.preferences.get("language", "English")
    _non_english = {"Telugu", "Tamil", "Kannada", "Malayalam", "Bengali", "Marathi", "Hindi"}
    if detected_lang in _non_english:
        # Always prefer the most specific regional language detected
        session.preferences["language"] = detected_lang
    elif detected_lang == "casual_en" and existing_lang == "English":
        session.preferences["language"] = "casual_en"
    elif "language" not in session.preferences:
        session.preferences["language"] = detected_lang
    # Keep tone in sync for the hardcoded template fallbacks
    session.preferences["tone"] = _detect_tone(msg)

    # Detect price/quality intent — persists for session so "show me cheap ones"
    # stays active even across subsequent messages (until overridden by a new intent).
    detected_intent = _detect_price_intent(msg)
    if detected_intent != "none":
        session.preferences["ranking_intent"] = detected_intent
        # A specific price intent without an explicit number clears any stale price cap
        # so we don't accidentally filter too aggressively.
        if detected_intent != "budget":
            session.preferences.pop("max_price", None)

    # Extract explicit price ceiling (e.g. "less than $130", "130 se kam")
    # Persists across messages; cleared when user expresses a non-budget intent.
    price_limit = _extract_price_limit(msg)
    if price_limit is not None:
        session.preferences["max_price"] = price_limit
        # A price cap always implies budget intent
        session.preferences["ranking_intent"] = "budget"

    cards = []
    comparison = None
    appointment_slots = []
    booking_card = None
    response_text = ""

    # ── STAGE: login — authenticate, greet, ask same/new vehicle ─────────
    # Pure Python — all data (name, vehicle) is in DB. No LLM needed.
    if intent == "login" or (not session.member_id and re.match(r"^M\d{4,6}$", msg, re.IGNORECASE)):
        member_id = re.match(r"M\d{4,6}", msg, re.IGNORECASE).group().upper()
        user = get_member(member_id)

        if not user:
            response_text = f"I couldn't find a member with ID **{member_id}**. Please double-check and try again."
        else:
            session.member_id = user.member_id
            session.stage = "confirm_vehicle"
            first = user.name.split()[0]
            v = user.vehicle
            response_text = (
                f"Hey {first}, welcome back! 👋 "
                f"Are you shopping for your **{v.year} {v.make} {v.model}** today, "
                f"or do you have a different vehicle?"
            )

    # ── STAGE: same vehicle → build cards — pure Python, no LLM ─────────
    # Name, vehicle, city, season all known. Greeting is deterministic.
    elif intent == "same_vehicle" and session.stage == "confirm_vehicle":
        user = get_member(session.member_id)
        if not user:
            add_to_history(req.session_id, "assistant", "Profile not found — please re-enter your member ID.")
            return JSONResponse({"message": "I couldn't load your profile — please re-enter your member ID.",
                                 "cards": [], "comparison": None, "appointment_slots": [],
                                 "booking_card": None, "quick_replies": [], "recovery": None})
        session.user_path = "A" if is_returning_buyer(session.member_id) else "B"
        session.stage = "browse"

        cards = _build_recommendation_cards(session, user)
        session.preferences["last_cards_ids"] = [c["tyre"]["id"] for c in cards]

        first = user.name.split()[0]
        city = user.location.city if user.location else ""
        season = _detect_season(city)
        v = user.vehicle

        use_case = session.preferences.get("use_case", "")
        ranking_intent = session.preferences.get("ranking_intent", "none")
        max_price_val = session.preferences.get("max_price")
        price_relaxed = session.preferences.pop("price_filter_relaxed", False)
        _intent_labels = {
            "budget": "cheapest options", "premium": "top-quality options",
            "performance": "best-performing options", "safety": "safest options",
            "longevity": "longest-lasting options", "value": "best value-for-money options",
        }
        if price_relaxed and max_price_val:
            intent_note = (
                f"The member wanted tyres under ${max_price_val:.0f} but none were available. "
                f"Say sorry we couldn't find any under ${max_price_val:.0f}, here are the closest options."
            )
        elif max_price_val:
            intent_note = f"The member set a price limit of ${max_price_val:.0f} — mention that all shown options are within their budget."
        elif ranking_intent != "none":
            intent_note = f"The member asked for {_intent_labels.get(ranking_intent, ranking_intent)} — acknowledge that briefly (e.g. 'Sorted by budget!' / 'Here are the safest picks!')."
        else:
            intent_note = "Include their previous tyre choice plus two alternatives." if session.user_path == "A" else "Show top pick, runner-up, and a budget option."
        system = (
            f"{_PERSONA} "
            f"You've just pulled up tyre recommendations for the member. "
            f"Write ONE short sentence (max 20 words) handing over the cards. "
            f"Include their name ({first}), their vehicle ({v.year} {v.make} {v.model}), "
            f"and{' their ' + use_case + ' and' if use_case else ''} the season ({season}) in {city}. "
            f"{intent_note} No emoji. Do not list the tyres — the UI shows the cards."
        )
        ctx = (
            f"Member: {first} | Vehicle: {v.year} {v.make} {v.model} | "
            f"City: {city} | Season: {season} | Use case: {use_case or 'everyday'} | "
            f"Intent: {ranking_intent} | "
            f"Path: {'A (returning)' if session.user_path == 'A' else 'B (new buyer)'} | "
            f"Cards ready: {len(cards)}"
        )
        response_text = _llm_respond(req.session_id, system, ctx)

        collect_feedback(req.session_id, "orchestrator", "implicit", "cards_shown",
                         session.preferences["last_cards_ids"][0] if session.preferences.get("last_cards_ids") else None)

    # ── STAGE: context clue before same/new answer ────────────────────────
    # User gave trip/use-case context before answering same/new vehicle.
    # Capture terrain, store use-case label, re-ask vehicle question naturally.
    elif intent == "context_then_vehicle" and session.stage == "confirm_vehicle":
        terrain_hint = _detect_terrain_from_msg(msg)
        if terrain_hint:
            session.preferences["override_terrain"] = terrain_hint

        # Detect correction phrases so we can acknowledge them naturally
        is_correction = bool(re.search(r"my bad|actually|sorry|i meant|wait|oops|correction", msg.lower()))

        m_lower = msg.lower()

        # Check for a known destination first — gives the most specific response
        destination_match = next(
            (v for k, v in _DESTINATION_LABELS.items() if k in m_lower), None
        )

        if destination_match:
            from datetime import datetime as _dt
            dest_name, dest_terrain, dest_note = destination_match
            use_case = f"trip to {dest_name}"
            # Add season-aware note based on destination + current month
            month = _dt.now().month
            _wet_destinations = {
                "assam", "kaziranga", "meghalaya", "cherrapunji", "shillong",
                "sikkim", "gangtok", "arunachal", "manipur", "nagaland",
                "mizoram", "coorg", "munnar", "ooty", "goa", "lonavala",
            }
            _snow_destinations = {
                "srinagar", "kashmir", "gulmarg", "sonamarg", "pahalgam",
                "kargil", "ladakh", "leh", "spiti", "manali", "rohtang",
            }
            season_note = ""
            dest_lower = dest_name.lower()
            if any(d in dest_lower for d in _snow_destinations):
                if month in (12, 1, 2, 3):
                    season_note = " Snow is still possible this time of year — all-terrain grip is critical."
                elif month in (4, 5):
                    season_note = " Snow is melting but roads are still slippery — grip matters."
                else:
                    season_note = " Roads are clearer now but can still be rough and unpredictable."
            elif any(d in dest_lower for d in _wet_destinations):
                if month in (4, 5):
                    season_note = " Pre-monsoon already — roads are getting wet."
                elif month in (6, 7, 8, 9):
                    season_note = " It's monsoon season there right now — wet grip is critical."
                else:
                    season_note = " That region gets heavy rain — wet grip is important."
            # Build a personalised opener using the member's vehicle + habits + tier.
            # LLM gets specific context so it doesn't sound generic.
            _user = get_member(session.member_id) if session.member_id else None
            _vehicle_str = (
                f"{_user.vehicle.year} {_user.vehicle.make} {_user.vehicle.model}"
                if _user and _user.vehicle else "their car"
            )
            _habits = ", ".join(_user.driving_habits[:2]) if _user and _user.driving_habits else ""
            _tier = _user.membership_tier if _user else ""
            correction_prefix = "No worries! " if is_correction else ""
            _opener_system = (
                f"{_PERSONA} "
                f"Member just told you they're going to {dest_name}. "
                f"React in ONE short sentence (max 15 words). "
                f"- Name the destination\n"
                f"- Give one specific, practical tyre insight for their {_vehicle_str} "
                f"on this route: {dest_note}{season_note}\n"
                f"{'- Start with: No worries! ' if is_correction else ''}"
                f"- IMPORTANT: reply in the SAME language the member used in their message\n"
                f"- Do NOT ask about the vehicle yet — that question comes right after\n"
                f"- No emoji"
            )
            _opener_ctx = (
                f"Member's message: '{msg}' | "
                f"Destination: {dest_name} | Vehicle: {_vehicle_str} | "
                f"Driving habits: {_habits} | Tier: {_tier} | "
                f"Terrain: {dest_terrain} | Season note: {season_note or 'none'}"
            )
            opener = _llm_respond(req.session_id, _opener_system, _opener_ctx) or (
                f"{correction_prefix}{dest_name}! {dest_note}.{season_note}"
            )
        elif any(k in m_lower for k in ["off-road", "off road", "mud", "trail", "4x4"]):
            use_case = "off-road adventure"
            opener = ("No worries! " if is_correction else "") + "Off-road — let's get you the right tyres for that."
        elif any(k in m_lower for k in ["monsoon", "rain"]):
            use_case = "the monsoon season"
            opener = ("No worries! " if is_correction else "") + "Monsoon driving — wet grip is going to matter."
        elif any(k in m_lower for k in ["winter", "snow", "ice"]):
            use_case = "winter driving"
            opener = ("No worries! " if is_correction else "") + "Winter roads — let's make sure you're sorted."
        elif any(k in m_lower for k in ["city", "urban", "daily", "commute"]):
            use_case = "city driving"
            opener = ("No worries! " if is_correction else "") + "City driving — got it."
        else:
            use_case = "road trip"
            # Extract a potential destination name from the message for LLM personalisation
            _stopwords = {
                # English travel/filler
                "i", "am", "going", "on", "a", "to", "the", "for", "trip",
                "drive", "travel", "want", "need", "tyres", "tires", "my",
                "road", "long", "planning", "we", "our", "is", "in", "and",
                "bad", "sorry", "actually", "oops", "correction", "mistake",
                # Hindi travel words — these are NOT destinations
                "ja", "jaa", "raha", "rahi", "rahe", "hu", "hun", "hoon",
                "hai", "ke", "ki", "ka", "liye", "se", "pe", "par", "wala",
                "wali", "leke", "lekar", "jaana", "nikal", "chal", "safar",
                "trip", "yatra",
                # Telugu travel words
                "velthunnanu", "veltunna", "velthanu", "veltanu", "potuunna",
                "nakku", "kosam", "ki", "nunchi",
                # Tamil travel words
                "ponren", "poven", "pogiren", "porom",
            }
            words = [w.strip(".,!?") for w in msg.split()]
            dest_words = [w for w in words if w.lower() not in _stopwords and len(w) > 2]
            extracted_dest = " ".join(dest_words[:3]).strip() if dest_words else ""

            if extracted_dest:
                from datetime import datetime as _dt
                month_name = _dt.now().strftime("%B")
                _dest_system = (
                    "You are a tyre advisor. Reply with exactly 1 sentence, max 12 words. "
                    "Name the destination and give one specific, practical driving or terrain insight for it this month. "
                    "No generic phrases like 'Road trip — nice!'. Be specific to the place."
                )
                _dest_ctx = f"Destination: {extracted_dest} | Month: {month_name}"
                try:
                    opener = _llm_respond(req.session_id, _dest_system, _dest_ctx)
                    if not opener:
                        opener = f"{extracted_dest.title()} — sounds like a great trip!"
                except Exception:
                    opener = f"{extracted_dest.title()} — sounds like a great trip!"
            else:
                opener = "Road trip — nice!"
        session.preferences["use_case"] = use_case

        user = get_member(session.member_id)
        first = user.name.split()[0] if user else "there"
        v = user.vehicle if user else None
        lang = session.preferences.get("language", "English")

        _has_template = lang in _VEHICLE_Q or lang in ("English", "casual_en", "Hindi")
        if _has_template:
            # Use hardcoded template for English, casual_en, Hindi
            _tone = session.preferences.get("tone", "formal")
            tmpl_key = lang if lang in _VEHICLE_Q else ("casual_en" if _tone == "casual" else "English")
            if v:
                tmpl = _VEHICLE_Q.get(tmpl_key, _VEHICLE_Q["English"])
                response_text = tmpl.format(opener=opener, year=v.year, make=v.make, model=v.model)
            else:
                tmpl = _VEHICLE_Q_NO_CAR.get(tmpl_key, _VEHICLE_Q_NO_CAR["English"])
                response_text = tmpl.format(opener=opener)
        else:
            # Non-English language (Telugu, Tamil, etc.) — use LLM so it's fluent
            vehicle_str = f"{v.year} {v.make} {v.model}" if v else None
            system = (
                f"{_PERSONA} "
                f"Start with this opener verbatim: '{opener}'. "
                f"Then in one short sentence ask if they are taking their "
                f"{vehicle_str or 'their current car'} or a different vehicle. "
                f"Keep the vehicle name ({vehicle_str or 'car make/model'}) in English."
            )
            ctx = f"Opener: {opener} | Vehicle: {vehicle_str or 'unknown'}"
            response_text = _llm_respond(req.session_id, system, ctx)

    # ── STAGE: new vehicle → ask for car make/model — pure Python ─────────
    # Season auto-detected. Terrain inferred from habits.
    # Car name → size via _infer_size_from_text(). Tyre size also accepted directly.
    elif intent == "new_vehicle" and session.stage == "confirm_vehicle":
        session.stage = "collect_vehicle"
        # Use LLM so the response mirrors the user's tone and references their trip context
        use_case = session.preferences.get("use_case", "")
        tone = session.preferences.get("tone", "formal")
        system = (
            f"{_PERSONA} "
            f"The member just said they'll be using a different car{' for their ' + use_case if use_case else ''}. "
            f"Ask what car it is — just make and model, keep it to one short sentence. "
            f"Sound like a friend, not a form. No bullet points, no lists."
        )
        ctx = f"Member tone: {tone} | Trip context: {use_case or 'general use'}"
        response_text = _llm_respond(req.session_id, system, ctx)

    # ── STAGE: collect tyre size or car make → build Path B cards ─────────
    # Primary: tyre size (e.g. 235/65R17) — used directly for search
    # Fallback: car make/model → infer size from _VEHICLE_SIZE_MAP
    # Fires from confirm_vehicle, collect_vehicle, browse, or greet — any pre-cart stage.
    elif intent == "new_vehicle_detail" and session.stage not in ("cart", "pay", "book", "complete"):
        session.stage = "collect_vehicle"  # normalise so rest of handler works
        # Build language instruction once — used in every LLM call in this handler
        _lang = session.preferences.get("language", "English")
        _lang_instr = _LANG_INSTRUCTION.get(_lang, "")
        user = get_member(session.member_id)

        # Safety guard: if the message looks like a same-vehicle confirmation in any
        # language (regional phrases slipped past the intent router), redirect cleanly.
        _same_guard = re.search(
            r"\bsame\b|\bavunu\b|\bunna\s+(vehicle|car|gaadi)\b|\btesuku\b|"
            r"^yes\b|^haan\b|^aama\b|^houdu\b|\bwahi\b",
            msg.lower()
        )
        if _same_guard:
            # User meant "same vehicle" — regional phrase slipped past intent router.
            # Redirect to same-vehicle flow with profile vehicle.
            session.user_path = "A" if is_returning_buyer(session.member_id) else "B"
            session.stage = "browse"
            cards = _build_recommendation_cards(session, user)
            session.preferences["last_cards_ids"] = [c["tyre"]["id"] for c in cards]
            first = user.name.split()[0] if user else "there"
            v = user.vehicle
            city = user.location.city if user and user.location else ""
            season = _detect_season(city)
            system = (
                f"{_PERSONA} Member confirmed same vehicle. Cards ready. "
                f"One sentence handing over the recommendations for their "
                f"{v.year} {v.make} {v.model}. No emoji."
            )
            ctx = f"Member: {first} | Vehicle: {v.year} {v.make} {v.model} | Season: {season}"
            response_text = _llm_respond(req.session_id, system, ctx)
            collect_feedback(req.session_id, "orchestrator", "implicit", "cards_shown",
                             session.preferences["last_cards_ids"][0] if cards else None)
        else:
            # 1. Explicit tyre size in message (e.g. "235/65R17")
            size_match = re.search(r"\d{3}/\d{2}R\d{2}", msg, re.IGNORECASE)
            tyre_size = size_match.group(0).upper() if size_match else None

            # Capture terrain if user mentioned it ("mostly off-road", "highway driving")
            terrain_from_msg = _detect_terrain_from_msg(msg)
            if terrain_from_msg:
                session.preferences["override_terrain"] = terrain_from_msg

            # 2. Car name → look up in expanded map + class fallback
            # Works with partial names: "CR-V", "Rogue", "my Elantra", "Kia SUV"
            if not tyre_size:
                tyre_size = _infer_size_from_text(msg)

            if not tyre_size:
                # Can't determine size — ask for more detail or give honest no-data message.
                parsed = _parse_vehicle_from_msg(msg)
                partial_make = session.preferences.get("partial_make")

                if partial_make:
                    # Already asked for model once — still no match → honest message
                    from app.services.stock_service import get_available_sizes
                    available = get_available_sizes()
                    system = (
                        f"{_PERSONA} {_lang_instr} "
                        f"We don't have tyre data for this {partial_make} model in our catalogue. "
                        f"Tell the member honestly in 1-2 sentences. "
                        f"Suggest they type the tyre size directly (e.g. 205/55R16 — "
                        f"it's on the sidewall of their current tyre). "
                        f"Sizes we carry: {', '.join(available[:8])}. "
                        f"Keep it warm and helpful, not a dead end."
                    )
                    ctx = f"Make tried: {partial_make} | Raw message: {msg}"
                    response_text = _llm_respond(req.session_id, system, ctx)
                    session.preferences.pop("partial_make", None)
                elif parsed and parsed.get("make"):
                    make = parsed["make"]
                    session.preferences["partial_make"] = make
                    known_models = _MAKE_MODELS.get(make.lower(), [])
                    model_hint = (
                        f"Mention these models by name as examples: {', '.join(known_models[:4])}."
                        if known_models else
                        "Ask for the model name — give 1-2 plausible example model names."
                    )
                    session.preferences["suggested_models"] = known_models[:6]
                    system = (
                        f"{_PERSONA} {_lang_instr} "
                        f"Member mentioned {make} but didn't give the model. "
                        f"Ask which {make} model in one short friendly sentence. "
                        f"{model_hint}"
                    )
                    ctx = f"Make: {make}"
                    response_text = _llm_respond(req.session_id, system, ctx)
                else:
                    system = (
                        f"{_PERSONA} {_lang_instr} "
                        f"Can't determine what vehicle this is from the message. "
                        f"Ask for the car make and model in one short, friendly sentence. "
                        f"Or suggest they type the tyre size directly (it's on the sidewall, e.g. 205/55R16)."
                    )
                    ctx = f"Raw message: {msg}"
                    response_text = _llm_respond(req.session_id, system, ctx)
            else:
                # Store the size and the car label the user mentioned
                session.preferences["override_tyre_size"] = tyre_size
                # Keep a display-friendly car name: prefer parsed make+model
                if not size_match:  # came from car name, not a typed tyre size
                    parsed = _parse_vehicle_from_msg(msg)
                    if parsed and parsed.get("model") and parsed["model"] != "Unknown":
                        car_label = f"{parsed['make']} {parsed['model']}"
                    else:
                        # Last resort: extract just the model name token from the message
                        model_m = _MODEL_NAMES_RE.search(msg)
                        car_label = model_m.group(1).title() if model_m else tyre_size
                    session.preferences["car_label"] = car_label
                session.user_path = "B"
                session.stage = "browse"

                # Build cards — season auto-detected, terrain from message > habits
                from app.services.stock_service import search_tyres as svc_search
                city = user.location.city if user and user.location else ""
                season = _detect_season(city)
                terrain = (
                    session.preferences.get("override_terrain")
                    or (_infer_terrain(user.driving_habits) if user else "highway")
                )
                _max_price_nv = session.preferences.get("max_price")
                results = svc_search(size=tyre_size, season=season, terrain=terrain, max_price=_max_price_nv, in_stock_only=True)
                if len(results) < 3:
                    # Broaden: relax season constraint, keep terrain
                    _extra = svc_search(size=tyre_size, terrain=terrain, max_price=_max_price_nv, in_stock_only=True)
                    _seen = {t.id for t in results}
                    results += [t for t in _extra if t.id not in _seen]
                if len(results) < 3:
                    # Broaden further: drop both season and terrain — size match only
                    _extra = svc_search(size=tyre_size, max_price=_max_price_nv, in_stock_only=True)
                    _seen = {t.id for t in results}
                    results += [t for t in _extra if t.id not in _seen]
                # If price filter leaves nothing, relax it gracefully
                if not results and _max_price_nv:
                    results = svc_search(size=tyre_size, season=season, terrain=terrain, in_stock_only=True)
                    session.preferences["price_filter_relaxed"] = True

                if not results:
                    from app.services.stock_service import get_available_sizes
                    available = get_available_sizes()
                    car_label = session.preferences.get("car_label", "") or tyre_size
                    system = (
                        f"{_PERSONA} {_lang_instr} "
                        f"We don't carry {tyre_size} tyres in our catalogue right now. "
                        f"Tell the member honestly in 2 short sentences. "
                        f"Mention we currently stock these sizes: {', '.join(available[:8])}. "
                        f"Suggest they check back or contact the tyre centre directly. "
                        f"Keep it warm — not a dead end, just honest."
                    )
                    ctx = (
                        f"Member vehicle/size: {car_label} ({tyre_size}) | "
                        f"Available sizes: {', '.join(available[:8])}"
                    )
                    response_text = _llm_respond(req.session_id, system, ctx)
                    session.stage = "confirm_vehicle"
                    session.preferences.pop("override_tyre_size", None)
                    add_to_history(req.session_id, "assistant", response_text)
                    return JSONResponse({"message": response_text, "cards": [], "comparison": None,
                                         "appointment_slots": [], "booking_card": None,
                                         "quick_replies": [], "recovery": None})

                # Brand-diverse top 3
                locs_path = Path(__file__).parent / "data" / "locations.json"
                locs = json.loads(locs_path.read_text(encoding="utf-8")) if locs_path.exists() else []
                from app.tools.content_tools import generate_personalised_msg
                from app.tools.recommendation_tools import generate_punch_line
                from app.services.stock_service import get_stock_badge

                seen_brands: set[str] = set()
                diverse: list = []
                for t in sorted(results, key=lambda x: x.rating, reverse=True):
                    if t.brand not in seen_brands or len(diverse) < 3:
                        diverse.append(t)
                        seen_brands.add(t.brand)
                    if len(diverse) == 3:
                        break

                member_ctx = json.dumps({
                    "driving_habits": user.driving_habits if user else [],
                    "location": user.location.model_dump() if user else {},
                    "membership_tier": user.membership_tier if user else "standard",
                    "vehicle": user.vehicle.model_dump() if user else {},
                })

                slot_defs = []
                if diverse:
                    slot_defs.append((diverse[0], "Top Pick", "top_pick", True))
                if len(diverse) > 1:
                    slot_defs.append((diverse[1], "Runner-up", "runner_up", False))
                _used_ids = {s[0].id for s in slot_defs}
                _budget_pool = sorted([t for t in results if t.id not in _used_ids], key=lambda t: t.member_price)
                if _budget_pool:
                    slot_defs.append((_budget_pool[0], "Budget Alt", "budget_alt", False))

                cards = []
                for tyre, tag, slot_type, is_top in slot_defs:
                    msg_text = generate_personalised_msg.invoke({
                        "tyre_json": json.dumps(tyre.model_dump()),
                        "member_context_json": member_ctx,
                        "slot_type": slot_type,
                    })
                    punch = generate_punch_line.invoke({"tyre_json": json.dumps(tyre.model_dump())}) if is_top else None
                    cards.append({
                        "tyre": tyre.model_dump(),
                        "slot_tag": tag,
                        "personalised_msg": msg_text,
                        "stock_badge": get_stock_badge(tyre, locs),
                        "punch_line": punch,
                    })

                session.preferences["last_cards_ids"] = [c["tyre"]["id"] for c in cards]
                first = user.name.split()[0] if user else "there"
                car_label = session.preferences.get("car_label", "")
                use_case = session.preferences.get("use_case", "")
                _ranking_intent = session.preferences.get("ranking_intent", "none")
                _max_price_val  = session.preferences.get("max_price")
                _price_relaxed  = session.preferences.pop("price_filter_relaxed", False)
                _intent_labels = {
                    "budget": "cheapest options", "premium": "top-quality options",
                    "performance": "best-performing options", "safety": "safest options",
                    "longevity": "longest-lasting options", "value": "best value-for-money options",
                }
                if _price_relaxed and _max_price_val:
                    _intent_note = f"No tyres found under ${_max_price_val:.0f} — say sorry, here are the closest options available."
                elif _max_price_val:
                    _intent_note = f"Member set a price limit of ${_max_price_val:.0f} — confirm all shown options are within budget."
                elif _ranking_intent != "none":
                    _intent_note = f"Member asked for {_intent_labels.get(_ranking_intent, _ranking_intent)} — acknowledge briefly."
                else:
                    _intent_note = "Mention different price points and brands."
                _card_system = (
                    f"{_PERSONA} {_lang_instr} "
                    f"You've just pulled up tyre recommendations. "
                    f"Write ONE short sentence (max 20 words) handing over the cards. "
                    f"Include their name ({first}), their car ({car_label or tyre_size}), "
                    f"and{' their ' + use_case + ' and' if use_case else ''} season ({season}). "
                    f"{_intent_note} No emoji."
                )
                _card_ctx = (
                    f"Member: {first} | Car: {car_label or tyre_size} | "
                    f"Size: {tyre_size} | Season: {season} | City: {city} | "
                    f"Intent: {_ranking_intent} | Use case: {use_case or 'everyday'} | Cards: {len(cards)}"
                )
                response_text = _llm_respond(req.session_id, _card_system, _card_ctx)
                collect_feedback(req.session_id, "orchestrator", "implicit", "cards_shown",
                                 session.preferences["last_cards_ids"][0] if session.preferences.get("last_cards_ids") else None)

    # ── STAGE: select tyre → move to detail ──────────────────────────────
    elif intent == "select_tyre" and session.member_id:
        tyre_id = _extract_tyre_id_from_msg(msg, session)
        user = get_member(session.member_id)

        if tyre_id:
            from app.services.stock_service import get_tyre_by_id
            tyre = get_tyre_by_id(tyre_id)
            session.preferences["selected_tyre_id"] = tyre_id
            session.stage = "detail"

            system = (
                f"{_PERSONA} "
                "2 sentences. The member just chose a tyre — react genuinely, like a friend saying "
                "'great pick!' Reference why it suits them (their driving style or vehicle). "
                "End by asking if they want to add it to their cart."
            )
            ctx = (
                f"Member: {user.name if user else 'Member'} | "
                f"Selected: {tyre.brand} {tyre.model} {tyre.size} | "
                f"Member price: ${tyre.member_price}/tyre | In stock: {tyre.stock.qty > 0} | "
                f"Vehicle: {user.vehicle.year} {user.vehicle.make} {user.vehicle.model if user else ''} | "
                f"Driving habits: {', '.join(user.driving_habits) if user else ''}"
            )
            response_text = _llm_respond(req.session_id, system, ctx)
        else:
            response_text = "Which tyre would you like to select? Please click **Select this tyre** on one of the cards."

    # ── STAGE: compare ────────────────────────────────────────────────────
    elif intent == "compare" and session.member_id:
        card_ids = session.preferences.get("last_cards_ids", [])
        if len(card_ids) >= 2:
            from app.tools.compare_tools import generate_comparison_card
            user = get_member(session.member_id)
            member_ctx = json.dumps({
                "driving_habits": user.driving_habits if user else [],
                "membership_tier": user.membership_tier if user else "standard",
                "vehicle": user.vehicle.model_dump() if user else {},
            })
            cmp_json = generate_comparison_card.invoke({
                "tyre_ids_json": json.dumps(card_ids[:3]),
                "member_context_json": member_ctx,
            })
            comparison = json.loads(cmp_json)
            response_text = "Here's the side-by-side comparison. The cost per 1,000 km helps you see the true value of each tyre over its lifetime."
        else:
            response_text = "I need at least 2 tyre recommendations to compare. Please start with your member ID first."

    # ── STAGE: add to cart ────────────────────────────────────────────────
    # Reached either via "Add to Cart" button (direct, skips detail step)
    # or via "confirm" after the detail/select step.
    elif intent == "add_cart" and session.member_id:
        tyre_id = (session.preferences.get("selected_tyre_id")
                   or _extract_tyre_id_from_msg(msg, session))
        user = get_member(session.member_id)

        if tyre_id and user:
            # Store tyre ID even when coming directly from "Add to Cart" button
            session.preferences["selected_tyre_id"] = tyre_id

            from app.services.cart_service import add_to_cart
            result = add_to_cart(session.member_id, tyre_id, quantity=4)
            if "error" in result:
                response_text = f"There was an issue adding to cart: {result['error']}"
            else:
                session.cart_id = result["cart_id"]
                session.stage = "cart"
                from app.services.stock_service import get_tyre_by_id, get_stock_badge
                from app.tools.appointment_tools import get_nearby_locations
                tyre = get_tyre_by_id(tyre_id)
                system = (
                    f"{_PERSONA} "
                    "1 sentence, max 15 words. Cart's in — say it like a friend texting, not a customer service rep. "
                    "Drop one number (savings or cashback). No exclamation overload. No 'fantastic' or 'perfect match'."
                )
                ctx = (
                    f"Member: {user.name} | Membership: {user.membership_tier} | "
                    f"Tyre: {tyre.brand} {tyre.model if tyre else ''} {tyre.size if tyre else ''} | "
                    f"Qty: 4 tyres | Subtotal: ${result['subtotal']:.2f} | "
                    f"Member savings: ${result['member_savings']:.2f} | "
                    f"Cashback estimate: ${result['cashback_estimate']:.2f} | Cart held 15 mins"
                )
                response_text = _llm_respond(req.session_id, system, ctx)

                # Build a single cart card so the tyre info is visible below the confirmation
                if tyre:
                    try:
                        _locs = json.loads(get_nearby_locations.invoke({"city": user.location.city}))
                    except Exception:
                        _locs = []
                    _subtotal_fmt = f"${result['subtotal']:.2f}"
                    _savings_fmt  = f"${result['member_savings']:.2f}"
                    cards = [{
                        "tyre": tyre.model_dump(),
                        "slot_tag": "In Cart",
                        "personalised_msg": (
                            f"4 tyres · {_subtotal_fmt} · saving {_savings_fmt}"
                        ),
                        "stock_badge": get_stock_badge(tyre, _locs),
                        "punch_line": None,
                    }]
        else:
            response_text = "Please tap **Add to Cart** on one of the tyre cards above."

    # ── STAGE: confirm payment ────────────────────────────────────────────
    elif intent == "confirm_pay" and session.cart_id:
        from app.services.payment_service import process_payment
        result = process_payment(session.member_id, session.cart_id)

        if "error" in result:
            response_text = f"Payment couldn't be processed: {result['error']}. Your cart is saved — please try again."
        else:
            session.order_id = result["order_id"]
            session.stage = "pay"

            # Build appointment slots — Python only
            from app.services.profile_service import get_member
            user = get_member(session.member_id)
            if user:
                from app.tools.appointment_tools import get_nearby_locations
                locs = json.loads(get_nearby_locations.invoke({"city": user.location.city}))
                best_location = locs[0] if locs else None
                if best_location:
                    # Use member's purchase history + driving habits to rank slots
                    appointment_slots = _suggest_smart_slots(user, best_location["id"], n=3)

            system = (
                f"{_PERSONA} "
                "1 sentence, max 15 words. Order confirmed — say it like a friend, not a receipt. "
                "Mention the order ID and cashback only. No emojis overload. No 'great tyres' or 'money back in your pocket'."
            )
            ctx = (
                f"Order ID: {result['order_id']} | "
                f"Total: ${result['total']:.2f} | "
                f"Cashback earned: ${result['cashback_earned']:.2f} | "
                f"Payment: {result['payment_method']}"
            )
            response_text = _llm_respond(req.session_id, system, ctx)
            collect_feedback(req.session_id, "orchestrator", "implicit", "payment_complete", None)

    # ── STAGE: book appointment slot ──────────────────────────────────────
    elif intent == "book_slot" and session.order_id and session.stage != "complete":
        from app.services.profile_service import get_member
        user = get_member(session.member_id)

        # Extract date/time/location from message or use suggestion
        slot_match = re.search(r"(\d{4}-\d{2}-\d{2})[^\d]+(\d{2}:\d{2})[^\w]*(W\d+)?", msg)
        if slot_match and user:
            from app.tools.appointment_tools import (
                book_appointment, link_order_to_booking,
                create_calendar_event, get_nearby_locations
            )
            date_str, time_str = slot_match.group(1), slot_match.group(2)
            locs = json.loads(get_nearby_locations.invoke({"city": user.location.city}))
            loc = locs[0] if locs else {"id": "W001", "name": "Costco Tyre Centre", "address": ""}
            tyre_id = session.preferences.get("selected_tyre_id", "")
            slot_id = f"{loc['id']}-{date_str}-{time_str.replace(':','')}"

            booking = json.loads(book_appointment.invoke({
                "member_id": session.member_id,
                "order_id": session.order_id,
                "location_id": loc["id"],
                "slot_id": slot_id,
                "date_str": date_str,
                "time_str": time_str,
                "tyre_id": tyre_id,
            }))

            if "error" in booking:
                response_text = f"That slot was just taken. {booking['error']}"
            else:
                session.booking_id = booking["booking_id"]
                session.stage = "complete"
                link_order_to_booking.invoke({
                    "order_id": session.order_id,
                    "booking_id": booking["booking_id"],
                })
                from app.services.stock_service import get_tyre_by_id
                tyre = get_tyre_by_id(tyre_id)
                create_calendar_event.invoke({
                    "booking_id": booking["booking_id"],
                    "member_name": user.name,
                    "location_name": loc.get("name", ""),
                    "location_address": loc.get("address", ""),
                    "date_str": date_str,
                    "time_str": time_str,
                    "tyre_model": f"{tyre.brand} {tyre.model}" if tyre else "Tyre",
                })
                # Post-purchase pipeline — wrapped so a failure never crashes the response
                try:
                    from app.services.post_purchase_service import (
                        schedule_reminders, send_survey, schedule_rotation_reminder
                    )
                    schedule_reminders(session.member_id, date_str, loc.get("name",""), tyre.model if tyre else "")
                    send_survey(session.member_id, session.order_id)
                    schedule_rotation_reminder(session.member_id, tyre_id, 0)
                except Exception as _e:
                    logger.warning(f"Post-purchase service error (non-fatal): {_e}")

                # Booking confirmed — pure Python card, zero LLM call
                from datetime import datetime as _dt
                try:
                    _d = _dt.strptime(date_str, "%Y-%m-%d")
                    readable_date = _d.strftime("%A, %B ") + str(_d.day)  # cross-platform, no leading zero
                except ValueError:
                    readable_date = date_str
                # Strip "Costco Tyre Centre — " prefix from location name
                _raw_loc = loc.get("name", "Costco Tyre Centre")
                _parts = re.split(r"Costco\s+Tyre\s+Centre\s*[-\u2013\u2014]+\s*", _raw_loc, maxsplit=1)
                _short_loc = _parts[-1].strip() if len(_parts) > 1 else _raw_loc

                booking_card = {
                    "booking_id":  booking["booking_id"],
                    "order_id":    session.order_id,
                    "date":        readable_date,
                    "time":        time_str,
                    "location":    _short_loc,
                    "address":     loc.get("address", ""),
                    "tyre":        f"{tyre.brand} {tyre.model} x4" if tyre else "Tyres",
                    "bring":       ["Vehicle registration", "Costco membership card"],
                    "calendar":    True,
                }

                # WhatsApp booking confirmation via Twilio — non-fatal if not configured
                try:
                    from app.services.whatsapp_service import send_booking_confirmation
                    _wa_result = send_booking_confirmation(
                        member_name=user.name,
                        booking_id=booking["booking_id"],
                        order_id=session.order_id,
                        date=readable_date,
                        time=time_str,
                        location=_short_loc,
                        address=loc.get("address", ""),
                        tyre=f"{tyre.brand} {tyre.model} x4" if tyre else "Tyres x4",
                    )
                    if _wa_result["sent"]:
                        logger.info("WhatsApp confirmation sent — SID: %s", _wa_result["sid"])
                except Exception as _e:
                    logger.warning(f"WhatsApp notification error (non-fatal): {_e}")

                first = user.name.split()[0]
                _book_system = (
                    f"{_PERSONA} Booking is confirmed. "
                    f"Write ONE warm sentence (max 15 words) confirming the appointment. "
                    f"Include their name ({first}) and the date ({readable_date}). "
                    f"Mention a reminder will be sent. No emoji."
                )
                _book_ctx = f"Member: {first} | Date: {readable_date} | Booking confirmed"
                response_text = _llm_respond(req.session_id, _book_system, _book_ctx)
                collect_feedback(req.session_id, "appointment", "implicit", "booking_complete", None)
        else:
            # Show smart-ranked slots based on member's schedule preference
            from app.services.profile_service import get_member
            user = get_member(session.member_id) if session.member_id else None
            if user:
                from app.tools.appointment_tools import get_nearby_locations
                locs = json.loads(get_nearby_locations.invoke({"city": user.location.city}))
                loc = locs[0] if locs else None
                if loc:
                    appointment_slots = _suggest_smart_slots(user, loc["id"], n=6)
            first = user.name.split()[0] if user else "there"
            _slots_system = (
                f"{_PERSONA} Appointment slots are ready. "
                f"Write ONE short sentence (max 15 words) presenting them. "
                f"Mention they're picked based on the member's schedule. No emoji."
            )
            response_text = _llm_respond(req.session_id, _slots_system, f"Member: {first} | Slots ready")

    # ── STAGE: complete — session finished, graceful replies only ─────────
    elif session.stage == "complete":
        user = get_member(session.member_id) if session.member_id else None
        first = user.name.split()[0] if user else "there"
        _done_system = (
            f"{_PERSONA} Session is complete, booking confirmed. "
            f"Write ONE warm closing sentence (max 15 words). "
            f"Include their name ({first}). Suggest starting a new session if needed. No emoji."
        )
        response_text = _llm_respond(req.session_id, _done_system, f"Member: {first} | Session complete")

    # ── STAGE: cancel / go back ───────────────────────────────────────────
    elif intent == "cancel" and session.member_id:
        prev_stage = "browse"
        session.stage = prev_stage
        user = get_member(session.member_id)
        cards = _build_recommendation_cards(session, user) if user else []
        if cards:
            session.preferences["last_cards_ids"] = [c["tyre"]["id"] for c in cards]
        response_text = "No problem — I've brought you back to your recommendations. Take your time."

    # ── STAGE: general conversation ───────────────────────────────────────
    else:
        user = get_member(session.member_id) if session.member_id else None
        system = (
            f"{_PERSONA} "
            "2–3 sentences. Answer like a knowledgeable friend — direct and helpful. "
            "Never invent prices, specs, or tyre names. "
            "If unsure, say 'I'd double-check that at costco.com or ask one of our tyre specialists in-store.'"
        )
        vehicle_str = f"{user.vehicle.year} {user.vehicle.make} {user.vehicle.model}" if user else "unknown"
        ctx = (
            f"Member: {user.name if user else 'unknown'} | "
            f"Vehicle: {vehicle_str} | "
            f"Stage: {session.stage} | Message: {msg}"
        )
        response_text = _llm_respond(req.session_id, system, ctx)

    # ── Quick-reply chips — stage-specific shortcut buttons for the UI ───
    # Each chip has {label, message}. The UI renders them as tappable buttons
    # that call sendMessage(chip.message). Text input always works too.
    quick_replies: list[dict] = []

    if session.stage == "confirm_vehicle" and session.member_id:
        u = get_member(session.member_id)
        if u:
            v = u.vehicle
            quick_replies = [
                {"label": f"Yes — {v.year} {v.make} {v.model}", "message": f"Yes, same car — {v.year} {v.make} {v.model}"},
                {"label": "No, I have a different vehicle", "message": "No, I have a different vehicle"},
            ]

    elif session.stage == "collect_vehicle":
        partial_make = session.preferences.get("partial_make", "").lower()
        if partial_make:
            # Prefer the exact list the LLM mentioned (stored when ask was generated)
            # so chips always match what the bot just said. Fall back to _MAKE_MODELS.
            models = (
                session.preferences.get("suggested_models")
                or _MAKE_MODELS.get(partial_make, [])
            )
            quick_replies = [{"label": m, "message": m} for m in models[:6]]
            # If we have no models at all for this make, still show vehicle-type chips
            if not quick_replies:
                quick_replies = [
                    {"label": "SUV / Crossover",  "message": "SUV"},
                    {"label": "Sedan",            "message": "Sedan"},
                    {"label": "Pickup Truck",     "message": "Pickup Truck"},
                    {"label": "Compact / Hatch",  "message": "Compact car"},
                ]
        else:
            # No make known — show vehicle type chips
            quick_replies = [
                {"label": "SUV / Crossover",  "message": "SUV"},
                {"label": "Sedan",            "message": "Sedan"},
                {"label": "Pickup Truck",     "message": "Pickup Truck"},
                {"label": "Sport / Coupe",    "message": "Sport coupe"},
                {"label": "Compact / Hatch",  "message": "Compact car"},
            ]

    elif session.stage == "cart":
        # After cart is confirmed, show checkout shortcut
        quick_replies = [
            {"label": "Confirm & Pay", "message": "confirm payment"},
            {"label": "Go back",       "message": "go back"},
        ]

    # ── Guardrail (pure Python — no LLM) ─────────────────────────────────
    tyre_ids = [c["tyre"]["id"] for c in cards] if cards else []
    vehicle = None
    if session.member_id:
        u = get_member(session.member_id)
        if u:
            vehicle = u.vehicle.model_dump()

    safe_response = get_guardrail().check(response_text, req.session_id, tyre_ids, vehicle)
    if safe_response is None:
        safe_response = response_text

    add_to_history(req.session_id, "assistant", safe_response)

    # ── Arize: record outcome attributes on span ──────────────────────────
    if _ARIZE_ENABLED:
        try:
            from opentelemetry import trace as _otel_trace
            _span = _otel_trace.get_current_span()
            _span.set_attribute("chat.response_stage",    session.stage or "")
            _span.set_attribute("chat.cards_returned",    len(cards))
            _span.set_attribute("chat.has_booking",       booking_card is not None)
            _span.set_attribute("chat.guardrail_applied", safe_response != response_text)
        except Exception:
            pass

    return {
        "message": safe_response,
        "cards": cards,
        "comparison": comparison,
        "appointment_slots": appointment_slots,
        "booking_card": booking_card,
        "stage": session.stage,
        "quick_replies": quick_replies,
        "drop_recovery": apply_recovery_rule(drop_signal, {}) if drop_signal else None,
    }

# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@app.post("/feedback")
async def feedback(req: FeedbackRequest):
    from app.services.eval_service import collect_feedback, update_scorecard
    collect_feedback(req.session_id, req.agent, "explicit", req.signal, req.tyre_id)
    delta = 1 if req.signal == "thumbs_up" else -1
    key = {"rec_ranking": "rec_ranking", "content": "content", "compare": "compare",
           "appointment": "appointment", "orchestrator": "orchestrator"}.get(req.agent, "rec_ranking")
    updated = update_scorecard(key, delta)
    return {"status": "recorded", "updated_score": updated.get("score")}

# ---------------------------------------------------------------------------
# Image Analysis — tyre identification + tyre health scoring
# ---------------------------------------------------------------------------

@app.post("/image-analyse")
async def image_analyse(req: ImageAnalyseRequest):
    """
    Analyse a tyre image using Claude Vision.

    - Sidewall photo  → extracts tyre size + finds matching recommendations
    - Tread/car photo → health score, wear analysis, buy recommendation

    Returns same JSON format as /chat so the frontend processResponse() handles it.
    """
    from app.services.image_service import analyze_tyre_image, build_health_message
    from app.services.profile_service import get_member
    from app.services.stock_service import search_tyres, get_stock_badge
    from app.tools.content_tools import generate_personalised_msg
    from app.tools.recommendation_tools import generate_punch_line

    session = get_session(req.session_id)
    user = get_member(session.member_id) if session.member_id else None

    result = analyze_tyre_image(req.image_data, req.image_type)
    scenario = result.get("scenario", "unclear")

    # ── Scenario: sidewall — identify tyre, run recommendations ─────────────
    if scenario == "sidewall":
        tyre_size  = result.get("tyre_size", "")
        brand      = result.get("brand", "")
        confidence = result.get("confidence", "medium")

        if not tyre_size:
            return JSONResponse({
                "message": "I could see a tyre sidewall but couldn't read the size markings clearly. "
                           "Please try a closer, well-lit photo of the numbers on the tyre side.",
                "cards": [], "stage": session.stage, "quick_replies": [],
                "comparison": None, "appointment_slots": [], "booking_card": None, "drop_recovery": None,
            })

        # Store detected size in session so subsequent flow uses it
        session.preferences["override_tyre_size"] = tyre_size
        if brand:
            session.preferences["detected_brand"] = brand

        conf_note = "" if confidence == "high" else " (please confirm this matches your tyre)"
        # Only mention brand if Vision returned something real (not "Unknown" / empty)
        brand_clean = brand if brand and brand.lower() not in ("unknown", "n/a", "none", "") else ""
        intro = (
            f"I can see from your image that your tyre size is **{tyre_size}**"
            + (f" — {brand_clean} tyre" if brand_clean else "")
            + f"{conf_note}. Here are the best options available for that size:"
        )

        # Find matching tyres (Top Pick + 2 alternatives)
        locs_path = Path(__file__).parent / "data" / "locations.json"
        locs = json.loads(locs_path.read_text(encoding="utf-8")) if locs_path.exists() else []

        results = search_tyres(size=tyre_size, in_stock_only=True)
        if len(results) < 3:
            results += search_tyres(size=tyre_size, in_stock_only=False)
        # De-duplicate
        seen_ids: set[str] = set()
        unique: list = []
        for t in results:
            if t.id not in seen_ids:
                seen_ids.add(t.id)
                unique.append(t)
        results = unique[:6]  # cap to avoid over-processing

        if not results:
            # Same broadening logic as the chat flow — relax season, then size-only
            from app.services.stock_service import broaden_search as _broaden
            broadened = _broaden(size=tyre_size)
            seen_ids2: set[str] = set()
            broad_unique: list = []
            for t in broadened:
                if t.id not in seen_ids2:
                    seen_ids2.add(t.id)
                    broad_unique.append(t)
            results = broad_unique[:6]

            if not results:
                # Truly nothing available — ask user to try manually
                return JSONResponse({
                    "message": (
                        f"I detected tyre size **{tyre_size}** from your image, but we don't currently "
                        f"carry that size. Please check back soon or try a nearby size."
                    ),
                    "cards": [], "stage": session.stage,
                    "quick_replies": [
                        {"label": "Search a different size", "message": "I want to search by tyre size"},
                        {"label": "Find tyres for my car", "message": "Find tyres for my car"},
                    ],
                    "comparison": None, "appointment_slots": [], "booking_card": None, "drop_recovery": None,
                })
            # Broadened results found — note it in the intro
            conf_note = "" if confidence == "high" else " (please confirm this matches your tyre)"
            intro = (
                f"We don't have an exact match for **{tyre_size}**, but here are the closest available options"
                + f"{conf_note}:"
            )

        member_ctx = json.dumps({
            "driving_habits": user.driving_habits if user else ["highway"],
            "location": user.location.model_dump() if user else {"city": "Unknown", "zip": "00000"},
            "membership_tier": user.membership_tier if user else "standard",
            "vehicle": user.vehicle.model_dump() if user else {"make": "Unknown", "model": "Unknown", "year": 2020},
        })

        slot_defs = [
            (results[0], "Top Pick",  "top_pick",  True),
            (results[1], "Runner-up", "runner_up",  False),
            (results[2] if len(results) > 2 else results[-1], "Budget Alt", "budget_alt", False),
        ]

        cards = []
        for tyre, tag, slot_type, is_top in slot_defs:
            msg_text = generate_personalised_msg.invoke({
                "tyre_json": json.dumps(tyre.model_dump()),
                "member_context_json": member_ctx,
                "slot_type": slot_type,
            })
            punch = generate_punch_line.invoke({"tyre_json": json.dumps(tyre.model_dump())}) if is_top else None
            cards.append({
                "tyre": tyre.model_dump(),
                "slot_tag": tag,
                "personalised_msg": msg_text,
                "stock_badge": get_stock_badge(tyre, locs),
                "punch_line": punch,
            })

        session.stage = "browse"
        session.preferences["last_cards_ids"] = [c["tyre"]["id"] for c in cards]

        return JSONResponse({
            "message": intro,
            "cards": cards,
            "stage": session.stage,
            "quick_replies": [],
            "comparison": None,
            "appointment_slots": [],
            "booking_card": None,
            "drop_recovery": None,
        })

    # ── Scenario: car_identified — detected car make/model → find tyres ─────
    if scenario == "car_identified":
        car_make       = result.get("car_make", "")
        car_model      = result.get("car_model", "")
        car_confidence = result.get("car_confidence", "medium")
        health_score   = result.get("health_score", 7)
        recommendation = result.get("recommendation", "continue")

        car_text = f"{car_make} {car_model}".strip()
        tyre_size = _infer_size_from_text(car_text) if car_text else None

        if tyre_size:
            # Car recognised + tyre size known → show recommendations immediately
            session.preferences["override_tyre_size"] = tyre_size
            session.preferences["car_label"] = car_text

            locs_path = Path(__file__).parent / "data" / "locations.json"
            locs = json.loads(locs_path.read_text(encoding="utf-8")) if locs_path.exists() else []

            city = user.location.city if user and user.location else ""
            season = _detect_season(city)
            terrain = _infer_terrain(user.driving_habits) if user else "highway"

            results = search_tyres(size=tyre_size, season=season, terrain=terrain, in_stock_only=True)
            if len(results) < 3:
                results += search_tyres(size=tyre_size, in_stock_only=True)
            seen_ids: set[str] = set()
            unique: list = []
            for t in results:
                if t.id not in seen_ids:
                    seen_ids.add(t.id)
                    unique.append(t)
            results = unique[:6]

            # Brand diversity
            seen_brands: set[str] = set()
            diverse: list = []
            for t in sorted(results, key=lambda x: x.rating, reverse=True):
                if t.brand not in seen_brands or len(diverse) < 3:
                    diverse.append(t)
                    seen_brands.add(t.brand)
                if len(diverse) == 3:
                    break

            conf_qualifier = " (I'm fairly confident — double-check if unsure)" if car_confidence != "high" else ""
            health_note = ""
            if recommendation in ("replace_soon", "replace_now") or health_score < 4:
                health_note = " Your tyres look like they need attention too —"

            intro = (
                f"I can see a **{car_text}** in your photo{conf_qualifier}.{health_note} "
                f"Here are the best tyres available for it ({tyre_size}):"
            )

            if not diverse:
                from app.services.stock_service import get_available_sizes
                available = get_available_sizes()
                return JSONResponse({
                    "message": (
                        f"I spotted a **{car_text}** in your image — great car! "
                        f"We don't currently carry **{tyre_size}** tyres in stock. "
                        f"Sizes we do carry: {', '.join(available[:6])}."
                    ),
                    "cards": [], "stage": session.stage,
                    "quick_replies": [
                        {"label": "Enter tyre size manually", "message": "I want to enter my tyre size manually"},
                    ],
                    "comparison": None, "appointment_slots": [], "booking_card": None, "drop_recovery": None,
                })

            member_ctx = json.dumps({
                "driving_habits": user.driving_habits if user else ["highway"],
                "location": user.location.model_dump() if user else {"city": "Unknown", "zip": "00000"},
                "membership_tier": user.membership_tier if user else "standard",
                "vehicle": user.vehicle.model_dump() if user else {"make": car_make, "model": car_model, "year": 2023},
            })

            slot_defs = [
                (diverse[0], "Top Pick",  "top_pick",  True),
                (diverse[1] if len(diverse) > 1 else diverse[0], "Runner-up", "runner_up",  False),
                (diverse[2] if len(diverse) > 2 else diverse[-1], "Budget Alt", "budget_alt", False),
            ]

            cards = []
            for tyre, tag, slot_type, is_top in slot_defs:
                msg_text = generate_personalised_msg.invoke({
                    "tyre_json": json.dumps(tyre.model_dump()),
                    "member_context_json": member_ctx,
                    "slot_type": slot_type,
                })
                punch = generate_punch_line.invoke({"tyre_json": json.dumps(tyre.model_dump())}) if is_top else None
                cards.append({
                    "tyre": tyre.model_dump(),
                    "slot_tag": tag,
                    "personalised_msg": msg_text,
                    "stock_badge": get_stock_badge(tyre, locs),
                    "punch_line": punch,
                })

            session.stage = "browse"
            session.preferences["last_cards_ids"] = [c["tyre"]["id"] for c in cards]

            return JSONResponse({
                "message": intro,
                "cards": cards,
                "stage": session.stage,
                "quick_replies": [],
                "comparison": None,
                "appointment_slots": [],
                "booking_card": None,
                "drop_recovery": None,
            })

        else:
            # Car recognised but model not in our size map → ask user to confirm
            conf_qualifier = " (I think)" if car_confidence != "high" else ""
            session.preferences["partial_make"] = car_make
            session.stage = "collect_vehicle"
            return JSONResponse({
                "message": (
                    f"I can see a **{car_text}**{conf_qualifier} in your photo! "
                    f"I don't have the exact tyre size for that model in my database. "
                    f"Could you confirm the model, or type the tyre size from the sidewall? "
                    f"(e.g. 205/55R16 — it's printed on the tyre)"
                ),
                "cards": [], "stage": session.stage,
                "quick_replies": [
                    {"label": f"It's a {car_model}", "message": f"It's a {car_make} {car_model}"},
                    {"label": "Enter tyre size", "message": "I'll enter the tyre size manually"},
                ],
                "comparison": None, "appointment_slots": [], "booking_card": None, "drop_recovery": None,
            })

    # ── Scenario: tread or car (unidentified) — health analysis ─────────────
    if scenario in ("tread", "car"):
        health_msg        = build_health_message(result)
        score             = result.get("health_score", 10)
        rec               = result.get("recommendation", "continue")
        needs_replacement = rec in ("replace_soon", "replace_now") or score < 4

        if needs_replacement:
            if user:
                # Ask whether to use the member's existing car or a different one.
                v = user.vehicle
                car_label = f"{v.year} {v.make} {v.model}"
                follow_up = f"\nWould you like me to find replacement tyres for your {car_label}?"
                quick_replies = [
                    {"label": f"Yes, for my {car_label}",
                     "message": f"Yes, same car — {v.year} {v.make} {v.model}"},
                    {"label": "No, I drive a different car",
                     "message": "No, I have a different vehicle"},
                ]
                session.stage = "confirm_vehicle"
            else:
                follow_up = "\nWould you like me to find replacement tyres for you?"
                quick_replies = [
                    {"label": "Yes, find me tyres", "message": "Yes, find me tyres"},
                    {"label": "No thanks",           "message": "No thanks"},
                ]
        else:
            follow_up = ""
            quick_replies = []

        return JSONResponse({
            "message": health_msg + follow_up,
            "cards": [],
            "stage": session.stage,
            "quick_replies": quick_replies,
            "comparison": None,
            "appointment_slots": [],
            "booking_card": None,
            "drop_recovery": None,
        })

    # ── Scenario: unclear ────────────────────────────────────────────────────
    msg = result.get("message", "I couldn't identify a tyre in that image.")
    return JSONResponse({
        "message": (
            f"{msg}\n\nFor best results:\n"
            "• Sidewall photo — photograph the side of the tyre showing the size numbers (e.g. 205/55R16)\n"
            "• Tread photo — photograph the tyre contact surface from above"
        ),
        "cards": [], "stage": session.stage,
        "quick_replies": [
            {"label": "Enter tyre size manually",  "message": "I want to enter my tyre size manually"},
            {"label": "Show all recommendations",  "message": "Show me tyre recommendations"},
        ],
        "comparison": None, "appointment_slots": [], "booking_card": None, "drop_recovery": None,
    })


# ---------------------------------------------------------------------------
# Voice (ElevenLabs TTS)
# ---------------------------------------------------------------------------

@app.get("/voice/status")
async def voice_status():
    from app.services.voice_service import voice_enabled
    return {"enabled": voice_enabled(), "model": os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")}

@app.post("/voice/tts")
async def voice_tts(req: TTSRequest):
    from app.services.voice_service import text_to_speech_stream, voice_enabled
    if not voice_enabled():
        return JSONResponse({"error": "Voice not configured — set ELEVENLABS_API_KEY in .env"}, status_code=503)
    async def audio_stream():
        async for chunk in text_to_speech_stream(req.text):
            yield chunk
    return StreamingResponse(audio_stream(), media_type="audio/mpeg",
                             headers={"Cache-Control": "no-cache"})

# ---------------------------------------------------------------------------
# Static routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_ui():
    # Prefer React build (frontend/dist) over legacy static UI
    react_index = _REACT_DIST / "index.html"
    if react_index.exists():
        return FileResponse(str(react_index))
    legacy_index = _STATIC_DIR / "index.html"
    return FileResponse(str(legacy_index)) if legacy_index.exists() else JSONResponse({"error": "UI not built"}, status_code=503)

@app.get("/favicon.svg", include_in_schema=False)
async def serve_favicon():
    favicon = _REACT_DIST / "favicon.svg"
    if favicon.exists():
        return FileResponse(str(favicon), media_type="image/svg+xml")
    return JSONResponse({"error": "not found"}, status_code=404)

@app.get("/demo-members")
async def demo_members():
    """Return first 5 members for login demo chips — DB first, JSON fallback."""
    from app.db.connection import db_available, get_conn, release_conn
    members = []

    if db_available():
        try:
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT member_id, full_name, membership_tier,
                               vehicle_make, vehicle_model, vehicle_year
                        FROM contacts
                        ORDER BY member_id
                        LIMIT 5
                    """)
                    for row in cur.fetchall():
                        members.append({
                            "member_id": row[0],
                            "name": row[1],
                            "tier": row[2].title() if row[2] else "Standard",
                            "vehicle": f"{row[5]} {row[3]} {row[4]}".strip(),
                        })
            finally:
                release_conn(conn)
        except Exception as e:
            logger.warning("demo_members DB failed: %s", e)

    # JSON fallback
    if not members:
        from app.services.profile_service import _load_users
        try:
            for u in _load_users()[:5]:
                v = u.get("vehicle", {})
                members.append({
                    "member_id": u["member_id"],
                    "name": u.get("name", ""),
                    "tier": u.get("membership_tier", "standard").title(),
                    "vehicle": f"{v.get('year','')} {v.get('make','')} {v.get('model','')}".strip(),
                })
        except Exception:
            pass

    return members


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.33.0", "active_sessions": len(SESSION_STORE),
            "app_env": os.environ.get("APP_ENV", "dev")}

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

from app.dashboard.dashboard import router as dashboard_router
app.include_router(dashboard_router)
