# View agent scorecard

Show the current agent performance scorecard and conversion metrics.

## Live scorecard via API

```bash
curl -s http://localhost:8000/dashboard/api | python -m json.tool
```

## Expected v33 baseline scores

| Agent | Score | Trend | Status |
|-------|-------|-------|--------|
| Guardrail | 86 | +3 | ✅ On target |
| Rec & Ranking | 78 | +4 | ✅ On target |
| Compare | 74 | +4 | ✅ On target |
| Content | 71 | +8 | ✅ On target |
| Appointment | 69 | -2 | ⚠️ Under review |
| Orchestrator | 67 | +5 | ✅ On target |

**Overall conversion: 35.2% (+2.1%)**

## Check for drop-off alerts

```bash
curl -s http://localhost:8000/dashboard/api | python -c "
import sys, json
data = json.load(sys.stdin)
alerts = [s for s in data.get('drop_alerts', []) if s.get('status') == 'warning']
print(f'Active alerts: {len(alerts)}')
for a in alerts:
    print(f'  ⚠️  {a[\"stage\"]}: {a[\"current_rate\"]}% (threshold: {a[\"threshold\"]}%)')
"
```
