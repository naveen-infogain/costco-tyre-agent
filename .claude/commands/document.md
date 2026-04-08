# /document — Apply Code Documentation Standards

Apply the full Code Documentation Standards from CLAUDE.md to a file in this project.

## What this skill does

Audits the target file and adds or improves:

1. **File-level module docstring** — module name, purpose, layer, dependencies, production notes
2. **API call comment blocks** — service name, endpoint, auth, params, rate limits, latency, cost, fallback
3. **Function / method docstrings** — Google style: summary, Args, Returns, Side effects, Example
4. **Section divider comments** — ASCII dividers for logical blocks in long files
5. **Inline comments** — non-obvious logic, magic numbers, regex patterns, fallback behaviour
6. **Production startup block** — in `app/main.py` only: env vars, start commands, health check, architecture notes
7. **TODO/FIXME tags** — structured format with owner and context

## Usage

```
/document app/main.py
/document app/agents/orchestrator.py
/document app/services/cart_service.py
/document app/tools/recommendation_tools.py
```

## Instructions for Claude

When this skill is invoked:

1. Read the target file in full.
2. Check each of the 7 standards above — note what is missing or incomplete.
3. Apply all missing/incomplete documentation in a single Edit pass:
   - Add module docstring at the top (after `from __future__ import annotations` if present)
   - Add API call comment block directly above every `get_llm().invoke()`, `httpx` call, `elevenlabs` call, or any `requests`/`aiohttp` call
   - Add Google-style docstring to every function and class that lacks one
   - Add or clean up section divider comments to match the `# ----` format
   - Add inline comments where logic is non-obvious — but do NOT add comments to self-evident lines
   - If the file is `app/main.py`, add the production startup block at the top of the file (after imports, before the FastAPI `app = FastAPI(...)` line)
4. Do NOT change any logic, variable names, or structure — documentation only.
5. After editing, print a summary: files changed, number of docstrings added, API call blocks added.

## API call block template (Anthropic)

```python
# ── External API Call ────────────────────────────────────────────────────
# Service:    Anthropic Claude  (claude-sonnet-4-6)
# Endpoint:   POST https://api.anthropic.com/v1/messages
# Auth:       ANTHROPIC_API_KEY (required in .env — app fails without it)
# Params:     max_tokens=1024, temperature=0
# Rate limit: ~60 req/min on Tier 1 — back off on HTTP 429
# Latency:    ~800ms p50 / ~2s p99
# Cost:       ~$0.003 per call (1K input + 1K output tokens, Sonnet pricing)
# Fallback:   Caller receives "" — must handle empty response gracefully
```

## API call block template (ElevenLabs)

```python
# ── External API Call ────────────────────────────────────────────────────
# Service:    ElevenLabs TTS  (eleven_turbo_v2_5)
# Endpoint:   POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream
# Auth:       ELEVENLABS_API_KEY (optional — returns 503 if absent)
# Params:     voice_id=ELEVENLABS_VOICE_ID, model_id=eleven_turbo_v2_5
# Rate limit: Plan-dependent (free = 10k chars/month)
# Latency:    ~300ms time-to-first-chunk (streaming MP3)
# Fallback:   /voice/status returns {"enabled": false} — UI hides voice button
```

## Standards reference

Full standard is in `CLAUDE.md` under **Code Documentation Standards**.
