from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

from app.supabase_client import supabase


def materialize_series(series_id: str, count: int = 30) -> list[dict]:
    rows = (
        supabase.table("recurring_series")
        .select("*")
        .eq("id", series_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return []
    row = rows[0]
    tz = ZoneInfo(row.get("timezone") or "UTC")
    dtstart = row["dtstart"]
    if isinstance(dtstart, str):
        dtstart = datetime.fromisoformat(str(dtstart).replace("Z", "+00:00"))
    rule = rrulestr(row["rrule"], dtstart=dtstart)
    duration = int(row["duration_minutes"])
    created: list[dict] = []
    for occurrence in list(rule)[:count]:
        if occurrence.tzinfo is None:
            start = occurrence.replace(tzinfo=tz)
        else:
            start = occurrence.astimezone(tz)
        end_dt = start + timedelta(minutes=duration)
        start_utc = start.astimezone(timezone.utc)
        end_utc = end_dt.astimezone(timezone.utc)
        slot_rows = (
            supabase.table("slots")
            .insert(
                {
                    "start_time": start_utc.isoformat(),
                    "end_time": end_utc.isoformat(),
                    "status": "available",
                    "timezone": row.get("timezone") or "UTC",
                    "tenant_id": row.get("tenant_id"),
                    "location_id": row.get("location_id"),
                    "resource_id": row.get("resource_id"),
                }
            )
            .execute()
            .data
        )
        slot_id = slot_rows[0]["id"] if slot_rows else None
        occ_rows = (
            supabase.table("recurring_occurrences")
            .upsert(
                {
                    "series_id": series_id,
                    "start_time": start_utc.isoformat(),
                    "end_time": end_utc.isoformat(),
                    "slot_id": slot_id,
                },
                on_conflict="series_id,start_time",
            )
            .execute()
            .data
        )
        created.append(occ_rows[0] if occ_rows else {"slot_id": slot_id})
    return created
