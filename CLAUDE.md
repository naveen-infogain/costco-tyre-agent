# Costco Tyre Agentic AI — Project Bible

## Overview
AI-powered tyre purchasing assistant for Costco members. The system guides members from login through tyre discovery, personalised recommendations, comparison, checkout, and appointment booking — using a multi-agent architecture built on LangChain + Claude.

**Target outcome:** 35%+ conversion rate with personalised, context-aware recommendations and frictionless booking.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Agent Framework | LangChain (`create_tool_calling_agent` + `AgentExecutor`) |
| LLM | `claude-sonnet-4-6` via `langchain-anthropic` |
| Memory | `ConversationBufferWindowMemory` (10-turn window, per session) |
| API | FastAPI + Uvicorn |
| UI | **React 18 + Vite** (port 5173) — separate `frontend/` folder |
| Legacy UI | `app/static/index.html` — still served at GET / but superseded by React |
| Mock Data | JSON files (tyres, users, locations, appointments) |
| Calendar | `icalendar` (.ics generation) |

### Dev Setup — Both servers must run together

```bash
# Terminal 1 — Backend
cd costco-tyre-agent
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY (required)
                              # add ELEVENLABS_API_KEY (optional — voice disabled if absent)
uvicorn app.main:app --reload  # http://localhost:8000

# Terminal 2 — Frontend
cd costco-tyre-agent/frontend
npm install
npm run dev                    # http://localhost:5173
```

> **Always use the React frontend at `http://localhost:5173`.**
> The Vite dev server proxies all `/chat`, `/feedback`, `/health`, `/demo-members`, `/voice`, `/dashboard` calls to FastAPI on port 8000 — no CORS config needed.

### Environment Variables (`.env`)
```
ANTHROPIC_API_KEY=sk-ant-...       # Required — app will not start without it
ELEVENLABS_API_KEY=...              # Optional — voice TTS disabled if absent
APP_ENV=dev                         # dev | prod
DB_HOST=localhost                   # Optional — falls back to JSON if DB unavailable
DB_PORT=5432
DB_NAME=costco_tyres
DB_USER=postgres
DB_PASSWORD=...
```

---

## Project Structure

```
costco-tyre-agent/
├── CLAUDE.md
├── app/                               # FastAPI backend (port 8000)
│   ├── main.py                        # FastAPI entry point + intent router
│   ├── agents/
│   │   ├── orchestrator.py            # Orchestrator Agent
│   │   ├── rec_ranking_agent.py       # Rec & Ranking Agent
│   │   ├── content_agent.py           # Content Agent
│   │   ├── compare_agent.py           # Compare Agent
│   │   ├── appointment_agent.py       # Appointment Agent
│   │   └── guardrail_agent.py         # Guardrail Agent (wraps all responses)
│   ├── services/
│   │   ├── profile_service.py         # Profile Service
│   │   ├── stock_service.py           # Stock Filter Service (DB + JSON hybrid)
│   │   ├── cart_service.py            # Cart Service
│   │   ├── payment_service.py         # Payment Service
│   │   ├── post_purchase_service.py   # Post-Purchase Service
│   │   ├── dropoff_tracker.py         # Drop-off Tracker + Rules Engine
│   │   └── eval_service.py            # Feedback Collector + Scorecard + Improvement Engine
│   ├── tools/
│   │   ├── profile_tools.py
│   │   ├── recommendation_tools.py
│   │   ├── content_tools.py
│   │   ├── compare_tools.py
│   │   ├── appointment_tools.py
│   │   └── guardrail_tools.py
│   ├── db/
│   │   └── connection.py              # psycopg2 pool, db_available(), JSON fallback
│   ├── dashboard/
│   │   ├── dashboard.py               # FastAPI routes for /dashboard
│   │   ├── analytics_store.py         # In-memory analytics aggregator
│   │   └── static/
│   │       └── dashboard.html         # Real-time dashboard UI
│   ├── data/
│   │   ├── tyres.json                 # Tyre catalogue (100 entries incl. Indian market)
│   │   ├── users.json                 # Member profiles + order history (50 members)
│   │   ├── locations.json             # Costco tyre centre locations
│   │   └── appointments.json          # Runtime booked appointments
│   ├── models/
│   │   └── schemas.py                 # Pydantic models
│   ├── logs/                          # Structured JSON logs (guardrail, errors, events)
│   └── static/
│       └── index.html                 # Legacy HTML chat UI (kept, served at GET /)
├── scripts/
│   ├── crm_to_json.py                 # CRM CSVs → tyres.json + users.json
│   └── init_db.py                     # PostgreSQL schema + CRM data loader
├── frontend/                          # React frontend (port 5173) ← PRIMARY UI
│   ├── package.json                   # React 18, Vite, jsPDF
│   ├── vite.config.js                 # Proxy /chat /feedback /health /voice /dashboard → :8000
│   └── src/
│       ├── App.jsx                    # Page router (signin → store → agent)
│       ├── index.css                  # All styles: MD3 tokens + all component CSS
│       ├── main.jsx
│       ├── hooks/
│       │   ├── useChat.js             # Session, sendMessage, processResponse, goBackToRecs
│       │   └── useVoice.js            # ElevenLabs TTS + Web Speech API STT
│       ├── pages/
│       │   ├── SignInPage.jsx         # First screen — member ID login + demo chips
│       │   ├── CostcoStorePage.jsx    # Costco store clone — browsing + Shop by Vehicle
│       │   └── AgentPage.jsx          # TireAssist AI chat page
│       └── components/
│           ├── SharedHeader.jsx       # Common header for Store + Agent pages
│           ├── ChatFeed.jsx           # Scrollable message feed (all message types)
│           ├── ChatInput.jsx          # Textarea + mic + send pill
│           ├── QuickReplies.jsx       # Quick reply chips (greyed after use)
│           ├── RecoveryBanner.jsx     # Drop recovery banner
│           └── cards/
│               ├── TyreCard.jsx       # Individual tyre card (active/inactive state)
│               ├── CardsGrid.jsx      # Cover-flow carousel of TyreCards
│               ├── DetailActions.jsx  # Add to Cart + Back buttons after detail view
│               ├── CompareCard.jsx    # Side-by-side comparison table
│               ├── SlotPicker.jsx     # Appointment slot chips
│               └── BookingCard.jsx    # Booking confirmation + jsPDF download
├── requirements.txt
└── .env.example
```

---

## React Frontend Architecture

The React app lives entirely in `frontend/`. It is **decoupled** from the backend — all it does is POST to `/chat` and `/feedback`, and render what the API returns.

### Page Flow

```
SignInPage  →  CostcoStorePage  →  AgentPage
   (default)       (after login)      (via toggle or Shop by Vehicle)
```

- `App.jsx` holds `page` state (`'signin' | 'store' | 'agent'`), `member` state (`{ id, name }`), and `initialVehicle` context.
- `useChat()` is instantiated in `App.jsx` and passed as `chatState` prop to `AgentPage`, so the chat session persists when toggling between Store and Agent pages.

### Pages

**`SignInPage.jsx`**
- Split panel: blue left (branding + member perks) / white right (form)
- Input: member ID (format `M10001`–`M99999`)
- On sign-in: POSTs member ID to `/chat`, extracts name from welcome message via regex, navigates to Store
- Demo chips: loaded dynamically from `GET /demo-members`; fallback hardcoded list

**`CostcoStorePage.jsx`**
- Visual clone of tires.costco.com layout
- Uses `SharedHeader` (with "Actual Site" toggle active)
- "Shop by Vehicle" form (Year / Make / Model dropdowns) → navigates to AgentPage with vehicle context pre-filled as first message
- Tyre category cards, featured tyre grid, brand strip — all static/mock data

**`AgentPage.jsx`**
- Dark background (`agent-bg`) + floating white card (`agent-card`, max-width 680px)
- Uses `SharedHeader` (with "Agentic Agent" toggle active)
- Title: "Meet TireAssist, Your AI Executive Assistant" — full 2-line on empty state, collapses to compact single line after first message
- Wires `useVoice` for mic (STT) and TTS
- `initialVehicle` sent via `useEffect` with 400ms delay + `vehicleSentRef` guard (prevents double-send)

### SharedHeader (`components/SharedHeader.jsx`)
- Shared by both Store and Agent pages
- Left: Costco logo mark + "Costco Wholesale" wordmark
- Center: Toggle pill — "Agentic Agent" | "Actual Site" (active = blue-purple gradient)
- Center-right: Stage pill (agent page only, shows current conversation stage)
- Right: Member avatar chip (initials + name + ID) + Cart button

### Chat Hook (`hooks/useChat.js`)

Key state and functions:
- `messages` — array of typed messages rendered by `ChatFeed`
- `stage` — current pipeline stage from backend response
- `sendMessage(text)` — POSTs to `/chat`, calls `processResponse`, auto-injects `detail_actions` message after a details request
- `goBackToRecs()` — re-appends the most recent `cards` message to the feed (used by Back button)
- `sendFeedback(signal, tyreId, agent)` — POSTs to `/feedback`
- `handleLoginResponse(data)` — called by App after sign-in to seed the first welcome message

**Message types** handled by `ChatFeed`:
| type | Component | Notes |
|------|-----------|-------|
| `bot` | `BotBubble` | Gray rounded bubble |
| `user` | `UserBubble` | Blue-purple gradient bubble |
| `cards` | `CardsGrid` | Cover-flow carousel |
| `detail_actions` | `DetailActions` | Add to Cart + Back buttons |
| `quickreplies` | `QuickReplies` | Chips, greyed after use |
| `slots` | `SlotPicker` | Appointment slot chips |
| `booking` | `BookingCard` | Confirmation + jsPDF download |
| `recovery` | `RecoveryBanner` | Drop recovery prompt |

### Tyre Recommendation Carousel (`components/cards/CardsGrid.jsx`)

- **Cover-flow carousel** — no arrow buttons; click a side card to bring it to centre
- `activeIdx` state (default `0` = Top Pick at centre)
- `posClass(idx)` maps distance from activeIdx to CSS class:
  - `cc-center` — hero card, full scale, drop-shadow
  - `cc-left1` / `cc-right1` — adjacent cards, 86% scale, 72% opacity
  - `cc-left2` / `cc-right2` — far cards, 72% scale, 38% opacity, pointer-events none
- Dot indicators below for navigation
- "Compare side by side" toggle below dots → shows `CompareCard`

**`TyreCard.jsx`** — `active` prop:
- `active=true` (centre card): shows Add to Cart, Details, thumbs up/down buttons
- `active=false` (side cards): hides action buttons, shows "Tap to view" hint

### Detail View Flow

When user clicks "Details" on a card:
1. `handleDetails(tyreId, slotTag)` in CardsGrid calls `onSendMessage("I'd like to view details for the {slotTag} option ({tyreId})")`
2. `useChat.sendMessage` detects the details pattern via regex → sets `detailContextRef`
3. Bot responds with detail text (rendered as `BotBubble`)
4. `useChat` auto-injects a `detail_actions` message: `{ type: 'detail_actions', tyreId, slotTag }`
5. `DetailActions` component renders two buttons:
   - **Add to Cart** → `sendMessage("add to cart {tyreId}")`
   - **Back to Recommendations** → `goBackToRecs()` re-appends the carousel

### Voice (`hooks/useVoice.js`)

- Checks `/voice/status` on mount — disables voice UI if `ELEVENLABS_API_KEY` not set
- STT: Web Speech API (`SpeechRecognition`) — mic button toggles listening
- TTS: POST to `/voice/tts` (ElevenLabs stream) — speaker button reads last bot response
- Mic button shows disabled state if voice not available

### CSS Architecture (`src/index.css`)

Single file, organised by section with ASCII dividers:
- MD3 design tokens (`:root` CSS variables — `--md-sys-color-*`, `--md-elevation-*`, `--md-sys-shape-*`)
- Costco brand colours (`--cs-blue: #005CA9`, `--cs-red: #E31837`)
- Sign-in page (`.signin-*`)
- Store page (`.cs-*`)
- Shared header (`.sh-*`)
- Agent page (`.agent-*`, `.ta-*` for TireAssist components)
- Tyre cards (`.tyre-card`, `.card-*`, `.slot-tag`, `.price-row`, etc.)
- Carousel (`.cc-*`)
- Detail actions (`.detail-actions`)
- Compare card (`.compare-*`)
- Booking card, slot picker, recovery banner

---

## Pending Tasks for Next Developer

### Task 5 — Voice Integration End-to-End
- `useVoice.js` hook is fully wired; only needs `ELEVENLABS_API_KEY` in `.env`
- Test: mic button → speech → `sendMessage` → bot response → TTS reads it aloud
- ElevenLabs voice ID configured via `ELEVENLABS_VOICE_ID` env var

### Task 6 — Checkout & Payment Flow (UI side)
- "Add to Cart" currently sends `add to cart {tyreId}` as a chat message
- The backend cart/payment pipeline already handles this
- **TODO:** Build a proper cart drawer/page in React:
  - Show cart items, quantity, member pricing, savings
  - Costco Visa auto-detect + cashback display
  - Confirm order → triggers appointment booking flow

### Task 7 — Appointment Booking UI Polish
- `SlotPicker.jsx` renders appointment slots as chips — works but basic
- **TODO:** Calendar-style slot picker (date tabs + time grid)
- Show predicted wait time per slot (from `predict_wait_times` backend)
- After booking: `BookingCard` shows confirmation + `.ics` download

### Task 8 — Mobile Responsive Polish
- Breakpoints exist at 768px in CSS
- **TODO:** Test on mobile viewport, especially the carousel (may need swipe gesture support)
- Swipe on `cc-wrapper` → advance `activeIdx` (use `onTouchStart`/`onTouchEnd` in CardsGrid)

### Task 9 — Dashboard Integration
- `GET /dashboard` serves `app/dashboard/static/dashboard.html` (plain HTML, existing)
- **TODO:** Optionally embed or link dashboard from SharedHeader or a new "Admin" page in React

---

## Agent Roster

### 1. Orchestrator Agent (`agents/orchestrator.py`)
**Entry point for every member session.**
- Authenticates member via `load_member_session()`
- Detects user type: returning (has tyre history) vs new buyer
- Routes to Path A or Path B
- Handles conversational preference collection (chat-based, not form-based)
- Manages overall conversation state and agent handoffs
- Collects: car type, tyre size, season, terrain, climate (auto-detected)

**Tools:** `load_member_session`, `detect_user_type`, `collect_preferences`, `auto_detect_climate`, `route_to_agent`

---

### 2. Profile Service (`services/profile_service.py`)
**Fetches member identity and purchase history.**
- `get_last_purchased_tyre(member_id)` → SKU, date, mileage
- `get_vehicle_history(member_id)` → all vehicles on record
- `load_member_preferences(member_id)` → driving habits, location, tier

---

### 3. Rec & Ranking Agent (`agents/rec_ranking_agent.py`)
**Core recommendation engine — runs in both paths.**

**Path A (returning):**
- `get_tyre_details(last_SKU)` — fetch exact last tyre
- `search_tyres(similar)` — find 2 alternatives
- Rank by: **repurchase fit**, upgrade value, popularity, **rating delta** (improvement since last purchase)
- Flag if last tyre is discontinued or has had a price change
- Tag picks: Best Repurchase / Best Upgrade / Most Popular

**Path B (new buyer):**
- `search_tyres(full_criteria)` — Vector DB + catalogue query
- Rank by multi-signal scoring:
  - Upgrade value
  - Regional popularity (trending near member)
  - Rating + sentiment
  - Value (price vs tread life)
  - Safety (load/speed/wet grip)
- Enforce diversity: each of top 3 leads a different signal
- `select_top_pick(ranked_list)` → #1 pick
- `generate_punch_line(tyre)` → bold, catchy one-liner for Top Pick

**Tools:** `search_tyres`, `get_tyre_details`, `rank_tyres`, `select_top_pick`, `generate_punch_line`, `broaden_search`, `handle_no_results`

---

### 4. Stock Filter Service (`services/stock_service.py`)
**Runs after every recommendation batch.**
- `check_stock(top_picks, member_location)` — queries stock per location
- Removes out-of-stock tyres from results
- Replaces with next best in-stock alternative
- Attaches stock badge: `✅ In stock at [nearest warehouse]`

---

### 5. Content Agent (`agents/content_agent.py`)
**Generates personalised message for each tyre slot.**

**Path A messages:**
- Best Repurchase: loyalty + price/value personalisation
- Best Upgrade: improvement delta vs member's current tyre
- Most Popular: regional social proof for member's vehicle type

**Path B messages:**
- Top Pick: personalised benefit for member's specific use case
- Runner-up: alternative angle tailored to member
- Budget alt: savings narrative personalised to member tier

**Tool:** `generate_personalised_msg(tyre, member_context, slot_type)`

---

### 6. Compare Agent (`agents/compare_agent.py`)
**Path B only — shown as a toggleable card.**
- Side-by-side comparison: price, tread life, noise, warranty, wet grip
- AI-generated pros/cons summary per tyre
- Total cost of ownership calculation
- Simplified from 5 columns → 3 columns (v33 improvement)

**Tool:** `generate_comparison_card(tyre_list, member_context)`

---

### 7. Appointment Agent (`agents/appointment_agent.py`)
**Runs after payment confirmation.**
- `get_nearby_locations(member_location)` → ranked Costco tyre centres
- `get_available_slots(location_id, date_range)` → open slots
- Smart suggest: least-busy slot within next 3 days
- `book_appointment(member_id, order_id, location_id, slot)` → confirmation
- `create_calendar_event(appointment)` → .ics file + email + push notification

**Tools:** `get_nearby_locations`, `get_available_slots`, `predict_wait_times`, `suggest_best_slot`, `book_appointment`, `link_order_to_booking`, `create_calendar_event`

> `predict_wait_times(location_id, slot)` — estimates install duration based on historical data to surface accurate wait time on Order Complete screen.

---

### 8. Guardrail Agent (`agents/guardrail_agent.py`)
**Wraps EVERY AI-generated response before it reaches the member.**
- Hallucination check (verify all tyre specs against catalogue)
- Tyre-vehicle fit validation (size/load/speed compatibility)
- PII redaction (no personal data in responses)
- Safety check (load index and speed rating meet vehicle requirements)
- Bias audit (no single brand dominating recommendations unfairly)

**Rule:** If guardrail fails → regenerate response, log violation, never surface raw failure to member.

---

## Supporting Services

### Cart Service (`services/cart_service.py`)
- `add_to_cart(member_id, tyre_id)`
- Reserve stock for 15-minute TTL
- Validate tyre-vehicle fit
- Apply member pricing, coupons, promotions
- Bundle suggestions: alignment, valve stems
- Return itemised price breakdown + savings

### Payment Service (`services/payment_service.py`)
- `process_payment(member_id, cart_id)`
- Auto-detect Costco Visa card
- Apply cashback rewards
- Generate order ID
- On failure → surface friendly error, preserve cart

### Post-Purchase Service (`services/post_purchase_service.py`)
- Day-before installation reminder (SMS)
- Install-complete alert
- 30-day satisfaction survey
- Collect rating + review → write back to profile
- Tyre rotation cron reminders (every 10,000km)
- Seasonal swap alerts
- Re-engage at predicted wear-out date

### Drop-off Tracker (`services/dropoff_tracker.py`)
- Log every stage transition with timestamp
- Detect: idle >2min, tab switch, exit intent
- Drop Rules Engine:
  - Price shock → show member savings vs retail
  - Overload → simplify to 1 pick only
  - Too long → offer express checkout
  - Confused → open live chat
  - Left site → recovery email in 1 hour
- Feed funnel analytics: stage-by-stage drop rates, cohort breakdowns

---

## User Flows

### Path A — Returning Buyer
```
Member Login
  → load_member_session() + detect_user_type() → "returning"
  → Profile Service: get_last_purchased_tyre() + get_vehicle_history()
  → Rec & Ranking: last SKU + 2 alternatives (Repurchase / Upgrade / Popular)
  → Stock Filter: remove OOS, badge in-stock
  → Content Agent: personalised msg per slot
  → PRESENT 3 OPTIONS (+ thumbs 👍👎)
      │
      ├─ 👍 Picks one ──→ [SHARED FLOW: Detail → Done]
      ├─ 👎 No        ──→ Orchestrator collects preferences → Path B Discovery
      └─ DROP         ──→ Drop-off Tracker
```

### Path B — New Buyer / Discovery
```
Member Login (or redirected from Path A)
  → Orchestrator: chat-collect (car type, size, season, terrain, climate)
      [on wrong input: validate → suggest_corrections() → re-ask, max 3 retries]
  → Rec & Ranking: search_tyres(full_criteria) → multi-signal rank → top 3
      [on 0 results: broaden_search() → relax terrain → relax season → handle_no_results()]
  → Stock Filter: remove OOS
  → Content Agent: Top pick / Runner-up / Budget msg
  → Compare Agent: side-by-side card (toggleable)
  → PRESENT RANKED RESULTS (+ thumbs 👍👎 + comparison toggle)
      │
      ├─ Picks one    ──→ [SHARED FLOW: Detail → Done]
      ├─ Refine       ──→ back to preference collection
      └─ DROP         ──→ Drop-off Tracker
```

### Shared Flow: Detail → Done
```
Tyre Detail Page
  (specs, member price, savings, stock, reviews, warranty, install info)
  → Add to cart?
      ├─ YES → Cart Service (15min stock reserve, fit check, coupons, bundles)
      ├─ Back → [Came from Path A? → Return to E_PRESENT]
      │         [Came from Path B? → Return to S_PRESENT]
      └─ DROP → Drop-off Tracker

  → Confirm Checkout?
      ├─ Confirm → Payment Service (Costco Visa, cashback, order ID)
      ├─ Cancel  → [Came from Path A? → Return to E_PRESENT]
      │            [Came from Path B? → Return to S_PRESENT]
      └─ DROP → Drop-off Tracker

  → Appointment Agent
      → get_nearby_locations() → get_available_slots() → predict_wait_times()
      → Smart suggest: least-busy slot in next 3 days
      → Member picks slot
      → book_appointment() → link_order_to_booking() → create_calendar_event()
  → ORDER COMPLETE
      ✔ Booking ID
      ✔ Calendar invite (.ics + email + push notification)
      ✔ Install time estimate (from predict_wait_times)
      ✔ What-to-bring checklist
      ✔ Live wait-time link
  → Post-Purchase Service (SMS reminder, survey, profile write-back, rotation cron, re-engage)
  → [On member's NEXT VISIT] → loops back to Orchestrator (load_member_session)
```

---

## Error Handling Rules

| Scenario | Response |
|----------|----------|
| Invalid car make/model | `validate_car_type()` → `suggest_corrections()` → re-ask (max 3x) |
| Invalid tyre size format | Show example format (e.g. 205/55R16) → re-ask |
| 0 search results | `broaden_search()`: relax terrain first, then season |
| Still 0 after broadening | `handle_no_results()` → friendly message → restart collection |
| Stock runs out mid-session | Cart TTL expires → notify member → re-check stock |
| Payment failure | Preserve cart → surface friendly error → retry option |
| Guardrail failure | Regenerate silently → log violation → never show raw error |
| Drop detected | Drop Rules Engine → contextual recovery action |

---

## Mock Data Schemas

### `data/tyres.json` — each entry
```json
{
  "id": "MIC-PRIM4-20555R16",
  "brand": "Michelin",
  "model": "Primacy 4",
  "size": "205/55R16",
  "load_index": 91,
  "speed_rating": "V",
  "season": "all-season",
  "terrain": "highway",
  "price": 189.99,
  "member_price": 169.99,
  "tread_life_km": 80000,
  "wet_grip": "A",
  "noise_db": 68,
  "rating": 4.8,
  "review_count": 1240,
  "warranty_years": 5,
  "compatible_vehicles": ["Toyota Camry 2018-2023", "Honda Accord 2017-2022"],
  "stock": {"warehouse_id": "W001", "qty": 24},
  "active_promotion": "Save $20 on set of 4"
}
```

### `data/users.json` — each entry
```json
{
  "member_id": "M10042",
  "name": "Sarah Chen",
  "membership_tier": "executive",
  "location": {"city": "Seattle", "zip": "98101"},
  "vehicle": {"make": "Toyota", "model": "Camry", "year": 2020},
  "driving_habits": ["highway", "daily commute"],
  "last_purchase": {
    "tyre_id": "BRI-TUR-20555R16",
    "date": "2024-09-15",
    "mileage_at_purchase": 34200
  }
}
```

### `data/locations.json` — each entry
```json
{
  "id": "W001",
  "name": "Costco Tyre Centre — Seattle Northgate",
  "address": "401 NE Northgate Way, Seattle WA 98125",
  "lat": 47.706,
  "lng": -122.325,
  "hours": "Mon-Fri 10am-8:30pm, Sat-Sun 9:30am-6pm",
  "avg_wait_mins": 35
}
```

---

## Coding Conventions

- All agent classes extend `BaseAgent` with a standard `run(input, session_id)` method
- Tools are defined with `@tool` decorator from LangChain
- Every agent response passes through `GuardrailAgent.check(response)` before being returned
- Session state stored in `SessionStore` (in-memory dict keyed by `session_id`)
- Mock services return realistic data; all functions are designed to be swapped for real APIs
- No global state — all context passed explicitly through agent inputs
- Errors logged to `app/logs/` with structured JSON format
- Environment variables: `ANTHROPIC_API_KEY`, `APP_ENV` (dev/prod)

---

## Code Documentation Standards

These rules apply to **every file** in this project. Use the `/document` skill to apply them to any file.

---

### 1. File-level module docstring (top of every `.py` file)

```python
"""
Module: <filename>
Purpose: <one-line description of what this module does>
Layer: agent | service | tool | model | dashboard | main
Dependencies:
  - <package or internal module>: <why it's used>
Production notes:
  - Env vars required: ANTHROPIC_API_KEY, APP_ENV
  - Rate limits: <any known limits>
  - Swap points: <what to replace when going from mock → real>
"""
```

---

### 2. API call comment block (directly above every external API call)

Every call to Anthropic, ElevenLabs, or any third-party API must have this block:

```python
# ── External API Call ────────────────────────────────────────────────────
# Service:    Anthropic Claude  (claude-sonnet-4-6)
# Endpoint:   POST https://api.anthropic.com/v1/messages
# Auth:       ANTHROPIC_API_KEY (required in .env)
# Params:     max_tokens=1024, temperature=0
# Rate limit: ~60 req/min on Tier 1 — back off on 429
# Latency:    ~800ms p50 / ~2s p99
# Cost:       ~$0.003 per call (1K in + 1K out tokens, sonnet pricing)
# Fallback:   Returns "" — caller must handle empty response gracefully
result = get_llm().invoke(messages)
```

For ElevenLabs TTS:
```python
# ── External API Call ────────────────────────────────────────────────────
# Service:    ElevenLabs TTS  (eleven_turbo_v2_5)
# Endpoint:   POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream
# Auth:       ELEVENLABS_API_KEY (optional — voice disabled if missing)
# Params:     voice_id from .env, model_id=eleven_turbo_v2_5
# Rate limit: Depends on plan (free = 10k chars/month)
# Latency:    ~300ms first chunk (streaming)
# Fallback:   Returns 503 if ELEVENLABS_API_KEY not set
async for chunk in text_to_speech_stream(text):
    yield chunk
```

---

### 3. Function / method docstring (Google style)

Every non-trivial function must have:

```python
def function_name(param1: str, param2: int = 4) -> dict:
    """
    One-line summary of what the function does.

    Longer explanation if the logic is non-obvious. Describe the business
    rule, the algorithm, or the edge cases handled here.

    Args:
        param1: Description including valid values or format constraints.
        param2: Description. Defaults to 4 (one set of tyres).

    Returns:
        Dict with keys: cart_id (str), subtotal (float), member_savings (float).
        Returns {"error": "<reason>"} on failure — never raises.

    Side effects:
        Writes to _CARTS in-memory dict. Stock reservation lasts 15 minutes.

    Example:
        result = add_to_cart("M10042", "MIC-PRIM4-20555R16", quantity=4)
        # {"cart_id": "uuid", "subtotal": 679.96, ...}
    """
```

---

### 4. Section divider comments (inside long files)

Long files (>100 lines) use ASCII dividers to delineate logical sections:

```python
# ---------------------------------------------------------------------------
# Section Name — brief description of what this block does
# ---------------------------------------------------------------------------
```

---

### 5. Inline comments — when to add, when not to

**Add** inline comments for:
- Non-obvious business logic: `# Soft pass — compatibility list is not exhaustive`
- Magic numbers/constants: `_CART_TTL_SECS = 15 * 60  # 15 minutes — matches stock reservation window`
- Regex patterns: `# Matches member IDs: M10042 – M99999`
- Fallback / recovery logic: `# Guardrail failed — fall back to raw response to avoid silent empty reply`

**Do NOT add** inline comments for:
- Self-evident code (`i += 1  # increment i`)
- Restating the variable name (`member_id = req.member_id  # get member id`)
- Every line in a simple loop or list comprehension

---

### 6. Production startup block (in `app/main.py` only)

The FastAPI app startup section must document the full production checklist:

```python
# ============================================================================
# PRODUCTION STARTUP CHECKLIST
# ============================================================================
# Required environment variables:
#   ANTHROPIC_API_KEY  — Claude API key (mandatory — app will not start without)
#   ELEVENLABS_API_KEY — ElevenLabs TTS key (optional — voice disabled if absent)
#   APP_ENV            — "dev" (default) | "prod" (enables CORS restrictions)
#   LOG_LEVEL          — "INFO" (default) | "DEBUG" | "WARNING"
#
# Start command (dev):
#   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
#
# Start command (prod):
#   APP_ENV=prod uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000
#
# Health check:
#   GET http://localhost:8000/health → {"status": "ok", "version": "0.33.0"}
#
# Key endpoints:
#   GET  /             → Chat UI (app/static/index.html)
#   POST /chat         → Main pipeline — 1 LLM call per message
#   POST /feedback     → Thumbs up/down signal collection
#   POST /voice/tts    → ElevenLabs TTS stream (requires ELEVENLABS_API_KEY)
#   GET  /dashboard    → Live analytics dashboard
#   GET  /dashboard/api → Analytics JSON (funnel, scorecard, alerts)
#
# Architecture: Python pipeline → 1 LLM call → GuardrailAgent (pure Python)
# No ReAct loop. LLM is called ONCE per /chat request for response text only.
# All data operations (search, rank, stock, cart, payment) are pure Python.
#
# Session state: in-memory dict (resets on server restart — by design for demo)
# Logs: app/logs/guardrail.json, feedback.json, funnel.json
# ============================================================================
```

---

### 7. TODO / FIXME tags (structured format)

```python
# TODO(owner): Short description — linked to sprint/ticket if applicable
# FIXME: Critical bug — describe the symptom and reproduction steps
# HACK: Explain why this workaround exists and what the real fix would be
# NOTE: Important context that reviewers must understand before changing this
```

---

### Applying standards with the `/document` skill

Run `/document <filename>` to have Claude audit and apply all documentation standards to any file in the project. The skill checks for missing module docstrings, undocumented API calls, missing function docstrings, and misformatted section dividers.

---

## Drop-off Tracking & Recovery (`services/dropoff_tracker.py`)

### Session Tracker
- Logs every stage transition with timestamp and session context
- Detects: idle >2min, tab switch, exit intent
- Stages tracked: Enter → Browse → Detail → Cart → Pay → Book → Complete

### Drop Rules Engine
Fires automatically when a drop signal is detected:

| Drop Signal | Recovery Action |
|-------------|----------------|
| Price shock (cart value jump) | Show member savings vs retail price |
| Overload (>3 refinements) | Simplify to 1 pick only — hide alternatives |
| Session too long (>8 min) | Offer express checkout flow |
| Confused (repeated back-navigation) | Open live chat widget |
| Left site | Recovery email triggered in 1 hour |

### Funnel Analytics
- Stage-by-stage drop rates logged per session
- Cohort breakdown: returning buyer vs new buyer
- Weekly trend dashboard auto-generated
- PM alert triggered if drop rate exceeds threshold

---

## Agent Evaluation & Improvement (`services/eval_service.py`)

### Feedback Loops (4 sources → Feedback Collector)

All four feed `eval_service.collect_feedback()` continuously:

| Source | Signal type | What is captured |
|--------|-------------|-----------------|
| E_PRESENT (Path A results) | Implicit + Explicit | Which slot picked, thumbs on suggestions + personalised msg |
| S_PRESENT (Path B results) | Implicit + Explicit | Which slot picked, which signal won, thumbs on suggestions + msg + compare card |
| Appointment Agent | Implicit | Slot accepted vs changed by member |
| Orchestrator | Implicit | Routing accuracy — correct Path A/B detection rate |

### Feedback Collector
**Implicit signals (from member actions):**
- Which option was picked (slot 1 / 2 / 3)
- Which ranking signal won (Repurchase / Upgrade / Popular / Value / Safety)
- NO rate and refine rate per session
- Checkout cancel rate

**Explicit signals (thumbs ratings):**
- 👍👎 on each tyre suggestion
- 👍👎 on each personalised message
- 👍👎 on comparison card
- Appointment slot: accepted vs changed

### Agent Scorecard (v33 Baseline)

| Agent | Score | Trend | Status |
|-------|-------|-------|--------|
| Guardrail | 86 | +3 | ✅ On target |
| Rec & Ranking | 78 | +4 | ✅ On target |
| Compare | 74 | +4 | ✅ On target |
| Content | 71 | +8 | ✅ On target |
| Appointment | 69 | -2 | ⚠️ Under review |
| Orchestrator | 67 | +5 | ✅ On target |

**Overall conversion: 35.2% (+2.1%)**

### Improvement Engine

**Deployed in v33:**
- Rec: popularity weight +8% → +3.2% pick rate
- Content: benefit-first messages → +12% CTR
- Compare: 5 columns → 3 columns → +5% open rate
- Guardrail: false positive fix → -40% false blocks

**Currently A/B Testing:**
- Rec: safety weight increase for SUVs
- Appointment: morning slot bias
- Content: emoji-enhanced messages
- Compare: bar charts vs numeric values

**Queued for next sprint:**
- Guardrail: brand diversity enforcement
- Rec: tread warranty as ranking factor
- Content: seasonal message variants

### Agent Evolution Tracker (v31 → v32 → v33)

| Agent | v31 | v32 | v33 | Key Change |
|-------|-----|-----|-----|------------|
| Rec & Ranking | 68 | 74 | 78 | basic search → multi-signal → diversity enforced |
| Content | 58 | 63 | 71 | generic hook → benefit-first → personalised |
| Compare | 65 | 70 | 74 | 5-col table → 3-col + cost/mile → AI pros/cons |
| Appointment | 65 | 71 | 69 ⚠️ | random slot → smart suggest → regression, rollback queued |
| Guardrail | 80 | 83 | 86 | basic checks → load rating → bias audit added |
| Orchestrator | 55 | 62 | 67 | form-based → chat-based → climate auto-detect |

### Improvement Engine → Agent Tuning Targets

Deployed improvements feed back into specific agents:

| Improvement type | Tunes |
|-----------------|-------|
| Ranking prompts & weights | Rec & Ranking Agent (Path A) |
| Search prompts & weights | Rec & Ranking Agent (Path B) |
| Personalised message prompts | Content Agent (Path A + Path B) |
| Comparison card format | Compare Agent |
| Slot suggestion logic | Appointment Agent |
| Intent routing logic | Orchestrator |
| Check thresholds + bias rules | Guardrail Agent |

### Review Cadence
- **Daily** — auto-deploy A/B test winners
- **Weekly** — review low-scored agent responses
- **Monthly** — full agent behavior audit
- **Quarterly** — model upgrade evaluation
- **Per version** — evolution report + rollback decisions

---

## Live Dashboard (`app/dashboard/`) — v33

The dashboard is a read-only web view fed by the analytics pipeline. It updates in real-time.

### Funnel View
```
Enter    → 10,000  (100%)
Browse   →  8,200  ( 82%)
Detail   →  6,100  ( 61%)
Cart     →  4,800  ( 48%)
Pay      →  4,100  ( 41%)
Book     →  3,700  ( 37%)
Complete →  3,500  ( 35%)
─────────────────────────
Conversion: 35.2% ↑ +2.1%
```

### Agent Rankings Panel
Live scorecard fed from `eval_service.scorecard`. Alerts fire when any agent drops below target.

### Improvement Tracker Panel
- Count of deployed improvements this month: 9
- Active A/B tests: 4
- Queued for next sprint: 3
- Top impact items highlighted

### Drop-off Alerts Panel

| Stage | Current | Threshold | Status |
|-------|---------|-----------|--------|
| Preferences | 12% | < 15% | ✅ |
| Browse options | 28% | < 25% | ⚠️ ACTION NEEDED |
| Detail view | 14% | < 15% | ✅ |
| Checkout | 13% | < 15% | ✅ |
| Payment | 3% | < 5% | ✅ |
| Scheduling | 8% | < 10% | ✅ |

### Dashboard Data Flow
```
Funnel Analytics  ──→  Funnel View panel
Agent Scorecard   ──→  Agent Rankings panel
Improvement Engine──→  Improvement Tracker panel
Drop Rules Engine ──→  Drop-off Alerts panel
```

### Dashboard Files
```
app/dashboard/
├── dashboard.py        # FastAPI routes for /dashboard
├── analytics_store.py  # In-memory analytics aggregator
└── static/
    └── dashboard.html  # Real-time dashboard UI
```
