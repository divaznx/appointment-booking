from supabase import Client, create_client

from app.config import get_settings


def create_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


# Service-role client for tables, RPCs, and admin only. Never sign_in or get_user on it.
supabase: Client = create_supabase_client()
