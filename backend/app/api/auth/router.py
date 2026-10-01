# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from typing import NoReturn

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UserDataUpdate,
    UserUpdate,
)
from app.api.deps import get_current_user
from app.models.user import User
from app.security.jwt import bearer_scheme
from app.services.auth_client import auth_client

router = APIRouter()


def _raise_for_response(response: httpx.Response) -> NoReturn:
    """Re-raises an upstream non-2xx httpx.Response as the equivalent
    HTTPException, forwarding its status code and JSON `detail` (or raw text
    if the body isn't valid JSON) so callers see the same error shape the
    auth service returned."""
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    raise HTTPException(status_code=response.status_code, detail=detail)


@router.post("/register", status_code=201)
async def register(body: RegisterRequest) -> dict:
    """Proxies straight to the auth service's own /register - this app never
    stores credentials itself, only the resulting identity's sub claim once
    it first authenticates (see get_current_user)."""
    try:
        return await auth_client.register(**body.model_dump(exclude_none=True))
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)


@router.post("/login")
async def login(body: LoginRequest) -> dict:
    """Proxies the upstream response as-is - including a 403 consent_required,
    so the frontend can redirect to our own /consent page."""
    response = await auth_client.login(identifier=body.identifier, password=body.password)
    if response.status_code == 200:
        return response.json()
    _raise_for_response(response)


@router.post("/refresh")
async def refresh(body: RefreshRequest) -> dict:
    """Exchanges a refresh token for a new access/refresh pair - this is what
    the frontend's apiFetch() calls transparently on a 401 before retrying
    the original request once."""
    try:
        return await auth_client.refresh(refresh_token=body.refresh_token)
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)


@router.post("/logout", status_code=204)
async def logout(
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> None:
    """Revokes the refresh token upstream; the access token in the bearer
    header identifies which session to invalidate. No local state to clear -
    this app doesn't persist sessions of its own."""
    try:
        await auth_client.logout(access_token=credentials.credentials, refresh_token=body.refresh_token)
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)


@router.get("/me")
async def me(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Ensures a local user row exists (via get_current_user) and returns the
    live profile from the auth service - not cached locally, so it's always
    current and never duplicates identity data this app doesn't own.

    Per the published MeResponse schema, consent_required and
    application_group_id are always present; user is populated only once
    consent is granted. We convert consent_required into the same 403 shape
    /login already uses, so the frontend has one code path for both (this
    also covers entry points that skip /login's own check, e.g. Google
    OAuth). `.get("user") or result` is kept as a defensive fallback for an
    earlier observed state where a granted response had no wrapper at all -
    cheap insurance, shouldn't trigger against the current schema.

    application_group_id is merged into the flat response so callers (e.g.
    the Account page) can use it for the group-attributes endpoints below
    without a second round trip."""
    try:
        result = await auth_client.get_me(access_token=credentials.credentials)
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)

    if result.get("consent_required"):
        raise HTTPException(
            status_code=403,
            detail={
                "consent_required": True,
                "application_group_id": result.get("application_group_id"),
            },
        )
    user = result.get("user") or result
    return {
        **user,
        "application_group_id": result.get("application_group_id"),
        # Locally-sourced, not part of the auth service's own identity data.
        "is_admin": current_user.is_admin,
    }


@router.patch("/me")
async def update_me(
    body: UserUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Proxies core profile fields to the auth service. No application_group_id
    in the response - that value doesn't change on a profile edit, and the
    frontend already has it from the initial GET /me."""
    try:
        return await auth_client.update_me(
            access_token=credentials.credentials,
            payload=body.model_dump(exclude_none=True),
        )
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)


@router.get("/me/group-attributes/{group_id}")
async def get_group_attributes(
    group_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """{application_group_id, user_data, updated_at} - user_data only,
    system_data is never included (hidden by the auth service itself)."""
    try:
        return await auth_client.get_group_attributes(
            access_token=credentials.credentials, group_id=group_id
        )
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)


@router.patch("/me/group-attributes/{group_id}")
async def update_group_attributes(
    group_id: str,
    body: UserDataUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Replaces the ENTIRE user_data object upstream - callers must send the
    full desired object (merged with whatever they already fetched), not
    just the changed keys."""
    try:
        return await auth_client.update_group_attributes(
            access_token=credentials.credentials,
            group_id=group_id,
            user_data=body.user_data or {},
        )
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)


@router.get("/group-info")
async def group_info() -> dict:
    """{id, name, description, scopes} for the group identified by our own
    X-Api-Key - needs no user token, used to render the consent page."""
    try:
        return await auth_client.get_group_info()
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)


@router.post("/consent/{group_id}/grant", status_code=204)
async def grant_consent(
    group_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> None:
    """Called from our own /consent page (not the auth service's hosted one)
    once the user agrees to the scopes shown via GET /group-info."""
    try:
        await auth_client.grant_consent(group_id=group_id, access_token=credentials.credentials)
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)


@router.post("/consent/{group_id}/reject", status_code=204)
async def reject_consent(
    group_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> None:
    """Called from our own /consent page when the user declines; the
    frontend follows this with a navigate to /consent-rejected."""
    try:
        await auth_client.reject_consent(group_id=group_id, access_token=credentials.credentials)
    except httpx.HTTPStatusError as exc:
        _raise_for_response(exc.response)
