from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    slot_id: int = Field(gt=0)


class AppointmentCancel(BaseModel):
    appointment_id: int = Field(gt=0)


class HoldRequest(BaseModel):
    hold_seconds: int = Field(default=120, ge=30, le=900)
