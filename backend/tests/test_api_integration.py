import asyncio
import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport
from supabase import create_client

pytestmark = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"),
    reason="Supabase credentials are not configured",
)


@pytest.fixture(scope="module")
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def admin():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _user_token(client, admin, prefix: str) -> tuple[str, str]:
    import time
    import uuid

    email = f"{prefix}.{int(time.time())}.{uuid.uuid4().hex[:6]}@gmail.com"
    password = "TestPass123!"
    admin.auth.admin.create_user(
        {"email": email, "password": password, "email_confirm": True}
    )
    response = client.post("/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["access_token"], body["user_id"]


def test_me_requires_auth(client):
    response = client.get("/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_login_and_me(client, admin):
    token, user_id = _user_token(client, admin, "pytestme")
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["user_id"] == user_id
    assert response.json()["role"] == "customer"


def _future_slot_id(client, admin) -> int:
    slots = client.get("/slots").json()
    if slots:
        return slots[0]["id"]
    start = datetime.now(timezone.utc) + timedelta(days=14)
    created = admin.table("slots").insert(
        {
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=30)).isoformat(),
            "status": "available",
        }
    ).execute()
    if not created.data:
        pytest.skip("could not create a slot for the race test")
    from app.services.availability import invalidate_availability_cache

    invalidate_availability_cache()
    return created.data[0]["id"]


def test_idor_cancel_is_forbidden_or_hidden(client, admin):
    token_a, _ = _user_token(client, admin, "pytesta")
    token_b, _ = _user_token(client, admin, "pytestb")
    slot_id = _future_slot_id(client, admin)
    booked = client.post(
        "/appointments",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"slot_id": slot_id},
    )
    if booked.status_code != 200:
        pytest.skip(f"could not book slot {slot_id}: {booked.text}")
    appt_id = booked.json()["id"]
    forbidden = client.delete(
        f"/appointments/{appt_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden.status_code in {403, 404}
    cancel = client.delete(
        f"/appointments/{appt_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert cancel.status_code == 200


def test_concurrent_booking_only_one_wins(client, admin):
    token_a, _ = _user_token(client, admin, "racea")
    token_b, _ = _user_token(client, admin, "raceb")
    slot_id = _future_slot_id(client, admin)

    async def book_both():
        from app.main import app

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await asyncio.gather(
                ac.post(
                    "/appointments",
                    headers={"Authorization": f"Bearer {token_a}"},
                    json={"slot_id": slot_id},
                ),
                ac.post(
                    "/appointments",
                    headers={"Authorization": f"Bearer {token_b}"},
                    json={"slot_id": slot_id},
                ),
            )

    results = asyncio.run(book_both())

    codes = sorted(r.status_code for r in results)
    assert 200 in codes
    assert 409 in codes
    winner_token, winner_resp = next(
        pair for pair in ((token_a, results[0]), (token_b, results[1])) if pair[1].status_code == 200
    )
    client.delete(
        f"/appointments/{winner_resp.json()['id']}",
        headers={"Authorization": f"Bearer {winner_token}"},
    )


def test_end_to_end_booking_lifecycle(client, admin):
    health = client.get("/health")
    assert health.status_code == 200, health.text
    assert health.json()["status"] == "ok"

    unauth = client.get("/me")
    assert unauth.status_code == 401

    token_a, user_a = _user_token(client, admin, "e2ea")
    token_b, _user_b = _user_token(client, admin, "e2eb")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    me = client.get("/me", headers=headers_a)
    assert me.status_code == 200, me.text
    assert me.json()["user_id"] == user_a
    assert me.json()["role"] == "customer"

    start = datetime.now(timezone.utc) + timedelta(days=21)
    created = admin.table("slots").insert(
        {
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=30)).isoformat(),
            "status": "available",
        }
    ).execute()
    assert created.data, "failed to create an isolated slot"
    slot_id = created.data[0]["id"]
    from app.services.availability import invalidate_availability_cache

    invalidate_availability_cache()

    slots = client.get("/slots")
    assert slots.status_code == 200, slots.text
    assert any(s["id"] == slot_id for s in slots.json())

    held = client.post(
        f"/slots/{slot_id}/hold",
        headers=headers_a,
        json={"hold_seconds": 120},
    )
    assert held.status_code == 200, held.text

    booked = client.post(
        "/appointments",
        headers=headers_a,
        json={"slot_id": slot_id},
    )
    assert booked.status_code == 200, booked.text
    appointment = booked.json()
    appt_id = appointment["id"]
    assert appointment["status"] == "booked"
    assert appointment["slot_id"] == slot_id

    mine = client.get("/appointments", headers=headers_a)
    assert mine.status_code == 200, mine.text
    assert any(row["id"] == appt_id for row in mine.json())

    export = client.get("/me/export", headers=headers_a)
    assert export.status_code == 200, export.text
    assert any(row["id"] == appt_id for row in export.json()["appointments"])

    conflict = client.post(
        "/appointments",
        headers=headers_b,
        json={"slot_id": slot_id},
    )
    assert conflict.status_code == 409, conflict.text

    stolen = client.delete(f"/appointments/{appt_id}", headers=headers_b)
    assert stolen.status_code in {403, 404}, stolen.text

    cancelled = client.delete(f"/appointments/{appt_id}", headers=headers_a)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    rebook = client.post(
        "/appointments",
        headers=headers_b,
        json={"slot_id": slot_id},
    )
    assert rebook.status_code == 200, rebook.text
    cleanup = client.delete(
        f"/appointments/{rebook.json()['id']}",
        headers=headers_b,
    )
    assert cleanup.status_code == 200, cleanup.text
