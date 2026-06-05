"""Shared test configuration — ensure project root is on sys.path and stub heavy deps."""
import sys
import os
import types
import importlib.util
import importlib
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Pre-import real heavy modules BEFORE any test file's module-level stubs can
# replace them with MagicMock. Some test files (e.g. test_llm_core_sanitize_*)
# stub sqlalchemy/core.database at module scope with `if mod not in sys.modules`,
# which fires during collection. If the real module hasn't been imported yet,
# the stub wins and contaminates every subsequent test that needs the real ORM.
try:
    import sqlalchemy  # noqa: F401
    import sqlalchemy.orm  # noqa: F401
    import core.database  # noqa: F401
except ImportError:
    pass  # not installed — the stubs below will handle it

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

# Prefer the real src.database shim when SQLAlchemy is installed (llm_core cache lookups).
if _has_module("sqlalchemy"):
    try:
        importlib.import_module("src.database")
    except Exception:
        pass

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
        sys.modules.pop("core.session_manager", None)
        sys.modules.pop("core.models", None)
    auth = sys.modules.get("core.auth")
    if auth is not None and not getattr(auth, "__file__", None):
        sys.modules.pop("core.auth", None)
    if needs_db_reload or "core.database" not in sys.modules:
        if "core.atomic_io" not in sys.modules:
            importlib.import_module("core.atomic_io")
        importlib.import_module("core.database")
        if "core.auth" not in sys.modules:
            importlib.import_module("core.auth")
        try:
            importlib.import_module("core.models")
            importlib.import_module("core.session_manager")
        except Exception:
            pass


_ROUTE_MODULES_TO_RELOAD = (
    "routes.model_routes",
    "routes.chat_routes",
    "routes.document_routes",
    "src.endpoint_resolver",
)

_SRC_MODULES_TO_RELOAD = (
    "src.agent_tools",
    "src.agent_loop",
    "src.llm_core",
    "src.tool_parsing",
    "src.tool_schemas",
    "src.tool_execution",
)


def _module_is_import_stub(mod) -> bool:
    if mod is None:
        return False
    return not getattr(mod, "__file__", None)


def restore_stubbed_route_modules() -> None:
    """Reload route modules commonly replaced by import-time sys.modules stubs."""
    for mod_name in _ROUTE_MODULES_TO_RELOAD:
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        if not _module_is_import_stub(mod):
            continue
        sys.modules.pop(mod_name, None)
        try:
            importlib.import_module(mod_name)
        except Exception:
            pass


def restore_stubbed_src_modules() -> None:
    """Reload src.* modules replaced by MagicMock during test module collection."""
    for mod_name in _SRC_MODULES_TO_RELOAD:
        mod = sys.modules.get(mod_name)
        if not _module_is_import_stub(mod):
            continue
        sys.modules.pop(mod_name, None)
        try:
            importlib.import_module(mod_name)
        except Exception:
            pass


def _webhook_manager_is_polluted() -> bool:
    """True when webhook_manager kept stale DB bindings from a stubbed import."""
    wm = sys.modules.get("src.webhook_manager")
    if wm is None or not getattr(wm, "__file__", None):
        return False
    if not _has_module("sqlalchemy"):
        return False
    try:
        from core.database import Webhook as real_webhook
    except Exception:
        return False
    return getattr(wm, "Webhook", None) is not real_webhook


def restore_webhook_manager_if_polluted() -> None:
    """Reload webhook_manager after tests import it with fake core/src.database."""
    if not _webhook_manager_is_polluted():
        return
    sys.modules.pop("src.webhook_manager", None)
    try:
        importlib.import_module("src.webhook_manager")
    except Exception:
        pass


def make_db_session(**overrides):
    """Minimal Session row satisfying NOT NULL endpoint_url (matches production)."""
    from core.database import Session as DbSession

    defaults = {
        "id": "test-session",
        "name": "test",
        "endpoint_url": "",
        "model": "m",
        "owner": "alice",
        "archived": False,
    }
    defaults.update(overrides)
    return DbSession(**defaults)


@pytest.fixture(autouse=True)
def _ensure_real_core_database(request):
    """Restore core.database when import-time or in-test stubs leaked MagicMocks."""
    modname = getattr(request.module, "__name__", "") or ""
    if modname.endswith("test_companion_pairing"):
        yield
        return
    restore_stubbed_src_modules()
    restore_stubbed_route_modules()
    if _core_database_is_stub() or _core_database_is_polluted():
        restore_real_core_modules()
    restore_webhook_manager_if_polluted()
    yield
    restore_stubbed_src_modules()
    if _core_database_is_stub() or _core_database_is_polluted():
        restore_real_core_modules()
        restore_stubbed_route_modules()
    restore_webhook_manager_if_polluted()

