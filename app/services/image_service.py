"""
Module: image_service
Purpose: Claude Vision API integration — tyre identification from sidewall images
         and tyre health analysis from tread/sole photos
Layer: service
Dependencies:
  - anthropic: Vision API for image analysis (claude-sonnet-4-6)
Production notes:
  - Env vars required: ANTHROPIC_API_KEY
  - Cost: ~$0.005–0.01 per image call (vision pricing)
  - Swap points: swap prompt constants to tune extraction accuracy
"""

from __future__ import annotations

import json
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt — instructs Claude to classify and analyse the tyre image
# ---------------------------------------------------------------------------
_VISION_PROMPT = """Analyse this tyre image and return ONLY a JSON object — no markdown, no explanation.

Determine which scenario applies:

SCENARIO A — TYRE SIDEWALL (image shows a tyre side with size numbers/text visible):
Extract the tyre size (format: XXX/XXRXX e.g. 205/55R16), brand, model if visible.
Return: {"scenario":"sidewall","tyre_size":"205/55R16","brand":"Michelin","model":"Primacy 4","confidence":"high"}

SCENARIO B — TYRE TREAD / SOLE (image shows the rubber contact surface or tread pattern):
Score the tyre health. DEFAULT to 7 or above unless you see obvious damage. Rules:
  - If tread grooves are clearly visible → score 7 minimum, likely 8
  - If tread is deep and tyre looks relatively new → score 9-10
  - Only score 5-6 if tread is noticeably shallow but grooves still exist
  - Only score 3-4 if tread wear indicators (raised bars in grooves) are visible
  - Only score 1-2 if tread is completely worn flat or tyre is damaged/cracked
  - Dirt, discolouration, or normal road grime does NOT reduce the score
  - When in doubt, score higher not lower
recommendation must be exactly one of: "continue" (score 5+), "replace_soon" (score 3-4), "replace_now" (score 1-2).
Return: {"scenario":"tread","health_score":8,"wear_level":"good","tread_depth_estimate":"6mm","wear_pattern":"even","recommendation":"continue","findings":["Finding 1","Finding 2"]}

SCENARIO C — VEHICLE (image shows a car and tyres are visible on it):
If tyres on the vehicle look inflated and normal with no obvious damage → score 7-8. Only go lower for visible bulges, flat spots, or completely bald tread.
Return: {"scenario":"car","health_score":7,"wear_level":"good","recommendation":"continue","findings":["Finding 1"]}

SCENARIO D — UNCLEAR (cannot determine tyre-related information):
Return: {"scenario":"unclear","message":"Brief description of what is shown"}

Return ONLY the JSON object, nothing else."""


def analyze_tyre_image(image_data: str, image_type: str) -> dict:
    """
    Analyse a tyre image using Claude Vision and return structured results.

    Args:
        image_data: Base64-encoded image bytes (no data URI prefix).
        image_type: MIME type — "image/jpeg" | "image/png" | "image/webp".

    Returns:
        Dict with 'scenario' key and scenario-specific fields:
        - sidewall: tyre_size, brand, model, confidence
        - tread:    health_score (1-10), wear_level, tread_depth_estimate,
                    wear_pattern, recommendation, findings
        - car:      health_score, wear_level, recommendation, findings
        - unclear:  message

    Side effects:
        None — pure analysis, no writes.

    Example:
        result = analyze_tyre_image(b64_str, "image/jpeg")
        # {"scenario": "sidewall", "tyre_size": "205/55R16", "brand": "Michelin", ...}
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"scenario": "unclear", "message": "Vision analysis unavailable — ANTHROPIC_API_KEY not set."}

    client = anthropic.Anthropic(api_key=api_key)

    try:
        # ── External API Call ────────────────────────────────────────────────
        # Service:    Anthropic Claude Vision  (claude-sonnet-4-6)
        # Endpoint:   POST https://api.anthropic.com/v1/messages
        # Auth:       ANTHROPIC_API_KEY (required in .env)
        # Params:     max_tokens=512, vision input via base64 image block
        # Rate limit: ~60 req/min on Tier 1 — back off on 429
        # Cost:       ~$0.005–0.01 per call (image tokens + output tokens)
        # Fallback:   Returns 'unclear' scenario — caller must handle gracefully
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": _VISION_PROMPT},
                ],
            }],
        )

        raw = response.content[0].text.strip()
        # Strip any accidental markdown code fences
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        return json.loads(raw)

    except json.JSONDecodeError as exc:
        logger.warning("image_service: failed to parse Vision response — %s", exc)
        return {"scenario": "unclear", "message": "Could not read the image clearly. Please try a well-lit, close-up photo."}
    except anthropic.RateLimitError:
        logger.warning("image_service: rate limit hit")
        return {"scenario": "unclear", "message": "Service is busy — please try again in a moment."}
    except Exception as exc:
        logger.error("image_service: unexpected error — %s", exc)
        return {"scenario": "unclear", "message": "Image analysis failed. Please try again."}


def build_health_message(result: dict) -> str:
    """
    Format a tyre health analysis result into a plain-text message.
    Only includes sections that have real content — no empty lines or labels.

    Args:
        result: Dict from analyze_tyre_image() with scenario 'tread' or 'car'.

    Returns:
        Plain string with newlines, ready for BotBubble (white-space: pre-wrap).
    """
    score       = result.get("health_score", 0)
    depth       = (result.get("tread_depth_estimate") or "").strip()
    pattern     = (result.get("wear_pattern") or "").strip().lower()
    recommendation = result.get("recommendation", "continue")
    # Filter out empty or whitespace-only findings
    findings    = [f.strip() for f in result.get("findings", []) if f and f.strip()]

    if score >= 7:
        indicator = "🟢"
        condition = "Good condition"
    elif score >= 5:
        indicator = "🟡"
        condition = "Moderate wear — monitor regularly"
    elif score >= 3:
        indicator = "🟠"
        condition = "Worn — replace soon"
    else:
        indicator = "🔴"
        condition = "Critical — replace immediately"

    rec_map = {
        "continue":     "Your tyres are in good shape. Continue monitoring every 5,000 km.",
        "replace_soon": "Your tyres are approaching the wear limit. Plan a replacement within the next 5,000–8,000 km.",
        "replace_now":  "Your tyres are unsafe. We strongly recommend replacing them as soon as possible.",
    }
    # For moderate scores (5-6) where rec is still "continue", give a softer note
    if score in (5, 6) and recommendation == "continue":
        rec_map["continue"] = "Your tyres have moderate wear but are still roadworthy. Start planning a replacement in the next 10,000–15,000 km."

    lines = [f"Tyre Health Analysis  {indicator}  {score}/10 — {condition}"]

    if depth:
        lines.append(f"Estimated tread depth: {depth}")
    if pattern and pattern not in ("even", ""):
        lines.append(f"Wear pattern: {pattern.capitalize()} — may indicate alignment or tyre pressure issues")
    if findings:
        lines.append("")
        lines.append("Findings:")
        for f in findings:
            lines.append(f"• {f}")

    lines.append("")
    lines.append(rec_map.get(recommendation, ""))

    return "\n".join(lines)
