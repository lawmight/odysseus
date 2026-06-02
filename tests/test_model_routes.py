"""Tests for model route helper functions — pure logic, no server needed."""
import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException

_endpoint_resolver = sys.modules.get("src.endpoint_resolver")
if _endpoint_resolver is not None and not getattr(_endpoint_resolver, "__file__", None):
    # Other tests stub this module during collection. These helper tests need
    # the real URL normalization helpers so Anthropic /v1 handling is covered.
    sys.modules.pop("src.endpoint_resolver", None)
    sys.modules.pop("routes.model_routes", None)

import routes.model_routes as model_routes
import src.endpoint_resolver as endpoint_resolver
from routes.model_routes import (
    CursorAdapterError,
    _match_provider_curated,
    _curate_models,
    _is_chat_model,
    _classify_endpoint,
    _probe_endpoint,
    _probe_single_model,
    _truthy,
    _PROVIDER_CURATED,
)
from src.llm_core import ANTHROPIC_MODELS


# ── _match_provider_curated ──

class TestMatchProviderCurated:
    def test_url_match_overrides_provider(self):
        assert _match_provider_curated("https://z.ai/v1", "openai") == "zai"

    def test_deepseek_url(self):
        assert _match_provider_curated("https://api.deepseek.com/v1", "openai") == "deepseek"

    def test_groq_url(self):
        assert _match_provider_curated("https://api.groq.com/openai/v1", "openai") == "groq"

    def test_mistral_url(self):
        assert _match_provider_curated("https://api.mistral.ai/v1", "openai") == "mistral"

    def test_together_url(self):
        assert _match_provider_curated("https://api.together.xyz/v1", "openai") == "together"

    def test_fireworks_url(self):
        assert _match_provider_curated("https://api.fireworks.ai/inference/v1", "openai") == "fireworks"

    def test_google_url(self):
        assert _match_provider_curated("https://generativelanguage.googleapis.com/v1beta", "openai") == "google"

    def test_xai_url(self):
        assert _match_provider_curated("https://api.x.ai/v1", "openai") == "xai"

    def test_ollama_url(self):
        assert _match_provider_curated("https://ollama.com/api", "openai") == "ollama"

    def test_no_url_match_returns_provider(self):
        assert _match_provider_curated("https://localhost:1234", "openai") == "openai"

    def test_none_provider_passthrough(self):
        assert _match_provider_curated("https://localhost:1234", None) is None

    def test_none_url_safe(self):
        assert _match_provider_curated(None, "openai") == "openai"


# ── _curate_models ──

class TestCurateModels:
    def test_known_provider_partitions(self):
        models = ["gpt-4o", "gpt-4o-mini", "ft:gpt-4o:custom", "some-random-model"]
        curated, extra = _curate_models(models, "openai")
        assert "gpt-4o" in curated
        assert "gpt-4o-mini" in curated
        assert "some-random-model" in extra

    def test_unknown_provider_returns_all_as_curated(self):
        models = ["model-a", "model-b"]
        curated, extra = _curate_models(models, "unknown_provider")
        assert curated == models
        assert extra == []

    def test_curated_sorted_by_priority(self):
        models = ["gpt-4o-mini", "gpt-4o", "o3"]
        curated, _ = _curate_models(models, "openai")
        # gpt-4o should come before gpt-4o-mini in the curated list priority
        gpt4o_idx = curated.index("gpt-4o")
        gpt4o_mini_idx = curated.index("gpt-4o-mini")
        assert gpt4o_idx < gpt4o_mini_idx

    def test_empty_models(self):
        curated, extra = _curate_models([], "openai")
        assert curated == []
        assert extra == []

    def test_deepseek_curated(self):
        models = ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"]
        curated, extra = _curate_models(models, "deepseek")
        assert "deepseek-chat" in curated
        assert "deepseek-reasoner" in curated
        assert "deepseek-coder" in extra

    def test_xai_curated(self):
        models = ["grok-4", "grok-3-fast", "grok-2"]
        curated, extra = _curate_models(models, "xai")
        assert "grok-4" in curated
        assert "grok-3-fast" in curated
        assert "grok-2" in extra

    def test_xai_current_grok_43_curated(self):
        curated, extra = _curate_models(["grok-4.3", "grok-4.3-fast"], "xai")
        assert curated == ["grok-4.3", "grok-4.3-fast"]
        assert extra == []

    def test_groq_current_models_curated(self):
        models = [
            "openai/gpt-oss-120b",
            "groq/compound",
            "llama-3.1-8b-instant",
            "llama-4-scout-17b-16e-instruct",
        ]
        curated, extra = _curate_models(models, "groq")
        assert curated == models
        assert extra == []

    def test_google_current_gemini_curated(self):
        curated, extra = _curate_models(["gemini-3.5-flash", "gemini-3.1-pro"], "google")
        assert curated == ["gemini-3.5-flash", "gemini-3.1-pro"]
        assert extra == []


# ── _is_chat_model ──

class TestIsChatModel:
    @pytest.mark.parametrize("model_id", [
        "gpt-4o", "gpt-4o-mini", "claude-sonnet-4", "llama-3.3-70b",
        "deepseek-chat", "gemini-2.0-flash", "o3",
        "llama-4-scout-17b-16e-instruct",
    ])
    def test_chat_models(self, model_id):
        assert _is_chat_model(model_id) is True

    @pytest.mark.parametrize("model_id", [
        "dall-e-3", "tts-1", "whisper-1", "text-embedding-3-small",
        "gpt-image-1", "sora-1",
    ])
    def test_non_chat_models(self, model_id):
        assert _is_chat_model(model_id) is False

    def test_realtime_excluded(self):
        assert _is_chat_model("gpt-4o-realtime-preview") is False

    def test_audio_preview_is_chat(self):
        # gpt-4o-audio-preview is a chat model (has "audio" not "gpt-audio")
        assert _is_chat_model("gpt-4o-audio-preview") is True

    def test_gpt_audio_is_not_chat(self):
        assert _is_chat_model("gpt-audio") is False

    def test_legacy_openai_instruct_is_not_chat(self):
        assert _is_chat_model("gpt-3.5-turbo-instruct") is False


# ── _classify_endpoint ──

class TestClassifyEndpoint:
    def test_localhost(self):
        assert _classify_endpoint("http://localhost:1234") == "local"

    def test_127(self):
        assert _classify_endpoint("http://127.0.0.1:8080/v1") == "local"

    def test_private_192(self):
        assert _classify_endpoint("http://192.168.1.100:5000") == "local"

    def test_private_10(self):
        assert _classify_endpoint("http://10.0.0.5:8000") == "local"

    def test_public_api(self):
        assert _classify_endpoint("https://api.openai.com/v1") == "api"

    def test_empty_string(self):
        assert _classify_endpoint("") == "api"

    def test_malformed_url(self):
        assert _classify_endpoint("not-a-url") == "api"


# ── setup probing ──

class TestSetupProbeSafety:
    @pytest.mark.parametrize("value", ["true", "1", "yes", "on", " TRUE "])
    def test_truthy_true_values(self, value):
        assert _truthy(value) is True

    @pytest.mark.parametrize("value", ["false", "0", "no", "", None])
    def test_truthy_false_values(self, value):
        assert _truthy(value) is False

    def test_keyed_probe_does_not_fallback_to_curated_on_auth_failure(self, monkeypatch):
        monkeypatch.setattr(endpoint_resolver, "resolve_url", lambda url: url, raising=False)
        monkeypatch.setattr(model_routes, "_normalize_base", lambda url: url.rstrip("/"))

        def fake_get(url, headers=None, timeout=None):
            request = httpx.Request("GET", url)
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

        monkeypatch.setattr(model_routes.httpx, "get", fake_get)

        assert _probe_endpoint("https://api.groq.com/openai/v1", "bad-key") == []

    def test_unkeyed_probe_can_still_use_curated_fallback(self, monkeypatch):
        monkeypatch.setattr(endpoint_resolver, "resolve_url", lambda url: url, raising=False)
        monkeypatch.setattr(model_routes, "_normalize_base", lambda url: url.rstrip("/"))

        def fake_get(url, headers=None, timeout=None):
            raise httpx.ConnectError("offline")

        monkeypatch.setattr(model_routes.httpx, "get", fake_get)

        assert _probe_endpoint("https://api.groq.com/openai/v1") == _PROVIDER_CURATED["groq"]

    def test_keyed_anthropic_probe_does_not_fallback_on_failure(self, monkeypatch):
        monkeypatch.setattr(endpoint_resolver, "resolve_url", lambda url: url, raising=False)
        monkeypatch.setattr(model_routes, "_normalize_base", lambda url: url.rstrip("/"))

        def fake_get(url, headers=None, timeout=None):
            raise httpx.ConnectError("offline")

        monkeypatch.setattr(model_routes.httpx, "get", fake_get)

        assert _probe_endpoint("https://api.anthropic.com/v1", "bad-key") == []

    def test_anthropic_probe_does_not_double_v1(self, monkeypatch):
        monkeypatch.setattr(endpoint_resolver, "resolve_url", lambda url: url, raising=False)
        monkeypatch.setattr(model_routes, "_normalize_base", lambda url: url.rstrip("/"))
        seen = []

        def fake_get(url, headers=None, timeout=None):
            seen.append(url)
            request = httpx.Request("GET", url)
            response = httpx.Response(
                200,
                request=request,
                json={"data": [{"id": "claude-sonnet-4-5"}]},
            )
            return response

        monkeypatch.setattr(model_routes.httpx, "get", fake_get)

        assert _probe_endpoint("https://api.anthropic.com/v1", "good-key") == ["claude-sonnet-4-5"]
        assert seen == ["https://api.anthropic.com/v1/models"]

    def test_ollama_cloud_probe_uses_native_tags_endpoint(self, monkeypatch):
        monkeypatch.setattr(endpoint_resolver, "resolve_url", lambda url: url, raising=False)
        monkeypatch.setattr(model_routes, "_normalize_base", lambda url: url.rstrip("/"))
        seen = []

        def fake_get(url, headers=None, timeout=None):
            seen.append((url, headers))
            request = httpx.Request("GET", url)
            response = httpx.Response(
                200,
                request=request,
                json={"models": [{"name": "gpt-oss:120b"}, {"model": "qwen3:235b"}]},
            )
            return response

        monkeypatch.setattr(model_routes.httpx, "get", fake_get)

        assert _probe_endpoint("https://ollama.com/api", "ollama-key") == ["gpt-oss:120b", "qwen3:235b"]
        assert seen == [("https://ollama.com/api/tags", {"Authorization": "Bearer ollama-key"})]

    def test_unkeyed_anthropic_probe_can_use_curated_fallback(self, monkeypatch):
        monkeypatch.setattr(endpoint_resolver, "resolve_url", lambda url: url, raising=False)
        monkeypatch.setattr(model_routes, "_normalize_base", lambda url: url.rstrip("/"))

        def fake_get(url, headers=None, timeout=None):
            raise httpx.ConnectError("offline")

        monkeypatch.setattr(model_routes.httpx, "get", fake_get)

        assert _probe_endpoint("https://api.anthropic.com/v1") == ANTHROPIC_MODELS

    def test_cursor_probe_uses_cursor_models_endpoint(self, monkeypatch):
        monkeypatch.setattr(model_routes, "list_cursor_models", lambda api_key, timeout=5: ["composer-2.5"])

        assert _probe_endpoint("cursor://local", "cur-key") == ["composer-2.5"]

    def test_cursor_probe_returns_empty_on_cursor_error(self, monkeypatch):
        def fail(api_key, timeout=5):
            raise CursorAdapterError("bad key", status=401)

        monkeypatch.setattr(model_routes, "list_cursor_models", fail)

        assert _probe_endpoint("cursor://local", "bad-key") == []

    def test_cursor_single_model_probe_checks_cursor_models(self, monkeypatch):
        monkeypatch.setattr(model_routes, "list_cursor_models", lambda api_key, timeout=8: ["composer-2.5"])

        assert _probe_single_model("cursor://local", "cur-key", "composer-2.5")["status"] == "ok"

    def test_cursor_single_model_probe_fails_when_model_missing(self, monkeypatch):
        monkeypatch.setattr(model_routes, "list_cursor_models", lambda api_key, timeout=8: ["other-model"])

        result = _probe_single_model("cursor://local", "cur-key", "composer-2.5")

        assert result["status"] == "fail"
        assert "Model not returned" in result["error"]


class _RouteCondition:
    def __init__(self, op, field, value=None, left=None, right=None):
        self.op = op
        self.field = field
        self.value = value
        self.left = left
        self.right = right

    def __or__(self, other):
        return _RouteCondition("or", None, None, self, other)


class _RouteColumn:
    def __init__(self, name):
        self.name = name

    def __eq__(self, value):
        return _RouteCondition("eq", self.name, value)

    def is_(self, value):
        return _RouteCondition("is", self.name, value)

    def desc(self):
        return _RouteCondition("desc", self.name)


class _RouteModelEndpoint:
    id = _RouteColumn("id")
    base_url = _RouteColumn("base_url")
    owner = _RouteColumn("owner")
    is_enabled = _RouteColumn("is_enabled")
    created_at = _RouteColumn("created_at")

    def __init__(self, **kwargs):
        self.hidden_models = None
        self.created_at = None
        for key, value in kwargs.items():
            setattr(self, key, value)


class _RouteQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conditions):
        for condition in conditions:
            self.rows = [row for row in self.rows if self._matches(row, condition)]
        return self

    @staticmethod
    def _matches(row, condition):
        if isinstance(condition, _RouteCondition):
            if condition.op == "eq":
                return getattr(row, condition.field) == condition.value
            if condition.op == "is":
                return getattr(row, condition.field, None) is condition.value
            if condition.op == "or":
                return _RouteQuery._matches(row, condition.left) or _RouteQuery._matches(
                    row, condition.right
                )
        return True

    def order_by(self, *args):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class _RouteDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return _RouteQuery(self.rows)

    def add(self, row):
        self.rows.append(row)

    def commit(self):
        pass

    def close(self):
        pass


def _model_endpoint_route(path, method):
    router = model_routes.setup_model_routes(model_discovery=None)
    for route in router.routes:
        if getattr(route, "path", "") == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"{method} {path} route not found")


def _fake_model_request(user=None):
    """Minimal FastAPI Request stand-in for route handlers that read request.state."""
    req = SimpleNamespace()
    req.state = SimpleNamespace(current_user=user)
    return req


@pytest.fixture
def cursor_route_env(monkeypatch, tmp_path):
    rows = []
    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", str(tmp_path))
    monkeypatch.setattr(model_routes, "ModelEndpoint", _RouteModelEndpoint)
    monkeypatch.setattr(model_routes, "SessionLocal", lambda: _RouteDb(rows))
    monkeypatch.setattr(model_routes, "require_admin", lambda request: None)
    monkeypatch.setattr(model_routes, "_load_settings", lambda: {})
    monkeypatch.setattr(model_routes, "_save_settings", lambda settings: None)
    _entries = [{"id": "composer-2.5", "displayName": "Composer 2.5"}]
    monkeypatch.setattr(model_routes, "list_cursor_model_entries", lambda api_key, timeout=5: list(_entries))
    monkeypatch.setattr(model_routes, "list_cursor_models", lambda api_key, timeout=5: ["composer-2.5"])
    return rows, str(tmp_path)


def test_create_cursor_endpoint_stores_provider_metadata(cursor_route_env):
    rows, workspace = cursor_route_env
    create = _model_endpoint_route("/api/model-endpoints", "POST")

    response = create(
        _fake_model_request(),
        name="cursor-endpoint",
        base_url="cursor://local",
        api_key="cur-key",
        skip_probe="false",
        require_models="false",
        provider="cursor",
        provider_config="",
        cursor_cwd=workspace,
        model_type="llm",
        supports_tools="",
        shared="true",
    )

    assert response["provider"] == "cursor"
    assert response["base_url"] == model_routes.CURSOR_LOCAL_URL
    assert response["supports_tools"] is False
    assert json.loads(response["provider_config"])["cwd"] == workspace
    assert rows[0].provider == "cursor"
    assert rows[0].base_url == model_routes.CURSOR_LOCAL_URL
    assert json.loads(rows[0].provider_config)["cwd"] == workspace


def test_list_model_endpoints_includes_cursor_metadata(cursor_route_env):
    rows, workspace = cursor_route_env
    rows.append(
        _RouteModelEndpoint(
            id="cur",
            name="cursor-endpoint",
            base_url=model_routes.CURSOR_LOCAL_URL,
            api_key="cur-key",
            is_enabled=True,
            model_type="llm",
            cached_models=json.dumps(["composer-2.5"]),
            supports_tools=False,
            provider="cursor",
            provider_config=json.dumps({"cwd": workspace}),
        )
    )
    list_endpoint = _model_endpoint_route("/api/model-endpoints", "GET")

    response = list_endpoint(SimpleNamespace())

    assert response[0]["provider"] == "cursor"
    assert json.loads(response[0]["provider_config"])["cwd"] == workspace


def test_create_cursor_endpoint_propagates_cursor_error(monkeypatch, cursor_route_env):
    _, workspace = cursor_route_env

    def fail(api_key, timeout=5):
        raise CursorAdapterError("bad key", status=401)

    monkeypatch.setattr(model_routes, "list_cursor_model_entries", fail)
    monkeypatch.setattr(model_routes, "list_cursor_models", fail)
    create = _model_endpoint_route("/api/model-endpoints", "POST")

    with pytest.raises(HTTPException) as excinfo:
        create(
            _fake_model_request(),
            name="cursor-endpoint-error",
            base_url="cursor://local",
            api_key="bad-key",
            skip_probe="false",
            require_models="false",
            provider="cursor",
            provider_config="",
            cursor_cwd=workspace,
            model_type="llm",
            supports_tools="",
            shared="true",
        )

    assert excinfo.value.status_code == 401
    assert "bad key" in excinfo.value.detail


def test_create_cursor_endpoint_rejects_non_llm_model_type(cursor_route_env):
    _, workspace = cursor_route_env
    create = _model_endpoint_route("/api/model-endpoints", "POST")

    with pytest.raises(HTTPException) as excinfo:
        create(
            _fake_model_request(),
            name="cursor-endpoint-image",
            base_url="cursor://local",
            api_key="cur-key",
            skip_probe="false",
            require_models="false",
            provider="cursor",
            provider_config="",
            cursor_cwd=workspace,
            model_type="image",
            supports_tools="",
            shared="true",
        )

    assert excinfo.value.status_code == 400
    assert "only support LLM" in excinfo.value.detail


def test_api_models_normalizes_cursor_cached_entries(monkeypatch, cursor_route_env):
    rows, workspace = cursor_route_env
    rows.append(
        _RouteModelEndpoint(
            id="cur",
            name="Cursor (local)",
            base_url=model_routes.CURSOR_LOCAL_URL,
            api_key="cur-key",
            is_enabled=True,
            model_type="llm",
            cached_models=json.dumps(
                [
                    {"id": "composer-2.5", "displayName": "Composer 2.5"},
                    {"id": "default", "displayName": "Auto"},
                ]
            ),
            provider="cursor",
            provider_config=json.dumps({"cwd": workspace}),
        )
    )
    monkeypatch.setattr(model_routes, "_auth_disabled", lambda: True)
    get_models = _model_endpoint_route("/api/models", "GET")

    result = get_models(_fake_model_request(user="admin"))

    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["models"] == ["composer-2.5", "default"]
    assert item["models_display"] == ["Composer 2.5", "Auto"]
    assert item["url"] == model_routes.CURSOR_LOCAL_URL


def test_ollama_endpoint_error_message_includes_troubleshooting():
    msg = model_routes._model_endpoint_error_message(
        "http://localhost:11434/v1",
        {"error": "Connection refused"},
    )

    assert "No Ollama models found" in msg
    assert "Connection refused" in msg
    assert "http://localhost:11434/v1" in msg
    assert "ollama list" in msg


def test_generic_endpoint_error_message_preserves_probe_error():
    msg = model_routes._model_endpoint_error_message(
        "https://api.example.com/v1",
        {"error": "HTTP 401"},
    )

    assert msg == "No models found for that provider/key. Last probe error: HTTP 401."
