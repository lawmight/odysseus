import json

import pytest

from src import llm_core
from src.providers import cursor_adapter


def test_cursor_model_list_accepts_stringified_headers(monkeypatch):
    seen = {}

    def fake_list_cursor_models(api_key, timeout=0):
        seen["api_key"] = api_key
        seen["timeout"] = timeout
        return ["composer-2.5"]

    monkeypatch.setattr(cursor_adapter, "list_cursor_models", fake_list_cursor_models)

    models = llm_core.list_model_ids(
        "cursor://local",
        timeout=7,
        headers=json.dumps({"Authorization": "Bearer cur-key"}),
    )

    assert models == ["composer-2.5"]
    assert seen == {"api_key": "cur-key", "timeout": 7}


@pytest.mark.asyncio
async def test_cursor_stream_accepts_stringified_headers(monkeypatch):
    seen = {}

    async def fake_stream_cursor_chat(model, messages, api_key, cwd=None, **kwargs):
        seen["model"] = model
        seen["messages"] = messages
        seen["api_key"] = api_key
        seen["cwd"] = cwd
        seen["kwargs"] = kwargs
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(cursor_adapter, "stream_cursor_chat", fake_stream_cursor_chat)

    chunks = [
        chunk
        async for chunk in llm_core.stream_llm(
            "cursor://local",
            "composer-2.5",
            [{"role": "user", "content": "Hello"}],
            headers=json.dumps({
                "Authorization": "Bearer cur-key",
                "X-Odysseus-Cursor-Cwd": "/workspace",
            }),
        )
    ]

    assert chunks == ["data: [DONE]\n\n"]
    assert seen["api_key"] == "cur-key"
    assert seen["cwd"] == "/workspace"
