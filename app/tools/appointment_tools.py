"""
Appointment Tools — LangChain @tool wrappers for location lookup,
slot suggestion, booking, and .ics calendar generation.
"""
from __future__ import annotations
import json
import uuid
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool

_LOC_PATH = Path(__file__).parent.parent / "data" / "locations.json"
_APPT_PATH = Path(__file__).parent.parent / "data" / "appointments.json"


def _load_locations() -> list[dict]:
    with open(_LOC_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_appointments() -> list[dict]:
    if not _APPT_PATH.exists():
        return []
    with open(_APPT_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_appointments(appts: list[dict]) -> None:
    _APPT_PATH.write_text(json.dumps(appts, indent=2), encoding="utf-8")


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Rough flat-earth distance in km."""
    return ((lat1 - lat2) ** 2 + (lng1 - lng2) ** 2) ** 0.5 * 111


# City → approximate lat/lng for proximity sorting
_CITY_COORDS = {
    "Seattle": (47.606, -122.332),
    "Portland": (45.523, -122.676),
    "San Francisco": (37.774, -122.419),
    "Los Angeles": (34.052, -118.243),
    "Phoenix": (33.448, -112.074),
}


@tool
def get_nearby_locations(city: str) -> str:
    """
    Return Costco tyre centre locations ranked by proximity to the member's city.
    Args:
        city: Member's city name (e.g. 'Seattle')
    Returns JSON list of locations sorted nearest first.
    """
    locations = _load_locations()
    coords = _CITY_COORDS.get(city, (37.774, -122.419))  # default SF

    ranked = sorted(
        locations,
        key=lambda loc: _distance_km(coords[0], coords[1], loc["lat"], loc["lng"]),
    )
    return json.dumps(ranked)


@tool
def get_available_slots(location_id: str, days_ahead: int = 3) -> str:
    """
    Return available appointment slots at a location for the next N days.
    Args:
        location_id: Warehouse ID (e.g. 'W001')
        days_ahead: Number of days to check (default 3)
    Returns JSON list of TimeSlot objects.
    """
    booked = {
        (a["location_id"], a["date"], a["time"])
        for a in _load_appointments()
        if a.get("status") == "confirmed"
    }

    slots = []
    base = date.today()
    times = ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"]

    for d in range(1, days_ahead + 1):
        slot_date = (base + timedelta(days=d)).isoformat()
        for t in times:
            available = (location_id, slot_date, t) not in booked
            slots.append({
                "slot_id": f"{location_id}-{slot_date}-{t.replace(':', '')}",
                "location_id": location_id,
                "date": slot_date,
                "time": t,
                "available": available,
                "estimated_duration_mins": 60,
            })

    return json.dumps(slots)


@tool
def predict_wait_times(location_id: str, slot_time: str) -> str:
    """
    Estimate installation wait time based on time of day and historical data.
    Args:
        location_id: Warehouse ID
        slot_time: Time string e.g. '10:00'
    Returns JSON with estimated_wait_mins and recommendation.
    """
    locations = _load_locations()
    loc = next((l for l in locations if l["id"] == location_id), None)
    base_wait = loc["avg_wait_mins"] if loc else 35

    # Morning slots are less busy
    hour = int(slot_time.split(":")[0])
    if hour < 11:
        adjusted = max(15, base_wait - 10)
        label = "Low wait — morning slot"
    elif hour >= 14:
        adjusted = base_wait + 10
        label = "Moderate wait — afternoon"
    else:
        adjusted = base_wait
        label = "Average wait — midday"

    return json.dumps({
        "location_id": location_id,
        "slot_time": slot_time,
        "estimated_wait_mins": adjusted,
        "recommendation": label,
    })


@tool
def suggest_best_slot(location_id: str) -> str:
    """
    Suggest the least-busy available slot within the next 3 days.
    Prefers morning slots for shorter wait times.
    Returns JSON of the recommended TimeSlot.
    """
    slots_json = get_available_slots.invoke({"location_id": location_id, "days_ahead": 3})
    slots = json.loads(slots_json)
    available = [s for s in slots if s["available"]]
    if not available:
        return json.dumps({"error": "No available slots in the next 3 days"})

    # Sort: morning first, then by date
    def slot_score(s: dict) -> tuple:
        hour = int(s["time"].split(":")[0])
        morning_bonus = 0 if hour < 11 else 1
        return (s["date"], morning_bonus, s["time"])

    best = sorted(available, key=slot_score)[0]
    return json.dumps(best)


@tool
def book_appointment(
    member_id: str,
    order_id: str,
    location_id: str,
    slot_id: str,
    date_str: str,
    time_str: str,
    tyre_id: str,
) -> str:
    """
    Book a tyre installation appointment.
    Args:
        member_id: Member ID (e.g. 'M10042')
        order_id: Order ID from payment confirmation
        location_id: Warehouse ID
        slot_id: Slot ID from get_available_slots
        date_str: Date in YYYY-MM-DD format
        time_str: Time in HH:MM format
        tyre_id: Tyre ID being installed
    Returns booking confirmation JSON.
    """
    appts = _load_appointments()

    # Check slot is still available
    taken = any(
        a["location_id"] == location_id and a["date"] == date_str and a["time"] == time_str
        and a.get("status") == "confirmed"
        for a in appts
    )
    if taken:
        return json.dumps({"error": "This slot was just taken. Please choose another."})

    booking_id = f"BK-{uuid.uuid4().hex[:8].upper()}"
    appt = {
        "booking_id": booking_id,
        "member_id": member_id,
        "order_id": order_id,
        "location_id": location_id,
        "slot_id": slot_id,
        "date": date_str,
        "time": time_str,
        "tyre_id": tyre_id,
        "status": "confirmed",
    }
    appts.append(appt)
    _save_appointments(appts)

    return json.dumps({"booking_id": booking_id, "status": "confirmed", **appt})


@tool
def link_order_to_booking(order_id: str, booking_id: str) -> str:
    """
    Link an order ID to a booking ID in the appointments log.
    Returns confirmation JSON.
    """
    appts = _load_appointments()
    for a in appts:
        if a["booking_id"] == booking_id:
            a["order_id"] = order_id
            _save_appointments(appts)
            return json.dumps({"status": "linked", "order_id": order_id, "booking_id": booking_id})
    return json.dumps({"error": f"Booking {booking_id} not found"})


@tool
def create_calendar_event(
    booking_id: str,
    member_name: str,
    location_name: str,
    location_address: str,
    date_str: str,
    time_str: str,
    tyre_model: str,
    estimated_duration_mins: int = 60,
) -> str:
    """
    Generate a .ics calendar event for a tyre installation appointment.
    Returns JSON with ics_content string and instructions.
    """
    try:
        from icalendar import Calendar, Event

        cal = Calendar()
        cal.add("prodid", "-//Costco Tyre Agent//costco.com//")
        cal.add("version", "2.0")

        event = Event()
        event.add("summary", f"Tyre Installation — {tyre_model}")
        event.add("description", (
            f"Costco Tyre Installation\n"
            f"Booking ID: {booking_id}\n"
            f"Tyre: {tyre_model}\n"
            f"Location: {location_name}\n"
            f"Address: {location_address}\n"
            f"What to bring: Vehicle registration, Costco membership card"
        ))

        dt_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        dt_end = dt_start + timedelta(minutes=estimated_duration_mins)
        event.add("dtstart", dt_start)
        event.add("dtend", dt_end)
        event.add("location", location_address)
        event.add("uid", f"{booking_id}@costco-tyre-agent")

        cal.add_component(event)
        ics_content = cal.to_ical().decode("utf-8")

        return json.dumps({
            "booking_id": booking_id,
            "ics_content": ics_content,
            "filename": f"costco-tyre-{booking_id}.ics",
            "instructions": "Download and open this file to add to your calendar.",
        })

    except ImportError:
        # icalendar not installed — return plain text summary
        return json.dumps({
            "booking_id": booking_id,
            "ics_content": None,
            "summary": f"Appointment: {tyre_model} installation on {date_str} at {time_str}",
            "location": location_address,
        })
