from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.errors import http_from_api_error


def test_maps_slot_conflict():
    err = APIError({"message": "Slot is not available", "code": "P0001", "hint": None, "details": None})
    http = http_from_api_error(err)
    assert isinstance(http, HTTPException)
    assert http.status_code == 409


def test_maps_forbidden_cancel():
    err = APIError({"message": "Forbidden", "code": "42501", "hint": None, "details": None})
    http = http_from_api_error(err)
    assert http.status_code == 403


def test_maps_missing_appointment():
    err = APIError({"message": "Appointment not found", "code": "P0002", "hint": None, "details": None})
    http = http_from_api_error(err)
    assert http.status_code == 404


def test_maps_unique_violation_to_conflict():
    err = APIError(
        {
            "message": 'duplicate key value violates unique constraint "appointments_one_active_per_slot"',
            "code": "23505",
            "hint": None,
            "details": None,
        }
    )
    http = http_from_api_error(err)
    assert http.status_code == 409
