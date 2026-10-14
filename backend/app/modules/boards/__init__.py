# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from app.modules.base import ModuleManifest
from app.modules.boards.payments import register_payment_purposes
from app.modules.boards.payments_status import log_payments_status
from app.modules.boards.router import router

# The payment gateway (stripe_payment_gate) finds this module's payment
# purpose by key; registering it is a plain in-memory call, so it is harmless
# where the gateway is switched off.
register_payment_purposes()

# on_startup: say in the console when payments are off and why - nothing else shows it.
manifest = ModuleManifest(key="boards", router=router, tags=["boards"], on_startup=log_payments_status)
