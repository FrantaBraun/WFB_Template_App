# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.config import Settings, get_settings


def _connection_config(settings: Settings, **overrides: object) -> ConnectionConfig:
    """Build a fastapi-mail ConnectionConfig from .env defaults, overridable per call."""
    fields = {
        "MAIL_USERNAME": settings.mail_username,
        "MAIL_PASSWORD": settings.mail_password,
        "MAIL_FROM": settings.mail_from,
        "MAIL_FROM_NAME": settings.mail_from_name,
        "MAIL_PORT": settings.mail_port,
        "MAIL_SERVER": settings.mail_server,
        "MAIL_STARTTLS": settings.mail_starttls,
        "MAIL_SSL_TLS": settings.mail_ssl_tls,
        "SUPPRESS_SEND": int(settings.mail_suppress_send),
        "USE_CREDENTIALS": bool(settings.mail_username),
    }
    fields.update(overrides)
    return ConnectionConfig(**fields)


async def send_email(
    subject: str,
    recipients: list[str],
    body: str,
    *,
    subtype: MessageType = MessageType.plain,
    settings: Settings | None = None,
    **connection_overrides: object,
) -> None:
    """Send an email. Connection defaults come from .env (MAIL_*) and can be
    overridden per call via connection_overrides, e.g. MAIL_FROM="other@x.com"."""
    resolved_settings = settings or get_settings()
    config = _connection_config(resolved_settings, **connection_overrides)
    message = MessageSchema(subject=subject, recipients=recipients, body=body, subtype=subtype)
    await FastMail(config).send_message(message)
