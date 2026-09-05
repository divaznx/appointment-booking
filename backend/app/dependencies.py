from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from app.supabase_client import create_supabase_client, supabase


@dataclass
class Principal:
    id: str
    email: str | None
    role: str
    tenant_id: str | None


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized()
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _unauthorized()
    try:
        auth_client = create_supabase_client()
        response = auth_client.auth.get_user(token)
        user = response.user
        if not user:
            raise _unauthorized("Invalid or expired token")
    except HTTPException:
        raise
    except Exception:
        raise _unauthorized("Invalid or expired token")

    role = "customer"
    tenant_id = None
    try:
        profiles = (
            supabase.table("profiles")
            .select("role,tenant_id")
            .eq("id", str(user.id))
            .limit(1)
            .execute()
            .data
        )
        if profiles:
            role = profiles[0].get("role") or "customer"
            tenant_id = profiles[0].get("tenant_id")
        else:
            role = (user.app_metadata or {}).get("role") or (
                user.user_metadata or {}
            ).get("role") or "customer"
    except Exception:
        role = (user.app_metadata or {}).get("role") or "customer"

    return Principal(
        id=str(user.id),
        email=user.email,
        role=role,
        tenant_id=str(tenant_id) if tenant_id else None,
    )


def require_roles(*roles: str):
    async def dependency(principal: Principal = Depends(get_current_user)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return principal

    return dependency
