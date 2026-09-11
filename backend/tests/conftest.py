# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Shared pytest fixtures: a TestClient, RSA keypairs and signed JWTs for
exercising app.security.jwt without a real auth service, and a rolled-back
db_session for isolated database tests."""

import os
import time
import uuid

# MAIL_SUPPRESS_SEND must be forced on before any app.* import below - the
# first one to resolve Settings (app.database's module-level get_settings()
# call, triggered by `from app.database import engine` further down)
# permanently caches its result via @lru_cache for the rest of the session,
# and this repo's real backend/.env has MAIL_SUPPRESS_SEND=false pointed at
# a placeholder SMTP host. Without this, any test path that reaches
# app.services.email.send_email() without itself injecting
# mail_test_settings - e.g. a service function called directly rather than
# through a request whose get_settings dependency is overridden, such as
# app.services.notifications.notify_new_version being invoked indirectly via
# app.services.api_document_versions.process_new_spec - would attempt a real
# outbound SMTP connection. setdefault, not a hard assignment, so a developer
# who sets this in their own shell for some other reason isn't silently
# overridden.
os.environ.setdefault("MAIL_SUPPRESS_SEND", "true")

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.security.jwt as jwt_module
from app.config import Settings
from app.database import engine
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """A synchronous FastAPI TestClient for routes that don't need to share
    an event loop with an async db_session (see db_session below)."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_public_key_cache():
    """app.security.jwt caches the auth service's public key in a module-level
    variable - reset it around every test so none of them leak state to another."""
    jwt_module._public_key = None
    yield
    jwt_module._public_key = None


def generate_rsa_keypair() -> tuple[str, str]:
    """Return (private_pem, public_pem) for a throwaway RSA keypair."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[str, str]:
    """Session-scoped: one throwaway RSA keypair reused across the whole test
    run, since generating a 2048-bit key per test would be wasteful and
    nothing here depends on a fresh key per test."""
    return generate_rsa_keypair()


@pytest.fixture()
def make_access_token(rsa_keypair):
    """Factory fixture: make_access_token(sub=..., **claim_overrides) -> signed JWT string.

    Signs with rsa_keypair's private key so tests can hand get_current_user_claims
    a real, verifiable RS256 token without ever calling the auth service."""
    private_pem, _ = rsa_keypair

    def _make(sub: str | None = None, **overrides) -> str:
        now = int(time.time())
        claims = {
            "sub": sub or str(uuid.uuid4()),
            "email": "user@example.com",
            "login": "testuser",
            "role_name": "user",
            "email_verified": True,
            "subscription": None,
            "iat": now,
            "exp": now + 900,
        }
        claims.update(overrides)
        return pyjwt.encode(claims, private_pem, algorithm="RS256")

    return _make


@pytest.fixture()
async def db_session() -> AsyncSession:
    """A session bound to a rolled-back transaction, so tests never leave rows behind."""
    async with engine.connect() as connection:
        await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        async with session_factory() as session:
            yield session
        await connection.rollback()


@pytest.fixture()
def auth_test_settings() -> Settings:
    """Settings pointed at a fake auth service host so respx can intercept
    every call - tests must never reach the real auth.withfbraun.com."""
    return Settings(auth_url="https://auth.test", auth_api_key="test-api-key")


@pytest.fixture()
def mail_test_settings() -> Settings:
    """Settings with mail_suppress_send=True: send_email still builds and
    "dispatches" a message internally, so FastMail's record_messages() can
    assert on it, but no real SMTP connection is opened."""
    return Settings(
        mail_username="test-user",
        mail_password="test-pass",
        mail_from="noreply@example.com",
        mail_server="smtp.example.com",
        mail_port=587,
        mail_starttls=True,
        mail_ssl_tls=False,
        mail_suppress_send=True,
    )
