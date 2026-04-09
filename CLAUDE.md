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

# Arize observability (optional — tracing disabled if not set)
ARIZE_SPACE_ID=...
ARIZE_API_KEY=...
ARIZE_PROJECT_NAME=costco-tyre-agent

# Twilio WhatsApp (optional — booking WA message disabled if not set)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxx
TWILIO_FROM_WHATSAPP=whatsapp:+14155238886   # Twilio sandbox number
TWILIO_TO_WHATSAPP=whatsapp:+91XXXXXXXXXX    # demo recipient number
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
│           ├── ChatInput.jsx          # Textarea + mic + TTS + send pill
│           ├── QuickReplies.jsx       # Quick reply chips (greyed after use)
│           ├── RecoveryBanner.jsx     # Drop recovery banner
│           └── cards/
│               ├── TyreCard.jsx       # Individual tyre card (active/inactive/"In Cart" state)
│               ├── CardsGrid.jsx      # Infinite cover-flow carousel of TyreCards
│               ├── DetailActions.jsx  # Add to Cart + Back buttons after detail view
│               ├── CompareCard.jsx    # Side-by-side comparison table
│               ├── SlotPicker.jsx     # Appointment slot chips + custom slot trigger
│               ├── CustomSlotModal.jsx # iOS drum-style date+time picker (scroll-snap)
│               └── BookingCard.jsx    # Booking confirmation + jsPDF invoice download
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

**Positive intent detection (add-to-cart shortcut):**
- Module-level `POSITIVE_INTENT` regex matches natural phrases: "yes", "sure", "I'll take it", "perfect", "add it", "sounds good", etc.
- `lastDetailRef` persists the last viewed tyre (`{ tyreId, slotTag }`) even after `detail_actions` is injected
- When `POSITIVE_INTENT` matches AND `lastDetailRef.current.tyreId` is set, `sendMessage` rewrites `backendMsg` to `"add to cart {tyreId}"` — the user bubble still shows their original phrase
- `lastDetailRef` is cleared after the rewrite so a second "yes" doesn't re-add the same tyre

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

- **Infinite cover-flow carousel** — no arrow buttons; click a side card to bring it to centre; wraps circularly
- `reorderCards()` runs on mount: moves Top Pick to index 1, Runner-up to index 0, Budget Alt to index 2 — so the default centre is always Top Pick
- `activeIdx` default = `1` (Top Pick at centre); `prev()` and `next()` wrap with modulo arithmetic
- `posClass(idx)` uses modular distance to handle wrapping:
  - `d = idx - activeIdx`; if `d > floor(n/2)` subtract `n`; if `d < -floor(n/2)` add `n`
  - `cc-center` — hero card, full scale, drop-shadow
  - `cc-left1` / `cc-right1` — adjacent cards, 86% scale
  - `cc-left2` / `cc-right2` — far cards, 72% scale, pointer-events none
- Side cards are subdued: `opacity: 0.45; filter: brightness(0.88) saturate(0.6)`
- Dot indicators below for navigation
- "Compare side by side" toggle below dots → shows `CompareCard`
- Carousel height = card height + 4px top/bottom padding (`cc-wrapper` bg `#F0F2F5`)

**`TyreCard.jsx`** — `active` prop + `slot_tag` variants:
- `active=true` (centre card): shows Details, thumbs up/down; Add to Cart hidden when `slot_tag === "In Cart"`
- `active=false` (side cards): hides all action buttons, shows "Tap to view" hint
- `slot_tag === "In Cart"`: green pill (`#1A8754`), `shopping_cart_checkout` icon — shown after add-to-cart confirmation
- Card layout (top to bottom): slot-tag pill → brand (gray caps) → model (bold) → size/season/terrain → price row → rating row → stock inline (no pill bg) → punch line or personalised msg → tread/warranty line

### Detail View Flow

When user clicks "Details" on a card:
1. `handleDetails(tyreId, slotTag)` in CardsGrid calls `onSendMessage("I'd like to view details for the {slotTag} option ({tyreId})")`
2. `useChat.sendMessage` detects the details pattern via regex → sets `detailContextRef` **and** `lastDetailRef`
3. Bot responds with detail text (rendered as `BotBubble`)
4. `useChat` auto-injects a `detail_actions` message: `{ type: 'detail_actions', tyreId, slotTag }`
5. `DetailActions` component renders two buttons:
   - **Add to Cart** → `sendMessage("add to cart {tyreId}")`
   - **Back to Recommendations** → `goBackToRecs()` re-appends the carousel

### Add-to-Cart Confirmation Flow

After `add to cart {tyreId}` is processed by the backend:
1. Backend `cart_service.add_to_cart()` reserves stock for 15 minutes
2. LLM writes a 1-sentence confirmation (e.g. "Done, Ed — you're saving $133 on those Alpines. 🛒")
3. Backend returns `cards` with a **single "In Cart" card** showing the tyre details + `"4 tyres · $xxx · saving $xx"` personalised msg
4. Frontend renders the confirmation bubble followed by the cart tyre card
5. Quick replies change to `["Confirm & Pay", "Go back"]`

### Custom Slot Picker (`components/cards/CustomSlotModal.jsx`)

Triggered by the "Pick date & time" card in `SlotPicker.jsx`:
- Single drum row: **Date** | divider | **Hour** | `:` | **Minute** | divider | **AM/PM**
- `DrumColumn` component uses `scroll-snap-type: y mandatory` with spacer divs (height = `ITEM_H × 2`) so first/last items can centre
- `buildDates()` generates 30 days: "Today", "Tomorrow", then named dates (e.g. "Thu Apr 10")
- On confirm: converts `YYYY-MM-DD` + 12h → 24h time, sends `"Book the slot on {isoDate} at {HH:MM}"`
- Backend regex: `r"(\d{4}-\d{2}-\d{2})[^\d]+(\d{2}:\d{2})"` — must receive ISO date + 24h time

### Voice (`hooks/useVoice.js`) — COMPLETE ✅

- `STT_SUPPORTED` checked once at module load (`window.SpeechRecognition || window.webkitSpeechRecognition`)
- Checks `/voice/status` on mount — `voiceEnabled` state controls TTS button visibility
- **STT**: `buildRecognition()` creates a **fresh** `SpeechRecognition` instance every toggle (never reused — avoids stale-state restart bugs)
  - `listeningRef` sync ref ensures callbacks see current state
  - `interimText` state exposes live partial transcript to `ChatInput` textarea
  - On final result → `_stopListening()` → `onTranscript(final.trim())` → message sent
- **TTS**: POST to `/voice/tts` (ElevenLabs stream) → `blob()` → `URL.createObjectURL` → `Audio.play()`
  - Toggle: if already playing, pause and clear
  - `isTtsPlaying` state drives speaker button icon (`volume_up` / `stop_circle`)
- Returns: `{ voiceEnabled, sttSupported, isListening, isTtsPlaying, interimText, toggleMic, speakLastResponse }`

**`ChatInput.jsx`** wiring:
- Mic button: `{sttSupported && (...)}` — only renders if browser supports STT
- TTS button: `{voiceEnabled && (...)}` — only renders if ElevenLabs configured
- Textarea shows `interimText` live; `readOnly={isListening}` prevents manual typing during STT
- Input bar: `.listening-active` class adds red glow; `.mic-pulse` span shows ripple animation

**`app/services/voice_service.py`**:
- `optimize_streaming_latency` only added for `turbo` or `flash` model IDs (deprecated in `eleven_v3+`)

### CSS Architecture (`src/index.css`)

Single file, organised by section with ASCII dividers:
- MD3 design tokens (`:root` CSS variables — `--md-sys-color-*`, `--md-elevation-*`, `--md-sys-shape-*`)
- Costco brand colours (`--cs-blue: #005CA9`, `--cs-red: #E31837`)
- Sign-in page (`.signin-*`)
- Store page (`.cs-*`)
- Shared header (`.sh-*`)
- Agent page (`.agent-*`, `.ta-*` for TireAssist components)
- Tyre cards (`.tyre-card`, `.card-content`, `.slot-tag`, `.slot-tag.in-cart`, `.price-row`, `.punch-row`, `.stock-inline`, etc.)
- Carousel (`.cc-*`) — side cards: `opacity: 0.45; filter: brightness(0.88) saturate(0.6)`
- Detail actions (`.detail-actions`)
- Compare card (`.compare-*`)
- Slot picker (`.slot-chip`, `.slot-chip-custom` dashed border)
- Drum picker (`.drum-col`, `scroll-snap-type: y mandatory`, fade masks `::before`/`::after`, `.drum-selected`)
- Booking card (`.bc-tiles` → 4-column grid, `.bc-sections` → 2-column)
- Recovery banner
- Voice (`.mic-pulse` `@keyframes mic-ring`, `.ta-input-bar.listening-active` red glow, `.ta-input-textarea.interim` italic)

---

## Completed Work Log

### ✅ Task 5 — Voice Integration
- `useVoice.js` fully implemented: STT (Web Speech API) + TTS (ElevenLabs streaming)
- Fresh `SpeechRecognition` instance per session — no stale-state restart bugs
- `interimText` live transcript shown in textarea while speaking
- `ChatInput` mic button renders only when browser supports STT; TTS button only when `ELEVENLABS_API_KEY` set
- `voice_service.py`: `optimize_streaming_latency` conditional (only for turbo/flash models — deprecated in eleven_v3+)
- Needs: `ELEVENLABS_API_KEY` in `.env`; test on Chrome (STT not supported on Firefox/Safari)

### ✅ Carousel Redesign
- Infinite circular wrapping via modular arithmetic in `posClass()`
- Default order: Runner-up (left) | **Top Pick (centre)** | Budget Alt (right)
- Side cards subdued: `opacity: 0.45; filter: brightness(0.88) saturate(0.6)`
- Height = card + 4px padding, light grey background

### ✅ TyreCard Redesign
- Flat layout (no coloured header), all content in `.card-content`
- `slot_tag === "In Cart"` → green pill, `shopping_cart_checkout` icon, no Add to Cart button
- Removed promo chip entirely

### ✅ Slot Picker + Custom Slot
- `SlotPicker.jsx` shows suggested slots as chips + a "Pick date & time" card (dashed border)
- `CustomSlotModal.jsx` — iOS drum-style picker (scroll-snap, no calendar)
- Custom slot confirms as ISO date + 24h time matching backend regex

### ✅ Booking Card + PDF Invoice
- 4 tiles in one horizontal row (Date / Time / Location / Order) + 2-column sections below
- PDF redesigned: navy header, green badge with drawn checkmark (two `line()` calls — no Unicode glyphs in jsPDF helvetica), KV rows, "What to bring" rectangles, numbered navy circles for "What happens next"

### ✅ Add-to-Cart Confirmation Card
- After cart add, backend returns a single "In Cart" tyre card alongside the confirmation message
- Positive intent detection in `useChat.js` — "yes", "I'll take it", "perfect", etc. auto-convert to `add to cart {tyreId}` when a tyre is in focus

### ✅ Image Analysis Fixes
- "Unknown" brand filtered from image search messages
- Tyre health scoring made liberal: default ≥7 unless obvious damage; dirt/grime does not reduce score
- Auto-broadening when image search returns 0 results (matches chat flow)

### ✅ Encoding Fix — Location Names
- Windows `read_text()` without `encoding='utf-8'` corrupted UTF-8 em-dash to `â€"` (cp1252)
- Fixed all 3 `locations.json` reads in `main.py` with `encoding='utf-8'`
- `stock_service.py` regex uses `[-\u2013\u2014]` Unicode escapes instead of raw em-dash characters

### ✅ Multilingual Vehicle Detection
- Tier 1.5 block in `_detect_intent()` — brand/model regex fires BEFORE stage rules and destination context
- `_MODEL_NAMES_RE` — compiled regex of 400+ car model names (sorted longest-first, prevents partial matches)
- `_KNOWN_MODEL_MAKES` — 50+ model → brand reverse lookup (nexon→Tata, creta→Hyundai, swift→Maruti Suzuki, etc.)
- `_MULTILANG_FILLERS` regex strips Telugu/Hindi filler words from extracted model name (`kosam`, `lo`, `se`, `mein`, `lekar`, etc.)
- Hindi `_LANG_MARKERS` expanded: jata, hun, lekar, wala, etc.
- `_MORPH_PATTERNS` expanded with "jata hun", "lekar" patterns
- `_LANG_INSTRUCTION` dict per language — appended to system prompt so LLM replies in same language as user
- Languages: English, Hindi, Telugu, Hinglish, Tamil, Kannada, Marathi, Bengali

### ✅ Price & Quality Intent Detection
- `_detect_price_intent(msg)` — returns `budget | premium | performance | safety | longevity | value | none`
- `_extract_price_limit(msg)` — extracts exact cap from "less than $130", "130 se kam", "130 kante takkuva" (multilingual)
- `_PRICE_INTENT_CONFIG` — per-intent sort lambdas + slot labels
- `session.preferences["max_price"]` stored and passed to all `search_tyres()` calls
- Graceful fallback: if `max_price` yields 0 results, sets `price_filter_relaxed` flag and shows closest options with a note

### ✅ Image Upload — Car Detection Flow
- `image_service.py` Vision prompt: Scenario C returns `car_identified` (make/model found) vs `car` (not found)
- `car_identified` response includes: `car_make`, `car_model`, `car_confidence`, `health_score`, `recommendation`
- `/image-analyse` handler: `car_identified` → `_infer_size_from_text(car_text)` → search → 3 tyre cards
- If size not in map → asks user to confirm, sets `partial_make`, stage=`collect_vehicle`
- If health worn → adds note to intro; if no stock → honest message with available sizes

### ✅ Arize Observability
- `_setup_arize()` in `main.py` — initialises OTel tracing to Arize platform on startup
- `LangChainInstrumentor` auto-traces all LLM calls (tokens, latency, model)
- Custom span attributes on every `/chat` request: `intent`, `stage`, `language`, `ranking_intent`, `cards_returned`, `guardrail_applied`
- Env vars: `ARIZE_SPACE_ID`, `ARIZE_API_KEY`, `ARIZE_PROJECT_NAME`
- Graceful: `try/except ImportError` — app runs normally without Arize packages installed
- Install: `pip install arize-otel openinference-instrumentation-langchain opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc`

### ✅ WhatsApp Booking Confirmation (Twilio)
- New service: `app/services/whatsapp_service.py`
- Fires after `booking_card` is built in the `book_slot` handler in `main.py`
- Sends formatted WhatsApp message: booking ID, order ID, date/time, location, tyre, bring-list
- Non-fatal: missing credentials → logs warning, booking flow continues unaffected
- Env vars: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_WHATSAPP`, `TWILIO_TO_WHATSAPP`
- For demo: `TWILIO_TO_WHATSAPP` is a fixed number (your own); swap for `user.phone_number` when phone added to member profiles
- Install: `pip install twilio`
- Twilio sandbox setup: send `join <keyword>` to `+14155238886` on WhatsApp once to activate

### ✅ CSS Fix — TTS Wave Bar Width
- `.tts-wave-bar` changed to `position: absolute; bottom: 4px; left: 0; right: 0; pointer-events: none`
- `.ta-input-bar` gets `position: relative; width: 100%; box-sizing: border-box`
- Prevents flex reflow that was shrinking the input bar width when TTS animation appeared

### ✅ Header Agent Name
- Toggle pill in `SharedHeader.jsx` updated from "Agentic Agent" → "TireAssist"
- Page title in `AgentPage.jsx` remains "Meet TireAssist, Your AI Executive Assistant"

### ✅ Favicon
- `frontend/public/favicon.svg` added
- `frontend/index.html` wired: `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />`

### ✅ Documentation
- `ARCHITECTURE.md` — full technical deep dive (pipeline, intent tiers, car mapping, search, language detection, image flow, agents, services, LangChain, 3rd party APIs, models, key decisions)
- `PRESENTATION.md` — jury-ready technical presentation (16 sections, talk-track format)

---

## Pending Tasks for Next Developer

### Task 6 — Voice Feature Enhancements

#### Completed ✅
- Speaker button removed from `ChatInput`
- Auto-TTS: when last user message came from mic (`voiceInputRef.current = true`), bot response is automatically spoken via ElevenLabs — no button needed
- TTS playing indicator: animated 5-dot wave below the input bar (`.tts-wave-bar`), input bar glows blue (`.tts-active`)
- Mic button disabled while TTS is playing (prevents overlap)
- `_humanise_for_tts()` in `voice_service.py`: strips markdown/codes, converts lists to natural sentences, expands abbreviations, converts prices to spoken form ("169 dollars and 99 cents"), removes emojis and tyre ID codes
- Content safety gate in `voice_service.py`: `_BLOCKED_PATTERNS` regex blocks inappropriate language before it reaches ElevenLabs API

#### 6a — Auto-TTS toggle
- **TODO:** Add a "Auto-read responses" toggle chip near the input bar; persist in `localStorage`
- Hook location: `useVoice.js` — watch `lastBotText` in a `useEffect`, call `speakLastResponse()` if auto-mode on and TTS not already playing

#### 6b — Hands-free mode
- **TODO:** After STT sends + TTS ends, auto-reactivate mic
- Flow: speak → send → TTS plays → `audio.onended` → re-activate mic if `handsFreeModeRef` on
- Guard: skip if user manually stopped, or stage is `complete`
- Hook location: `useVoice.js` `audio.onended` callback

#### 6c — Voice persona selector
- **TODO:** `GET /voice/voices` endpoint + small UI selector (3–4 presets: Rachel, Josh, Elli, Antoni)
- Store chosen `voice_id` in `localStorage`; send as param in `/voice/tts` POST body
- Backend: `voice_service.py` reads `voice_id` from body, falls back to `ELEVENLABS_VOICE_ID` env var

#### 6d — STT error feedback
- **TODO:** On `no-speech` → toast; `not-allowed` → persistent banner; `network` → graceful fallback
- Add `sttError` state in `useVoice.js`; render error chip above input bar in `ChatInput.jsx`

#### 6e — TTS playback controls
- **TODO:** Waveform animation on bot bubble being read; optional speed control (0.75×/1×/1.25×)
- ElevenLabs supports `speaking_rate` in the POST body

### Task 7 — WhatsApp: Per-Member Phone Numbers
- Currently `TWILIO_TO_WHATSAPP` is a single fixed number (demo mode)
- **TODO:** Add `phone_number` field to `users.json` and `User` Pydantic model (`schemas.py`)
- **TODO:** Update `whatsapp_service.py` to accept `to_number` param; caller passes `user.phone_number`
- **TODO:** Update `main.py` `book_slot` handler: pass `user.phone_number` (formatted as `whatsapp:+{number}`) to `send_booking_confirmation()`

### Task 8 — Details Button
- Tyre card "Details" button click is intentionally disabled / deferred
- **TODO:** Wire up a detail view — either an expanded card or a modal — showing full specs (tread life, wet grip, noise dB, compatible vehicles, warranty, reviews)
- Suggested: expand the existing `BotBubble` detail flow triggered by "I'd like to view details for..." OR build a `DetailModal` component

### Task 9 — Production Hardening
- Session state is in-memory (`SESSION_STORE` dict) — resets on server restart
- **TODO:** Swap for Redis or PostgreSQL-backed session store for multi-worker deployments
- `CART_RESERVE_MINUTES=15` TTL is in-memory only — needs a background task to expire carts
- Payment flow is mocked (`payment_service.py`) — needs real payment gateway integration
- `users.json` / `tyres.json` → swap for live DB queries when moving to production

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
