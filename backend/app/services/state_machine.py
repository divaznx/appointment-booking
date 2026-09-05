ALLOWED = {
    "held": {"booked", "expired", "cancelled"},
    "booked": {"cancelled", "completed", "no_show"},
    "cancelled": set(),
    "completed": set(),
    "no_show": set(),
    "expired": set(),
    "available": {"held", "booked"},
}


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED.get(current, set())
