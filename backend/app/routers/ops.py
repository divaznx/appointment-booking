from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.config import get_settings
from app.dependencies import Principal, require_roles
from app.schemas.ops import RecurringSeriesCreate, WebhookEndpointCreate
from app.security.webhooks import canonical_json, sign_payload, verify_signature
from app.services.recurrence import materialize_series
from app.supabase_client import supabase

router = APIRouter(tags=["ops"])


@router.post("/recurring-series")
async def create_recurring_series(
    body: RecurringSeriesCreate,
    user: Principal = Depends(require_roles("staff", "admin")),
):
    inserted = (
        supabase.table("recurring_series")
        .insert(
            {
                "rrule": body.rrule,
                "dtstart": body.dtstart,
                "duration_minutes": body.duration_minutes,
                "timezone": body.timezone,
                "tenant_id": body.tenant_id or user.tenant_id,
                "location_id": body.location_id,
                "resource_id": body.resource_id,
            }
        )
        .execute()
        .data
    )
    if not inserted:
        raise HTTPException(status_code=500, detail="Failed to create series")
    series_id = inserted[0]["id"]
    occurrences = materialize_series(series_id, body.materialize_count)
    return {"series": inserted[0], "occurrences": occurrences}


@router.post("/webhooks/endpoints")
async def register_webhook(
    body: WebhookEndpointCreate,
    user: Principal = Depends(require_roles("admin")),
):
    rows = (
        supabase.table("webhook_endpoints")
        .insert(
            {
                "url": str(body.url),
                "secret": body.secret,
                "tenant_id": body.tenant_id or user.tenant_id,
            }
        )
        .execute()
        .data
    )
    return rows[0] if rows else {"status": "ok"}


@router.post("/webhooks/inbound")
async def inbound_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    settings = get_settings()
    body = await request.body()
    if not verify_signature(settings.webhook_secret, body, x_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return {"accepted": True}


@router.post("/internal/jobs/drain")
async def drain_outbox(
    user: Principal = Depends(require_roles("admin")),
    x_internal_token: str | None = Header(default=None),
):
    settings = get_settings()
    if x_internal_token != settings.internal_job_token:
        raise HTTPException(status_code=401, detail="Invalid worker token")
    jobs = (
        supabase.table("outbox_jobs")
        .select("*")
        .is_("processed_at", "null")
        .order("id")
        .limit(20)
        .execute()
        .data
    ) or []
    delivered = []
    endpoints = supabase.table("webhook_endpoints").select("*").execute().data or []
    for job in jobs:
        payload = {"job_type": job["job_type"], "payload": job["payload"], "id": job["id"]}
        body = canonical_json(payload)
        for endpoint in endpoints:
            signature = sign_payload(endpoint["secret"], body)
            delivered.append(
                {
                    "job_id": job["id"],
                    "url": endpoint["url"],
                    "signature": signature,
                    "body": payload,
                }
            )
        from datetime import datetime, timezone

        supabase.table("outbox_jobs").update(
            {"processed_at": datetime.now(timezone.utc).isoformat(), "attempts": job.get("attempts", 0) + 1}
        ).eq("id", job["id"]).execute()
    return {"processed": len(jobs), "deliveries": delivered}


@router.get("/audit-log")
async def list_audit_log(user: Principal = Depends(require_roles("admin", "staff"))):
    query = supabase.table("audit_log").select("*").order("created_at", desc=True).limit(100)
    if user.role != "admin" and user.tenant_id:
        query = query.eq("tenant_id", user.tenant_id)
    return query.execute().data or []
