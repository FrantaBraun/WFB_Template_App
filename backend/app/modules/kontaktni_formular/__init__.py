# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from app.modules.base import ModuleManifest
from app.modules.kontaktni_formular.router import router

manifest = ModuleManifest(key="kontaktni_formular", router=router, tags=["kontaktni_formular"])
