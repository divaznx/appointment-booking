from datetime import datetime, timedelta, timezone

from app.services.availability import is_bookable, slot_start_utc


def _slot(**overrides):
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    end = start + timedelta(minutes=30)
    base = {
        "id": 1,
        "status": "available",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "booking_model": "single",
        "capacity": 1,
        "booked_count": 0,
    }
    base.update(overrides)
    return base


def test_slot_start_utc_parses_z_suffix():
    start = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    parsed = slot_start_utc({"start_time": "2026-09-06T12:00:00Z"})
    assert parsed == start


def test_past_slot_is_not_bookable():
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    slot = _slot(start_time=start.isoformat(), end_time=(start + timedelta(minutes=30)).isoformat())
    assert is_bookable(slot) is False


def test_future_available_slot_is_bookable():
    assert is_bookable(_slot()) is True


def test_held_slot_is_not_bookable_for_others():
    held_until = datetime.now(timezone.utc) + timedelta(minutes=5)
    slot = _slot(status="held", held_until=held_until.isoformat())
    assert is_bookable(slot) is False


def test_capacity_slot_bookable_until_full():
    slot = _slot(booking_model="capacity", capacity=3, booked_count=2, status="available")
    assert is_bookable(slot) is True
    slot["booked_count"] = 3
    assert is_bookable(slot) is False
