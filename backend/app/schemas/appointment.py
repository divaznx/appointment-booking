from pydantic import BaseModel
from uuid import UUID


class AppointmentCreate(BaseModel):
    slot_id: int
    user_id: UUID


class AppointmentCancel(BaseModel):
    appointment_id: int
    user_id: UUID