from fastapi import FastAPI, HTTPException

from app.supabase_client import supabase
from app.schemas.appointment import AppointmentCreate, AppointmentCancel
from app.schemas.auth import SignUpRequest, LoginRequest
#from supabase.exceptions import APIError
from postgrest.exceptions import APIError
from supabase_auth.errors import AuthApiError
from uuid import UUID


app = FastAPI(
    title="Appointment Booking API",
    description="Backend API for appointment booking system",
    version="0.1.0",
)


@app.get("/")
async def health_check():
    return {"status": "ok"}


@app.get("/slots")
async def get_slots():
    response = supabase.table("slots").select("*").execute()

    print("Supabase response:", response)

    return response.data


@app.post("/appointments")
async def create_appointment(appointment: AppointmentCreate):

    # 1. Find the requested slot
    # Check slot
    # slot_response = (
    #     supabase
    #     .table("slots")
    #     .select("*")
    #     .eq("id", appointment.slot_id)
    #     .execute()
    # )

    # if not slot_response.data:
    #     raise HTTPException(
    #         status_code=404,
    #         detail=f"Slot with id {appointment.slot_id} not found"
    #     )

    # slot = slot_response.data[0]

    # if slot["status"] != "available":
    #     raise HTTPException(
    #         status_code=409,
    #         detail=f"Slot with id {appointment.slot_id} is already booked"
    #     )

    # # Create appointment
    # try:
        # appointment_response = (
        #     supabase
        #     .table("appointments")
        #     .insert({
        #         "slot_id": appointment.slot_id,
        #         "user_id": str(appointment.user_id),
        #         "status": "booked"
        #     })
        #     .execute()
        # )

    #     appointment_response = (
    #         supabase
    #         .table("appointments")
    #         .insert({
    #             "slot_id": appointment.slot_id,
    #             "user_id": str(appointment.user_id),
    #             "status": "booked"
    #         })
    #         .execute()
    #     )

    #     print("APPOINTMENT RESPONSE:", appointment_response)

    # except APIError:
    #     raise HTTPException(
    #         status_code=409,
    #         detail="Slot is already booked"
    #     )

    # # Mark slot as booked
    # supabase \
    #     .table("slots") \
    #     .update({"status": "booked"}) \
    #     .eq("id", appointment.slot_id) \
    #     .execute()

    # return appointment_response.data[0]
    # response = supabase.rpc(
    #     "book_appointment",
    #     {
    #         "p_slot_id": appointment.slot_id,
    #         "p_user_id": str(appointment.user_id)
    #     }
    # ).execute()

    # if not response.data:
    #     raise HTTPException(
    #         status_code=409,
    #         detail="Slot is not available"
    #     )

    # return response.data

    try:
        response = supabase.rpc(
            "book_appointment",
            {
                "p_slot_id": appointment.slot_id,
                "p_user_id": str(appointment.user_id)
            }
        ).execute()

    except APIError as e:
        if e.code == "P0001":
            raise HTTPException(
                status_code=409,
                detail="Slot is not available"
            )

        raise HTTPException(
            status_code=500,
            detail="Failed to create appointment"
        )

    return response.data

@app.get("/appointments")
async def get_appointments():
    response = ( 
        supabase
        .table("appointments")
        .select("*")
        .execute()
    )

    return response.data[0]

@app.get("/appointments/{user_id}")
async def get_appointments(user_id: UUID):
    response = (
        supabase
        .table("appointments")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )

    return response.data[0]

@app.delete("/appointments")
async def cancel_appointment(request: AppointmentCancel):

    try:
        response = (
            supabase
            .rpc(
                "cancel_appointment",
                {
                    "p_appointment_id": request.appointment_id,
                    "p_user_id": str(request.user_id)
                }
            )
            .execute()
        )

    except APIError as e:
        if e.code == "P0001":
            raise HTTPException(
                status_code=404,
                detail="Appointment not found or already cancelled"
            )

        raise HTTPException(
            status_code=500,
            detail="Failed to cancel appointment"
        )

    return response.data

@app.post("/signup")
async def signup(request: SignUpRequest):

    try:
        response = supabase.auth.sign_up(
            {
                "email": request.email,
                "password": request.password,
            }
        )

        return {
            "message": "User created successfully",
            "user_id": response.user.id if response.user else None,
        }

    except APIError as e:
        raise HTTPException(
            status_code=400,
            detail=e.message,
        )


@app.post("/login")
async def login(request: LoginRequest):
    try:
        response = supabase.auth.sign_in_with_password(
            {
                "email": request.email,
                "password": request.password,
            }
        )

        return {
            "message": "Login successful",
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user_id": response.user.id,
        }

    except AuthApiError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        )