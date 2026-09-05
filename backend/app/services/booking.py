from typing import Any

from postgrest.exceptions import APIError

from app.errors import http_from_api_error
from app.services.availability import invalidate_availability_cache
from app.services.audit import write_audit
from app.supabase_client import supabase


def as_record(data: Any) -> dict:
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


def book_slot(slot_id: int, user_id: str, idempotency_key: str | None = None) -> dict:
    payload: dict[str, Any] = {"p_slot_id": slot_id, "p_user_id": user_id}
    if idempotency_key:
        payload["p_idempotency_key"] = idempotency_key
    try:
        response = supabase.rpc("book_slot_locked", payload).execute()
    except APIError as e:
        raise http_from_api_error(e) from e
    invalidate_availability_cache()
    row = as_record(response.data)
    write_audit(
        "appointment.booked",
        user_id,
        "appointment",
        str(row.get("id")),
        None,
        {"slot_id": slot_id},
    )
    return row


def cancel_appointment(appointment_id: int, user_id: str, as_staff: bool) -> dict:
    try:
        response = supabase.rpc(
            "cancel_slot_locked",
            {
                "p_appointment_id": appointment_id,
                "p_user_id": user_id,
                "p_as_staff": as_staff,
            },
        ).execute()
    except APIError as e:
        raise http_from_api_error(e) from e
    invalidate_availability_cache()
    write_audit(
        "appointment.cancelled",
        user_id,
        "appointment",
        str(appointment_id),
        None,
    )
    return as_record(response.data)


def hold_slot(slot_id: int, user_id: str, hold_seconds: int) -> dict:
    try:
        response = supabase.rpc(
            "hold_slot",
            {
                "p_slot_id": slot_id,
                "p_user_id": user_id,
                "p_hold_seconds": hold_seconds,
            },
        ).execute()
    except APIError as e:
        raise http_from_api_error(e) from e
    invalidate_availability_cache()
    write_audit("slot.held", user_id, "slot", str(slot_id), None)
    return as_record(response.data)


def list_user_appointments(user_id: str, tenant_id: str | None) -> list:
    query = supabase.table("appointments").select("*").eq("user_id", user_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    response = query.order("created_at", desc=True).execute()
    return response.data or []
