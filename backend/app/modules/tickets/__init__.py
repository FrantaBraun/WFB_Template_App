# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from app.modules.base import ModuleManifest
from app.modules.kontaktni_formular.hooks import CONTACT_FORM_RECEIVED
from app.modules.tickets.mailbox import mailbox_poller
from app.modules.tickets.router import router
from app.modules.tickets.service import contact_form_hook

# No `requires`: the module stands on its own. It extends the contact form
# (a message becomes a ticket) only when that module is enabled too, and uses
# the CRM only when that is enabled - both are optional, see service.py.
manifest = ModuleManifest(
    key="tickets",
    router=router,
    tags=["tickets"],
    hooks={CONTACT_FORM_RECEIVED: contact_form_hook},
    background_tasks=(mailbox_poller,),
)
