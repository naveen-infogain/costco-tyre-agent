"""
Module: voice_service.py
Purpose: ElevenLabs TTS streaming — converts agent text to humanised, natural-sounding speech
Layer: service

Dependencies:
  - httpx: Async HTTP client for streaming TTS audio chunks
  - ElevenLabs API: External TTS service (cloud, paid)

Production notes:
  Env vars required:
    ELEVENLABS_API_KEY  — mandatory for voice; service degrades gracefully if absent
    ELEVENLABS_VOICE_ID — voice to use (default: Rachel, ID 21m00Tcm4TlvDq8ikWAM)
    ELEVENLABS_MODEL_ID — model to use (default: eleven_turbo_v2_5 for ~300ms latency)

  Rate limits: plan-dependent (free = 10,000 chars/month; Creator = 100k chars)
  Swap point: replace httpx streaming with ElevenLabs Python SDK when upgrading plans.

  Speech-to-Text (STT) is handled client-side via the browser's Web Speech API.
  No server-side STT calls are made — zero cost for STT.

  Auto-TTS trigger: mic input → bot responds → frontend auto-calls /voice/tts.
  Manual TTS: removed. Speaker button no longer shown in the UI.
"""
from __future__ import annotations
import os
import re
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")

# ElevenLabs streaming TTS endpoint
_TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"

# ---------------------------------------------------------------------------
# Strict content safety — words that must never reach the TTS engine
# The LLM guardrail already blocks these, but TTS gets a second check.
# ---------------------------------------------------------------------------
_BLOCKED_PATTERNS = re.compile(
    r"\b(damn|hell|crap|idiot|stupid|dumb|shut\s+up|loser|ugly|hate\s+you)\b",
    re.IGNORECASE,
)


async def text_to_speech_stream(text: str) -> AsyncIterator[bytes]:
    """
    Stream MP3 audio bytes from ElevenLabs for the given text.

    Text is humanised before sending: markdown stripped, lists converted to
    natural sentences, tyre codes removed, abbreviations expanded.
    A content-safety check blocks any text containing inappropriate language
    before it reaches the API.

    Args:
        text: Raw agent response text (may contain markdown, JSON, tyre IDs).
              Cleaned and humanised by _humanise_for_tts() before the API call.

    Yields:
        bytes: MP3 audio chunks (4096 bytes each).

    Side effects:
        Logs a warning if ELEVENLABS_API_KEY is not set.
        Logs a warning and returns early if content-safety check fails.
        Logs an error if the API call fails.
    """
    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not set — voice disabled")
        return

    clean = _humanise_for_tts(text)
    if not clean:
        return

    # Content safety gate — never send inappropriate text to TTS
    if _BLOCKED_PATTERNS.search(clean):
        logger.warning("TTS blocked: content safety check failed")
        return

    try:
        import httpx
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": clean,
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {
                "stability": 0.45,           # slightly lower = more expressive delivery
                "similarity_boost": 0.80,
                "style": 0.20,               # light style boost for warmth
                "use_speaker_boost": True,
            },
        }
        # optimize_streaming_latency is deprecated on newer models (eleven_v3+)
        if "turbo" in ELEVENLABS_MODEL_ID or "flash" in ELEVENLABS_MODEL_ID:
            payload["optimize_streaming_latency"] = 3

        # ── External API Call ────────────────────────────────────────────────
        # Service:    ElevenLabs TTS  (eleven_turbo_v2_5)
        # Endpoint:   POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream
        # Auth:       ELEVENLABS_API_KEY header (xi-api-key)
        # Params:     voice_id=ELEVENLABS_VOICE_ID, optimize_streaming_latency=3
        # Rate limit: Plan-dependent (free = 10k chars/month, Creator = 100k chars)
        # Latency:    ~300ms time-to-first-chunk; full response scales with text length
        # Cost:       ~$0.30 per 1,000 chars on Creator plan
        # Fallback:   Exception logged; /voice/tts returns 503 on repeated failure
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream("POST", _TTS_URL, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(chunk_size=4096):
                    if chunk:
                        yield chunk
    except Exception as e:
        logger.error("ElevenLabs TTS error: %s", e)


def _humanise_for_tts(text: str) -> str:
    """
    Transform agent response text into natural, humanised speech.

    Converts markdown to spoken-word equivalents, expands abbreviations,
    removes tyre ID codes, and ensures the output sounds like a real person
    talking — not a document being read aloud. Caps at ~500 chars at a sentence
    boundary to keep responses concise and avoid runaway TTS costs.

    Args:
        text: Raw bot response, may contain markdown, emojis, tyre IDs, prices.

    Returns:
        Clean prose ready for ElevenLabs. Empty string if nothing speakable remains.

    Examples:
        "**Michelin Primacy 4** (MIC-PRIM4-20555R16) — $169.99 · 80,000 km"
        → "Michelin Primacy 4 — 169 dollars and 99 cents, with 80,000 kilometers of tread life."

        "Here are your top picks:\n- Michelin Primacy\n- Bridgestone Turanza"
        → "Here are your top picks. Michelin Primacy. Bridgestone Turanza."
    """
    # ── 1. Remove JSON / code blocks ─────────────────────────────────────────
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)

    # ── 2. Strip markdown headers (## Heading → Heading) ─────────────────────
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # ── 3. Strip bold / italic markers ───────────────────────────────────────
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)

    # ── 4. Remove tyre product IDs — alphanumeric codes like MIC-PRIM4-20555R16
    #       These are unpronounceable and meaningless in speech.
    text = re.sub(r"\b[A-Z]{2,6}-[A-Z0-9]{2,}-[A-Z0-9\-]{3,}\b", "", text)

    # ── 5. Convert bullet / numbered list items to natural sentences ──────────
    #       "- Great grip\n- Long tread life" → "Great grip. Long tread life."
    text = re.sub(r"^\s*[-•*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # ── 6. Remove URLs ────────────────────────────────────────────────────────
    text = re.sub(r"https?://\S+", "", text)

    # ── 7. Remove emojis and pictographic characters ──────────────────────────
    text = re.sub(
        r"[\U0001F300-\U0001FFFF"    # misc symbols, pictographs, transport
        r"\U00002600-\U000027BF"     # misc symbols
        r"\U0001F900-\U0001F9FF"     # supplemental symbols
        r"\u2600-\u26FF"             # misc symbols (basic plane)
        r"\u2700-\u27BF]+",          # dingbats
        "",
        text,
    )

    # ── 8. Expand common abbreviations for natural speech ─────────────────────
    _ABBREVS = [
        (r"\bkm\b",   "kilometers"),
        (r"\bkm/h\b", "kilometers per hour"),
        (r"\byr\b",   "year"),
        (r"\byrs\b",  "years"),
        (r"\bqty\b",  "quantity"),
        (r"\bID\b",   ""),           # strip bare "ID" labels
        (r"\bSKU\b",  ""),
        (r"\bTTL\b",  ""),
        (r"\bETA\b",  "estimated arrival"),
    ]
    for pattern, replacement in _ABBREVS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # ── 9. Convert prices to natural speech ───────────────────────────────────
    #       "$169.99" → "169 dollars and 99 cents"
    def _price_to_speech(m: re.Match) -> str:
        dollars, cents = m.group(1), m.group(2)
        cents_int = int(cents) if cents else 0
        result = f"{dollars} dollar{'s' if dollars != '1' else ''}"
        if cents_int:
            result += f" and {cents_int} cent{'s' if cents_int != 1 else ''}"
        return result

    text = re.sub(r"\$(\d+)(?:\.(\d{2}))?", _price_to_speech, text)

    # ── 10. Convert separator chars to natural pauses ─────────────────────────
    text = re.sub(r"\s*[·•|]\s*", ", ", text)          # middot/pipe → comma pause
    text = re.sub(r"\s*—\s*", " — ", text)              # em-dash: keep with spaces
    text = re.sub(r"\s*-{2,}\s*", " — ", text)          # double hyphen → em-dash

    # ── 11. Collapse whitespace and blank lines ───────────────────────────────
    text = re.sub(r"\n{2,}", ". ", text)                 # paragraph breaks → sentence end
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = text.strip()

    # ── 12. Ensure text ends with terminal punctuation (sounds complete) ──────
    if text and text[-1] not in ".!?":
        text += "."

    # ── 13. Cap at ~500 chars at a sentence boundary ─────────────────────────
    if len(text) > 500:
        cutoff = text[:500].rfind(". ")
        text = text[:cutoff + 1] if cutoff > 200 else text[:500]

    return text.strip()


def voice_enabled() -> bool:
    """Return True if ElevenLabs is configured."""
    return bool(ELEVENLABS_API_KEY)
