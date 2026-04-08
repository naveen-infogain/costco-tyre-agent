"""
Module: voice_service.py
Purpose: ElevenLabs TTS streaming for converting agent text to speech
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
"""
from __future__ import annotations
import os
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")

# ElevenLabs streaming TTS endpoint
_TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"


async def text_to_speech_stream(text: str) -> AsyncIterator[bytes]:
    """
    Stream MP3 audio bytes from ElevenLabs for the given text.

    Yields audio chunks as they arrive from the streaming endpoint.
    Uses eleven_turbo_v2_5 for minimum time-to-first-chunk latency (~300ms).
    Text is cleaned and capped at 500 chars before sending to control cost and latency.

    Args:
        text: Raw agent response text (may contain markdown, JSON, URLs).
              Cleaned internally by _clean_for_tts() before the API call.

    Yields:
        bytes: MP3 audio chunks (4096 bytes each).
               Caller (StreamingResponse in main.py) sends chunks directly to browser.

    Side effects:
        Logs a warning if ELEVENLABS_API_KEY is not set.
        Logs an error if the API call fails.
        Returns without yielding if voice is disabled or text is empty after cleaning.
    """
    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not set — voice disabled")
        return

    # Strip markdown, code blocks, and URLs — voice reads clean prose only
    clean = _clean_for_tts(text)
    if not clean:
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
                "stability": 0.5,          # 0-1: higher = more consistent voice
                "similarity_boost": 0.75,  # 0-1: higher = closer to original voice
                "style": 0.0,              # 0-1: 0 = neutral, no style exaggeration
                "use_speaker_boost": True, # Enhances voice clarity
            },
            "optimize_streaming_latency": 3,  # 0-4: 3 = aggressive latency optimisation
        }

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


def _clean_for_tts(text: str) -> str:
    """Remove markdown, JSON blocks, and trim to ~500 chars for TTS."""
    import re
    # Remove JSON code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`[^`]+`", "", text)
    # Remove markdown emphasis
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Cap at 500 chars at sentence boundary
    if len(text) > 500:
        cutoff = text[:500].rfind(". ")
        text = text[:cutoff + 1] if cutoff > 200 else text[:500]
    return text


def voice_enabled() -> bool:
    """Return True if ElevenLabs is configured."""
    return bool(ELEVENLABS_API_KEY)
