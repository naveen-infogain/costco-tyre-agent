"""
Guardrail Tools — checks run on every agent response before it reaches the member.
Checks: hallucination, tyre-vehicle fit, PII redaction, safety, bias audit.
"""
from __future__ import annotations
import json
import re
import time
from pathlib import Path
from langchain_core.tools import tool
from app.services import stock_service

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_PII_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                                  # SSN
    re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),                      # phone
    re.compile(r"\b\d{5}(?:-\d{4})?\b"),                                    # ZIP (loose)
]


def _log_guardrail(check: str, result: str, session_id: str, reason: str = "") -> None:
    log_file = _LOG_DIR / "guardrail.json"
    entries: list = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
    entries.append({
        "check": check,
        "result": result,
        "session_id": session_id,
        "reason": reason,
        "timestamp": time.time(),
    })
    log_file.write_text(json.dumps(entries[-500:], indent=2), encoding="utf-8")


@tool
def check_hallucination(response_text: str, tyre_ids_json: str, session_id: str) -> str:
    """
    Verify that any tyre specs mentioned in the response match the actual catalogue.
    Args:
        response_text: The agent's response string
        tyre_ids_json: JSON list of tyre IDs referenced in the response
        session_id: Current session ID for logging
    Returns JSON: {"pass": true} or {"pass": false, "reason": "..."}
    """
    try:
        tyre_ids = json.loads(tyre_ids_json)
    except Exception:
        tyre_ids = []

    for tid in tyre_ids:
        tyre = stock_service.get_tyre_by_id(tid)
        if not tyre:
            reason = f"Tyre ID {tid} referenced but not in catalogue"
            _log_guardrail("hallucination", "violation", session_id, reason)
            return json.dumps({"pass": False, "reason": reason})

        # Check price is not wildly off (within $50 of real price)
        price_mentions = re.findall(r"\$(\d+(?:\.\d{2})?)", response_text)
        for pm in price_mentions:
            mentioned = float(pm)
            if abs(mentioned - tyre.member_price) > 50 and abs(mentioned - tyre.price) > 50:
                reason = f"Price ${pm} in response doesn't match {tid} (${tyre.member_price})"
                _log_guardrail("hallucination", "violation", session_id, reason)
                return json.dumps({"pass": False, "reason": reason})

    _log_guardrail("hallucination", "pass", session_id)
    return json.dumps({"pass": True})


@tool
def validate_fit(tyre_id: str, vehicle_json: str, session_id: str) -> str:
    """
    Confirm a tyre is compatible with the member's vehicle.
    Args:
        tyre_id: Tyre ID to check
        vehicle_json: JSON with make, model, year fields
        session_id: Current session ID for logging
    Returns JSON: {"pass": true} or {"pass": false, "reason": "..."}
    """
    tyre = stock_service.get_tyre_by_id(tyre_id)
    if not tyre:
        reason = f"Tyre {tyre_id} not found in catalogue"
        _log_guardrail("fit_validation", "violation", session_id, reason)
        return json.dumps({"pass": False, "reason": reason})

    try:
        vehicle = json.loads(vehicle_json)
        make = vehicle.get("make", "").lower()
        model = vehicle.get("model", "").lower()
    except Exception:
        _log_guardrail("fit_validation", "pass", session_id, "vehicle parse failed — soft pass")
        return json.dumps({"pass": True, "note": "Could not parse vehicle — soft pass"})

    for compat in tyre.compatible_vehicles:
        if make in compat.lower() or model in compat.lower():
            _log_guardrail("fit_validation", "pass", session_id)
            return json.dumps({"pass": True})

    # Soft pass — compatibility list not exhaustive; warn but don't block
    note = f"{tyre_id} not in verified list for {make} {model} — size {tyre.size}"
    _log_guardrail("fit_validation", "warning", session_id, note)
    return json.dumps({"pass": True, "warning": note})


@tool
def redact_pii(response_text: str, session_id: str) -> str:
    """
    Strip any PII from a response before it reaches the member.
    Args:
        response_text: Raw agent response
        session_id: Current session ID for logging
    Returns JSON: {"clean_text": "...", "redacted": true/false}
    """
    clean = response_text
    redacted = False
    for pattern in _PII_PATTERNS:
        if pattern.search(clean):
            clean = pattern.sub("[REDACTED]", clean)
            redacted = True

    if redacted:
        _log_guardrail("pii_redaction", "violation", session_id, "PII found and redacted")
    else:
        _log_guardrail("pii_redaction", "pass", session_id)

    return json.dumps({"clean_text": clean, "redacted": redacted})


@tool
def check_safety(tyre_id: str, session_id: str) -> str:
    """
    Verify that a tyre's load index and speed rating meet minimum safety standards.
    Args:
        tyre_id: Tyre ID to check
        session_id: Current session ID for logging
    Returns JSON: {"pass": true} or {"pass": false, "reason": "..."}
    """
    tyre = stock_service.get_tyre_by_id(tyre_id)
    if not tyre:
        reason = f"Tyre {tyre_id} not found"
        _log_guardrail("safety", "violation", session_id, reason)
        return json.dumps({"pass": False, "reason": reason})

    # Minimum load index 80 for passenger vehicles
    if tyre.load_index < 80:
        reason = f"Load index {tyre.load_index} below minimum 80"
        _log_guardrail("safety", "violation", session_id, reason)
        return json.dumps({"pass": False, "reason": reason})

    # Speed rating must be recognised
    valid_ratings = {"Q", "S", "T", "H", "V", "W", "Y", "Z"}
    if tyre.speed_rating not in valid_ratings:
        reason = f"Speed rating {tyre.speed_rating!r} not recognised"
        _log_guardrail("safety", "violation", session_id, reason)
        return json.dumps({"pass": False, "reason": reason})

    _log_guardrail("safety", "pass", session_id)
    return json.dumps({"pass": True, "load_index": tyre.load_index, "speed_rating": tyre.speed_rating})


@tool
def audit_bias(tyre_ids_json: str, session_id: str) -> str:
    """
    Check that recommendations aren't dominated by a single brand.
    Args:
        tyre_ids_json: JSON list of recommended tyre IDs (typically 3)
        session_id: Current session ID for logging
    Returns JSON: {"pass": true} or {"pass": false, "reason": "..."}
    """
    try:
        tyre_ids = json.loads(tyre_ids_json)
    except Exception:
        return json.dumps({"pass": True, "note": "Could not parse tyre IDs"})

    if len(tyre_ids) <= 1:
        _log_guardrail("bias_audit", "pass", session_id, "single result — no bias check needed")
        return json.dumps({"pass": True})

    brands = []
    for tid in tyre_ids:
        t = stock_service.get_tyre_by_id(tid)
        if t:
            brands.append(t.brand)

    if not brands:
        return json.dumps({"pass": True})

    from collections import Counter
    counts = Counter(brands)
    dominant_brand, dominant_count = counts.most_common(1)[0]

    if dominant_count == len(brands) and len(brands) > 1:
        reason = f"All {len(brands)} slots are {dominant_brand} — brand diversity required"
        _log_guardrail("bias_audit", "violation", session_id, reason)
        return json.dumps({"pass": False, "reason": reason, "brand_counts": dict(counts)})

    _log_guardrail("bias_audit", "pass", session_id)
    return json.dumps({"pass": True, "brand_counts": dict(counts)})
