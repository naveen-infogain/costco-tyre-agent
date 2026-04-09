"""
Module: whatsapp_service
Purpose: Send WhatsApp booking confirmation messages via Twilio
Layer: service
Dependencies:
  - twilio: Twilio REST client for WhatsApp messaging
  - os: reads TWILIO_* environment variables
Production notes:
  - Env vars required: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
                       TWILIO_FROM_WHATSAPP, TWILIO_TO_WHATSAPP
  - Twilio WhatsApp sandbox: sender must be whatsapp:+14155238886 (sandbox)
    or your approved WhatsApp Business number
  - TWILIO_TO_WHATSAPP: recipient number in E.164 format e.g. whatsapp:+919876543210
  - Swap point: replace TWILIO_TO_WHATSAPP with user.phone_number when
    phone numbers are added to member profiles
  - Silently skips (no exception) if credentials are not set — app runs normally
"""
from __future__ import annotations
import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credential loading — all optional; service no-ops if any are missing
# ---------------------------------------------------------------------------
_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID", "")
_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN", "")
_FROM_WA      = os.environ.get("TWILIO_FROM_WHATSAPP", "")   # whatsapp:+14155238886
_TO_WA        = os.environ.get("TWILIO_TO_WHATSAPP", "")     # whatsapp:+91XXXXXXXXXX


def _whatsapp_enabled() -> bool:
    """Return True only when all four Twilio env vars are set."""
    return bool(_ACCOUNT_SID and _AUTH_TOKEN and _FROM_WA and _TO_WA)


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def _build_booking_message(
    member_name: str,
    booking_id: str,
    order_id: str,
    date: str,
    time: str,
    location: str,
    address: str,
    tyre: str,
) -> str:
    """
    Build the WhatsApp booking confirmation message body.

    Args:
        member_name: Member's full name (e.g. "Sarah Chen")
        booking_id:  Booking reference (e.g. "BK-20250409-ABC1")
        order_id:    Order reference (e.g. "ORD-20250409-XY12")
        date:        Human-readable date (e.g. "Wednesday, April 9")
        time:        24h time string (e.g. "10:30")
        location:    Short location name (e.g. "Seattle Northgate")
        address:     Full address string
        tyre:        Tyre description (e.g. "Michelin Primacy 4 x4")

    Returns:
        Formatted WhatsApp message string (plain text, no markdown).
    """
    first = member_name.split()[0]
    return (
        f"Hi {first}! 🎉 Your Costco tyre appointment is confirmed.\n\n"
        f"📅 *{date}* at *{time}*\n"
        f"📍 {location}\n"
        f"   {address}\n"
        f"🛞 {tyre}\n"
        f"🔖 Booking ID: `{booking_id}`\n"
        f"📦 Order ID: `{order_id}`\n\n"
        f"Please bring:\n"
        f"  • Vehicle registration\n"
        f"  • Costco membership card\n\n"
        f"See you there! — TireAssist 🚗"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_booking_confirmation(
    member_name: str,
    booking_id: str,
    order_id: str,
    date: str,
    time: str,
    location: str,
    address: str,
    tyre: str,
) -> dict:
    """
    Send a WhatsApp booking confirmation to the configured recipient number.

    Silently succeeds (logs a warning) if Twilio credentials are not set,
    so the booking flow is never interrupted by a missing WhatsApp config.

    Args:
        member_name: Member's display name.
        booking_id:  Booking reference ID.
        order_id:    Order reference ID.
        date:        Human-readable appointment date.
        time:        Appointment time (HH:MM).
        location:    Short location name.
        address:     Full location address.
        tyre:        Tyre model description including quantity.

    Returns:
        Dict with keys:
          - sent (bool): True if message was dispatched successfully.
          - sid  (str):  Twilio message SID on success, "" on skip/failure.
          - error(str):  Error description on failure, "" on success.

    Side effects:
        Calls Twilio REST API — one outbound WhatsApp message per booking.

    Example:
        result = send_booking_confirmation(
            "Sarah Chen", "BK-001", "ORD-001",
            "Wednesday, April 9", "10:30",
            "Seattle Northgate", "401 NE Northgate Way, Seattle WA",
            "Michelin Primacy 4 x4"
        )
        # {"sent": True, "sid": "SM...", "error": ""}
    """
    if not _whatsapp_enabled():
        logger.info("whatsapp_service: credentials not set — skipping WhatsApp notification")
        return {"sent": False, "sid": "", "error": "Twilio credentials not configured"}

    body = _build_booking_message(
        member_name=member_name,
        booking_id=booking_id,
        order_id=order_id,
        date=date,
        time=time,
        location=location,
        address=address,
        tyre=tyre,
    )

    # ── External API Call ────────────────────────────────────────────────────
    # Service:    Twilio WhatsApp  (Messages REST API)
    # Endpoint:   POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json
    # Auth:       TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN (Basic auth)
    # From:       TWILIO_FROM_WHATSAPP (whatsapp:+14155238886 for sandbox)
    # To:         TWILIO_TO_WHATSAPP   (whatsapp:+91XXXXXXXXXX)
    # Rate limit: ~1 msg/sec per number; free sandbox = 5 recipients max
    # Latency:    ~500ms–1s
    # Fallback:   Returns {"sent": False, "error": ...} — never raises
    try:
        from twilio.rest import Client  # lazy import — app runs without twilio installed
        client = Client(_ACCOUNT_SID, _AUTH_TOKEN)
        message = client.messages.create(
            from_=_FROM_WA,
            to=_TO_WA,
            body=body,
        )
        logger.info("WhatsApp confirmation sent — SID: %s", message.sid)
        return {"sent": True, "sid": message.sid, "error": ""}
    except ImportError:
        logger.warning("whatsapp_service: twilio package not installed — run: pip install twilio")
        return {"sent": False, "sid": "", "error": "twilio package not installed"}
    except Exception as exc:
        logger.error("WhatsApp send failed: %s", exc)
        return {"sent": False, "sid": "", "error": str(exc)}
