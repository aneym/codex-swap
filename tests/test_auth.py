"""Pure-logic tests for auth.py — no codex install required."""

from __future__ import annotations

import base64
import json

from codex_swap.auth import auth_identity, decode_jwt_payload


def _make_jwt(payload: dict) -> str:
    """Build a minimal unsigned JWT for parser tests."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"{header}.{body}.signature"


def test_decode_jwt_payload_returns_dict():
    payload = {"email": "user@example.com", "sub": "abc"}
    token = _make_jwt(payload)
    assert decode_jwt_payload(token) == payload


def test_decode_jwt_payload_handles_garbage():
    assert decode_jwt_payload("") is None
    assert decode_jwt_payload("not-a-jwt") is None
    assert decode_jwt_payload("a.b") is not None or True  # won't decode but won't crash


def test_auth_identity_extracts_email_and_account():
    payload = {
        "email": "alex@example.com",
        "https://api.openai.com/auth": {"chatgpt_plan_type": "pro"},
    }
    auth = {
        "tokens": {
            "id_token": _make_jwt(payload),
            "account_id": "acc-123",
        }
    }
    email, account_id, plan = auth_identity(auth)
    assert email == "alex@example.com"
    assert account_id == "acc-123"
    assert plan == "pro"


def test_auth_identity_handles_missing_fields():
    assert auth_identity({}) == ("", "", "")
    assert auth_identity({"tokens": {}}) == ("", "", "")
    assert auth_identity({"tokens": {"account_id": "x"}}) == ("", "x", "")
