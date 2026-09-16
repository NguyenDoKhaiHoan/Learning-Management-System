"""Week 2 identity, account-state and live authorization behavior."""

from typing import Annotated
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from src.config.config import Settings
from src.core.database.database import get_connection
from src.core.security.dependencies import require_permissions
from src.core.security.jwt import create_access_token, decode_access_token
from src.main import create_app
from src.modules.identity_access.application.passwords import hash_password, verify_password
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.user_role.infrastructure.repository import RoleRepository


def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="mysql+aiomysql://u:p@localhost/lms",
        jwt_secret="week-two-test-secret-" * 3,
    )


@pytest.fixture
def client(monkeypatch):
    connection = AsyncMock()
    app = create_app(settings())

    async def connection_dependency():
        yield connection

    app.dependency_overrides[get_connection] = connection_dependency
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
    monkeypatch.setattr(RoleRepository, "get_role_codes", AsyncMock(return_value=["ADMIN"]))

    @app.get("/test/permission")
    async def permission_route(
        user: Annotated[object, Depends(require_permissions(["course.write"]))],
    ):
        return {"ok": bool(user)}

    with TestClient(app) as test_client:
        yield test_client, connection


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")
    assert first != second
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong password", first)
    assert not verify_password("anything", "malformed")


def test_login_issues_access_token_for_active_account(client, monkeypatch):
    test_client, _ = client
    password_hash = hash_password("valid-password")
    lookup = AsyncMock(
        return_value={
            "id": 7,
            "email": "user@example.com",
            "username": "user",
            "hashed_password": password_hash,
            "status": "ACTIVE",
        }
    )
    monkeypatch.setattr(IdentityRepository, "get_credentials_by_login", lookup)
    response = test_client.post(
        "/api/v1/auth/login",
        json={"login": " User@Example.com ", "password": "valid-password"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["token_type"] == "bearer"
    assert decode_access_token(response.json()["data"]["access_token"], settings()) == 7
    assert lookup.await_args.args[0] == "user@example.com"


@pytest.mark.parametrize("account", [None, "INACTIVE", "LOCKED"])
def test_login_rejects_unknown_or_ineligible_account(client, monkeypatch, account):
    test_client, _ = client
    row = None
    if account:
        row = {
            "id": 7,
            "hashed_password": hash_password("valid-password"),
            "status": account,
        }
    monkeypatch.setattr(
        IdentityRepository, "get_credentials_by_login", AsyncMock(return_value=row)
    )
    response = test_client.post(
        "/api/v1/auth/login", json={"login": "user", "password": "valid-password"}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_rejects_wrong_password(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr(
        IdentityRepository,
        "get_credentials_by_login",
        AsyncMock(
            return_value={
                "id": 7,
                "hashed_password": hash_password("valid-password"),
                "status": "ACTIVE",
            }
        ),
    )
    response = test_client.post(
        "/api/v1/auth/login", json={"login": "user", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_admin_can_change_account_status(client, monkeypatch):
    test_client, connection = client
    update = AsyncMock(return_value=True)
    monkeypatch.setattr(IdentityRepository, "set_status", update)
    token = create_access_token(7, settings())
    response = test_client.patch(
        "/api/v1/auth/users/9/status",
        json={"status": "LOCKED"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {"user_id": "9", "status": "LOCKED"}
    connection.commit.assert_awaited_once()


def test_admin_can_assign_and_revoke_role(client, monkeypatch):
    test_client, connection = client
    monkeypatch.setattr(
        RoleRepository,
        "get_role",
        AsyncMock(return_value={"id": 3, "code": "INSTRUCTOR", "name": "Instructor"}),
    )
    assign = AsyncMock(return_value=21)
    revoke = AsyncMock(return_value=True)
    monkeypatch.setattr(RoleRepository, "assign_role", assign)
    monkeypatch.setattr(RoleRepository, "revoke_role", revoke)
    token = create_access_token(7, settings())
    headers = {"Authorization": f"Bearer {token}"}

    response = test_client.put("/api/v1/users/9/roles/INSTRUCTOR", headers=headers)
    assert response.status_code == 201
    assert response.json()["data"] == {"user_id": "9", "role": "INSTRUCTOR"}
    response = test_client.delete("/api/v1/users/9/roles/INSTRUCTOR", headers=headers)
    assert response.status_code == 200
    assign.assert_awaited_once_with(9, 3)
    revoke.assert_awaited_once_with(9, 3)
    assert connection.commit.await_count == 2


def test_permission_guard_uses_current_database_grants(client, monkeypatch):
    test_client, _ = client
    token = create_access_token(7, settings())
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(
        RoleRepository, "get_permission_codes", AsyncMock(return_value=["course.read"])
    )
    assert test_client.get("/test/permission", headers=headers).status_code == 403
    monkeypatch.setattr(
        RoleRepository,
        "get_permission_codes",
        AsyncMock(return_value=["course.read", "course.write"]),
    )
    assert test_client.get("/test/permission", headers=headers).status_code == 200
