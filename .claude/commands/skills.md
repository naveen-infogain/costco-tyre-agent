# Costco Tyre Agent — Skills Reference

This file lists all available Claude Code project skills (slash commands) for the Costco Tyre Agent project.

---

## Available Skills

### Dev & Server
| Skill | Purpose | When to use |
|-------|---------|-------------|
| `/start` | Boot server | Beginning of every dev session |
| `/env-check` | Validate Python, packages, .env, data files, API key | Before first run or after machine setup |
| `/reset-data` | Clean demo state (appointments + logs) | Before presentations/demos |

### API Testing
| Skill | Purpose | When to use |
|-------|---------|-------------|
| `/test-chat` | End-to-end Path A + Path B chat tests | After any code changes |
| `/api-test` | Full API suite — health, chat flow, dashboard API, response schema | Deep endpoint validation |

### Agent Debugging
| Skill | Purpose | When to use |
|-------|---------|-------------|
| `/debug-agent` | Test each agent in isolation, check scorecard trend | When responses look wrong |
| `/view-logs` | Inspect guardrail, error, funnel logs | Diagnosing agent behaviour |
| `/scorecard` | Live agent scorecard + drop-off alerts | Monitoring system health |

### Data Management
| Skill | Purpose | When to use |
|-------|---------|-------------|
| `/add-tyre` | Extend the tyre catalogue | Adding new tyre data |

### Security
| Skill | Purpose | When to use |
|-------|---------|-------------|
| `/security-check` | Full security audit: key scan, PII leak, CORS, log audit | Before every demo or deployment |
| `/guardrail-test` | Test all 5 guardrail checks: hallucination, fit, PII, safety, bias | After guardrail changes |

### Documentation
| Skill | Purpose | When to use |
|-------|---------|-------------|
| `/document <file>` | Apply full code documentation standards to any file | After writing new code; before code review or production deploy |

---

### `/start`
**Start the development server.**
Installs dependencies and launches the FastAPI app at http://localhost:8000.

### `/env-check`
**Validate the full environment.**
Checks Python version, all pip packages, `.env` file, API key connectivity, and data file integrity. Run this first on any new machine.

### `/test-chat`
**Test the chat API endpoint.**
Sends sample requests for both Path A (M10042 — Sarah Chen) and Path B (M10044 — Emily Torres). Includes health check and dashboard API test.

### `/api-test`
**Full API test suite.**
Tests every endpoint: health, full chat flow (greet → login → preferences → feedback), dashboard funnel, and agent scorecard. Shows response schema.

### `/debug-agent`
**Debug individual agents.**
Isolates each agent (Orchestrator, Rec & Ranking, Compare, Appointment, Guardrail) with targeted test messages. Shows scorecard trend bar chart.

### `/view-logs`
**Inspect agent logs.**
Shows guardrail violations, errors, and event logs from `app/logs/`. Supports filtering by type.

### `/reset-data`
**Reset runtime state for a fresh demo.**
Clears booked appointments and log files. Session/cart state resets on server restart.

### `/add-tyre`
**Add a new tyre to the catalogue.**
Shows the full tyre JSON schema and all valid field values. Edit `app/data/tyres.json` directly.

### `/scorecard`
**View the agent performance scorecard.**
Shows live scores via the dashboard API. Includes v33 baseline and drop-off alert checker.

### `/security-check`
**Full security audit.**
Scans for hardcoded API keys, checks `.env` is not committed, validates PII redaction, audits log files, and shows production security checklist.

### `/guardrail-test`
**Test all 5 guardrail checks.**
Runs targeted tests for: hallucination detection, tyre-vehicle fit validation, PII redaction, safety (load index/speed rating), and brand bias audit. Shows pass/fail per check.

### `/document <filename>`
**Apply code documentation standards to a file.**
Adds or improves: module docstring, API call comment blocks (service / endpoint / auth / rate limit / cost / fallback), Google-style function docstrings, section dividers, inline comments for non-obvious logic, and the production startup block in main.py. Does NOT change logic — documentation only.

---

---

## Agent Architecture Quick Map

```
User Message
    ↓
POST /chat  (app/main.py)
    ↓
OrchestratorAgent  (app/agents/orchestrator.py)
    ├─ Path A (returning) ─→ RecRankingAgent → ContentAgent
    └─ Path B (new)       ─→ RecRankingAgent → ContentAgent → CompareAgent
                                    ↓
                            AppointmentAgent  (after payment)
                                    ↓
                            GuardrailAgent    (wraps EVERY response)
                                    ↓
                            ChatResponse → UI
```

---

## Data Files

| File | Contents | Editable |
|------|----------|----------|
| `app/data/tyres.json` | 30 tyre entries | ✅ Yes — use `/add-tyre` schema |
| `app/data/users.json` | 5 member profiles | ✅ Yes |
| `app/data/locations.json` | 5 Costco tyre centres | ✅ Yes |
| `app/data/appointments.json` | Booked appointments (runtime) | ✅ Reset with `/reset-data` |

---

## Test Members

| Member ID | Name | Type | Vehicle | City |
|-----------|------|------|---------|------|
| M10042 | Sarah Chen | Returning (Path A) | Toyota Camry 2020 | Seattle |
| M10043 | James Park | Returning (Path A) | Ford F-150 2021 | Portland |
| M10044 | Emily Torres | New buyer (Path B) | Honda CR-V 2022 | San Francisco |
| M10045 | David Kim | New buyer (Path B) | BMW 3 Series 2022 | Los Angeles |
| M10046 | Lisa Wang | Returning (Path A) | Toyota RAV4 2019 | Phoenix |
