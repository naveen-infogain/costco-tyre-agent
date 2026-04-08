from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Tyre catalogue
# ---------------------------------------------------------------------------

class TyreStock(BaseModel):
    warehouse_id: str
    qty: int


class Tyre(BaseModel):
    id: str
    brand: str
    model: str
    size: str
    load_index: int
    speed_rating: str
    season: str                   # all-season | winter | summer
    terrain: str                  # highway | city | all-terrain
    price: float
    member_price: float
    tread_life_km: int
    wet_grip: str                 # A | B | C
    noise_db: int
    rating: float
    review_count: int
    warranty_years: int
    compatible_vehicles: list[str]
    stock: TyreStock
    active_promotion: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Member profiles
# ---------------------------------------------------------------------------

class UserLocation(BaseModel):
    city: str
    zip: str


class Vehicle(BaseModel):
    make: str
    model: str
    year: int


class LastPurchase(BaseModel):
    tyre_id: str
    date: str
    mileage_at_purchase: int


class User(BaseModel):
    member_id: str
    name: str
    membership_tier: str          # standard | gold | executive
    location: UserLocation
    vehicle: Vehicle
    driving_habits: list[str]
    last_purchase: Optional[LastPurchase] = None


# ---------------------------------------------------------------------------
# Locations & appointments
# ---------------------------------------------------------------------------

class Location(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    hours: str
    avg_wait_mins: int


class TimeSlot(BaseModel):
    slot_id: str
    location_id: str
    date: str                     # YYYY-MM-DD
    time: str                     # HH:MM
    available: bool
    estimated_duration_mins: int


class Appointment(BaseModel):
    booking_id: str
    member_id: str
    order_id: str
    location_id: str
    slot_id: str
    date: str
    time: str
    tyre_id: str
    status: str                   # confirmed | cancelled


# ---------------------------------------------------------------------------
# Cart & orders
# ---------------------------------------------------------------------------

class CartItem(BaseModel):
    tyre_id: str
    quantity: int
    unit_price: float
    member_price: float
    promotion_applied: Optional[str] = None


class Cart(BaseModel):
    cart_id: str
    member_id: str
    items: list[CartItem]
    subtotal: float
    member_savings: float
    cashback_estimate: float
    reserved_until: str           # ISO timestamp
    bundles_suggested: list[str]  # e.g. ["alignment", "valve stems"]


class OrderSummary(BaseModel):
    order_id: str
    member_id: str
    cart_id: str
    total: float
    payment_method: str
    cashback_earned: float
    status: str                   # confirmed | failed


# ---------------------------------------------------------------------------
# Session & chat
# ---------------------------------------------------------------------------

class SessionState(BaseModel):
    session_id: str
    member_id: Optional[str] = None
    user_path: Optional[str] = None    # "A" | "B"
    stage: str = "enter"               # enter|browse|detail|cart|pay|book|complete
    preferences: dict = {}
    cart_id: Optional[str] = None
    order_id: Optional[str] = None
    booking_id: Optional[str] = None
    last_active: float = 0.0


class ChatMessage(BaseModel):
    role: str                     # user | assistant
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class RecommendationCard(BaseModel):
    tyre: Tyre
    slot_tag: str                 # "Best Repurchase" | "Best Upgrade" | "Most Popular" | "Top Pick" | "Runner-up" | "Budget Alt"
    personalised_msg: str
    stock_badge: str              # "✅ In stock at Seattle Northgate"
    punch_line: Optional[str] = None   # Top Pick only


class ComparisonCard(BaseModel):
    tyres: list[Tyre]
    pros_cons: dict[str, dict]    # tyre_id -> {pros: [...], cons: [...]}
    cost_per_km: dict[str, float] # tyre_id -> cost per km


class ChatResponse(BaseModel):
    message: str
    cards: list[RecommendationCard] = []
    comparison: Optional[ComparisonCard] = None
    appointment_slots: list[TimeSlot] = []
    stage: str = "enter"


# ---------------------------------------------------------------------------
# Analytics & evaluation
# ---------------------------------------------------------------------------

class FunnelStage(BaseModel):
    stage: str
    visitors: int
    drop_rate: float


class AgentScorecardEntry(BaseModel):
    agent: str
    score: int
    trend: int
    status: str                   # "on_target" | "under_review"


class DropAlert(BaseModel):
    stage: str
    current_rate: float
    threshold: float
    status: str                   # "ok" | "warning"


class FeedbackEntry(BaseModel):
    session_id: str
    agent: str
    signal_type: str              # "implicit" | "explicit"
    signal: str                   # e.g. "pick_slot_1", "thumbs_up"
    tyre_id: Optional[str] = None
    timestamp: float
