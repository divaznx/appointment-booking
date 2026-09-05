from typing import Any

from app.supabase_client import supabase


def write_audit(
    action: str,
    actor_id: str | None,
    entity_type: str,
    entity_id: str | None = None,
    tenant_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        supabase.table("audit_log").insert(
            {
                "action": action,
                "actor_id": actor_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "tenant_id": tenant_id,
                "metadata": metadata or {},
            }
        ).execute()
    except Exception:
        return


def enqueue_job(job_type: str, payload: dict[str, Any]) -> None:
    try:
        supabase.table("outbox_jobs").insert(
            {"job_type": job_type, "payload": payload}
        ).execute()
    except Exception:
        return
