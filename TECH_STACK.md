# Costco Tyre Agent — Technology Stack

---

## Overview

| Category | Count |
|----------|-------|
| AI Agents | 6 |
| Backend Services | 7 |
| LangChain Tool Sets | 6 |
| External APIs | 3 (Anthropic, ElevenLabs, PostgreSQL) |
| Frontend Libraries | 3 (React, Vite, jsPDF) |

---

## Frontend

| Technology | Version | Purpose |
|-----------|---------|---------|
| **React** | 18 | UI framework — component tree, state, hooks |
| **Vite** | latest | Dev server + bundler; proxies all API calls to FastAPI on port 8000 |
| **jsPDF** | latest | Client-side PDF generation for booking confirmation invoice download |
| **Material Symbols** | Google CDN | Icon font used throughout the UI |
| **CSS (index.css)** | — | Single-file stylesheet using MD3 design tokens (CSS variables) |

### Frontend Pages

| Page | File | Description |
|------|------|-------------|
| Sign In | `SignInPage.jsx` | Member ID login, demo member chips |
| Store | `CostcoStorePage.jsx` | Costco store clone, Shop by Vehicle |
| Agent Chat | `AgentPage.jsx` | TireAssist AI chat interface |

---

## Voice Pipeline

```
User speaks  ──→  [Web Speech API]  ──→  Text  ──→  /chat  ──→  Bot response
                   (STT, browser)                              ──→  [ElevenLabs]  ──→  Audio
                                                                     (TTS, cloud)
```

### Speech-to-Text (STT)

| Property | Value |
|----------|-------|
| **Technology** | Web Speech API (`window.SpeechRecognition`) |
| **Provider** | Browser-native (Chrome, Edge) |
| **Cost** | Free — no API key, no server calls |
| **Latency** | ~0ms (runs in browser) |
| **Language** | en-US (configurable) |
| **Implementation** | `frontend/src/hooks/useVoice.js` — `buildRecognition()` |
| **Notes** | Fresh instance per utterance (prevents stale-state restarts). `interimText` shown live in textarea. Not supported on Firefox/Safari. |

### Text-to-Speech (TTS)

| Property | Value |
|----------|-------|
| **Technology** | ElevenLabs Streaming TTS |
| **Model** | `eleven_turbo_v2_5` (default) — ~300ms time-to-first-chunk |
| **Voice** | Rachel (`21m00Tcm4TlvDq8ikWAM`) — configurable via `ELEVENLABS_VOICE_ID` |
| **Cost** | ~$0.30 per 1,000 chars (Creator plan) |
| **Rate limit** | Free = 10k chars/month; Creator = 100k chars/month |
| **Endpoint** | `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream` |
| **Auth** | `ELEVENLABS_API_KEY` env var (optional — voice disabled if absent) |
| **Implementation** | `app/services/voice_service.py` + `frontend/src/hooks/useVoice.js` |
| **Trigger** | Auto-plays after mic input. Manual download button triggers PDF only. |
| **Text prep** | `_humanise_for_tts()` — strips markdown, converts lists to prose, expands abbreviations, converts prices to spoken form, removes tyre ID codes, removes emojis |
| **Safety gate** | `_BLOCKED_PATTERNS` regex blocks inappropriate language before API call |

### Voice Flow (end-to-end)

```
1. User taps mic button
2. Web Speech API starts listening (fresh instance)
3. Interim transcript shown live in textarea (italic)
4. Final transcript → sendMessage() called
5. voiceInputRef = true (marks this as a voice-triggered message)
6. Frontend rewrites if needed:
     - Natural date/time → "Book the slot on YYYY-MM-DD at HH:MM"
     - Positive intent + tyre in focus → "add to cart {tyreId}"
     - "download" + booking confirmed → generateBookingPDF() (no backend call)
7. POST /chat → backend pipeline → response text
8. Auto-TTS: lastBotText change detected → speakLastResponse() called
9. ElevenLabs streams MP3 → browser plays
10. Input bar shows animated wave dots while TTS plays
```

---

## Backend

| Technology | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.11+ | Runtime language |
| **FastAPI** | latest | REST API framework |
| **Uvicorn** | latest | ASGI server |
| **LangChain** | latest | Agent framework (`create_tool_calling_agent` + `AgentExecutor`) |
| **langchain-anthropic** | latest | Claude LLM integration |
| **httpx** | latest | Async HTTP client — ElevenLabs TTS streaming |
| **psycopg2-binary** | latest | PostgreSQL connection pool |
| **python-dotenv** | latest | `.env` file loading |
| **icalendar** | latest | `.ics` calendar invite generation |
| **Pydantic** | v2 | Request/response schema validation |

---

## AI / LLM

| Property | Value |
|----------|-------|
| **Model** | `claude-sonnet-4-6` |
| **Provider** | Anthropic |
| **Integration** | `langchain-anthropic` (`ChatAnthropic`) |
| **Endpoint** | `POST https://api.anthropic.com/v1/messages` |
| **Auth** | `ANTHROPIC_API_KEY` env var (required) |
| **Cost** | ~$0.003 per call (1K in + 1K out tokens, Sonnet pricing) |
| **Rate limit** | ~60 req/min on Tier 1 — backs off on 429 |
| **Calls per /chat** | **1** — single LLM call per request (no ReAct loop) |
| **Image analysis** | Claude Vision API — same model, base64 image in message |
| **Intent classification** | Tier 3 fallback only — most intents handled by pure Python regex (Tiers 1 & 2) |

---

## Agents (6 total)

### 1. Orchestrator Agent
- **File:** `app/agents/orchestrator.py`
- **Role:** Entry point for every session. Authenticates member, detects Path A (returning) vs Path B (new buyer), manages conversation state and agent handoffs.
- **Tools:** `load_member_session`, `detect_user_type`, `collect_preferences`, `auto_detect_climate`, `route_to_agent`

### 2. Rec & Ranking Agent
- **File:** `app/agents/rec_ranking_agent.py`
- **Role:** Core recommendation engine. Path A: repurchase + 2 alternatives ranked by loyalty/upgrade/popularity. Path B: multi-signal ranking (value, safety, regional popularity, rating, sentiment). Enforces diversity across top 3.
- **Tools:** `search_tyres`, `get_tyre_details`, `rank_tyres`, `select_top_pick`, `generate_punch_line`, `broaden_search`, `handle_no_results`

### 3. Content Agent
- **File:** `app/agents/content_agent.py`
- **Role:** Generates personalised message for each tyre slot. Tailors copy to member's vehicle, driving habits, location, membership tier, and which signal won (repurchase / upgrade / value / safety).
- **Tools:** `generate_personalised_msg`

### 4. Compare Agent
- **File:** `app/agents/compare_agent.py`
- **Role:** Side-by-side comparison card (3 columns). AI-generated pros/cons per tyre, total cost of ownership calculation.
- **Tools:** `generate_comparison_card`

### 5. Appointment Agent
- **File:** `app/agents/appointment_agent.py`
- **Role:** Post-payment booking. Finds nearby Costco tyre centres, surfaces available slots, smart-suggests least-busy slot in next 3 days, books appointment, generates `.ics` calendar invite.
- **Tools:** `get_nearby_locations`, `get_available_slots`, `predict_wait_times`, `suggest_best_slot`, `book_appointment`, `link_order_to_booking`, `create_calendar_event`

### 6. Guardrail Agent
- **File:** `app/agents/guardrail_agent.py`
- **Role:** Wraps **every** AI response before it reaches the member. Checks: hallucination (verify specs against catalogue), tyre-vehicle fit, PII redaction, safety (load/speed rating), brand bias audit. On fail: regenerate silently, log violation.
- **Tools:** `guardrail_tools.py` (check functions)

---

## Backend Services (7 total)

| Service | File | Responsibility |
|---------|------|---------------|
| **Profile Service** | `profile_service.py` | Member lookup, vehicle history, purchase history, preferences |
| **Stock Service** | `stock_service.py` | Tyre search (DB + JSON), stock badge generation, out-of-stock filtering |
| **Cart Service** | `cart_service.py` | Add to cart, 15-min stock reservation, fit check, coupons, price breakdown |
| **Payment Service** | `payment_service.py` | Costco Visa detection, cashback rewards, order ID generation |
| **Post-Purchase Service** | `post_purchase_service.py` | SMS reminders, satisfaction survey, rotation cron, re-engagement |
| **Drop-off Tracker** | `dropoff_tracker.py` | Stage transition logging, idle/exit detection, recovery rules engine |
| **Eval Service** | `eval_service.py` | Feedback collection (implicit + explicit), agent scorecard, improvement engine |

---

## Voice Service

| File | Role |
|------|------|
| `app/services/voice_service.py` | ElevenLabs TTS streaming, text humanisation, content safety gate |

Key functions:
- `text_to_speech_stream(text)` — streams MP3 chunks from ElevenLabs
- `_humanise_for_tts(text)` — transforms bot response to natural speech prose
- `_BLOCKED_PATTERNS` — content safety regex (never sends inappropriate text to TTS)
- `voice_enabled()` — returns True if `ELEVENLABS_API_KEY` is set

---

## Image Analysis

| Property | Value |
|----------|-------|
| **Technology** | Claude Vision API |
| **File** | `app/services/image_service.py` |
| **Endpoint** | `POST /image-analyse` |
| **Scenarios** | `sidewall` (tyre size detection) · `tread` (health scoring) · `car` (vehicle detection) · `unclear` |
| **Health scoring** | 1–10 scale. Liberal scoring: default ≥7 unless obvious damage. Dirt/grime does NOT reduce score. |
| **Cost** | Same as LLM (~$0.003 per image call) |

---

## Database

| Property | Value |
|----------|-------|
| **Primary DB** | PostgreSQL (optional) |
| **Driver** | `psycopg2-binary` |
| **Fallback** | JSON files (`app/data/`) — app works fully without a DB |
| **Schema** | 8 tables (members, tyres, orders, vehicles, locations, appointments, feedback, sessions) |
| **Loader** | `scripts/init_db.py` — creates schema + loads CRM data |

### Mock Data Files

| File | Contents |
|------|----------|
| `app/data/tyres.json` | 100 tyres — Western catalogue + 65 Indian market tyres (MRF, CEAT, Apollo, etc.) |
| `app/data/users.json` | 50 member profiles with vehicle history and last purchase |
| `app/data/locations.json` | Costco tyre centre locations with coordinates and hours |
| `app/data/appointments.json` | Runtime booked appointments (written at booking time) |

---

## Intent Routing (no LLM for most intents)

The `/chat` pipeline uses a **3-tier intent router** before any LLM call:

| Tier | Method | Examples |
|------|--------|---------|
| **Tier 1** — Global rules | Pure Python regex, stage-independent | `add to cart`, `book`, `slot`, `cancel`, member ID login |
| **Tier 2** — Stage rules | Pure Python regex, context-sensitive | `confirm_vehicle`: "yes/same" → same_vehicle; `cart`: "yes/ok" → confirm_pay |
| **Tier 3** — LLM classifier | Single LLM call, returns one label | Ambiguous messages that Tiers 1+2 can't classify |

Intent labels: `login | context_then_vehicle | same_vehicle | new_vehicle | new_vehicle_detail | select_tyre | compare | add_cart | confirm_pay | cancel | book_slot | general`

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/chat` | Main pipeline — member message → agent response |
| `POST` | `/feedback` | Thumbs up/down signal collection |
| `POST` | `/image-analyse` | Tyre image analysis (Vision API) |
| `POST` | `/voice/tts` | ElevenLabs TTS stream |
| `GET` | `/voice/status` | Returns `{ enabled: bool }` — whether TTS is configured |
| `GET` | `/demo-members` | Returns list of demo member IDs for sign-in chips |
| `GET` | `/health` | `{ status: "ok", version: "..." }` |
| `GET` | `/dashboard` | Live analytics dashboard (HTML) |
| `GET` | `/dashboard/api` | Analytics JSON (funnel, scorecard, alerts) |

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | **Required** | Claude LLM + Vision API — app will not start without it |
| `ELEVENLABS_API_KEY` | Optional | TTS voice — voice features disabled if absent |
| `ELEVENLABS_VOICE_ID` | Optional | ElevenLabs voice (default: Rachel `21m00Tcm4TlvDq8ikWAM`) |
| `ELEVENLABS_MODEL_ID` | Optional | TTS model (default: `eleven_turbo_v2_5`) |
| `APP_ENV` | Optional | `dev` (default) \| `prod` |
| `DB_HOST` | Optional | PostgreSQL host (falls back to JSON if not set) |
| `DB_PORT` | Optional | PostgreSQL port (default: 5432) |
| `DB_NAME` | Optional | PostgreSQL database name |
| `DB_USER` | Optional | PostgreSQL user |
| `DB_PASSWORD` | Optional | PostgreSQL password |

---

## Dev Setup

```bash
# Terminal 1 — Backend (port 8000)
cd costco-tyre-agent
pip install -r requirements.txt
cp .env.example .env       # add ANTHROPIC_API_KEY
uvicorn app.main:app --reload

# Terminal 2 — Frontend (port 5173)
cd costco-tyre-agent/frontend
npm install
npm run dev
```

Open **http://localhost:5173** — Vite proxies all API calls to FastAPI, no CORS config needed.
