# API Endpoint Tests

Full suite of API endpoint tests for the Costco Tyre Agent.

## Health & Info

```bash
# Health check
curl -s http://localhost:8000/health | python -m json.tool

# OpenAPI schema
curl -s http://localhost:8000/openapi.json | python -m json.tool

# Interactive API docs
start http://localhost:8000/docs
```

---

## Chat API — Full Flow Tests

### Step 1: Greet (no member ID yet)
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "api-test-001", "message": "Hello"}' | python -m json.tool
```

### Step 2: Path A — Returning buyer login
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "api-test-001", "message": "M10042"}' | python -m json.tool
```

### Step 3: Path B — New buyer login
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "api-test-002", "message": "M10044"}' | python -m json.tool
```

### Step 4: Provide tyre preferences (Path B)
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "api-test-002", "message": "225/45R17, all-season, highway driving"}' | python -m json.tool
```

### Step 5: Thumbs up feedback
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "api-test-001", "message": "thumbs_up MIC-PRIM4-20555R16"}' | python -m json.tool
```

---

## Dashboard API

```bash
# Full analytics payload
curl -s http://localhost:8000/dashboard/api | python -m json.tool

# Funnel only
curl -s http://localhost:8000/dashboard/api | python -c "
import sys, json
d = json.load(sys.stdin)
for s in d.get('funnel', []):
    bar = '#' * int(s['visitors'] / 100)
    print(f\"{s['stage']:10} {s['visitors']:5} visitors  {s['drop_rate']:5.1f}% drop  {bar}\")
"

# Agent scorecard only
curl -s http://localhost:8000/dashboard/api | python -c "
import sys, json
d = json.load(sys.stdin)
print(f\"{'Agent':20} {'Score':6} {'Trend':6} Status\")
print('-' * 50)
for a in d.get('scorecard', []):
    trend = f\"+{a['trend']}\" if a['trend'] >= 0 else str(a['trend'])
    flag = '✅' if a['status'] == 'on_target' else '⚠️'
    print(f\"{a['agent']:20} {a['score']:6} {trend:6} {flag}\")
"
```

---

## Response Schema

Every `POST /chat` response follows this structure:
```json
{
  "message": "string",
  "cards": [
    {
      "tyre": { ... },
      "slot_tag": "Top Pick | Best Repurchase | ...",
      "personalised_msg": "string",
      "stock_badge": "✅ In stock at ...",
      "punch_line": "string (Top Pick only)"
    }
  ],
  "comparison": {
    "tyres": [...],
    "columns": [...],
    "pros_cons": {...},
    "cost_per_1000km": {...}
  },
  "appointment_slots": [...],
  "stage": "enter | browse | detail | cart | pay | book | complete"
}
```
