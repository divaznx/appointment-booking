from fastapi import HTTPException
from postgrest.exceptions import APIError


def http_from_api_error(exc: APIError) -> HTTPException:
    code = (exc.code or "").upper()
    message = (exc.message or str(exc)).lower()

    if code == "42501" or "forbidden" in message:
        return HTTPException(status_code=403, detail="You cannot modify this appointment")
    if code == "P0002" or ("not found" in message and "cancelled" not in message):
        return HTTPException(status_code=404, detail="Appointment not found")
    if code == "P0001":
        if "not found" in message or "cancelled" in message:
            return HTTPException(
                status_code=404,
                detail="Appointment not found or already cancelled",
            )
        return HTTPException(status_code=409, detail="Slot is not available")
    if code == "23505" or "duplicate key" in message:
        return HTTPException(status_code=409, detail="Slot is not available")
    if code in {"PGRST202", "42883"}:
        return HTTPException(status_code=503, detail="Booking procedure is not installed")
    return HTTPException(status_code=500, detail="Database request failed")
