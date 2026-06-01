import json

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
