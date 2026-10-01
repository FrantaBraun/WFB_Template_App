# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from app.modules.base import ModuleManifest
from app.modules.event_calendar.router import router

manifest = ModuleManifest(key="event_calendar", router=router, tags=["event_calendar"])
