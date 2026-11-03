# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.webhook import TeamWebhook
from app.services.safe_http import UnsafeUrlError, safe_post

logger = logging.getLogger(__name__)

EVENT_VERSION_CREATED = "document.version_created"
EVENT_PING = "ping"
SLACK_HOST = "hooks.slack.com"


@dataclass(frozen=True)
class DeliveryResult:
    """ok is true for any 2xx answer. error is a short fixed phrase, never
    the receiver's own words (it is stored and shown to the team)."""

    ok: bool
    status_code: int | None = None
    error: str | None = None


def new_secret() -> str:
    """The signing secret of a generic webhook: 32 random bytes, hex."""
    return secrets.token_hex(32)


def mask_url(url: str) -> str:
    """The URL with everything that could let someone else use it hidden: the
    host and the first path segment stay, the rest - which is what a chat
    tool's webhook URL really is - becomes dots, with the last four characters
    so a team can tell its webhooks apart."""
    scheme, _, rest = url.partition("://")
    host, _, tail = rest.partition("/")
    tail = tail.split("?")[0]
    if not tail:
        return f"{scheme}://{host}/"
    first = tail.split("/")[0]
    return f"{scheme}://{host}/{first}/…{tail[-4:]}" if len(tail) > len(first) + 1 else f"{scheme}://{host}/…{tail[-4:]}"


def _escape_slack(text: str) -> str:
    """Slack reads &, < and > in a message as markup (links, mentions)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_version_event(
    doc: ApiDocument, version: ApiDocumentVersion, frontend_url: str, integration_names: list[str]
) -> dict:
    """What happened, as the JSON a generic webhook receives: the document, the
    version, how many changes of each severity it brought over the one it
    replaced (null when unknown) and - only the receiving team's own - the
    integrations that use the document. The links are to this application."""
    base = frontend_url.rstrip("/")
    summary = version.change_summary
    has_changes = bool(summary) and any(summary.values())
    return {
        "event": EVENT_VERSION_CREATED,
        "delivery_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "document": {"id": str(doc.id), "title": doc.title, "url": f"{base}/api-docs/{doc.id}"},
        "version": {
            "id": str(version.id),
            "version": version.version,
            "content_changed": version.content_changed,
            "source": version.source,
            "fetched_at": version.fetched_at.isoformat() if version.fetched_at else None,
        },
        "changes": (
            {"breaking": summary.get("breaking", 0), "warning": summary.get("warning", 0), "info": summary.get("info", 0)}
            if summary
            else None
        ),
        "changes_url": f"{base}/api-docs/{doc.id}/versions/{version.id}/changes" if has_changes else None,
        "integrations": integration_names,
    }


def build_ping_event() -> dict:
    return {
        "event": EVENT_PING,
        "delivery_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message": "A test message from API Hub - your webhook works.",
    }


def slack_message(event: dict) -> dict:
    """The event as a Slack message (mrkdwn): one headline, the integrations it
    affects, and links. Everything that came from a user is escaped."""
    if event["event"] == EVENT_PING:
        return {"text": f":white_check_mark: {_escape_slack(event['message'])}"}
    document, version = event["document"], event["version"]
    title, number = _escape_slack(document["title"]), _escape_slack(version["version"])
    if version["content_changed"]:
        headline = f"*{title}* changed without a new version number (*{number}*)"
    else:
        headline = f"*{title}* has a new version: *{number}*"
    changes = event["changes"]
    if changes and changes["breaking"]:
        count = changes["breaking"]
        headline += f" - :warning: {count} breaking change{'s' if count != 1 else ''}"
    lines = [headline]
    if event["integrations"]:
        lines.append("Affects: " + ", ".join(_escape_slack(name) for name in event["integrations"]))
    links = [f"<{document['url']}|View the documentation>"]
    if event["changes_url"]:
        links.append(f"<{event['changes_url']}|What changed>")
    lines.append(" · ".join(links))
    return {"text": "\n".join(lines)}


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """HMAC-SHA256 over "<timestamp>.<body>": the timestamp is signed with the
    body, so a captured request cannot be replayed later under a new one."""
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def _request_for(webhook: TeamWebhook, event: dict) -> tuple[bytes, dict[str, str]]:
    headers = {"Content-Type": "application/json", "User-Agent": "API-Hub-Webhook/1.0"}
    if webhook.kind == "slack":
        return json.dumps(slack_message(event), ensure_ascii=False).encode(), headers
    body = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode()
    timestamp = str(int(time.time()))
    headers.update(
        {
            "X-ApiHub-Event": event["event"],
            "X-ApiHub-Delivery": event["delivery_id"],
            "X-ApiHub-Timestamp": timestamp,
            "X-ApiHub-Signature": f"sha256={sign(webhook.secret or '', timestamp, body)}",
        }
    )
    return body, headers


async def send(webhook: TeamWebhook, event: dict, settings: Settings) -> DeliveryResult:
    """One delivery. Never raises: whatever goes wrong becomes a result with a
    short fixed error, so one broken webhook cannot disturb another or the
    check that produced the event."""
    body, headers = _request_for(webhook, event)
    try:
        result = await safe_post(
            webhook.url,
            body,
            headers,
            timeout=settings.webhook_timeout_seconds,
            allow_private=settings.outbound_allow_private_addresses,
        )
    except UnsafeUrlError:
        return DeliveryResult(ok=False, error="The address is not allowed")
    except httpx.TimeoutException:
        return DeliveryResult(ok=False, error="Timed out")
    except httpx.HTTPError:
        return DeliveryResult(ok=False, error="Could not connect")
    except Exception:
        logger.exception("Unexpected failure delivering webhook %s", webhook.id)
        return DeliveryResult(ok=False, error="Unexpected error")
    if 200 <= result.status_code < 300:
        return DeliveryResult(ok=True, status_code=result.status_code)
    return DeliveryResult(ok=False, status_code=result.status_code, error=f"The receiver answered {result.status_code}")


def record(webhook: TeamWebhook, result: DeliveryResult) -> None:
    """Remember how the last delivery went (the caller commits)."""
    webhook.last_attempt_at = datetime.now(timezone.utc)
    webhook.last_status = "ok" if result.ok else "error"
    webhook.last_error = None if result.ok else result.error
    webhook.consecutive_failures = 0 if result.ok else (webhook.consecutive_failures or 0) + 1


async def deliver_version_event(
    db: AsyncSession,
    doc: ApiDocument,
    version: ApiDocumentVersion,
    integration_names_by_team: dict[uuid.UUID, list[str]],
    settings: Settings,
) -> None:
    """Call the enabled webhooks of every team that should hear about this
    version - `integration_names_by_team` maps each such team to the names of
    ITS OWN integrations that use the document (empty for a team that owns it
    and uses it nowhere). A webhook set to "only breaking changes" stays quiet
    when the version has none. The calls run side by side, each with its own
    timeout, so the slowest receiver - not their sum - is what the caller
    waits for; the results are recorded in one commit."""
    if not integration_names_by_team:
        return
    webhooks = (
        (
            await db.execute(
                select(TeamWebhook)
                .where(TeamWebhook.team_id.in_(integration_names_by_team), TeamWebhook.enabled.is_(True))
                .order_by(TeamWebhook.created_at)
            )
        )
        .scalars()
        .all()
    )
    breaking = (version.change_summary or {}).get("breaking", 0)
    due = [webhook for webhook in webhooks if breaking or not webhook.only_breaking]
    if not due:
        return
    results = await asyncio.gather(
        *(
            send(
                webhook,
                build_version_event(doc, version, settings.frontend_url, integration_names_by_team[webhook.team_id]),
                settings,
            )
            for webhook in due
        )
    )
    for webhook, result in zip(due, results):
        record(webhook, result)
    await db.commit()
