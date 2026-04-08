# Environment & Dependency Check

Validate the environment is correctly set up before running the server.

---

## 1. Check Python version

```bash
python --version
# Required: Python 3.11 or higher
```

---

## 2. Check all required packages are installed

```bash
python -c "
packages = [
    ('fastapi', 'fastapi'),
    ('uvicorn', 'uvicorn'),
    ('langchain', 'langchain'),
    ('langchain_anthropic', 'langchain-anthropic'),
    ('anthropic', 'anthropic'),
    ('pydantic', 'pydantic'),
    ('dotenv', 'python-dotenv'),
    ('icalendar', 'icalendar'),
    ('aiofiles', 'aiofiles'),
]
missing = []
for module, pkg in packages:
    try:
        __import__(module)
        print(f'✅ {pkg}')
    except ImportError:
        print(f'❌ {pkg} — run: pip install {pkg}')
        missing.append(pkg)
if missing:
    print()
    print('Install missing packages:')
    print('pip install', ' '.join(missing))
else:
    print()
    print('All dependencies satisfied ✅')
"
```

---

## 3. Validate .env file

```bash
python -c "
from pathlib import Path
import os

env_file = Path('.env')
example_file = Path('.env.example')

if not env_file.exists():
    print('❌ .env file not found')
    print('   Run: cp .env.example .env  then add your ANTHROPIC_API_KEY')
    exit()

content = env_file.read_text()
lines = {l.split('=')[0].strip(): l.split('=',1)[1].strip() if '=' in l else ''
         for l in content.splitlines() if l and not l.startswith('#')}

checks = {
    'ANTHROPIC_API_KEY': lambda v: v.startswith('sk-ant-') and len(v) > 20,
    'APP_ENV': lambda v: v in ('dev', 'prod'),
}

for key, validate in checks.items():
    val = lines.get(key, '')
    if not val:
        print(f'❌ {key} is missing')
    elif validate(val):
        masked = val[:8] + '...' if len(val) > 8 else val
        print(f'✅ {key} = {masked}')
    else:
        print(f'⚠️  {key} looks incorrect — value: {val[:12]}...')
"
```

---

## 4. Verify data files exist and are valid JSON

```bash
python -c "
import json
from pathlib import Path

files = [
    'app/data/tyres.json',
    'app/data/users.json',
    'app/data/locations.json',
    'app/data/appointments.json',
]

for path in files:
    f = Path(path)
    if not f.exists():
        print(f'❌ {path} not found')
        continue
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
        count = len(data) if isinstance(data, list) else '(object)'
        print(f'✅ {path} — {count} entries')
    except json.JSONDecodeError as e:
        print(f'❌ {path} — invalid JSON: {e}')
"
```

---

## 5. Test Anthropic API key connectivity

```bash
python -c "
import os
from pathlib import Path

# Load .env manually
env = Path('.env')
if env.exists():
    for line in env.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

key = os.environ.get('ANTHROPIC_API_KEY', '')
if not key:
    print('❌ ANTHROPIC_API_KEY not set')
    exit()

try:
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=10,
        messages=[{'role': 'user', 'content': 'Say OK'}]
    )
    print('✅ Anthropic API connection successful')
    print('   Response:', msg.content[0].text)
except Exception as e:
    print(f'❌ Anthropic API error: {e}')
"
```

---

## Full environment check (run all)

```bash
echo "--- Python version ---" && python --version && \
echo "--- Packages ---" && pip show fastapi langchain langchain-anthropic anthropic pydantic uvicorn 2>&1 | grep -E "^Name|^Version" && \
echo "--- Data files ---" && python -c "
import json
from pathlib import Path
for f in ['app/data/tyres.json','app/data/users.json','app/data/locations.json','app/data/appointments.json']:
    p = Path(f)
    status = f'{len(json.loads(p.read_text()))} entries' if p.exists() else 'MISSING'
    print(f'  {f}: {status}')
" && \
echo "--- .env ---" && python -c "
from pathlib import Path
print('  .env:', 'found' if Path('.env').exists() else 'MISSING — copy from .env.example')
print('  .env.example:', 'found' if Path('.env.example').exists() else 'MISSING')
"
```
