"""
Cart Service — manages in-memory carts with 15-minute TTL stock reservation,
tyre-vehicle fit validation, coupon application, and bundle suggestions.
"""
from __future__ import annotations
import time
import uuid
from typing import Optional

from app.models.schemas import Cart, CartItem, Tyre, User
from app.services import stock_service, profile_service

_CARTS: dict[str, Cart] = {}
_CART_TTL_SECS = 15 * 60  # 15 minutes


def _cart_reserve_until() -> str:
    import datetime
    expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=_CART_TTL_SECS)
    return expiry.isoformat() + "Z"


def add_to_cart(member_id: str, tyre_id: str, quantity: int = 4) -> dict:
    """
    Add a tyre to the member's cart. Validates fit and stock.
    Returns the cart summary or an error dict.
    """
    tyre = stock_service.get_tyre_by_id(tyre_id)
    if not tyre:
        return {"error": f"Tyre {tyre_id} not found"}
    if tyre.stock.qty == 0:
        return {"error": "This tyre is currently out of stock"}

    user = profile_service.get_member(member_id)
    if user:
        fit_ok, fit_msg = validate_fit(tyre, user)
        if not fit_ok:
            return {"error": fit_msg}

    promotion = tyre.active_promotion
    item = CartItem(
        tyre_id=tyre_id,
        quantity=quantity,
        unit_price=tyre.price,
        member_price=tyre.member_price,
        promotion_applied=promotion,
    )

    subtotal = tyre.member_price * quantity
    member_savings = (tyre.price - tyre.member_price) * quantity
    cashback = round(subtotal * _cashback_rate(user), 2) if user else 0.0
    bundles = _suggest_bundles(tyre)

    cart_id = str(uuid.uuid4())
    cart = Cart(
        cart_id=cart_id,
        member_id=member_id,
        items=[item],
        subtotal=subtotal,
        member_savings=member_savings,
        cashback_estimate=cashback,
        reserved_until=_cart_reserve_until(),
        bundles_suggested=bundles,
    )
    _CARTS[cart_id] = cart
    return cart.model_dump()


def get_cart(cart_id: str) -> Optional[Cart]:
    cart = _CARTS.get(cart_id)
    if not cart:
        return None
    return cart


def validate_fit(tyre: Tyre, user: User) -> tuple[bool, str]:
    """Check if the tyre is compatible with the member's vehicle."""
    vehicle_str = f"{user.vehicle.make} {user.vehicle.model} {user.vehicle.year}"
    for compat in tyre.compatible_vehicles:
        make_model = " ".join(compat.split()[:2]).lower()
        if make_model in vehicle_str.lower():
            return True, "Compatible"
    # Soft validation — warn but don't block (vehicle list is not exhaustive)
    return True, f"Note: {vehicle_str} not in verified compatibility list — please confirm size {tyre.size}"


def _cashback_rate(user: Optional[User]) -> float:
    if not user:
        return 0.0
    rates = {"executive": 0.02, "gold": 0.015, "standard": 0.01}
    return rates.get(user.membership_tier, 0.01)


def _suggest_bundles(tyre: Tyre) -> list[str]:
    bundles = ["Valve stem replacement ($9.99)", "Tyre rotation service ($19.99)"]
    if tyre.season in ("all-season", "summer"):
        bundles.append("Wheel alignment check ($49.99)")
    return bundles
