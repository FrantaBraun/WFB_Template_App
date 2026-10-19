# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Who runs the site, for its legal pages (Privacy, Terms, Cookies).

These are per-server values, so they come from backend/.env (`PROVIDER_*`,
see .env.example) like the contact details do, not from a tracked file. The
class reads the same .env as app.config.Settings but is the module's own, so
the shared Settings does not change on this branch. Like get_settings() it is
loaded once per process: editing .env needs a restart.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import BASE_DIR


class ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_prefix="PROVIDER_", extra="ignore")

    name: str = ""
    ico: str = ""
    dic: str = ""
    vat_payer: bool = False
    address: str = ""
    # How the provider is entered in the public register, one text per
    # language (e.g. the trade register entry of a natural person).
    registration_cs: str = ""
    registration_en: str = ""
    email: str = ""
    phone: str = ""
    web: str = ""
    # Optional separate address for data-protection requests.
    dpo_email: str = ""
    # ISO date (YYYY-MM-DD) the legal texts are effective from.
    effective_from: str = ""


@lru_cache
def get_provider_settings() -> ProviderSettings:
    """Cached for the process lifetime and injected into the route via
    Depends so tests can override it, like get_settings."""
    return ProviderSettings()
