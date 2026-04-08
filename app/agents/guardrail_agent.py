"""
Guardrail Agent — wraps EVERY response before it reaches the member.
Runs 5 checks: hallucination, fit validation, PII redaction, safety, bias audit.
On failure: logs violation, returns None (caller must regenerate).
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from app.tools.guardrail_tools import (
    check_hallucination,
    validate_fit,
    redact_pii,
    check_safety,
    audit_bias,
)

logger = logging.getLogger(__name__)


class GuardrailAgent:
    def check(
        self,
        response: str,
        session_id: str,
        tyre_ids: Optional[list[str]] = None,
        vehicle: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Run all guardrail checks on a response.

        Returns the (possibly redacted) safe response, or None if a hard
        violation was detected (caller should regenerate).

        Args:
            response:   Raw agent response text
            session_id: Current session ID
            tyre_ids:   Tyre IDs referenced in the response (for hallucination/safety/bias)
            vehicle:    Member vehicle dict {make, model, year} (for fit check)
        """
        tyre_ids = tyre_ids or []
        tyre_ids_json = json.dumps(tyre_ids)

        # 1. Hallucination check
        result = json.loads(check_hallucination.invoke({
            "response_text": response,
            "tyre_ids_json": tyre_ids_json,
            "session_id": session_id,
        }))
        if not result.get("pass"):
            logger.warning("Guardrail HALLUCINATION violation: %s", result.get("reason"))
            return None

        # 2. Tyre-vehicle fit validation (per tyre)
        if vehicle:
            vehicle_json = json.dumps(vehicle)
            for tid in tyre_ids:
                fit = json.loads(validate_fit.invoke({
                    "tyre_id": tid,
                    "vehicle_json": vehicle_json,
                    "session_id": session_id,
                }))
                if not fit.get("pass"):
                    logger.warning("Guardrail FIT violation: %s", fit.get("reason"))
                    return None

        # 3. Safety check (per tyre)
        for tid in tyre_ids:
            safety = json.loads(check_safety.invoke({
                "tyre_id": tid,
                "session_id": session_id,
            }))
            if not safety.get("pass"):
                logger.warning("Guardrail SAFETY violation: %s", safety.get("reason"))
                return None

        # 4. Bias audit
        if len(tyre_ids) > 1:
            bias = json.loads(audit_bias.invoke({
                "tyre_ids_json": tyre_ids_json,
                "session_id": session_id,
            }))
            if not bias.get("pass"):
                logger.warning("Guardrail BIAS violation: %s", bias.get("reason"))
                return None

        # 5. PII redaction (always runs — cleans output even on pass)
        pii_result = json.loads(redact_pii.invoke({
            "response_text": response,
            "session_id": session_id,
        }))
        clean = pii_result.get("clean_text", response)
        if pii_result.get("redacted"):
            logger.info("Guardrail PII: redacted content in session %s", session_id)

        return clean
