from app.security.webhooks import canonical_json, sign_payload, verify_signature


def test_hmac_round_trip():
    body = canonical_json({"event": "appointment.booked", "id": 1})
    signature = sign_payload("super-secret", body)
    assert verify_signature("super-secret", body, signature) is True


def test_hmac_rejects_wrong_secret():
    body = canonical_json({"event": "appointment.booked"})
    signature = sign_payload("super-secret", body)
    assert verify_signature("other-secret", body, signature) is False


def test_hmac_rejects_missing_header():
    assert verify_signature("secret", b"{}", None) is False
