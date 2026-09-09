"""Unit tests for the signup endpoint.

These tests mock Supabase Auth to verify the backend correctly handles:
- new signups (success)
- existing-email signups (409 conflict)
- invalid request data (validation errors)
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _fake_user(*, identities=None):
    """Return a lightweight object that looks like a Supabase User."""
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        email="test@example.com",
        identities=identities,
    )


# ── New email → signup succeeds ──────────────────────────────────────────────

@patch("app.routers.auth.write_audit")
@patch("app.routers.auth.supabase")
@patch("app.routers.auth.create_supabase_client")
def test_signup_new_email_succeeds(mock_create_client, mock_supabase, mock_audit, client):
    fake_auth_client = MagicMock()
    fake_auth_client.auth.sign_up.return_value = SimpleNamespace(
        user=_fake_user(identities=[{"provider": "email"}]),
        session=None,
    )
    mock_create_client.return_value = fake_auth_client
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

    response = client.post("/signup", json={
        "email": "newuser@example.com",
        "password": "StrongPass123!",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "User created successfully"
    assert body["user_id"] is not None


# ── Existing email → 409 conflict ────────────────────────────────────────────

@patch("app.routers.auth.write_audit")
@patch("app.routers.auth.supabase")
@patch("app.routers.auth.create_supabase_client")
def test_signup_existing_email_returns_409(mock_create_client, mock_supabase, mock_audit, client):
    fake_auth_client = MagicMock()
    # Supabase returns a fake user with empty identities for existing emails
    fake_auth_client.auth.sign_up.return_value = SimpleNamespace(
        user=_fake_user(identities=[]),
        session=None,
    )
    mock_create_client.return_value = fake_auth_client

    response = client.post("/signup", json={
        "email": "existing@example.com",
        "password": "StrongPass123!",
    })

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


# ── Existing email with None identities → 409 conflict ──────────────────────

@patch("app.routers.auth.write_audit")
@patch("app.routers.auth.supabase")
@patch("app.routers.auth.create_supabase_client")
def test_signup_existing_email_none_identities_returns_409(mock_create_client, mock_supabase, mock_audit, client):
    fake_auth_client = MagicMock()
    fake_auth_client.auth.sign_up.return_value = SimpleNamespace(
        user=_fake_user(identities=None),
        session=None,
    )
    mock_create_client.return_value = fake_auth_client

    response = client.post("/signup", json={
        "email": "existing2@example.com",
        "password": "StrongPass123!",
    })

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


# ── Invalid signup data → validation error ───────────────────────────────────

def test_signup_missing_email_returns_422(client):
    response = client.post("/signup", json={
        "password": "StrongPass123!",
    })
    assert response.status_code == 422


def test_signup_short_password_returns_422(client):
    response = client.post("/signup", json={
        "email": "valid@example.com",
        "password": "short",
    })
    assert response.status_code == 422


def test_signup_invalid_email_format_returns_422(client):
    response = client.post("/signup", json={
        "email": "not-an-email",
        "password": "StrongPass123!",
    })
    assert response.status_code == 422
