import json
import os
from types import SimpleNamespace

import httpx
import pytest

from src.providers import cursor_adapter


def test_list_cursor_models_parses_items(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            json={"items": [{"id": "composer-2.5", "displayName": "Composer"}]},
        )

    monkeypatch.setattr(cursor_adapter.httpx, "get", fake_get)

    assert cursor_adapter.list_cursor_model_entries("cur-key") == [
        {"id": "composer-2.5", "displayName": "Composer"},
    ]
    assert cursor_adapter.list_cursor_models("cur-key") == ["composer-2.5"]
    assert seen["url"] == cursor_adapter.CURSOR_MODELS_URL
    assert seen["headers"]["Authorization"].startswith("Basic ")


def test_normalize_cached_cursor_models_legacy_strings():
    assert cursor_adapter.normalize_cached_cursor_models(["composer-2.5"]) == [
        {"id": "composer-2.5", "displayName": "composer-2.5"},
    ]


@pytest.mark.parametrize("api_key", [None, ""])
def test_list_cursor_models_requires_api_key(api_key):
    with pytest.raises(cursor_adapter.CursorAdapterError) as excinfo:
        cursor_adapter.list_cursor_models(api_key)

    assert excinfo.value.status == 401
    assert "API key required" in str(excinfo.value)


@pytest.mark.parametrize("status_code", [401, 403])
def test_list_cursor_models_rejected_api_key(monkeypatch, status_code):
    def fake_get(url, headers=None, timeout=None):
        request = httpx.Request("GET", url)
        response = httpx.Response(status_code, request=request)
        raise httpx.HTTPStatusError("auth error", request=request, response=response)

    monkeypatch.setattr(cursor_adapter.httpx, "get", fake_get)

    with pytest.raises(cursor_adapter.CursorAdapterError) as excinfo:
        cursor_adapter.list_cursor_models("cur-key")

    assert excinfo.value.status == status_code
    assert "Cursor rejected the API key" in str(excinfo.value)


def test_list_cursor_models_other_http_error(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        request = httpx.Request("GET", url)
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("server error", request=request, response=response)

    monkeypatch.setattr(cursor_adapter.httpx, "get", fake_get)

    with pytest.raises(cursor_adapter.CursorAdapterError) as excinfo:
        cursor_adapter.list_cursor_models("cur-key")

    assert excinfo.value.status == 500
    assert "HTTP 500" in str(excinfo.value)


def test_list_cursor_models_request_error(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        request = httpx.Request("GET", url)
        raise httpx.RequestError("connection failed", request=request)

    monkeypatch.setattr(cursor_adapter.httpx, "get", fake_get)

    with pytest.raises(cursor_adapter.CursorAdapterError) as excinfo:
        cursor_adapter.list_cursor_models("cur-key")

    assert excinfo.value.status == 503
    assert "Could not reach" in str(excinfo.value)


def test_validate_cursor_cwd_allows_filesystem_root(monkeypatch):
    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", "/")
    cwd = os.getcwd()

    assert cursor_adapter.validate_cursor_cwd(cwd) == cwd


def test_iter_content_blocks_expands_tuple_content():
    class Block:
        type = "text"
        text = "hello"

    class Payload:
        content = (Block(),)

    class Event:
        message = Payload()

    blocks = list(cursor_adapter._iter_content_blocks(Event()))
    assert len(blocks) == 1
    assert cursor_adapter._get_attr(blocks[0], "text") == "hello"


def test_build_cursor_prompt_merges_history():
    prompt = cursor_adapter.build_cursor_prompt(
        [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "What did I say?"},
        ]
    )

    assert "System instructions:\nBe concise." in prompt
    assert "User:\nHello" in prompt
    assert "Assistant:\nHi" in prompt
    assert prompt.endswith("User:\nWhat did I say?")


def test_build_cursor_user_message_resume_uses_last_turn_only():
    messages = [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Second question"},
    ]
    payload, _ = cursor_adapter.build_cursor_user_message(messages, resume=True)
    if cursor_adapter.UserMessage is not None:
        assert isinstance(payload, cursor_adapter.UserMessage)
        assert "Second question" in payload.text
        assert "Hello" not in payload.text or "Conversation" not in payload.text
    else:
        assert "Second question" in payload


def test_cursor_headers_include_workspace_config():
    headers = cursor_adapter.cursor_headers("cur-key", json.dumps({"cwd": "/workspace"}))

    assert headers["Authorization"] == "Bearer cur-key"
    assert headers["X-Odysseus-Cursor-Cwd"] == "/workspace"


@pytest.mark.asyncio
async def test_stream_cursor_chat_reports_missing_sdk(monkeypatch):
    monkeypatch.setattr(cursor_adapter, "CURSOR_SDK_AVAILABLE", False)
    monkeypatch.setattr(cursor_adapter, "validate_cursor_cwd", lambda cwd: cwd or "/workspace")
    chunks = [
        chunk
        async for chunk in cursor_adapter.stream_cursor_chat(
            "composer-2.5",
            [{"role": "user", "content": "Hello"}],
            api_key="cur-key",
            cwd="/workspace",
        )
    ]

    assert len(chunks) == 1
    assert chunks[0].startswith("event: error")
    assert "requirements-cursor.txt" in chunks[0]


@pytest.mark.asyncio
async def test_stream_cursor_chat_resume_path(monkeypatch):
    monkeypatch.setattr(cursor_adapter, "CURSOR_SDK_AVAILABLE", True)
    monkeypatch.setattr(cursor_adapter, "validate_cursor_cwd", lambda cwd: cwd or "/workspace")

    class FakeRun:
        async def messages(self):
            yield SimpleNamespace(type="assistant", message=SimpleNamespace(content="pong"))

        async def cancel(self):
            return None

    class FakeAgent:
        agent_id = "agent-existing"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def send(self, message, options=None):
            assert options is not None
            assert options.get("model") == "composer-2.5"
            return FakeRun()

    agents_resource = SimpleNamespace(resume_called=False)

    class FakeAgents:
        async def resume(self, agent_id, options):
            agents_resource.resume_called = True
            assert agent_id == "agent-existing"
            return FakeAgent()

        async def create(self, **kwargs):
            raise AssertionError("create should not run when cursor_agent_id is set")

    class FakeClient:
        agents = FakeAgents()

    async def fake_bridge(_cwd):
        return FakeClient()

    monkeypatch.setattr(cursor_adapter, "_get_bridge_client", fake_bridge)

    chunks = [
        c
        async for c in cursor_adapter.stream_cursor_chat(
            "composer-2.5",
            [{"role": "user", "content": "Reply pong"}],
            api_key="cur-key",
            cwd="/workspace",
            cursor_agent_id="agent-existing",
            odysseus_session_id="sess-1",
        )
    ]
    assert any("pong" in c for c in chunks)
    assert agents_resource.resume_called


@pytest.mark.asyncio
async def test_cancel_cursor_run_invokes_sdk_cancel():
    class FakeRun:
        def __init__(self):
            self.cancelled = False

        async def cancel(self):
            self.cancelled = True

    run = FakeRun()
    await cursor_adapter.register_cursor_run("sess-cancel", run)
    assert await cursor_adapter.cancel_cursor_run("sess-cancel") is True
    assert run.cancelled is True


@pytest.mark.asyncio
async def test_close_cursor_bridges_exits_cached_contexts():
    closed = []

    class FakeContext:
        async def __aexit__(self, exc_type, exc, tb):
            closed.append(True)

    cursor_adapter._bridge_clients.clear()
    cursor_adapter._bridge_clients["/workspace"] = {"ctx": FakeContext(), "client": object()}

    await cursor_adapter.close_cursor_bridges()

    assert closed == [True]
    assert not cursor_adapter._bridge_clients


def test_resolve_endpoint_utility_skips_cursor(monkeypatch):
    import importlib
    import src.endpoint_resolver as er
    import src.settings as settings_mod

    importlib.reload(settings_mod)
    settings = {"utility_endpoint_id": "cur-ep", "utility_model": "composer-2.5"}
    monkeypatch.setattr(settings_mod, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(
        settings_mod,
        "get_user_setting",
        lambda key, owner, default=None: settings.get(key, default if default is not None else ""),
    )

    class FakeEp:
        id = "cur-ep"
        base_url = "cursor://local"
        api_key = "key"
        is_enabled = True
        provider = "cursor"
        provider_config = None
        cached_models = json.dumps([{"id": "composer-2.5", "displayName": "Composer"}])

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return FakeEp()

    class FakeDb:
        def query(self, model):
            return FakeQuery()

        def close(self):
            pass

    monkeypatch.setattr(er, "SessionLocal", lambda: FakeDb())

    url, model, headers = er.resolve_endpoint(
        "utility",
        fallback_url="http://fallback/v1",
        fallback_model="fb-model",
        fallback_headers={"X": "1"},
    )
    assert url == "http://fallback/v1"
    assert model == "fb-model"
    assert headers == {"X": "1"}


def test_resolve_task_rejects_cursor_session_fallback(monkeypatch):
    import importlib
    import src.endpoint_resolver as er
    import src.settings as settings_mod

    importlib.reload(settings_mod)
    settings = {}
    monkeypatch.setattr(settings_mod, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(
        settings_mod,
        "get_user_setting",
        lambda key, owner, default=None: settings.get(key, default if default is not None else ""),
    )

    url, model, headers = er.resolve_endpoint(
        "task",
        fallback_url="cursor://local",
        fallback_model="composer-2.5",
        fallback_headers={"Authorization": "Bearer key"},
    )
    assert url is None
    assert model is None
    assert headers is None
