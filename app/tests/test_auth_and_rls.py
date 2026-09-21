"""Integration tests for Phase 0: Real Authentication (Argon2id) & RLS Isolation."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.api.main import app
from app.core.auth import verify_password
from app.domain.models import Tenant, User


@pytest.fixture
async def auth_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_auth_signup_hashes_with_argon2id_and_creates_tenant(auth_client, db_session):
    """Verifies that signup creates a tenant, hashes password via Argon2id, and sets session cookie."""
    payload = {
        "email": "candidate@example.com",
        "password": "SecurePassword123!",
        "name": "Alex Candidate",
        "plan": "pro",
    }

    res = await auth_client.post("/api/auth/signup", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["user"]["email"] == "candidate@example.com"
    assert data["tenant"]["name"] == "Alex Candidate"
    assert data["tenant"]["plan"] == "pro"
    assert "access_token" in data
    assert "session_token" in res.cookies

    # Verify directly in DB that password was hashed with Argon2id
    stmt = select(User).where(User.email == "candidate@example.com")
    user = (await db_session.execute(stmt)).scalar_one()
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password("SecurePassword123!", user.password_hash) is True


@pytest.mark.asyncio
async def test_auth_signup_duplicate_email_rejected(auth_client, db_session):
    """Verifies that duplicate registration is rejected with HTTP 400."""
    payload = {
        "email": "unique@example.com",
        "password": "Password123!",
        "name": "User One",
        "plan": "free",
    }
    res1 = await auth_client.post("/api/auth/signup", json=payload)
    assert res1.status_code == 201

    res2 = await auth_client.post("/api/auth/signup", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_auth_login_lifecycle_and_me_endpoint(auth_client):
    """Verifies login with valid and invalid passwords, and /api/auth/me resolution."""
    # 1. Signup
    signup_payload = {
        "email": "login_test@example.com",
        "password": "MySecretPassword99#",
        "name": "Login Tester",
        "plan": "pro",
    }
    await auth_client.post("/api/auth/signup", json=signup_payload)

    # 2. Invalid password login
    bad_login = await auth_client.post(
        "/api/auth/login",
        json={"email": "login_test@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401

    # 3. Valid password login
    good_login = await auth_client.post(
        "/api/auth/login",
        json={"email": "login_test@example.com", "password": "MySecretPassword99#"},
    )
    assert good_login.status_code == 200
    token = good_login.json()["access_token"]

    # 4. Access /api/auth/me via Bearer token
    me_res = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == "login_test@example.com"
    assert me_res.json()["tenant"]["name"] == "Login Tester"


@pytest.mark.asyncio
async def test_auth_magic_link_recovery_flow(auth_client):
    """Verifies password recovery magic link generation and verification."""
    signup_payload = {
        "email": "magic_user@example.com",
        "password": "StrongPassword888!",
        "name": "Magic User",
        "plan": "pro",
    }
    await auth_client.post("/api/auth/signup", json=signup_payload)

    # Request magic link
    magic_req = await auth_client.post(
        "/api/auth/magic-link",
        json={"email": "magic_user@example.com"},
    )
    assert magic_req.status_code == 200
    magic_token = magic_req.json()["token"]

    # Verify magic link
    verify_res = await auth_client.post(
        "/api/auth/magic-link/verify",
        json={"token": magic_token},
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["user"]["email"] == "magic_user@example.com"
    assert "access_token" in verify_res.json()
