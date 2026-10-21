# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Guards the frontend's module loading against an import cycle.

frontend/src/modules/registry.ts imports every module's index.tsx. If code
inside a module (or anything a module imports) imported registry.ts back, the
two would form a cycle, and whether the application started or died with
"Cannot access 'default' before initialization" would depend on which of the
two a page happened to import first - it surfaced only on an application whose
home page imports a module's exports. Modules use moduleStore.ts instead (see
the note at its top); only the entry point imports registry.ts. There is no
frontend test runner, so this is a plain text check."""

import re
from pathlib import Path

MODULES_DIR = Path(__file__).resolve().parents[2] / "frontend" / "src" / "modules"
IMPORTS_REGISTRY = re.compile(r"""from\s+['"](?:\.{1,2}/)+(?:modules/)?registry['"]""")


def _sources():
    return [p for p in MODULES_DIR.rglob("*") if p.suffix in (".ts", ".tsx") and p.name != "registry.ts"]


def test_the_frontend_modules_folder_is_where_this_test_expects_it():
    assert (MODULES_DIR / "registry.ts").is_file()
    assert (MODULES_DIR / "moduleStore.ts").is_file()
    assert _sources()


def test_no_module_file_imports_the_registry():
    offenders = [str(p.relative_to(MODULES_DIR)) for p in _sources() if IMPORTS_REGISTRY.search(p.read_text(encoding="utf-8"))]

    assert not offenders, f"import moduleStore instead of registry (import cycle) in: {offenders}"


def test_the_store_itself_does_not_import_any_module():
    store = (MODULES_DIR / "moduleStore.ts").read_text(encoding="utf-8")

    assert not re.search(r"import\.meta\.glob\s*[<(]", store), "the store must not load modules itself (that is registry.ts)"
    assert not IMPORTS_REGISTRY.search(store)
