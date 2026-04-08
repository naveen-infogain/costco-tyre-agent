"""
Payment Service — mock payment processing with Costco Visa detection,
cashback rewards, and order ID generation.
"""
from __future__ import annotations
import uuid
from typing import Optional

from app.models.schemas import Cart, OrderSummary
from app.services.cart_service import get_cart

_ORDERS: dict[str, OrderSummary] = {}


def process_payment(member_id: str, cart_id: str, payment_method: Optional[str] = None) -> dict:
    """
    Process payment for the given cart. Returns an OrderSummary or error dict.
    Auto-detects Costco Visa and applies cashback.
    """
    cart = get_cart(cart_id)
    if not cart:
        return {"error": "Cart not found or expired"}
    if cart.member_id != member_id:
        return {"error": "Cart does not belong to this member"}

    # Auto-detect Costco Visa if not specified
    if not payment_method:
        payment_method = "Costco Visa Rewards"

    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    order = OrderSummary(
        order_id=order_id,
        member_id=member_id,
        cart_id=cart_id,
        total=cart.subtotal,
        payment_method=payment_method,
        cashback_earned=cart.cashback_estimate,
        status="confirmed",
    )
    _ORDERS[order_id] = order
    return order.model_dump()


def get_order(order_id: str) -> Optional[OrderSummary]:
    return _ORDERS.get(order_id)


def payment_failure_response(cart_id: str) -> dict:
    """Return a friendly error response preserving the cart for retry."""
    return {
        "error": "Payment could not be processed at this time.",
        "cart_id": cart_id,
        "action": "retry",
        "message": "Your cart has been saved. Please try again or use a different payment method.",
    }
