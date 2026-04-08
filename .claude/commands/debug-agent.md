# Debug Individual Agents

Trigger and inspect each agent in isolation to diagnose issues.

---

## Check which agent handled a session

```bash
curl -s http://localhost:8000/dashboard/api | python -c "
import sys, json
d = json.load(sys.stdin)
logs = d.get('recent_agent_calls', [])
for l in logs[-10:]:
    print(f\"{l.get('timestamp','')} | {l.get('agent','?'):20} | session={l.get('session_id','?')[:8]} | {l.get('status','?')}\")
"
```

---

## Test individual agents via focused chat messages

### Orchestrator — routing detection
```bash
# Should detect 'returning' for M10042
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "dbg-orch", "message": "M10042"}' | python -c "
import sys, json
r = json.load(sys.stdin)
print('Stage:', r.get('stage'))
print('Message:', r.get('message', '')[:200])
"
```

### Rec & Ranking — Path B search
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "dbg-rec", "message": "M10044"}' > /tmp/s1.json

curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "dbg-rec", "message": "205/55R16 all-season highway"}' | python -c "
import sys, json
r = json.load(sys.stdin)
cards = r.get('cards', [])
print(f'Cards returned: {len(cards)}')
for c in cards:
    t = c.get('tyre', {})
    print(f\"  [{c.get('slot_tag')}] {t.get('brand')} {t.get('model')} — {c.get('stock_badge')}\")
"
```

### Compare Agent
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "dbg-cmp", "message": "compare"}' | python -c "
import sys, json
r = json.load(sys.stdin)
cmp = r.get('comparison')
if cmp:
    print('Comparison card returned ✅')
    print('Tyres:', [t.get('id') for t in cmp.get('tyres', [])])
else:
    print('No comparison card ❌')
"
```

### Appointment Agent
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "dbg-appt", "message": "book appointment"}' | python -c "
import sys, json
r = json.load(sys.stdin)
slots = r.get('appointment_slots', [])
print(f'Slots returned: {len(slots)}')
for s in slots[:3]:
    print(f\"  {s.get('date')} {s.get('time')} @ {s.get('location_id')} — available={s.get('available')}\")
"
```

---

## Guardrail — check last violation log

```bash
python -c "
import json
from pathlib import Path
log = Path('app/logs/guardrail.json')
if log.exists():
    entries = json.loads(log.read_text())
    for e in entries[-5:]:
        print(json.dumps(e, indent=2))
else:
    print('No guardrail log yet')
"
```

---

## Agent scorecard trend

```bash
curl -s http://localhost:8000/dashboard/api | python -c "
import sys, json
d = json.load(sys.stdin)
for a in sorted(d.get('scorecard', []), key=lambda x: x['score'], reverse=True):
    bar = '█' * (a['score'] // 10)
    trend = f\"+{a['trend']}\" if a['trend'] >= 0 else str(a['trend'])
    print(f\"{a['agent']:20} {a['score']:3}/100  {bar}  ({trend})\")
"
```
