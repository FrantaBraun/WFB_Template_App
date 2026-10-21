# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from app.modules.base import ModuleManifest
from app.modules.table_reservations.router import router

manifest = ModuleManifest(key="table_reservations", router=router, tags=["table_reservations"])
