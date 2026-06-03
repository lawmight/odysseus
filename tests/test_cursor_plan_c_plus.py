"""Plan C+ tests: Cursor generateImage tool surfacing in Chat."""

import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.providers import cursor_adapter


def _parse_sse_data(chunk: str) -> dict:
    assert chunk.startswith("data: ")
    return json.loads(chunk[6:].strip())


def test_cursor_tool_call_running_emits_tool_start():
    event = SimpleNamespace(
        name="generateImage",
        status="running",
        args={"prompt": "a red circle"},
    )
    chunks = cursor_adapter.cursor_tool_call_chunks(event, workspace="/workspace", model="composer-2.5")
    assert len(chunks) == 1
    payload = _parse_sse_data(chunks[0])
    assert payload["type"] == "tool_start"
    assert payload["tool"] == "generate_image"
    assert "red circle" in payload["command"]


def test_cursor_tool_call_unknown_tool_is_ignored():
    event = SimpleNamespace(name="run_terminal_cmd", status="running", args={})
    assert cursor_adapter.cursor_tool_call_chunks(event, workspace="/workspace", model="m") == []


def test_extract_generate_image_path_from_nested_dict(tmp_path, monkeypatch):
    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", str(tmp_path))
    img = tmp_path / "out.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    result = {"output": {"filePath": str(img)}}
    assert cursor_adapter.extract_generate_image_path(result, str(tmp_path)) == str(img.resolve())


def test_cursor_tool_call_completed_publishes_image_url(tmp_path, monkeypatch):
    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", str(tmp_path))
    img = tmp_path / "gen.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    event = SimpleNamespace(
        name="generateImage",
        status="completed",
        args={"prompt": "blue square"},
        result={"path": str(img)},
    )
    chunks = cursor_adapter.cursor_tool_call_chunks(
        event, workspace=str(tmp_path), model="composer-2.5"
    )
    assert len(chunks) == 1
    payload = _parse_sse_data(chunks[0])
    assert payload["type"] == "tool_output"
    assert payload["tool"] == "generate_image"
    assert payload["image_url"].startswith("/api/generated-image/")
    assert "blue square" in payload["image_prompt"]
    filename = payload["image_url"].rsplit("/", 1)[-1]
    assert (Path("data/generated_images") / filename).is_file()


def test_cursor_tool_call_completed_accepts_base64(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", str(tmp_path))
    png = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")
    event = SimpleNamespace(
        name="generateImage",
        status="completed",
        args={"description": "test"},
        result={"b64_json": png},
    )
    chunks = cursor_adapter.cursor_tool_call_chunks(
        event, workspace=str(tmp_path), model="composer-2.5"
    )
    payload = _parse_sse_data(chunks[0])
    assert payload["exit_code"] == 0
    assert payload["image_url"].startswith("/api/generated-image/")


@pytest.mark.asyncio
async def test_stream_cursor_chat_forwards_tool_call_events(monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", str(tmp_path))
    monkeypatch.setattr(cursor_adapter, "CURSOR_SDK_AVAILABLE", True)
    monkeypatch.setattr(cursor_adapter, "validate_cursor_cwd", lambda cwd: str(tmp_path))

    img = tmp_path / "circle.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    class FakeRun:
        async def messages(self):
            yield SimpleNamespace(type="assistant", message=SimpleNamespace(content="done"))
            yield SimpleNamespace(
                type="tool_call",
                name="generateImage",
                status="running",
                args={"prompt": "circle"},
            )
            yield SimpleNamespace(
                type="tool_call",
                name="generateImage",
                status="completed",
                args={"prompt": "circle"},
                result={"path": str(img)},
            )

        async def cancel(self):
            return None

    class FakeAgent:
        agent_id = "agent-1"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def send(self, message, options=None):
            return FakeRun()

    class FakeAgents:
        async def create(self, **kwargs):
            return FakeAgent()

    class FakeClient:
        agents = FakeAgents()

    async def fake_bridge(_cwd):
        return FakeClient()

    monkeypatch.setattr(cursor_adapter, "_get_bridge_client", fake_bridge)

    chunks = [
        c
        async for c in cursor_adapter.stream_cursor_chat(
            "composer-2.5",
            [{"role": "user", "content": "draw a circle"}],
            api_key="cur-key",
            cwd=str(tmp_path),
        )
    ]
    joined = "".join(chunks)
    assert '"type": "tool_start"' in joined
    assert '"image_url": "/api/generated-image/' in joined


def test_chat_routes_blocks_cursor_in_agent_mode():
    """Regression: Agent + Cursor must stay Chat-only blocked."""
    import inspect

    import routes.chat_routes as chat_routes

    source = inspect.getsource(chat_routes.setup_chat_routes)
    assert "Cursor endpoints are for Chat only" in source
