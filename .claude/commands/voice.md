# Voice Agent Setup (ElevenLabs)

Configure and test the ElevenLabs TTS voice agent for the Costco Tyre Assistant.

---

## Setup

1. Get your API key from https://elevenlabs.io (free tier: 10,000 chars/month)
2. Add to `.env`:
   ```
   ELEVENLABS_API_KEY=sk_...
   ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
   ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
   ```
3. Restart server: `uvicorn app.main:app --reload`

---

## Voice IDs — Recommended for a retail assistant

| Voice | ID | Character |
|-------|-----|-----------|
| Rachel (default) | `21m00Tcm4TlvDq8ikWAM` | Warm, professional, clear |
| Adam | `pNInz6obpgDQGcFmaJgB` | Authoritative, confident |
| Bella | `EXAVITQu4vr4xnSDxMaL` | Friendly, approachable |
| Elli | `MF3mGyEYCl7XYWbV9V6O` | Upbeat, energetic |

---

## Check voice status

```bash
curl -s http://localhost:8000/voice/status | python -m json.tool
# {"enabled": true, "model": "eleven_turbo_v2_5"}
```

## Test TTS endpoint directly

```bash
curl -s -X POST http://localhost:8000/voice/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Welcome to Costco Tyre Assistant. I am here to help you find the perfect tyres."}' \
  --output test_voice.mp3

# Play it (Windows)
start test_voice.mp3
```

## Test with a longer response

```bash
curl -s -X POST http://localhost:8000/voice/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Great news Sarah! Based on your Toyota Camry and your previous Bridgestone Turanza, I have found three excellent options for you today. Your top pick is the Michelin Primacy 4 at one hundred and sixty nine dollars member price, with an impressive 4.8 star rating and 80,000 kilometre tread life."}' \
  --output test_voice2.mp3 && start test_voice2.mp3
```

---

## UI — Voice controls in the chat

| Control | What it does |
|---------|-------------|
| 🎤 Mic button | Click to start/stop speech-to-text (browser Web Speech API) |
| 🔊 Speaker button | Click to read the last assistant response aloud via ElevenLabs |
| Click speaker again | Stops playback |

**Browser compatibility:**
- Chrome / Edge: ✅ Full support (STT + TTS)
- Firefox: ✅ TTS only (no Web Speech API for STT)
- Safari: ⚠️ Limited STT support

---

## Model comparison

| Model | Latency | Quality | Use case |
|-------|---------|---------|----------|
| `eleven_turbo_v2_5` | ~300ms | Good | Real-time chat (recommended) |
| `eleven_turbo_v2` | ~400ms | Better | Balanced |
| `eleven_multilingual_v2` | ~700ms | Best | High quality demos |

---

## Disable voice

Remove `ELEVENLABS_API_KEY` from `.env` or set it to empty.
The UI will hide the speaker button and disable the mic tooltip.
