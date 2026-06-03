"""Shared test configuration — ensure project root is on sys.path and stub heavy deps."""
import sys
import os
import types
import importlib.util
import importlib
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _has_module(mod_name: str) -> bool:
    try:
        return importlib.util.find_spec(mod_name) is not None
    except (ImportError, ValueError):
        return False


# Stub optional dependencies only when they are not installed. Do not replace
# real FastAPI/Starlette/Pydantic modules: route tests import their subpackages.
for mod_name in [
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.types", "sqlalchemy.ext", "sqlalchemy.ext.declarative",
    "sqlalchemy.ext.hybrid", "sqlalchemy.sql", "sqlalchemy.sql.expression",
    "sqlalchemy.sql.sqltypes", "bcrypt", "pyotp",
    "httpx", "fastapi", "fastapi.responses", "fastapi.routing",
    "starlette", "starlette.responses", "starlette.middleware", "starlette.middleware.base",
    "pydantic",
]:
    if mod_name not in sys.modules and not _has_module(mod_name):
        sys.modules[mod_name] = MagicMock()

if "src.database" not in sys.modules:
    _db = types.ModuleType("src.database")
    _db.SessionLocal = MagicMock()
    _db.ModelEndpoint = MagicMock()
    sys.modules["src.database"] = _db

# Several route tests stub `core.database` at import time with a bare
# ModuleType that lacks ORM symbols. Preload the real module when SQLAlchemy
# is installed so later tests (e.g. task scheduler delivery) can import Base.
if _has_module("sqlalchemy"):
    import importlib
    if "core.atomic_io" not in sys.modules:
        importlib.import_module("core.atomic_io")
    if "core.database" not in sys.modules:
        importlib.import_module("core.database")
    if "core.auth" not in sys.modules:
        importlib.import_module("core.auth")


def _core_database_is_stub() -> bool:
    mod = sys.modules.get("core.database")
    if mod is None:
        return False
    if type(mod).__name__ == "_DBStub":
        return True
    session_local = getattr(mod, "SessionLocal", None)
    if isinstance(session_local, MagicMock):
        base = getattr(mod, "Base", None)
        engine = getattr(mod, "engine", None)
        return isinstance(base, MagicMock) or isinstance(engine, MagicMock)
    return False


def _core_database_is_polluted() -> bool:
    """True when a prior test patched ORM symbols on the real core.database module."""
    mod = sys.modules.get("core.database")
    if mod is None or _core_database_is_stub():
        return False
    if not getattr(mod, "__file__", None):
        return False
    for attr in ("ChatMessage", "Session", "Webhook", "Base", "SessionLocal"):
        if isinstance(getattr(mod, attr, None), MagicMock):
            return True
    return False


def restore_real_core_modules() -> None:
    """Reload real ORM modules after a test file replaced or patched core.database."""
    if not _has_module("sqlalchemy"):
        return
    needs_db_reload = _core_database_is_stub() or _core_database_is_polluted()
    if needs_db_reload:
        sys.modules.pop("core.database", None)
    auth = sys.modules.get("core.auth")
    if auth is not None and not getattr(auth, "__file__", None):
        sys.modules.pop("core.auth", None)
    if needs_db_reload or "core.database" not in sys.modules:
        if "core.atomic_io" not in sys.modules:
            importlib.import_module("core.atomic_io")
        importlib.import_module("core.database")
        if "core.auth" not in sys.modules:
            importlib.import_module("core.auth")


@pytest.fixture(autouse=True)
def _ensure_real_core_database(request):
    """Restore core.database when import-time or in-test stubs leaked MagicMocks."""
    modname = getattr(request.module, "__name__", "") or ""
    if modname.endswith("test_companion_pairing"):
        yield
        return
    if _core_database_is_stub() or _core_database_is_polluted():
        restore_real_core_modules()
    yield



