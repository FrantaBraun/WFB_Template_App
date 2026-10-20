# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from app.modules.articles.router import router
from app.modules.base import ModuleManifest

manifest = ModuleManifest(key="articles", router=router, tags=["articles"])
