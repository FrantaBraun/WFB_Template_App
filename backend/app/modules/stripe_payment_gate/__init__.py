# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from app.modules.base import ModuleManifest
from app.modules.stripe_payment_gate.router import router

manifest = ModuleManifest(key="stripe_payment_gate", router=router, tags=["stripe_payment_gate"])
