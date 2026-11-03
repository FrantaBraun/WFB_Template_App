# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""A team's webhooks (Slack, or its own endpoint) for new versions, mounted at
/api/teams/{team_id}/webhooks. Any member of the team may see them (masked);
only an owner may add, change, remove or test one - a webhook sends the
team's documents' news out of the application, and its URL is a secret.

The URL is checked when it is saved against calling the server's own network
(app/services/safe_http.py) and again on every delivery; a Slack webhook must
be on hooks.slack.com, which is the only place Slack's incoming webhooks are."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.models.team import TeamMembership
from app.models.user import User
from app.models.webhook import TeamWebhook
from app.services.safe_http import UnsafeUrlError, check_url, split_url
from app.services.webhooks import SLACK_HOST, build_ping_event, mask_url, new_secret, record, send

router = APIRouter()

MAX_WEBHOOKS_PER_TEAM = 10


class WebhookCreate(BaseModel):
    kind: Literal["slack", "generic"]
    url: str = Field(..., min_length=1, max_length=2048)
    name: str | None = Field(default=None, max_length=100)
    only_breaking: bool = False

    @field_validator("url")
    @classmethod
    def _strip_url(cls, value: str) -> str:
        return value.strip()


class WebhookUpdate(BaseModel):
    """PATCH body - only these three can change (the URL cannot: a different
    address is a different, new webhook, with a new secret). Applied with
    exclude_unset, so an omitted field is left alone; the flags are not
    nullable, an explicit null is a 422."""

    name: str | None = Field(default=None, max_length=100)
    only_breaking: bool = False
    enabled: bool = True


class WebhookOut(BaseModel):
    """url_masked, never the URL: for a Slack webhook the URL is itself the
    right to post to the channel."""

    id: uuid.UUID
    kind: str
    name: str | None
    url_masked: str
    only_breaking: bool
    enabled: bool
    last_attempt_at: datetime | None
    last_status: str | None
    last_error: str | None
    consecutive_failures: int
    created_at: datetime


class WebhookCreated(WebhookOut):
    """The answer to creating one. secret is the key a generic webhook's
    signature is made with - shown here, once, and never again (null for
    Slack, which has none)."""

    secret: str | None


class WebhookTestResult(BaseModel):
    ok: bool
    status_code: int | None
    error: str | None


def _out(webhook: TeamWebhook) -> WebhookOut:
    return WebhookOut(
        id=webhook.id,
        kind=webhook.kind,
        name=webhook.name,
        url_masked=mask_url(webhook.url),
        only_breaking=webhook.only_breaking,
        enabled=webhook.enabled,
        last_attempt_at=webhook.last_attempt_at,
        last_status=webhook.last_status,
        last_error=webhook.last_error,
        consecutive_failures=webhook.consecutive_failures,
        created_at=webhook.created_at,
    )


async def _membership(db: AsyncSession, team_id: uuid.UUID, user: User) -> TeamMembership:
    """404 for a team the caller is not in - indistinguishable from one that
    does not exist, as everywhere in this application."""
    membership = (
        await db.execute(
            select(TeamMembership).where(TeamMembership.team_id == team_id, TeamMembership.user_id == user.id)
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return membership


async def _require_owner(db: AsyncSession, team_id: uuid.UUID, user: User) -> None:
    if (await _membership(db, team_id, user)).role != "owner":
        raise HTTPException(status_code=403, detail="Only a team owner can manage its webhooks")


async def _get_webhook(db: AsyncSession, team_id: uuid.UUID, webhook_id: uuid.UUID) -> TeamWebhook:
    webhook = await db.get(TeamWebhook, webhook_id)
    if webhook is None or webhook.team_id != team_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@router.get("")
async def list_webhooks(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookOut]:
    await _membership(db, team_id, current_user)
    rows = (
        await db.execute(select(TeamWebhook).where(TeamWebhook.team_id == team_id).order_by(TeamWebhook.created_at))
    ).scalars()
    return [_out(webhook) for webhook in rows]


@router.post("", status_code=201)
async def create_webhook(
    team_id: uuid.UUID,
    body: WebhookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WebhookCreated:
    """422 for a URL that may not be called (not https, credentials in it, a
    host that does not resolve or resolves to a non-public address) or, for
    Slack, one not on hooks.slack.com; 409 past MAX_WEBHOOKS_PER_TEAM."""
    await _require_owner(db, team_id, current_user)
    allow_private = settings.outbound_allow_private_addresses
    try:
        _, host, _, _ = split_url(body.url, allow_private=allow_private)
        if body.kind == "slack" and host != SLACK_HOST and not allow_private:
            raise UnsafeUrlError(f"A Slack webhook URL must be on {SLACK_HOST}")
        await check_url(body.url, allow_private=allow_private)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    count = await db.scalar(select(func.count()).select_from(TeamWebhook).where(TeamWebhook.team_id == team_id))
    if (count or 0) >= MAX_WEBHOOKS_PER_TEAM:
        raise HTTPException(status_code=409, detail=f"A team can have at most {MAX_WEBHOOKS_PER_TEAM} webhooks")

    webhook = TeamWebhook(
        team_id=team_id,
        kind=body.kind,
        name=(body.name or "").strip() or None,
        url=body.url,
        secret=new_secret() if body.kind == "generic" else None,
        only_breaking=body.only_breaking,
        created_by_user_id=current_user.id,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return WebhookCreated(**_out(webhook).model_dump(), secret=webhook.secret)


@router.patch("/{webhook_id}")
async def update_webhook(
    team_id: uuid.UUID,
    webhook_id: uuid.UUID,
    body: WebhookUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookOut:
    await _require_owner(db, team_id, current_user)
    webhook = await _get_webhook(db, team_id, webhook_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "name":
            value = (value or "").strip() or None
        setattr(webhook, field, value)
    await db.commit()
    await db.refresh(webhook)
    return _out(webhook)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    team_id: uuid.UUID,
    webhook_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_owner(db, team_id, current_user)
    await db.delete(await _get_webhook(db, team_id, webhook_id))
    await db.commit()


@router.post("/{webhook_id}/test")
async def test_webhook(
    team_id: uuid.UUID,
    webhook_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WebhookTestResult:
    """Sends a test message right now and says how it went (also recorded on
    the webhook like any delivery). 200 with ok false when the receiver does not
    like it - that is the answer, not an error of this request."""
    await _require_owner(db, team_id, current_user)
    webhook = await _get_webhook(db, team_id, webhook_id)
    result = await send(webhook, build_ping_event(), settings)
    record(webhook, result)
    await db.commit()
    return WebhookTestResult(ok=result.ok, status_code=result.status_code, error=result.error)
