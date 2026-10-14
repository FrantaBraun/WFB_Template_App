# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Why payments are off - and the two places that say so.

Payments are offered only where three things are in place: the payment
gateway module is switched on in modules.json, its two Stripe keys are in
.env, and the provider's details (who issues the payment documents) are filled
in boards.json. Missing any of them, GET /payments says `enabled: false` and
the frontend simply leaves every payment option out - which, with nothing
said, looks like a bug rather than a setting. So the same conditions are
spelled out in the console at startup (log_payments_status, run through the
module manifest's on_startup hook) and to administrators on the moderation
page (GET /manage/payments-status).

Only the *presence* of a key is ever reported, never its value.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.modules.boards.config import BoardsConfig, get_config
from app.modules.registry import load_enabled_module_keys

logger = logging.getLogger(__name__)

GATEWAY_MODULE = "stripe_payment_gate"

GATEWAY_DISABLED = "gateway_module_disabled"
SECRET_KEY_MISSING = "stripe_secret_key_missing"
WEBHOOK_SECRET_MISSING = "stripe_webhook_secret_missing"
PROVIDER_INCOMPLETE = "provider_incomplete"


@dataclass(frozen=True)
class Problem:
    """One reason payments are off. `missing` names the provider fields that
    are blank, for PROVIDER_INCOMPLETE."""

    code: str
    missing: tuple[str, ...] = ()


def gateway_problems(settings: Settings, enabled_modules: Iterable[str]) -> list[Problem]:
    """What keeps the gateway itself from working: the module not switched
    on, and the Stripe keys that are not set."""
    problems = []
    if GATEWAY_MODULE not in set(enabled_modules):
        problems.append(Problem(GATEWAY_DISABLED))
    if not settings.stripe_secret_key:
        problems.append(Problem(SECRET_KEY_MISSING))
    if not settings.stripe_webhook_secret:
        problems.append(Problem(WEBHOOK_SECRET_MISSING))
    return problems


def provider_problems(config: BoardsConfig) -> list[Problem]:
    """The provider's details, when they are not complete enough to issue a document."""
    missing = config.invoicing.provider.missing_fields()
    return [Problem(PROVIDER_INCOMPLETE, tuple(missing))] if missing else []


def problems(settings: Settings, config: BoardsConfig, enabled_modules: Iterable[str]) -> list[Problem]:
    """Every reason payments are off; empty when they are on."""
    return gateway_problems(settings, enabled_modules) + provider_problems(config)


def describe(problem: Problem) -> str:
    """One problem as a sentence for the console: what is wrong and which file to edit."""
    if problem.code == GATEWAY_DISABLED:
        return (
            f'The payment gateway module is not enabled: add "{GATEWAY_MODULE}" to backend/modules.json '
            "(and to frontend/public/modules.json)."
        )
    if problem.code == SECRET_KEY_MISSING:
        return "STRIPE_SECRET_KEY is not set in backend/.env."
    if problem.code == WEBHOOK_SECRET_MISSING:
        return "STRIPE_WEBHOOK_SECRET is not set in backend/.env."
    if problem.code == PROVIDER_INCOMPLETE:
        return (
            "The provider's details are incomplete in backend/modules/boards.json (invoicing.provider): "
            f"missing {', '.join(problem.missing)}. The same details belong in `provider` in "
            "frontend/public/legal.json."
        )
    return problem.code


def log_payments_status() -> None:
    """The module's startup hook: one warning that lists every reason payments
    are off, or a line saying they are on. It never fails the startup - the
    caller catches whatever goes wrong - and never prints a secret."""
    found = problems(get_settings(), get_config(), load_enabled_module_keys())
    if not found:
        logger.info("Payments are on")
        return
    lines = [
        "Payments are OFF - authors cannot pay for posts, and no payment option is shown. Why:",
        *(f"  - {describe(problem)}" for problem in found),
        "Restart the backend after changing the configuration: it is read once, at startup.",
    ]
    logger.warning("\n".join(lines))
