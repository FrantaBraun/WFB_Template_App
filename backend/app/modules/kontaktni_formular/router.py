# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.modules.kontaktni_formular.config import ContactFormConfig, get_contact_form_config
from app.modules.kontaktni_formular.hooks import (
    ContactFormHook,
    ContactHookResult,
    ContactSubmission,
    get_contact_form_hooks,
)
from app.modules.kontaktni_formular.schemas import ContactDetails, ContactFormRequest, ContactInfoResponse
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


def _public_url(name: str, value: str) -> str | None:
    """`value` if it is an absolute http(s) URL, else None - the page puts
    these in an href, so e.g. a javascript: URL must never get that far. A
    non-empty value that is dropped is logged, otherwise a typo in .env
    would just make the link vanish without a word."""
    value = value.strip()
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme in ("http", "https") and parts.netloc:
        return value
    logger.warning("%s is not an http(s) URL and is left out of the contact page", name)
    return None


@router.get("/info", response_model=ContactInfoResponse)
async def contact_info(
    language: str | None = Query(default=None, max_length=35),
    settings: Settings = Depends(get_settings),
    config: ContactFormConfig = Depends(get_contact_form_config),
) -> ContactInfoResponse:
    """What the contact page shows around the form: the per-language texts
    from the module config and the public details from Settings. Public by
    design (it is a public page), so it exposes only these fields - never
    any other setting - and the delivery address only when the config's
    show_email is on."""
    texts = config.page_texts_for(language)
    return ContactInfoResponse(
        title=texts.title,
        intro=texts.intro,
        aside=texts.aside,
        details=ContactDetails(
            email=(settings.contact_mail.strip() or None) if config.show_email else None,
            address=settings.contact_address.strip() or None,
            github_url=_public_url("CONTACT_GITHUB_URL", settings.contact_github_url),
            linkedin_url=_public_url("CONTACT_LINKEDIN_URL", settings.contact_linkedin_url),
        ),
    )


async def _run_hooks(
    hooks: list[ContactFormHook], db: AsyncSession, submission: ContactSubmission
) -> ContactHookResult:
    """Calls every hook (see hooks.py) and merges what they return - the
    first tag / Reply-To wins. A hook that raises is logged and skipped after
    a rollback, so the session is usable again and the message still goes out."""
    tag: str | None = None
    reply_to: str | None = None
    for hook in hooks:
        try:
            result = await hook(db, submission)
        except Exception:
            logger.exception("A contact form hook failed - continuing without it")
            await db.rollback()
            continue
        if result is not None:
            tag = tag or result.subject_tag
            reply_to = reply_to or result.reply_to
    return ContactHookResult(subject_tag=tag, reply_to=reply_to)


def _tagged(tag: str | None, subject: str) -> str:
    return f"{tag} - {subject}" if tag else subject


@router.post("/submit", status_code=204)
async def submit_contact_form(
    body: ContactFormRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    settings: Settings = Depends(get_settings),
    config: ContactFormConfig = Depends(get_contact_form_config),
    db: AsyncSession = Depends(get_db),
    hooks: list[ContactFormHook] = Depends(get_contact_form_hooks),
) -> None:
    """Sends the message to Settings.contact_mail and, when the module
    config's send_reply is on, a confirmation email to the sender in the
    language the form was submitted in (body.language, else the config's
    default_language). The sender is identified by their real name when
    signed in, or by their supplied reply_to address (required in that
    case) when they're not.

    Modules that take part through the CONTACT_FORM_RECEIVED hook (e.g.
    tickets) run first; what they return can prefix the subjects of both mails
    and redirect the sender's answers (see hooks.ContactHookResult)."""
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

    outcome = await _run_hooks(
        hooks,
        db,
        ContactSubmission(
            subject=body.subject,
            message=body.message,
            sender_name=sender_name,
            reply_to=reply_to,
            language=body.language,
            signed_in=claims is not None,
        ),
    )

    try:
        email_body = (
            f"Contact form message:\nFrom: {sender_name} <{reply_to}>\n"
            f"Language: {body.language or '-'}\n\n{body.message}"
        )
        await send_email(
            _tagged(outcome.subject_tag, body.subject), [settings.contact_mail], email_body, settings=settings
        )
        if config.send_reply:
            reply_subject, reply_body = config.reply_template_for(body.language).render(
                sender_name=sender_name, reply_to=reply_to, subject=body.subject, message=body.message
            )
            await send_email(
                _tagged(outcome.subject_tag, reply_subject),
                [reply_to],
                reply_body,
                settings=settings,
                reply_to=[outcome.reply_to] if outcome.reply_to else None,
            )
    except Exception as exc:
        logger.exception("Failed to send contact form email")
        raise HTTPException(status_code=502, detail="Failed to send message") from exc
