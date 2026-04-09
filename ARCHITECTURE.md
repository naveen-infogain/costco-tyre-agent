# Costco Tyre Agent — Architecture & Technical Deep Dive

---

## Table of Contents

1. [System Overview](#system-overview)
2. [How the Pipeline Works](#how-the-pipeline-works)
3. [Intent Routing — 3-Tier System](#intent-routing--3-tier-system)
4. [Car Name → Tyre Size Mapping](#car-name--tyre-size-mapping)
5. [Search & Filtering — How Tyres Are Found](#search--filtering--how-tyres-are-found)
6. [Why No Vector DB / Embeddings](#why-no-vector-db--embeddings)
7. [Language Detection](#language-detection)
8. [Image Upload Flow — Car & Tyre Detection](#image-upload-flow--car--tyre-detection)
9. [Each Agent — What It Does](#each-agent--what-it-does)
10. [Each Service — What It Does](#each-service--what-it-does)
10. [LangChain — How It Is Used](#langchain--how-it-is-used)
11. [3rd Party APIs & Integrations](#3rd-party-apis--integrations)
12. [Which Model for What](#which-model-for-what)
13. [Data Flow — End to End](#data-flow--end-to-end)
14. [Key Architectural Decisions](#key-architectural-decisions)
15. [Indexing & Data Access Patterns](#indexing--data-access-patterns)

---

## System Overview

The Costco Tyre Agent is a **FastAPI + React** conversational assistant that guides members from login through tyre discovery, recommendations, checkout, and appointment booking.

```
Browser (React / Vite :5173)
         ↕  HTTP (Vite proxy)
FastAPI backend (:8000)
  ├── Intent Router (3-tier: regex → rules → LLM)
  ├── Pure Python pipeline (search, cart, payment, booking)
  ├── Single LLM call per message (Claude Sonnet 4.6)
  └── Guardrail checks (pure Python, no LLM)
```

**Core design principle:** The LLM writes responses. Python handles everything else. No ReAct loops.

---

## How the Pipeline Works

Every `POST /chat` request goes through this sequence:

```
1. Load or create session (in-memory SessionState)
2. Detect language → store in session.preferences["language"]
3. Classify intent (Tier 1 regex → Tier 1.5 vehicle detection → Tier 2 stage rules → Tier 3 LLM)
4. Execute handler based on intent × stage
   ├── Pure Python: search tyres, add to cart, process payment, book appointment
   └── LLM call (1 per message): write the response text
5. Guardrail agent: check response before sending
6. Return JSON: { message, cards, quick_replies, slots, booking_card }
```

**One LLM call per message. Never more.**

---

## Intent Routing — 3-Tier System

All implemented in `app/main.py → _detect_intent()`.

### Tier 1 — Global rules (stage-independent)

Pure Python regex. Fires first regardless of stage.

| Pattern | Intent |
|---------|--------|
| `^M\d{4,6}$` | `login` |
| `my bad`, `actually!`, `sorry` | `context_then_vehicle` |
| `add to cart`, `add.to.cart` | `add_cart` |
| `compar`, `side.by.side`, `vs`, `versus` | `compare` |
| `book`, `schedule`, `appointment`, `install`, `slot` | `book_slot` |
| `cancel`, `go back`, `start over` | `cancel` |

### Tier 1.5 — Multilingual vehicle detection

Runs **before** stage-sensitive rules. Catches car brand/model in any language.

```python
_VEHICLE_STAGES = {"confirm_vehicle", "collect_vehicle", "browse", "greet", None, ""}
if session.stage in _VEHICLE_STAGES:
    if tyre_size_regex matches      → new_vehicle_detail
    if car_brand_regex matches      → new_vehicle_detail  (tata, honda, hyundai, ...)
    if _MODEL_NAMES_RE matches      → new_vehicle_detail  (nexon, creta, swift, ...)
```

This is why "Nenu Hyderabad ki Tata nexon lo velthanu" correctly routes to `new_vehicle_detail` — brand `tata` is detected before any destination/travel-context check.

### Tier 2 — Stage-sensitive rules

Context matters. Same word = different intent at different stages.

| Stage | Pattern | Intent |
|-------|---------|--------|
| `cart` | `yes`, `ok`, `confirm` | `confirm_pay` |
| `confirm_vehicle` | `same`, `avunu`, `aama`, `houdu` | `same_vehicle` |
| `confirm_vehicle` | car brand / model name | `new_vehicle_detail` |
| `confirm_vehicle` | `going to`, city name, `jata hun` | `context_then_vehicle` |
| `collect_vehicle` | anything | `new_vehicle_detail` |

### Tier 3 — LLM fallback

Single-token classification call. **Only runs when Tiers 1+2 produce no match.**

```python
system = "Classify user message into ONE of: login | context_then_vehicle | ... | general"
# Returns single label, no explanation, ~200ms latency
```

---

## Car Name → Tyre Size Mapping

**No LLM used. Zero cost. Zero latency.**

### How it works

```
User says: "I have a Tata Nexon"
          ↓
_infer_size_from_text("I have a Tata Nexon")
          ↓
Step 1: Loop _VEHICLE_SIZE_MAP → "nexon" found → "195/60R16"
          ↓
Use "195/60R16" as tyre size for all searches
```

### `_VEHICLE_SIZE_MAP` (app/main.py, ~400 entries)

Direct substring match. Key = model name (lowercase), value = OEM tyre size.

```python
_VEHICLE_SIZE_MAP = {
    # Indian market
    "nexon":    "195/60R16",
    "punch":    "185/70R15",
    "harrier":  "235/60R18",
    "creta":    "215/60R17",
    "brezza":   "195/60R16",
    "swift":    "175/65R15",
    # North America
    "cr-v":     "235/65R17",
    "camry":    "215/55R17",
    "f-150":    "265/60R18",
    # ... 400+ models total
}
```

If model not found: class-based fallback.

```python
_CLASS_SIZE_DEFAULTS = {
    "compact_suv": "215/60R16",   # Nexon, Venue, Sonet
    "suv":         "235/65R17",
    "sedan":       "205/55R16",
    "compact":     "185/65R15",
    "minicar":     "165/80R13",   # Alto, Kwid
    "truck":       "265/70R17",
}
```

### `_MODEL_NAMES_RE` — multilingual model extraction

Compiled regex from all keys in `_VEHICLE_SIZE_MAP` (sorted longest-first to avoid partial matches):

```python
_MODEL_NAMES_RE = re.compile(
    r"(?<![a-z])(" + "|".join(sorted(model_names, key=len, reverse=True)) + r")(?![a-z])",
    re.IGNORECASE,
)
```

Used in:
1. **Intent routing** — detect model name in any language message
2. **`_parse_vehicle_from_msg()`** — extract make+model from mixed-language text
3. **Car label** — clean "Tata Nexon" label from "Mumbai jata hun Tata nexon lekar"

### `_KNOWN_MODEL_MAKES` — model → brand lookup

When user says only model name (no brand):

```python
_KNOWN_MODEL_MAKES = {
    "nexon": "Tata", "creta": "Hyundai", "swift": "Maruti Suzuki",
    "sonet": "Kia", "hector": "MG", "thar": "Mahindra", ...
}
```

Flow: `"nexon per jata hun"` → `_MODEL_NAMES_RE` finds "nexon" → `_KNOWN_MODEL_MAKES["nexon"]` = "Tata" → `make="Tata", model="Nexon"`.

---

## Search & Filtering — How Tyres Are Found

**Location:** `app/services/stock_service.py → search_tyres()`

### Data sources (in priority order)

```
1. PostgreSQL DB (if DB_HOST set and reachable)
   └── SELECT * FROM products WHERE size=? AND season=? AND terrain=? AND stock_qty > 0

2. JSON fallback (always available)
   └── app/data/tyres.json — 100 entries (Western + Indian market)

3. Hybrid: if DB returns 0 results, supplements from JSON
   └── Ensures Indian-market tyres (MRF, CEAT, Apollo, SYN-*) are always findable
```

### Search logic

```python
def search_tyres(size, season, terrain, max_price, brand, in_stock_only):
    # Try DB first
    if db_available():
        results = _search_db(size, season, terrain, max_price, brand, in_stock_only)
        if len(results) < 3:
            # Supplement from JSON for items DB might not have
            json_results = _search_json(...)
            results += [t for t in json_results if t.id not in seen_ids]
    else:
        results = _search_json(size, season, terrain, max_price, brand, in_stock_only)
    return results
```

### Progressive broadening (in main.py card builder)

```
Step 1: search(size=X, season=detected, terrain=detected)  →  if < 3 results:
Step 2: search(size=X, terrain=detected)                   →  if < 3 results:
Step 3: search(size=X)                                     →  if 0 results: no-results message
```

### Brand diversity enforcement

After getting results, main.py picks top 3 with brand diversity:

```python
seen_brands = set()
for tyre in sorted(results, key=lambda x: x.rating, reverse=True):
    if tyre.brand not in seen_brands or len(diverse) < 3:
        diverse.append(tyre)
        seen_brands.add(tyre.brand)
    if len(diverse) == 3:
        break
```

---

## Why No Vector DB / Embeddings

| Approach | Vector DB (e.g. pgvector, Pinecone) | Our Approach (SQL + JSON) |
|----------|-------------------------------------|---------------------------|
| Query type | "tyres similar to X" (semantic) | "tyres for size X, season Y, terrain Z" (exact filters) |
| Catalogue size | Suitable for 100k+ docs | 100 tyres — overkill |
| Cost | Embedding model + vector store | Zero |
| Latency | 50–200ms embedding + ANN search | <5ms SQL |
| Accuracy | Good for fuzzy/semantic | SQL filters are exact and reliable |
| Maintainability | Requires re-indexing on updates | Just update JSON/DB row |

**Verdict:** Tyre search is **structured retrieval** (size, season, terrain, price, brand). Vector search adds cost and complexity with no accuracy benefit for this domain. If the catalogue grows to 10,000+ tyres with free-text descriptions, embeddings would make sense.

---

## Language Detection

**Location:** `app/main.py → _detect_language(msg)`

**Zero cost — no LLM used.**

### How it works

```
Pass 1 — Word-list match (exact words, O(n) dict lookup)
  "leke", "gaadi", "haan" → Hindi
  "nenu", "velthanu", "ledu" → Telugu
  "enna", "romba", "nalla" → Tamil
  ... (6 regional languages + Hindi)

Pass 2 — Morphological suffix patterns (catches conjugated verbs)
  Telugu: words ending in -unnanu, -thanu, -andi
  Hindi:  "ja raha hun", "jata hun", "lekar"
  Tamil:  words ending in -ndaan, -raan
  Kannada: words ending in -enu, -ide

Pass 3 — Casual English detection
  "lol", "haha", "gonna", "wanna" → casual_en
  Short, lowercase messages → casual_en

Default → English
```

### Language persistence

Once detected, language sticks for the session (won't flip back to English if user sends a short English message):

```python
if detected_lang in _non_english_languages:
    session.preferences["language"] = detected_lang  # sticky
```

### How language affects responses

Every LLM call in the pipeline appends `_LANG_INSTRUCTION[lang]` to the system prompt:

```python
_LANG_INSTRUCTION = {
    "Hindi":   "Reply in Hinglish — mix Hindi naturally. Use yaar, boss, chalo where natural.",
    "Telugu":  "Reply entirely in Telugu. Keep tyre sizes, brands, prices in English.",
    "Tamil":   "Reply entirely in Tamil. Keep tyre sizes, brands, prices in English.",
    ...
    "English": "",  # default persona handles this
}
```

---

## Image Upload Flow — Car & Tyre Detection

**Endpoint:** `POST /image-analyse`
**File:** `app/services/image_service.py` + `app/main.py`

### How it works

User taps the camera icon in the chat input → image is base64-encoded → sent to `/image-analyse`. Claude Vision analyses the image and returns a scenario label. The endpoint then routes to the correct flow.

### Scenarios

```
Upload image
     │
     ▼
Claude Vision (_VISION_PROMPT)
     │
     ├── "sidewall"       → read tyre size from markings → search tyres by size
     ├── "car_identified" → detect car make/model → map to OEM size → search tyres
     ├── "car"            → car visible but not recognised → health check only
     ├── "tread"          → tyre tread close-up → health score
     └── "unclear"        → guidance message, ask for better photo
```

### `car_identified` — new flow (car image → tyre recommendations)

```
1. Claude Vision returns:
   { "scenario": "car_identified", "car_make": "Tata", "car_model": "Nexon",
     "car_confidence": "high", "health_score": 7, "recommendation": "continue" }

2. _infer_size_from_text("Tata Nexon")
   → "nexon" in _VEHICLE_SIZE_MAP → "195/60R16"

3. If size found:
   → search_tyres(size="195/60R16", season=auto, terrain=auto, in_stock_only=True)
   → brand diversity → top 3 cards
   → "I can see a Tata Nexon in your photo! Here are the best tyres for it (195/60R16):"
   → Returns 3 tyre cards, session.stage = "browse"

4. If size NOT found (unknown model):
   → session.preferences["partial_make"] = car_make
   → session.stage = "collect_vehicle"
   → "I can see a Tata [model]! I don't have the exact tyre size — could you confirm the model
      or type the size from your sidewall?"
   → Quick replies: ["It's a [model]", "Enter tyre size"]

5. If health check shows worn tyres:
   → Intro includes: "Your tyres look like they need attention too —"
```

### `sidewall` — existing flow

```
1. Claude Vision returns: { "scenario": "sidewall", "tyre_size": "195/60R16", ... }
2. search_tyres(size=detected_size, in_stock_only=True)
3. Returns 3 cards (Top Pick / Runner-up / Budget Alt)
```

### `tread` / `car` — health analysis flow

```
1. Claude Vision scores health 1–10 (default ≥7 unless obvious damage)
2. build_health_message() → formats score, findings, recommendation
3. If score < 4 or recommendation = "replace_now/soon":
   → Ask to find replacement tyres (with member's existing car or new one)
   → session.stage = "confirm_vehicle" so next message flows naturally
4. If score ≥ 7:
   → "Your tyres are in good shape." No chips.
```

### Full decision matrix

| Image shows | Claude detects | Result |
|-------------|---------------|--------|
| Car with recognisable make/model | `car_identified` | Tyre recommendations for that car |
| Car, make/model not recognisable | `car` | Health score + optional replacement flow |
| Tyre sidewall with size numbers | `sidewall` | Recommendations matching detected size |
| Tyre tread close-up | `tread` | Health score + wear analysis |
| Blurry / unrelated | `unclear` | Help message + manual options |

### Prompt engineering (image_service.py `_VISION_PROMPT`)

- Instructs Claude to return **only JSON** — no markdown, no explanation
- Scenario C (vehicle) now has two sub-outcomes: `car_identified` (make+model found) vs `car` (not found)
- Liberal health scoring: dirt/grime does NOT reduce score; default ≥7 unless obvious damage
- Confidence field (`car_confidence`: high/medium/low) propagates to user message ("I think" qualifier)

---

## Each Agent — What It Does

All agents are in `app/agents/`. They use LangChain's `create_react_agent()` with a LangGraph `MemorySaver`. The skeletal agent definitions exist; the active pipeline logic runs in `app/main.py`.

### 1. Orchestrator Agent (`agents/orchestrator.py`)

**Role:** Entry point for every session.

- Authenticates member via `load_member_session()`
- Detects user type: **Path A** (returning buyer, has tyre history) vs **Path B** (new buyer)
- Manages overall conversation state and agent hand-offs
- Collects preferences conversationally (not via form): car type, season, terrain, climate

**Tools:** `load_member_session`, `detect_user_type`, `collect_preferences`, `auto_detect_climate`, `route_to_agent`

**Currently:** Logic inlined in `app/main.py` (session loading, path detection, stage transitions)

---

### 2. Rec & Ranking Agent (`agents/rec_ranking_agent.py`)

**Role:** Core recommendation engine.

**Path A (returning buyer):**
- Fetches last purchased tyre (SKU, date, mileage)
- Searches 2 alternatives
- Ranks by: repurchase fit, upgrade value, popularity, rating delta
- Tags: Best Repurchase / Best Upgrade / Most Popular

**Path B (new buyer):**
- Searches full catalogue with member criteria
- Multi-signal ranking: value, safety, regional popularity, rating, sentiment
- Enforces diversity: each of top 3 leads a different signal
- Tags: Top Pick / Runner-up / Budget Alt

**Tools:** `search_tyres`, `get_tyre_details`, `rank_tyres`, `select_top_pick`, `generate_punch_line`, `broaden_search`, `handle_no_results`

**Currently:** Logic inlined in `app/main.py → _build_recommendation_cards()`

---

### 3. Content Agent (`agents/content_agent.py`)

**Role:** Generates personalised message for each tyre card slot.

- Tailors copy to: member's vehicle, driving habits, location, membership tier
- Different message per slot type (repurchase loyalty vs upgrade delta vs value savings)

**Tool:** `generate_personalised_msg(tyre_json, member_context_json, slot_type)`

**Currently:** `generate_personalised_msg` @tool called directly in `_build_recommendation_cards()`

---

### 4. Compare Agent (`agents/compare_agent.py`)

**Role:** Side-by-side comparison of top 3 tyres.

- 3 columns: price, tread life, noise, warranty, wet grip
- AI-generated pros/cons per tyre (heuristic rules, no LLM)
- Total cost of ownership (price ÷ tread_life × 1000 = cost per 1000 km)

**Tool:** `generate_comparison_card(tyre_list_json, member_context_json)`

**Triggered:** When user says "compare", "vs", "side by side"

---

### 5. Appointment Agent (`agents/appointment_agent.py`)

**Role:** Books installation appointment after payment.

- Finds nearest Costco tyre centres by flat-earth distance from member city
- Surfaces available slots (7 per day, 7 days ahead)
- Smart suggestion: morning slots preferred (less busy), earliest date first
- Books slot, writes to `app/data/appointments.json`
- Generates `.ics` calendar invite via `icalendar` library

**Tools:** `get_nearby_locations`, `get_available_slots`, `predict_wait_times`, `suggest_best_slot`, `book_appointment`, `link_order_to_booking`, `create_calendar_event`

**Currently:** Tools called directly in `app/main.py` booking handler

---

### 6. Guardrail Agent (`agents/guardrail_agent.py`)

**Role:** Runs safety checks on every AI-generated response before it reaches the member.

**5 checks (all pure Python — no LLM):**

| Check | What it does |
|-------|-------------|
| `check_hallucination` | Verifies any tyre IDs mentioned exist in catalogue; prices within ±$50 of actual |
| `validate_fit` | Ensures recommended tyre size is compatible with member's vehicle |
| `redact_pii` | Strips email addresses, phone numbers, SSN, ZIP codes from response |
| `check_safety` | Load index ≥80, speed rating is a valid letter (N–Y) |
| `audit_bias` | No single brand dominates 2+ of 3 recommended slots |

**On failure:** Regenerates response silently, logs violation to `app/logs/guardrail.json`, never surfaces raw error to member.

---

## Each Service — What It Does

### Profile Service (`services/profile_service.py`)

Loads member data. **DB → JSON fallback.**

| Function | Returns |
|----------|---------|
| `get_member(member_id)` | Full User model (vehicle, habits, location, tier) |
| `get_last_purchased_tyre(member_id)` | LastPurchase (tyre_id, date, mileage) or None |
| `is_returning_buyer(member_id)` | True if last_purchase exists |
| `load_member_preferences(member_id)` | Dict: habits, location, tier, vehicle |

---

### Stock Service (`services/stock_service.py`)

Tyre catalogue search. **DB → JSON hybrid.**

| Function | Returns |
|----------|---------|
| `search_tyres(size, season, terrain, ...)` | List of Tyre models |
| `get_tyre_by_id(tyre_id)` | Single Tyre or None |
| `check_stock(tyre_ids, warehouse_id)` | Dict of tyre_id → bool |
| `get_stock_badge(tyre, locations)` | Human-readable badge: "In stock at Seattle Northgate" |
| `get_available_sizes()` | All distinct sizes in catalogue |
| `broaden_search(...)` | Same as search but relaxes constraints |

**Search is SQL WHERE + JSON filter — no embeddings.**

---

### Cart Service (`services/cart_service.py`)

In-memory cart with 15-minute TTL stock reservation.

| Function | Returns |
|----------|---------|
| `add_to_cart(member_id, tyre_id, qty)` | Cart dict with subtotal, savings, cashback |
| `get_cart(cart_id)` | Cart or None |
| `validate_fit(tyre, user)` | (bool, msg) — soft warning only, never blocks |
| `_cashback_rate(user)` | Executive: 2% / Gold: 1.5% / Standard: 1% |
| `_suggest_bundles(tyre)` | Upsell: alignment check, valve stems, etc. |

---

### Payment Service (`services/payment_service.py`)

Mock payment. Returns structured order.

| Function | Returns |
|----------|---------|
| `process_payment(member_id, cart_id, method)` | OrderSummary (order_id, total, cashback, method) |

- Auto-detects Costco Visa
- Generates `ORD-` prefixed order ID

---

### Post-Purchase Service (`services/post_purchase_service.py`)

After order confirmed:

- Day-before installation SMS reminder
- Install-complete alert
- 30-day satisfaction survey
- Rating/review write-back to profile
- Tyre rotation cron reminder at 10,000 km
- Seasonal swap alerts
- Re-engagement at predicted wear-out

---

### Drop-off Tracker (`services/dropoff_tracker.py`)

Monitors session health:

- Logs every stage transition with timestamp
- Detects: idle >2min, tab switch, exit intent

**Recovery rules:**

| Signal | Action |
|--------|--------|
| Price shock | Show member savings vs retail |
| Too many refinements | Simplify to 1 pick only |
| Session >8 min | Offer express checkout |
| Confused (repeated back-nav) | Open live chat |
| Left site | Recovery email in 1 hour |

---

### Eval Service (`services/eval_service.py`)

Feedback collection and agent scoring:

- Collects implicit signals (which card picked, which signal won)
- Collects explicit signals (thumbs up/down on each tyre + message)
- Maintains agent scorecard (Guardrail: 86, Rec: 78, Content: 71, ...)
- Improvement engine: deploys A/B winners, tracks uplift

---

### Voice Service (`services/voice_service.py`)

ElevenLabs TTS streaming. **Optional — app works without it.**

| Function | Does |
|----------|------|
| `text_to_speech_stream(text)` | Streams MP3 chunks from ElevenLabs |
| `_humanise_for_tts(text)` | 13-step pipeline: strips markdown, tyre IDs, prices→spoken, lists→prose, 500 char cap |
| `_BLOCKED_PATTERNS` | Content safety regex: blocks inappropriate language before TTS API call |
| `voice_enabled()` | True if `ELEVENLABS_API_KEY` is set |

---

## LangChain — How It Is Used

### What LangChain provides

| Component | Used | How |
|-----------|------|-----|
| `ChatAnthropic` | ✅ Yes | LLM wrapper — every `_llm_respond()` call |
| `SystemMessage / HumanMessage / AIMessage` | ✅ Yes | Building conversation history for context |
| `@tool` decorator | ✅ Yes | Wraps service functions for agent compatibility |
| `create_react_agent()` | ⚠️ Defined, not active | Agent definitions in `agents/` — architecture ready but main.py bypasses |
| `MemorySaver` (LangGraph) | ⚠️ In agents/ only | Session memory for when ReAct agents run |
| `AgentExecutor` | ❌ Not used | Replaced by deterministic pipeline in main.py |
| `ConversationBufferWindowMemory` | ❌ Not used | Replaced by `CHAT_HISTORY` dict in main.py (last 8 messages) |
| Vector stores / embeddings | ❌ Not used | No semantic search needed |

### Where LangChain is used in main.py

```python
# LLM initialisation
from langchain_anthropic import ChatAnthropic

def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        max_tokens=1024,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )

# Every response call
def _llm_respond(session_id, system_prompt, context_str):
    messages = [SystemMessage(content=system_prompt)]
    messages += get_history(session_id)   # last 8 messages
    messages += [HumanMessage(content=context_str)]
    result = get_llm().invoke(messages)
    return result.content
```

### Tools are called directly (not via agent executor)

```python
# In _build_recommendation_cards():
msg_text = generate_personalised_msg.invoke({
    "tyre_json": json.dumps(tyre.model_dump()),
    "member_context_json": member_ctx,
    "slot_type": slot_type,
})
punch = generate_punch_line.invoke({"tyre_json": json.dumps(tyre.model_dump())})
```

These `@tool` functions are called as regular Python functions. The `@tool` decorator is used so they're also usable in the agent definitions when/if those are activated.

### When would the ReAct agents activate?

The agent definitions in `agents/` are the intended production architecture for a future phase where each agent runs autonomously. Currently, `main.py` replicates their logic deterministically for cost control and speed. Swapping to full agents requires:
1. Remove inline handlers from main.py
2. Route each intent to the relevant agent's `.run()` method
3. Agents will call tools and iterate until done (ReAct loop)

---

## 3rd Party APIs & Integrations

### 1. Anthropic Claude API

| Property | Value |
|----------|-------|
| Model | `claude-sonnet-4-6` |
| Used for | Response text generation, Tier 3 intent classification, image analysis |
| Auth | `ANTHROPIC_API_KEY` in `.env` (required — app won't start without it) |
| Endpoint | `POST https://api.anthropic.com/v1/messages` |
| Cost | ~$0.003 per chat message (1K in + 1K out tokens) |
| Rate limit | ~60 req/min on Tier 1 — backs off on 429 |
| Latency | ~800ms p50 / ~2s p99 |
| Calls per `/chat` | **1** — single LLM call for response text only |
| Integration | `langchain-anthropic` → `ChatAnthropic` class |

**Image analysis (`POST /image-analyse`):**
- Same model, same API call
- Base64 image passed in message content
- Scenarios: sidewall (read tyre size), tread (health score 1–10), car (detect make/model), unclear
- Liberal scoring: default ≥7 unless obvious damage; dirt/grime does NOT reduce score

---

### 2. ElevenLabs TTS API

| Property | Value |
|----------|-------|
| Used for | Text-to-speech for bot responses (voice mode) |
| Auth | `ELEVENLABS_API_KEY` in `.env` (optional — voice disabled if absent) |
| Endpoint | `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream` |
| Model | `eleven_turbo_v2_5` (default) — ~300ms time-to-first-chunk |
| Voice | Rachel (`21m00Tcm4TlvDq8ikWAM`) — configurable via `ELEVENLABS_VOICE_ID` |
| Cost | ~$0.30 per 1,000 chars (Creator plan) |
| Rate limit | Free: 10k chars/month / Creator: 100k chars/month |
| Latency | ~300ms first chunk (streaming) |
| Response | Streaming MP3 — piped directly to browser via `StreamingResponse` |
| Integration | `httpx.AsyncClient` (async streaming), `voice_service.py` |

**Text pre-processing before API call (`_humanise_for_tts`):**
1. Strip markdown (`**bold**`, `*italic*`, `#headers`)
2. Remove tyre ID codes (`MIC-PRIM4-20555R16`)
3. Convert lists to prose sentences
4. Expand abbreviations (km → kilometres, yr → year)
5. Convert prices to spoken form (`$169.99` → `169 dollars and 99 cents`)
6. Remove emojis
7. Strip URLs
8. Normalise separators (` — ` → `, `)
9. Fix whitespace
10. Add terminal punctuation if missing
11. Cap at 500 characters

**Content safety gate:** `_BLOCKED_PATTERNS` regex blocks inappropriate language before sending to ElevenLabs.

---

### 3. PostgreSQL (optional)

| Property | Value |
|----------|-------|
| Used for | Member profiles, tyre catalogue, orders, appointments |
| Auth | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` in `.env` |
| Driver | `psycopg2-binary` (connection pool, 1–10 connections) |
| Fallback | JSON files in `app/data/` — app runs fully without a DB |
| Integration | `app/db/connection.py` — lazy init, `db_available()` health check |

**8 tables:** members, tyres, orders, vehicles, locations, appointments, feedback, sessions

**No pg_vector extension.** Pure relational queries only.

---

### 4. Web Speech API (client-side STT)

| Property | Value |
|----------|-------|
| Used for | Speech-to-text (user speaks → text) |
| Provider | Browser-native (`window.SpeechRecognition` / `window.webkitSpeechRecognition`) |
| Cost | Free — no API key, no server calls |
| Latency | ~0ms (runs entirely in browser) |
| Support | Chrome, Edge only — not Firefox/Safari |
| Integration | `frontend/src/hooks/useVoice.js → buildRecognition()` |

---

### 5. `icalendar` (calendar invites)

| Property | Value |
|----------|-------|
| Used for | Generate `.ics` calendar invite after appointment booking |
| Integration | `app/tools/appointment_tools.py → create_calendar_event()` |
| Cost | Free (Python library) |

---

## Which Model for What

| Task | Model | Notes |
|------|-------|-------|
| Bot response text | `claude-sonnet-4-6` | 1 call per `/chat` message |
| Intent classification (Tier 3 fallback) | `claude-sonnet-4-6` | Single-token output, ~200ms |
| Image analysis (tyre sidewall / tread / car) | `claude-sonnet-4-6` via Vision API | Base64 image in message |
| Text-to-speech | ElevenLabs `eleven_turbo_v2_5` | Rachel voice, ~300ms latency |
| Speech-to-text | Browser Web Speech API | Free, no model, Chrome/Edge only |
| Vehicle name → tyre size | `_VEHICLE_SIZE_MAP` dict lookup | No model — pure Python |
| Language detection | `_LANG_MARKERS` + regex patterns | No model — pure Python |
| Intent routing (Tiers 1+1.5+2) | Pure Python regex | No model |
| Tyre search & ranking | SQL/JSON filter + rating sort | No model |
| Guardrail checks | Pure Python rules | No model |
| Personalised messages | Hardcoded templates (Python) | No model (generate_personalised_msg tool) |
| Punch lines | Hardcoded heuristics (Python) | No model |
| Comparison card | Hardcoded heuristics (Python) | No model |

**Summary: Claude Sonnet 4.6 is used for exactly 3 things — writing response text, classifying ambiguous intents, and analysing images. Everything else is Python.**

---

## Data Flow — End to End

### Example: "Mumbai jata hun Tata nexon lekar"

```
1. POST /chat { message: "Mumbai jata hun Tata nexon lekar", session_id: "..." }

2. Language detection:
   _detect_language() → "jata", "hun", "lekar" in Hindi markers → "Hindi"
   session.preferences["language"] = "Hindi"

3. Intent routing:
   Tier 1: no global rule match
   Tier 1.5: stage="confirm_vehicle", "tata" matches brand regex → "new_vehicle_detail"

4. Handler: new_vehicle_detail
   _infer_size_from_text("Mumbai jata hun Tata nexon lekar")
     → "nexon" found in _VEHICLE_SIZE_MAP → "195/60R16"
   _parse_vehicle_from_msg() → { make: "Tata", model: "Nexon", year: None }
   car_label = "Tata Nexon"
   terrain detected: "highway" (Mumbai = city driving default)
   season = "all-season" (April, Mumbai)

5. Tyre search:
   stock_service.search_tyres(size="195/60R16", season="all-season", terrain="highway")
   → DB query → 5 results
   → brand diversity → top 3: [Apollo, MRF, Bridgestone]

6. Card generation:
   For each tyre:
     generate_personalised_msg.invoke({tyre, member_ctx, slot_type})  ← hardcoded template
   For top pick:
     generate_punch_line.invoke({tyre})  ← heuristic

7. LLM call (1 call):
   system = f"{_PERSONA} {_LANG_INSTRUCTION['Hindi']} Write ONE sentence handing over cards..."
   ctx = "Member: Rahul | Car: Tata Nexon | Size: 195/60R16 | Season: all-season"
   → Claude replies in Hinglish: "Rahul bhai, Tata Nexon ke liye 3 dum acche options nikale hain..."

8. Guardrail check:
   check_hallucination() ✓
   validate_fit() ✓
   redact_pii() ✓
   check_safety() ✓
   audit_bias() ✓

9. Response:
   { message: "Rahul bhai...", cards: [3 tyre cards], quick_replies: ["See details", "Compare"] }
```

---

## Key Architectural Decisions

| Decision | Why |
|----------|-----|
| **1 LLM call per message** | Lower cost ($0.003 vs $0.01+ per ReAct loop), faster (1 call vs 3–5), deterministic |
| **Python regex for intent routing** | Zero cost, zero latency; LLM fallback only for <1% of messages |
| **Vehicle→size map (400+ entries)** | Eliminates LLM call for car→tyre mapping; exact OEM sizes, no hallucination |
| **No vector DB** | 100-tyre catalogue with structured attributes; SQL WHERE clauses are faster, cheaper, and more accurate than ANN search |
| **Language detection via word lists** | Free, fast, zero LLM cost; covers Telugu/Tamil/Kannada/Hindi conjugation via morphological patterns |
| **Guardrail runs after LLM** | LLM focuses on tone; guardrail enforces facts separately |
| **DB + JSON hybrid** | PostgreSQL for production; JSON for local dev + regional Indian tyres that may not be in DB |
| **Cart TTL 15 min** | Balances UX vs stock waste |
| **Agents defined but not active** | Architecture ready to switch to full ReAct loop per agent; deterministic pipeline cheaper for MVP |
| **ElevenLabs optional** | Voice gracefully degrades; app fully functional without it |
| **Browser STT (Web Speech API)** | Zero cost; no server-side audio processing; only Chrome/Edge |

---

## Indexing & Data Access Patterns

### PostgreSQL indexes (from `scripts/init_db.py`)

```sql
-- Tyre search (most common query)
CREATE INDEX idx_tyres_size ON tyres(size);
CREATE INDEX idx_tyres_season ON tyres(season);
CREATE INDEX idx_tyres_terrain ON tyres(terrain);

-- Member lookup
CREATE INDEX idx_members_id ON members(member_id);

-- Appointment lookup
CREATE INDEX idx_appointments_booking ON appointments(booking_id);
CREATE INDEX idx_appointments_member ON appointments(member_id);
```

### JSON file access (fallback)

- Loaded from disk on every cold start, then cached in-memory for the session
- `tyres.json` — 100 entries, ~50KB, Python list in `_TYRE_CACHE`
- `users.json` — 50 members, ~30KB, Python dict keyed by `member_id`
- `locations.json` — ~20 locations, read with `encoding='utf-8'` (important: em-dash in location names)

### In-memory stores (runtime only, reset on restart)

```python
SESSION_STORE: dict[str, SessionState]    # keyed by session_id
CHAT_HISTORY:  dict[str, list[Message]]   # last 10 messages per session
_CARTS:        dict[str, Cart]            # 15-min TTL, in-memory
```

**Production note:** For multi-worker or persistent sessions, replace `SESSION_STORE` with Redis and `_CARTS` with a Redis sorted set (score = expiry timestamp).

---

## Quick Reference: File → Responsibility

| File | Layer | Uses LLM? | Uses DB? |
|------|-------|-----------|---------|
| `app/main.py` | Pipeline | ✅ 1 call/msg | ✅ via services |
| `agents/orchestrator.py` | Agent | ✅ (when active) | ✅ |
| `agents/rec_ranking_agent.py` | Agent | ✅ (when active) | ✅ |
| `agents/content_agent.py` | Agent | ✅ (when active) | ❌ |
| `agents/compare_agent.py` | Agent | ✅ (when active) | ❌ |
| `agents/appointment_agent.py` | Agent | ✅ (when active) | ✅ |
| `agents/guardrail_agent.py` | Agent | ❌ pure Python | ❌ |
| `services/profile_service.py` | Service | ❌ | ✅ |
| `services/stock_service.py` | Service | ❌ | ✅ |
| `services/cart_service.py` | Service | ❌ | ❌ (in-memory) |
| `services/payment_service.py` | Service | ❌ | ❌ (mock) |
| `services/voice_service.py` | Service | ❌ | ❌ |
| `services/dropoff_tracker.py` | Service | ❌ | ❌ |
| `services/eval_service.py` | Service | ❌ | ❌ |
| `tools/recommendation_tools.py` | Tool | ❌ (hardcoded) | ✅ |
| `tools/content_tools.py` | Tool | ❌ (hardcoded) | ❌ |
| `tools/guardrail_tools.py` | Tool | ❌ | ❌ |
| `tools/appointment_tools.py` | Tool | ❌ | ✅ |
| `db/connection.py` | DB | ❌ | ✅ |
| `dashboard/analytics_store.py` | Analytics | ❌ | ❌ (in-memory) |
