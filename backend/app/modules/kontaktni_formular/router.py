# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.modules.kontaktni_formular.schemas import ContactFormRequest
from app.security.jwt import get_current_user_claims
from app.services.auth_client import auth_client
from app.services.email import send_email

logger = logging.getLogger(__name__)

router = APIRouter()

# auto_error=False so an anonymous request reaches the route with
# credentials=None instead of FastAPI rejecting it with a 401 before the
# handler ever runs - this endpoint is meant to work for signed-in and
# anonymous visitors alike.
_optional_bearer = HTTPBearer(auto_error=False)


async def _resolve_sender_name(claims: dict, access_token: str) -> str:
    """The verified JWT only carries email/login (see conftest.py's
    make_access_token), not first/last name - that lives on the auth
    service's own live profile. Falls back to the JWT's email/login claim
    if that call fails or consent isn't granted yet - a contact-form
    submission shouldn't be blocked on either."""
    fallback = claims.get("email") or claims.get("login") or ""
    try:
        result = await auth_client.get_me(access_token=access_token)
    except httpx.HTTPStatusError:
        return fallback
    if result.get("consent_required"):
        return fallback
    user = result.get("user") or result
    full_name = f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip()
    return full_name or fallback


@router.post("/submit", status_code=204)
async def submit_contact_form(
    body: ContactFormRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    """Sends the message to Settings.contact_mail, plus a copy to the
    sender's own address as their confirmation of submission - signed with
    the sender's real name when they're signed in, or their supplied
    reply_to address (required in that case) when they're not."""
    if not settings.contact_mail:
        raise RuntimeError(
            "CONTACT_MAIL is not configured - set it in backend/.env before enabling this module."
        )

    claims: dict | None = None
    if credentials is not None:
        try:
            claims = await get_current_user_claims(credentials)
        except HTTPException:
            claims = None

    if claims is not None:
        reply_to = claims.get("email") or ""
        sender_name = await _resolve_sender_name(claims, credentials.credentials)
    else:
        if not body.reply_to:
            raise HTTPException(status_code=422, detail="reply_to is required when not signed in")
        reply_to = body.reply_to
        sender_name = body.reply_to

    email_body = f"Od: {sender_name} <{reply_to}>\n\n{body.message}"

    try:
        await send_email(body.subject, [settings.contact_mail], email_body, settings=settings)
        await send_email(body.subject, [reply_to], email_body, settings=settings)
    except Exception as exc:
        logger.exception("Failed to send contact form email")
        raise HTTPException(status_code=502, detail="Failed to send message") from exc
