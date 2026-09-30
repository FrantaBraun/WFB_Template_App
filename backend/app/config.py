# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/api_hub_db"

    # Application
    app_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    cors_enabled: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]

    # API documents (app/services/spec_storage.py, openapi_spec.py) - where
    # uploaded/fetched spec files are stored, and limits on ingesting them.
    # uploads_dir matches scripts/upgrade.sh's UPLOADS_DIR env var, which
    # already backs up/restores this directory across redeploys.
    uploads_dir: str = "./uploads"
    max_spec_file_size_bytes: int = 10_000_000
    spec_fetch_timeout_seconds: float = 10.0

    # Automatic recheck scheduler (app/services/scheduler.py) - periodically
    # scans ApiDocuments for a due recheck_period and reuses the same
    # fetch_and_process logic as a manual recheck.
    scheduler_enabled: bool = True
    recheck_scan_interval_minutes: int = 60

    # Feature modules (see app/modules/) are deliberately NOT configured
    # here: which ones are mounted is set in the git-tracked
    # backend/modules.json, so it follows the branch rather than .env.

    # Authorization (auth.withfbraun.com)
    auth_url: str = "https://auth.withfbraun.com"
    auth_api_key: str = ""

    # Contact form module (app/modules/kontaktni_formular) - recipient for
    # every submission; empty by default so a deployment that enables the
    # module without setting this fails loudly (see the module's router)
    # rather than silently mailing nobody.
    contact_mail: str = ""

    reply_message_to_contact_form: bool = True
    reply_message_subject_contact_form: str = "Thank you for your message from the contact form"
    reply_message_body_contact_form: str = "Thank you for your message, {sender_name}!\n\nWe have received your message and will get back to you as soon as possible.\n\nYour message:\n{body.message}"

    # Stripe payment gate module (app/modules/stripe_payment_gate) - empty
    # by default; the module's endpoints fail loudly (503) until both keys
    # are set, rather than half-working. stripe_api_url is only overridden
    # by tests (respx) or a local fake - never point it anywhere else.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_api_url: str = "https://api.stripe.com"

    # Email (SMTP)
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "noreply@example.com"
    mail_server: str = "smtp.example.com"
    mail_port: int = 587
    mail_starttls: bool = True
    mail_ssl_tls: bool = False
    mail_suppress_send: bool = False

    # Logging
    logging_level: str = "INFO"
    logging_dir: str = "logs"
    logging_filename: str = "app.log"
    logging_days_history: int = 5
    logging_message_format: str = r"%(asctime)s %(levelname)s\t- %(module)s.%(funcName)s: %(message)s"


@lru_cache
def get_settings() -> Settings:
    """Build and cache the Settings singleton for the process lifetime.

    Because this is cached, a running process never picks up .env changes
    without a restart - `uvicorn --reload` only watches .py files, not .env.
    """
    return Settings()
