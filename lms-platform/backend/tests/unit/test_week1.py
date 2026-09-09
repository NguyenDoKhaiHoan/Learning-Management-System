"""HTTP contracts, token validation, role gating and sanitized structured logs."""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from src.config.config import Settings
from src.core.database.database import get_connection
from src.core.middleware.trace import JsonFormatter, trace_context
from src.core.security.dependencies import require_roles
from src.core.security.jwt import create_access_token
from src.main import create_app
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.user_role.infrastructure.repository import RoleRepository


def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="mysql+aiomysql://u:p@localhost/lms",
        jwt_secret="test-secret-" * 5,
    )


class Input(BaseModel):
    amount: int


@pytest.fixture
def client(monkeypatch):
    app = create_app(settings())

    async def connection():
        yield AsyncMock()

    app.dependency_overrides[get_connection] = connection
    monkeypatch.setattr(
        IdentityRepository,
        "get_user",
        AsyncMock(
            return_value={
                "id": 7,
                "email": "user@example.com",
                "username": "user",
                "status": "ACTIVE",
            }
        ),
    )
    monkeypatch.setattr(RoleRepository, "get_role_codes", AsyncMock(return_value=["STUDENT"]))

    @app.get("/test/error/{status}")
    def fail(status: int):
        if status == 500:
            raise RuntimeError("private-db-password")
        raise HTTPException(status, detail="private-db-password")

    @app.post("/test/validate")
    def validate(body: Input):
        return body

    @app.get("/test/conflict")
    def conflict():
        raise IntegrityError("private SQL", {}, Exception(1062, "private-db-value"))

    @app.get("/test/staff")
    def staff(user: Annotated[object, Depends(require_roles(["ADMIN", "INSTRUCTOR"]))]):
        return {"ok": True}

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.mark.parametrize("status", [401, 403, 404, 409, 422, 500])
def test_error_contract(client, status):
    response = client.get(f"/test/error/{status}", headers={"X-Trace-ID": "trace-test"})
    assert response.status_code == status
    assert set(response.json()) == {"code", "message", "details", "trace_id"}
    assert response.json()["trace_id"] == response.headers["x-trace-id"] == "trace-test"
    assert "private-db-password" not in response.text


def test_validation_and_unmatched_route(client):
    response = client.post("/test/validate", json={"amount": "secret-input"})
    assert response.status_code == 422
    assert response.json()["details"][0]["location"] == ["body", "amount"]
    assert "secret-input" not in response.text
    missing = client.get("/does-not-exist")
    assert missing.json()["code"] == "NOT_FOUND"


def test_missing_token_and_success(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    token = create_access_token(7, settings())
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["data"]["id"] == "7"
    assert response.json()["data"]["roles"] == ["STUDENT"]
    assert response.json()["trace_id"] == response.headers["x-trace-id"]


@pytest.mark.parametrize(
    "mutation",
    [
        "expired",
        "signature",
        "issuer",
        "audience",
        "refresh",
        "missing_exp",
        "future",
        "subject",
        "algorithm",
        "bad_exp",
        "empty_jti",
    ],
)
def test_invalid_tokens(client, mutation):
    config = settings()
    claims = jwt.decode(
        create_access_token(7, config),
        config.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        audience=config.jwt_audience,
    )
    key, algorithm = config.jwt_secret.get_secret_value(), "HS256"
    if mutation == "expired":
        claims["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    elif mutation == "signature":
        key = "different-secret-" * 5
    elif mutation == "issuer":
        claims["iss"] = "wrong"
    elif mutation == "audience":
        claims["aud"] = "wrong"
    elif mutation == "refresh":
        claims["token_type"] = "refresh"
    elif mutation == "missing_exp":
        del claims["exp"]
    elif mutation == "future":
        claims["nbf"] = datetime.now(UTC) + timedelta(hours=1)
    elif mutation == "subject":
        claims["sub"] = "1 OR 1=1"
    elif mutation == "bad_exp":
        claims["exp"] = []
    elif mutation == "empty_jti":
        claims["jti"] = ""
    else:
        algorithm = "HS384"
    token = jwt.encode(claims, key, algorithm=algorithm)
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


@pytest.mark.parametrize("state", [None, "INACTIVE", "LOCKED"])
def test_ineligible_user(client, monkeypatch, state):
    user = None if state is None else {"id": 7, "status": state}
    monkeypatch.setattr(IdentityRepository, "get_user", AsyncMock(return_value=user))
    token = create_access_token(7, settings())
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_roles_come_from_database(client, monkeypatch):
    config = settings()
    claims = jwt.decode(
        create_access_token(7, config),
        config.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        audience=config.jwt_audience,
    )
    claims["roles"] = ["ADMIN"]
    token = jwt.encode(claims, config.jwt_secret.get_secret_value(), algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/test/staff", headers=headers).status_code == 403
    monkeypatch.setattr(RoleRepository, "get_role_codes", AsyncMock(return_value=["INSTRUCTOR"]))
    assert client.get("/test/staff", headers=headers).status_code == 200


def test_trace_validation_and_log_sanitization(client):
    response = client.get("/does-not-exist?password=private", headers={"x-trace-id": "!" * 100})
    assert len(response.headers["x-trace-id"]) == 32
    record = logging.LogRecord("lms", logging.INFO, "", 0, "secret token", (), None)
    record.event = "http_request"
    record.route = "/api/v1/auth/me"
    output = JsonFormatter().format(record)
    assert "secret token" not in output
    assert json.loads(output)["event"] == "http_request"
    assert trace_context.get() == ""


def test_sql_conflict_is_sanitized(client):
    response = client.get("/test/conflict")
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"
    assert "private" not in response.text
