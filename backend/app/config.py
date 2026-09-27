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
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/slavickovy_knihohratky_db"

    # Application
    app_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    cors_enabled: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]

    # Feature modules (see app/modules/) - keys of the pluggable modules to
    # mount for this deployment. Empty by default: this template ships no
    # modules of its own. Toggling this never changes the DB schema - every
    # discovered module's tables are always migrated regardless of this list.
    enabled_modules: list[str] = []

    # Authorization (auth.withfbraun.com)
    auth_url: str = "https://auth.withfbraun.com"
    auth_api_key: str = ""

    # Contact form module (app/modules/kontaktni_formular) - recipient for
    # every submission; empty by default so a deployment that enables the
    # module without setting this fails loudly (see the module's router)
    # rather than silently mailing nobody.
    contact_mail: str = ""

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

    # Uploads (admin-authored images for Page/Article content). Local dev
    # default is fine as-is; a production .env must point somewhere that
    # survives a deploy - see scripts/upgrade.sh's backend/ wipe-and-recreate.
    uploads_dir: str = "./uploads"

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
