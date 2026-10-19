# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging
from datetime import date
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query

from app.modules.freelancer.schemas import ProviderInfo
from app.modules.freelancer.settings import ProviderSettings, get_provider_settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _web_url(value: str) -> str:
    """`value` if it is an absolute http(s) URL, else "" (it ends up in an
    href); a non-empty value that is dropped is logged so a typo in .env does
    not just make the link vanish."""
    value = value.strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme in ("http", "https") and parts.netloc:
        return value
    logger.warning("PROVIDER_WEB is not an http(s) URL and is left out of the legal pages")
    return ""


def _effective_from(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        logger.warning("PROVIDER_EFFECTIVE_FROM is not an ISO date (YYYY-MM-DD) and is left out of the legal pages")
        return None


def _registration(settings: ProviderSettings, language: str | None) -> str:
    """The registration text for `language` ("en-GB" -> en); the other
    language's when that one is empty."""
    primary = (language or "cs").strip().lower().replace("_", "-").split("-")[0]
    ordered = [settings.registration_en, settings.registration_cs] if primary == "en" else [settings.registration_cs, settings.registration_en]
    return next((text.strip() for text in ordered if text.strip()), "")


@router.get("/provider", response_model=ProviderInfo)
async def provider_info(
    language: str | None = Query(default=None, max_length=35),
    settings: ProviderSettings = Depends(get_provider_settings),
) -> ProviderInfo:
    """Public by design: a site has to publish who runs it. Only the
    provider's own details are returned - never any other setting."""
    info = ProviderInfo(
        name=settings.name.strip(),
        ico=settings.ico.strip(),
        dic=settings.dic.strip(),
        vat_payer=settings.vat_payer,
        address=settings.address.strip(),
        registration=_registration(settings, language),
        email=settings.email.strip(),
        phone=settings.phone.strip(),
        web=_web_url(settings.web),
        dpo_email=settings.dpo_email.strip(),
        effective_from=_effective_from(settings.effective_from),
    )
    info.configured = bool(info.name and info.ico and info.address and info.email)
    return info
