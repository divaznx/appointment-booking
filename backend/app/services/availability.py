from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def slot_start_utc(slot: dict[str, Any]) -> datetime:
    raw = str(slot["start_time"]).replace("Z", "+00:00")
    start = datetime.fromisoformat(raw)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start.astimezone(timezone.utc)


def is_bookable(slot: dict[str, Any], now: datetime | None = None) -> bool:
    now = now or _now()
    if slot_start_utc(slot) <= now:
        return False
    held_until = slot.get("held_until")
    if held_until and slot.get("status") == "held":
        held = datetime.fromisoformat(str(held_until).replace("Z", "+00:00"))
        if held.tzinfo is None:
            held = held.replace(tzinfo=timezone.utc)
        if held > now:
            return False
    model = slot.get("booking_model") or "single"
    if model == "capacity":
        capacity = int(slot.get("capacity") or 1)
        booked = int(slot.get("booked_count") or 0)
        return booked < capacity
    return slot.get("status") in ("available", "held")


_CACHE_TS: float | None = None
_CACHE_TTL_SECONDS = 15
_STORE: dict[tuple, list] = {}


def list_available_slots(tenant_id: str | None = None, location_id: str | None = None):
    from app.supabase_client import supabase

    query = supabase.table("slots").select("*")
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    if location_id:
        query = query.eq("location_id", location_id)
    response = query.execute()
    now = _now()
    return [slot for slot in response.data or [] if is_bookable(slot, now)]


def list_available_slots_cached(tenant_id: str | None = None, location_id: str | None = None):
    import time

    global _CACHE_TS
    key = (tenant_id, location_id)
    now = time.monotonic()
    if key in _STORE and _CACHE_TS and now - _CACHE_TS < _CACHE_TTL_SECONDS:
        return _STORE[key]
    data = list_available_slots(tenant_id, location_id)
    _CACHE_TS = now
    _STORE[key] = data
    return data


def invalidate_availability_cache() -> None:
    global _CACHE_TS
    _STORE.clear()
    _CACHE_TS = None
