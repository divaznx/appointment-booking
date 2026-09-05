from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from postgrest.exceptions import APIError

from app.dependencies import Principal, get_current_user, require_roles
from app.schemas.appointment import AppointmentCancel, AppointmentCreate, HoldRequest
from app.services.availability import invalidate_availability_cache, list_available_slots_cached
from app.services.audit import enqueue_job, write_audit
from app.supabase_client import supabase

router = APIRouter(tags=["appointments"])


def _rpc_or_legacy_book(slot_id: int, user_id: str, idempotency_key: str | None):
    payload = {"p_slot_id": slot_id, "p_user_id": user_id}
    if idempotency_key:
        payload["p_idempotency_key"] = idempotency_key
    try:
        return supabase.rpc("book_slot_locked", payload).execute()
    except APIError as e:
        if e.code == "P0001":
            raise
        if e.code in {"PGRST202", "42883"} or "does not exist" in str(e).lower():
            return supabase.rpc(
                "book_appointment",
                {"p_slot_id": slot_id, "p_user_id": user_id},
            ).execute()
        raise


def _rpc_or_legacy_cancel(appointment_id: int, user_id: str, as_staff: bool):
    try:
        return supabase.rpc(
            "cancel_slot_locked",
            {
                "p_appointment_id": appointment_id,
                "p_user_id": user_id,
                "p_as_staff": as_staff,
            },
        ).execute()
    except APIError as e:
        if e.code == "P0001":
            raise
        if e.code in {"PGRST202", "42883"} or "does not exist" in str(e).lower():
            return supabase.rpc(
                "cancel_appointment",
                {"p_appointment_id": appointment_id, "p_user_id": user_id},
            ).execute()
        raise


@router.get("/slots")
async def get_slots(
    tenant_id: str | None = Query(default=None),
    location_id: str | None = Query(default=None),
    tz: str | None = Query(default=None, description="IANA timezone for display offsets"),
):
    slots = list_available_slots_cached(tenant_id, location_id)
    if not tz:
        return slots
    try:
        zone = ZoneInfo(tz)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timezone")
    localized = []
    for slot in slots:
        item = dict(slot)
        start = datetime.fromisoformat(str(slot["start_time"]).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(slot["end_time"]).replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        item["start_time_local"] = start.astimezone(zone).isoformat()
        item["end_time_local"] = end.astimezone(zone).isoformat()
        item["display_timezone"] = tz
        localized.append(item)
    return localized


@router.post("/slots/{slot_id}/hold")
async def hold_slot(
    slot_id: int,
    body: HoldRequest,
    user: Principal = Depends(get_current_user),
):
    try:
        response = supabase.rpc(
            "hold_slot",
            {
                "p_slot_id": slot_id,
                "p_user_id": user.id,
                "p_hold_seconds": body.hold_seconds,
            },
        ).execute()
    except APIError as e:
        if e.code == "P0001":
            raise HTTPException(status_code=409, detail="Slot is not available")
        raise HTTPException(
            status_code=503,
            detail="Hold is unavailable until production SQL is applied",
        )
    invalidate_availability_cache()
    write_audit("slot.held", user.id, "slot", str(slot_id), user.tenant_id)
    return response.data


@router.post("/appointments")
async def create_appointment(
    appointment: AppointmentCreate,
    request: Request,
    user: Principal = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    try:
        response = _rpc_or_legacy_book(
            appointment.slot_id,
            user.id,
            idempotency_key,
        )
    except APIError as e:
        if e.code == "P0001":
            raise HTTPException(status_code=409, detail="Slot is not available")
        raise HTTPException(status_code=500, detail="Failed to create appointment")

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else {}
    invalidate_availability_cache()
    write_audit(
        "appointment.booked",
        user.id,
        "appointment",
        str((data or {}).get("id")),
        user.tenant_id,
        {"slot_id": appointment.slot_id, "path": str(request.url.path)},
    )
    return data


def _list_my_appointments(user: Principal):
    query = supabase.table("appointments").select("*").eq("user_id", user.id)
    if user.tenant_id:
        query = query.eq("tenant_id", user.tenant_id)
    response = query.order("created_at", desc=True).execute()
    return response.data or []


@router.get("/appointments")
async def get_appointments(user: Principal = Depends(get_current_user)):
    return _list_my_appointments(user)


@router.get("/appointments/me")
async def get_my_appointments(user: Principal = Depends(get_current_user)):
    return _list_my_appointments(user)


def _cancel(appointment_id: int, user: Principal):
    as_staff = user.role in ("staff", "admin")
    try:
        response = _rpc_or_legacy_cancel(appointment_id, user.id, as_staff)
    except APIError as e:
        if e.code == "P0001":
            raise HTTPException(
                status_code=404,
                detail="Appointment not found or already cancelled",
            )
        raise HTTPException(status_code=500, detail="Failed to cancel appointment")
    invalidate_availability_cache()
    write_audit("appointment.cancelled", user.id, "appointment", str(appointment_id), user.tenant_id)
    return response.data


@router.delete("/appointments/{appointment_id}")
async def cancel_appointment_by_id(
    appointment_id: int,
    user: Principal = Depends(get_current_user),
):
    return _cancel(appointment_id, user)


@router.delete("/appointments")
async def cancel_appointment(
    body: AppointmentCancel,
    user: Principal = Depends(get_current_user),
):
    return _cancel(body.appointment_id, user)
