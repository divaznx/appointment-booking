from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.dependencies import Principal, get_current_user
from app.schemas.auth import LoginRequest, SignUpRequest
from app.services.audit import write_audit
from app.supabase_client import create_supabase_client, supabase
from supabase_auth.errors import AuthApiError

router = APIRouter(tags=["auth"])


@router.get("/oauth/{provider}/url")
async def oauth_authorize_url(provider: str, redirect_to: str | None = None):
    settings = get_settings()
    allowed = {"google", "apple", "azure", "github"}
    if provider not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported OAuth provider")
    redirect = redirect_to or settings.oauth_redirect_url
    url = (
        f"{settings.supabase_url.rstrip('/')}/auth/v1/authorize"
        f"?provider={provider}&redirect_to={redirect}"
    )
    return {"authorization_url": url, "provider": provider, "protocol": "OAuth2/OIDC"}


@router.post("/signup")
async def signup(request: SignUpRequest):
    settings = get_settings()
    try:
        auth_client = create_supabase_client()
        response = auth_client.auth.sign_up(
            {"email": request.email, "password": request.password}
        )
    except AuthApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if settings.auto_confirm_email and response.user:
        supabase.auth.admin.update_user_by_id(
            str(response.user.id),
            {"email_confirm": True},
        )
    if response.user:
        try:
            supabase.table("profiles").insert(
                {"id": str(response.user.id), "role": "customer"}
            ).execute()
        except Exception:
            pass
        write_audit("user.signup", str(response.user.id), "user", str(response.user.id))

    return {
        "message": "User created successfully",
        "user_id": response.user.id if response.user else None,
        "email_confirmation_required": not settings.auto_confirm_email,
    }


@router.post("/login")
async def login(request: LoginRequest):
    try:
        auth_client = create_supabase_client()
        response = auth_client.auth.sign_in_with_password(
            {"email": request.email, "password": request.password}
        )
    except AuthApiError as e:
        raise HTTPException(status_code=401, detail=str(e))

    if not response.session or not response.user:
        raise HTTPException(status_code=401, detail="Login failed")

    write_audit("user.login", str(response.user.id), "user", str(response.user.id))
    return {
        "message": "Login successful",
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "token_type": "bearer",
        "user_id": response.user.id,
    }


@router.get("/me")
async def get_me(user: Principal = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
    }


@router.get("/me/export")
async def export_my_data(user: Principal = Depends(get_current_user)):
    appointments = (
        supabase.table("appointments")
        .select("*")
        .eq("user_id", user.id)
        .execute()
        .data
    )
    write_audit("gdpr.export", user.id, "user", user.id)
    return {
        "user": {"id": user.id, "email": user.email, "role": user.role},
        "appointments": appointments or [],
    }


@router.delete("/me")
async def delete_my_account(user: Principal = Depends(get_current_user)):
    supabase.table("appointments").delete().eq("user_id", user.id).execute()
    try:
        supabase.table("profiles").delete().eq("id", user.id).execute()
    except Exception:
        pass
    supabase.auth.admin.delete_user(user.id)
    write_audit("gdpr.delete", user.id, "user", user.id)
    return {"message": "Account and appointment records deleted"}
