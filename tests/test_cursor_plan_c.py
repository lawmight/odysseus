"""Plan C acceptance tests for Cursor Chat BYOK polish."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.providers import cursor_adapter


def test_list_cursor_model_entries_parses_display_names(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        import httpx

        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "items": [
                    {"id": "composer-2.5", "displayName": "Composer 2.5"},
                    {"id": "claude-4.6-sonnet", "displayName": "Claude Sonnet"},
                ]
            },
        )

    monkeypatch.setattr(cursor_adapter.httpx, "get", fake_get)
    entries = cursor_adapter.list_cursor_model_entries("cur-key")
    assert entries == [
        {"id": "composer-2.5", "displayName": "Composer 2.5"},
        {"id": "claude-4.6-sonnet", "displayName": "Claude Sonnet"},
    ]
    assert cursor_adapter.list_cursor_models("cur-key") == [
        "composer-2.5",
        "claude-4.6-sonnet",
    ]


def test_normalize_cached_cursor_models_legacy_strings():
    assert cursor_adapter.normalize_cached_cursor_models(["composer-2.5"]) == [
        {"id": "composer-2.5", "displayName": "composer-2.5"},
    ]


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


@pytest.mark.asyncio
async def test_stream_cursor_chat_resume_path(monkeypatch):
    monkeypatch.setattr(cursor_adapter, "CURSOR_SDK_AVAILABLE", True)
    monkeypatch.setattr(cursor_adapter, "validate_cursor_cwd", lambda cwd: cwd or "/workspace")

    class FakeRun:
        def __init__(self):
            self.cancelled = False

        async def messages(self):
            yield SimpleNamespace(type="assistant", message=SimpleNamespace(content="pong"))

        async def cancel(self):
            self.cancelled = True

    class FakeAgent:
        agent_id = "agent-existing"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def send(self, message):
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


def test_resolve_endpoint_utility_skips_cursor(monkeypatch):
    """Cursor must not be used for utility/task/research/vision resolvers."""
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
