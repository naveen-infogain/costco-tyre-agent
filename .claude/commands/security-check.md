# Security Checks

Run these checks before every demo, commit, or deployment.

---

## 1. API Key Exposure Scan

Check that secrets never appear in code, logs, or responses.

```bash
# Scan all Python files for hardcoded API keys
python -c "
import re
from pathlib import Path
pattern = re.compile(r'sk-ant-[a-zA-Z0-9\-_]{10,}')
found = []
for f in Path('app').rglob('*.py'):
    text = f.read_text(encoding='utf-8', errors='ignore')
    if pattern.search(text):
        found.append(str(f))
if found:
    print('❌ HARDCODED KEY FOUND in:', found)
else:
    print('✅ No hardcoded API keys in source code')
"

# Check .env is not committed (should only have .env.example)
python -c "
from pathlib import Path
env = Path('.env')
if env.exists():
    print('⚠️  .env file exists locally (do NOT commit this)')
else:
    print('✅ .env not present (use .env.example as template)')
example = Path('.env.example')
if example.exists():
    print('✅ .env.example present')
"
```

---

## 2. PII Redaction Check (Guardrail)

Verify the guardrail strips personal data from responses.

```bash
# Send a message containing a fake PII pattern — guardrail should redact it
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sec-pii-test", "message": "My email is test@example.com and my SSN is 123-45-6789"}' | python -c "
import sys, json
r = json.load(sys.stdin)
msg = r.get('message', '')
pii_patterns = ['@', 'SSN', '123-45', 'password']
for p in pii_patterns:
    if p.lower() in msg.lower():
        print(f'❌ PII pattern found in response: {p!r}')
    else:
        print(f'✅ {p!r} not leaked in response')
"
```

---

## 3. Guardrail Coverage Check

Ensure every response is wrapped by the guardrail.

```bash
python -c "
import ast
from pathlib import Path

main = Path('app/main.py').read_text(encoding='utf-8')
if 'guardrail' in main.lower():
    print('✅ Guardrail referenced in main.py')
else:
    print('❌ Guardrail NOT found in main.py — responses may be unwrapped')

chat_route = [l for l in main.splitlines() if 'def chat' in l or 'guardrail' in l]
for l in chat_route:
    print(' ', l.strip())
"
```

---

## 4. Input Validation Check

Verify that tyre size and member ID inputs are validated before agent processing.

```bash
# Invalid member ID — should return friendly error, not a stack trace
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sec-val-001", "message": "INVALID_ID"}' | python -c "
import sys, json
r = json.load(sys.stdin)
msg = r.get('message', '')
if 'error' in msg.lower() or 'not found' in msg.lower() or 'try again' in msg.lower():
    print('✅ Invalid member ID handled gracefully')
else:
    print('⚠️  Check response for unhandled error:', msg[:200])
"

# SQL/injection-style input — should not cause a crash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sec-inj-001", "message": "\" OR 1=1 --"}' | python -c "
import sys, json
try:
    r = json.load(sys.stdin)
    print('✅ Injection input handled — server did not crash')
    print('Response stage:', r.get('stage'))
except:
    print('❌ Unexpected response to injection input')
"
```

---

## 5. Log File Audit

Check logs don't contain raw API keys or sensitive member data.

```bash
python -c "
import json, re
from pathlib import Path

log_dir = Path('app/logs')
if not log_dir.exists():
    print('No logs directory yet')
    exit()

key_pattern = re.compile(r'sk-ant-[a-zA-Z0-9\-_]{10,}')
pii_pattern = re.compile(r'\b\d{3}-\d{2}-\d{4}\b|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

for log_file in log_dir.glob('*.json'):
    text = log_file.read_text(encoding='utf-8', errors='ignore')
    if key_pattern.search(text):
        print(f'❌ API key found in {log_file.name}')
    elif pii_pattern.search(text):
        print(f'⚠️  Possible PII in {log_file.name} — review manually')
    else:
        print(f'✅ {log_file.name} looks clean')
"
```

---

## 6. CORS & Rate Limiting Reminder

```
For production deployment:
  ✅ Set APP_ENV=prod in .env
  ✅ Restrict CORS origins (remove wildcard *)
  ✅ Add rate limiting (e.g. slowapi or nginx upstream)
  ✅ Store ANTHROPIC_API_KEY in secrets manager, not .env
  ✅ Enable HTTPS (TLS termination at load balancer)
  ✅ Rotate API key every 90 days
```

---

## Full Security Audit (run all checks)

```bash
echo "=== 1. API Key Scan ===" && \
python -c "
import re; from pathlib import Path
p = re.compile(r'sk-ant-[a-zA-Z0-9\-_]{10,}')
bad = [str(f) for f in Path('app').rglob('*.py') if p.search(f.read_text(errors='ignore'))]
print('❌ Keys found:', bad) if bad else print('✅ Clean')
" && \
echo "=== 2. .env Check ===" && \
python -c "from pathlib import Path; print('⚠️  .env present' if Path('.env').exists() else '✅ No .env in repo')" && \
echo "=== 3. Log Audit ===" && \
python -c "
import re; from pathlib import Path
for f in Path('app/logs').glob('*.json') if Path('app/logs').exists() else []:
    t = f.read_text(errors='ignore')
    issues = []
    if re.search(r'sk-ant-', t): issues.append('API key')
    if re.search(r'\d{3}-\d{2}-\d{4}', t): issues.append('SSN pattern')
    print(f'❌ {f.name}: {issues}' if issues else f'✅ {f.name}')
" && \
echo "=== Security audit complete ==="
```
