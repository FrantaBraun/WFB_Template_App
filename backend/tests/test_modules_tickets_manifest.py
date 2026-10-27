# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""How the tickets module plugs into the rest: what its manifest declares, and
that the contact form only takes part in it while the module is enabled."""

from app.modules.kontaktni_formular.hooks import CONTACT_FORM_RECEIVED
from app.modules.registry import discover_modules, get_enabled_hooks
from app.modules.tickets import manifest
from app.modules.tickets.mailbox import mailbox_poller
from app.modules.tickets.service import contact_form_hook


def test_the_manifest_declares_the_contact_form_hook_the_poller_and_no_requirements():
    assert manifest.key == "tickets"
    assert manifest.requires == ()  # stands on its own; the contact form and the CRM are optional
    assert manifest.hooks == {CONTACT_FORM_RECEIVED: contact_form_hook}
    assert manifest.background_tasks == (mailbox_poller,)
    assert manifest.router is not None


def test_the_module_is_discovered_under_its_folder_name():
    assert "tickets" in {m.key for m in discover_modules()}


def test_the_contact_form_only_takes_part_while_the_module_is_enabled():
    assert get_enabled_hooks(CONTACT_FORM_RECEIVED, ["tickets"]) == [contact_form_hook]
    assert get_enabled_hooks(CONTACT_FORM_RECEIVED, ["kontaktni_formular"]) == []
    assert get_enabled_hooks(CONTACT_FORM_RECEIVED, []) == []
