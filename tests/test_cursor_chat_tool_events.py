"""Cursor Chat tool_events persistence."""

import ast
import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.providers import cursor_adapter
from routes.chat_helpers import tool_event_from_chat_tool_output

_CHAT_ROUTES = Path(__file__).resolve().parent.parent / "routes" / "chat_routes.py"


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


def test_extract_generate_image_path_from_cursor_value_envelope(tmp_path, monkeypatch):
    workspace = tmp_path / "repo"
    workspace.mkdir()
    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", str(workspace))
    assets = tmp_path / ".cursor" / "projects" / "workspace" / "assets"
    assets.mkdir(parents=True)
    img = assets / "logo.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    result = {"status": "success", "value": {"filePath": str(img)}}
    assert cursor_adapter.extract_generate_image_path(result, str(workspace)) == str(img.resolve())


def test_cursor_tool_call_completed_cursor_sdk_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", str(tmp_path))
    assets = tmp_path / ".cursor" / "projects" / "ws" / "assets"
    assets.mkdir(parents=True)
    img = assets / "gen.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    event = SimpleNamespace(
        name="generateImage",
        status="completed",
        args={"prompt": "cursor logo"},
        result={"status": "success", "value": {"filePath": str(img)}},
    )
    chunks = cursor_adapter.cursor_tool_call_chunks(
        event, workspace=str(tmp_path), model="composer-2.5"
    )
    payload = _parse_sse_data(chunks[0])
    assert payload["exit_code"] == 0
    assert payload["image_url"].startswith("/api/generated-image/")


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


@pytest.mark.asyncio
async def test_stream_heartbeat_does_not_cancel_slow_tool_completion(monkeypatch, tmp_path):
    import asyncio

    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", str(tmp_path))
    monkeypatch.setenv("CURSOR_STREAM_HEARTBEAT_SEC", "0.05")
    monkeypatch.setattr(cursor_adapter, "CURSOR_SDK_AVAILABLE", True)
    monkeypatch.setattr(cursor_adapter, "validate_cursor_cwd", lambda cwd: str(tmp_path))

    img = tmp_path / "delayed.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    class FakeRun:
        async def messages(self):
            yield SimpleNamespace(
                type="tool_call",
                name="generateImage",
                status="running",
                args={"prompt": "star"},
            )
            await asyncio.sleep(0.2)
            yield SimpleNamespace(
                type="tool_call",
                name="generateImage",
                status="completed",
                args={"prompt": "star"},
                result={"path": str(img)},
            )

        async def cancel(self):
            return None

    class FakeAgent:
        agent_id = "agent-delay"

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

    joined = "".join(
        [
            c
            async for c in cursor_adapter.stream_cursor_chat(
                "composer-2.5",
                [{"role": "user", "content": "star"}],
                api_key="cur-key",
                cwd=str(tmp_path),
            )
        ]
    )
    assert ": heartbeat" in joined
    assert '"image_url": "/api/generated-image/' in joined


def test_tool_event_from_chat_tool_output_matches_native_shape():
    data = {
        "type": "tool_output",
        "tool": "generate_image",
        "command": "a red circle",
        "output": "Generated image.",
        "exit_code": 0,
        "image_url": "/api/generated-image/abc.png",
        "image_id": "id-1",
        "image_prompt": "a red circle",
        "image_model": "composer-2.5",
    }
    ev = tool_event_from_chat_tool_output(data)
    assert ev is not None
    assert ev["round"] == 1
    assert ev["tool"] == "generate_image"
    assert ev["image_url"] == "/api/generated-image/abc.png"
    assert ev["image_id"] == "id-1"
    assert ev["exit_code"] == 0


def test_tool_event_from_chat_tool_output_ignores_non_output():
    assert tool_event_from_chat_tool_output({"type": "tool_start", "tool": "generate_image"}) is None


def test_chat_mode_accumulates_tool_output_with_helper():
    """Chat mode uses tool_event_from_chat_tool_output for reload metadata."""
    source = _CHAT_ROUTES.read_text(encoding="utf-8")
    assert "tool_event_from_chat_tool_output" in source
    assert "_cursor_tool_events" in source
    idx = source.find('elif data.get("type") in ("tool_start", "tool_output")')
    assert idx != -1
    snippet = source[idx : idx + 800]
    assert "tool_event_from_chat_tool_output" in snippet


def test_chat_mode_save_passes_tool_events_to_save_assistant_response():
    """Regression: Cursor Chat stream must persist tool_events for reload bubbles."""
    source = _CHAT_ROUTES.read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "save_assistant_response":
            kw = {k.arg for k in node.keywords if k.arg}
            if "tool_events" in kw:
                found = True
                break
    assert found, "save_assistant_response must accept tool_events= in chat_routes.py"
