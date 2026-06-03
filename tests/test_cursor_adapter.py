import json
import os

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

    assert cursor_adapter.list_cursor_models("cur-key") == ["composer-2.5"]
    assert seen["url"] == cursor_adapter.CURSOR_MODELS_URL
    assert seen["headers"]["Authorization"].startswith("Basic ")


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
