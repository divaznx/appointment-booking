from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from app.dependencies import Principal, get_current_user
from app.schemas.appointment import AppointmentCancel, AppointmentCreate, HoldRequest
from app.services import booking as booking_service
from app.services.availability import list_available_slots, slot_start_utc

router = APIRouter(tags=["appointments"])


def _localize_slots(slots: list[dict], tz: str | None) -> list[dict]:
    if not tz:
        return slots
    try:
        zone = ZoneInfo(tz)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid timezone") from exc
    localized = []
    for slot in slots:
        item = dict(slot)
        start = slot_start_utc(slot)
        end_raw = datetime.fromisoformat(str(slot["end_time"]).replace("Z", "+00:00"))
        if end_raw.tzinfo is None:
            end_raw = end_raw.replace(tzinfo=timezone.utc)
        item["start_time_local"] = start.astimezone(zone).isoformat()
        item["end_time_local"] = end_raw.astimezone(zone).isoformat()
        item["display_timezone"] = tz
        localized.append(item)
    return localized


@router.get("/slots")
async def get_slots(
    tenant_id: str | None = Query(default=None),
    location_id: str | None = Query(default=None),
    tz: str | None = Query(default=None, description="IANA timezone for display offsets"),
):
    slots = list_available_slots(tenant_id, location_id)
    return _localize_slots(slots, tz)


@router.post("/slots/{slot_id}/hold")
async def hold_slot(
    slot_id: int,
    body: HoldRequest,
    user: Principal = Depends(get_current_user),
):
    return booking_service.hold_slot(slot_id, user.id, body.hold_seconds)


@router.post("/appointments")
async def create_appointment(
    appointment: AppointmentCreate,
    user: Principal = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return booking_service.book_slot(
        appointment.slot_id,
        user.id,
        idempotency_key,
    )


@router.get("/appointments")
async def get_appointments(user: Principal = Depends(get_current_user)):
    return booking_service.list_user_appointments(user.id, user.tenant_id)


@router.delete("/appointments/{appointment_id}")
async def cancel_appointment_by_id(
    appointment_id: int,
    user: Principal = Depends(get_current_user),
):
    as_staff = user.role in ("staff", "admin")
    return booking_service.cancel_appointment(appointment_id, user.id, as_staff)


@router.delete("/appointments")
async def cancel_appointment(
    body: AppointmentCancel,
    user: Principal = Depends(get_current_user),
):
    as_staff = user.role in ("staff", "admin")
    return booking_service.cancel_appointment(body.appointment_id, user.id, as_staff)
