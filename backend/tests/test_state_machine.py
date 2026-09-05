from app.services.state_machine import can_transition


def test_booked_can_be_cancelled():
    assert can_transition("booked", "cancelled") is True


def test_cancelled_is_terminal():
    assert can_transition("cancelled", "booked") is False


def test_held_can_be_booked():
    assert can_transition("held", "booked") is True


def test_unknown_status_cannot_transition():
    assert can_transition("weird", "booked") is False
