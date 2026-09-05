from pydantic import BaseModel, Field, HttpUrl


class RecurringSeriesCreate(BaseModel):
    rrule: str = Field(min_length=8, examples=["FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=12"])
    dtstart: str
    duration_minutes: int = Field(gt=0, le=24 * 60)
    timezone: str = "UTC"
    tenant_id: str | None = None
    location_id: str | None = None
    resource_id: str | None = None
    materialize_count: int = Field(default=12, ge=1, le=100)


class WebhookEndpointCreate(BaseModel):
    url: HttpUrl
    secret: str = Field(min_length=16)
    tenant_id: str | None = None
