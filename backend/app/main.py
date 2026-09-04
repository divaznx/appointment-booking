from fastapi import FastAPI
from app.supabase_client import supabase

app = FastAPI(
    title="Appointment Booking API",
    description="Backend API for appointment booking system",  
    version="0.1.0",
)

@app.get("/")
async def health_check():
    return {"status": "ok"}

# @app.get("/slots")
# async def get_slots():
#     response = supabase.table("slots").select("*").execute()
#     return response.data

@app.get("/slots")
def get_slots():
    response = supabase.table("slots").select("*").execute()
    return response.data