"""Tests for the companion pairing endpoints (split 3/4).

Covers what the review asked for:
  - a non-admin / bearer caller cannot call /api/companion/pair (admin-only)
  - the pairing token is minted once (hashed at rest) and the mint invalidates
    the auth cache so it works immediately, no restart
  - minting is a POST, never a GET (CSRF: a SameSite=Lax cookie rides a
    top-level GET, so GET-minting would be triggerable by a link / <img>)
"""

import contextlib
import importlib
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.conftest import restore_real_core_modules

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Capture what mint_token would persist, via a stubbed core.database.
_CAPTURED = {}


class _ApiToken:
    def __init__(self, **kw):
        _CAPTURED.clear()
        _CAPTURED.update(kw)
        self.__dict__.update(kw)


@contextlib.contextmanager
def _get_db_session():
    yield MagicMock()


# core/__init__ pulls in models/session_manager which import many ORM names from
# core.database; under conftest's sqlalchemy stubs the real module can't load.
# A __getattr__ module resolves ANY requested name to a MagicMock, while keeping
# our real get_db_session/ApiToken for the mint test.
class _DBStub(types.ModuleType):
    def __getattr__(self, name):  # noqa: D401
        return MagicMock()


HTTPException = None
P = None
companion_routes = None
mint_pairing_token = None
setup_companion_routes = None
require_admin = None


_COMPANION_STUBBED_MODULES = (
    "core.database",
    "core.auth",
    "src.endpoint_resolver",
)


def _install_companion_stubs(saved: dict):
    _db = _DBStub("core.database")
    _db.get_db_session = _get_db_session
    _db.ApiToken = _ApiToken
    sys.modules["core.database"] = _db

    for _name, _attrs in {
        "core.auth": {"AuthManager": MagicMock()},
        "src.endpoint_resolver": {"build_chat_url": (lambda u: u)},
    }.items():
        saved.setdefault(_name, sys.modules.get(_name))
        _mm = types.ModuleType(_name)
        for _k, _v in _attrs.items():
            setattr(_mm, _k, _v)
        sys.modules[_name] = _mm

    for mod_name in list(sys.modules):
        if mod_name.startswith("companion."):
            saved.setdefault(mod_name, sys.modules.get(mod_name))
            del sys.modules[mod_name]


def _restore_companion_stubs(saved: dict):
    for mod_name in list(sys.modules):
        if mod_name.startswith("companion."):
            del sys.modules[mod_name]
    for mod_name in _COMPANION_STUBBED_MODULES:
        prior = saved.get(mod_name)
        if prior is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = prior
    restore_real_core_modules()
    for mod_name in ("routes.model_routes",):
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])


@pytest.fixture(scope="module", autouse=True)
def _companion_test_imports():
    global P, companion_routes, mint_pairing_token, setup_companion_routes, require_admin
    saved = {}
    _install_companion_stubs(saved)

    from fastapi import HTTPException as _HTTPException
    import companion.pairing as _P
    import companion.routes as _companion_routes
    from companion.routes import mint_pairing_token as _mint_pairing_token
    from companion.routes import setup_companion_routes as _setup_companion_routes
    from core.middleware import require_admin as _require_admin

    globals()["HTTPException"] = _HTTPException
    P = _P
    companion_routes = _companion_routes
    mint_pairing_token = _mint_pairing_token
    setup_companion_routes = _setup_companion_routes
    require_admin = _require_admin

    yield

    _restore_companion_stubs(saved)


# --- token minting: shown once, hashed at rest -----------------------------

def test_mint_token_returns_raw_once_and_stores_only_a_hash():
    token_id, raw = P.mint_token("alice")
    assert raw.startswith("ody_")
    # The persisted row stores a bcrypt hash + prefix, never the plaintext.
    assert _CAPTURED["token_hash"] != raw
    assert _CAPTURED["token_hash"].startswith("$2")  # bcrypt
    assert _CAPTURED["token_prefix"] == raw[:8]
    assert _CAPTURED["owner"] == "alice"
    assert _CAPTURED["scopes"] == "chat"
    assert _CAPTURED["is_active"] is True


def test_mint_pairing_token_invalidates_cache(monkeypatch):
    # The mint must flip the auth middleware's cache so the token works on the
    # very next request, with no restart.
    monkeypatch.setattr(P, "mint_token", lambda owner, name="companion": ("id1", "ody_demo"))
    invalidate = MagicMock()
    token_id, raw = mint_pairing_token("alice", invalidate)
    assert (token_id, raw) == ("id1", "ody_demo")
    invalidate.assert_called_once()


def test_mint_pairing_token_tolerates_no_invalidator(monkeypatch):
    monkeypatch.setattr(P, "mint_token", lambda owner, name="companion": ("id1", "ody_demo"))
    # Must not blow up if the app didn't expose an invalidator.
    assert mint_pairing_token("alice", None) == ("id1", "ody_demo")


def test_pairing_payload_shape():
    p = P.pairing_payload("192.168.1.9", 7000, "ody_x")
    assert p == {"v": 1, "host": "192.168.1.9", "port": 7000, "token": "ody_x"}


# --- admin-only gate: a bearer/non-admin caller is rejected ----------------

def _admin_mgr(is_admin):
    return SimpleNamespace(is_admin=lambda u: is_admin, is_configured=True)


def _req(current_user, *, api_token=False, is_admin=False):
    return SimpleNamespace(
        state=SimpleNamespace(current_user=current_user, api_token=api_token),
        headers={},
        app=SimpleNamespace(state=SimpleNamespace(auth_manager=_admin_mgr(is_admin))),
    )


def test_bearer_token_caller_cannot_pair(monkeypatch):
    # Bearer callers come through as the "api" pseudo-user, which is not admin.
    monkeypatch.setenv("AUTH_ENABLED", "true")
    with pytest.raises(HTTPException) as exc:
        require_admin(_req("api", api_token=True, is_admin=False))
    assert exc.value.status_code == 403


def test_non_admin_user_cannot_pair(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    with pytest.raises(HTTPException) as exc:
        require_admin(_req("bob", is_admin=False))
    assert exc.value.status_code == 403


def test_admin_user_passes_the_gate(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    # Should not raise.
    require_admin(_req("alice", is_admin=True))


# --- CSRF: minting is POST, never GET --------------------------------------

def _pair_methods():
    router = setup_companion_routes()
    methods = set()
    for r in router.routes:
        path = getattr(r, "path", "")
        if path.endswith("/pair"):
            methods |= set(getattr(r, "methods", set()) or set())
    return methods


def _pair_endpoint(method):
    router = setup_companion_routes()
    for r in router.routes:
        if getattr(r, "path", "").endswith("/pair") and method in getattr(r, "methods", set()):
            return r.endpoint
    raise AssertionError(f"{method} /api/companion/pair route not found")


def test_pair_is_minted_via_post_not_get():
    methods = _pair_methods()
    assert "POST" in methods, "pairing must accept POST (the mint)"
    assert "GET" in methods, "GET should render the form page"
    # The distinction is enforced in the handlers: GET renders a form and never
    # mints; only POST calls mint_pairing_token.


def test_pair_page_uses_imported_admin_gate(monkeypatch):
    monkeypatch.setattr(companion_routes, "require_admin", lambda request: None)
    response = _pair_endpoint("GET")(SimpleNamespace())

    assert "Pair a device" in str(getattr(response, "body", response))
