import os

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY is not set")

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    )

print("Supabase client initialized successfully")
