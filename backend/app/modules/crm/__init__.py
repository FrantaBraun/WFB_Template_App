# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from app.modules.base import ModuleManifest
from app.modules.crm.router import router

manifest = ModuleManifest(key="crm", router=router, tags=["crm"])
