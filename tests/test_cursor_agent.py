import json
from pathlib import Path

from src.providers.cursor_agent import cursor_agent_tool_call_chunks


class _ToolEvent:
    def __init__(self, name, status, args=None, result=None):
        self.name = name
        self.status = status
        self.args = args
        self.result = result


def test_cursor_agent_tool_call_running_emits_tool_start():
    chunks = cursor_agent_tool_call_chunks(
        _ToolEvent("read_file", "running", {"path": "app.py"})
    )
    assert len(chunks) == 1
    payload = json.loads(chunks[0].removeprefix("data: ").strip())
    assert payload["type"] == "tool_start"
    assert payload["tool"] == "read_file"
    assert payload["command"]


def test_cursor_agent_tool_call_completed_emits_tool_output():
    chunks = cursor_agent_tool_call_chunks(
        _ToolEvent("run_terminal_cmd", "completed", {"command": "ls"}, result={"exit": 0})
    )
    assert len(chunks) == 1
    payload = json.loads(chunks[0].removeprefix("data: ").strip())
    assert payload["type"] == "tool_output"
    assert payload["tool"] == "run_terminal_cmd"
    assert payload["exit_code"] == 0


def test_cursor_agent_tool_call_failed_emits_tool_output():
    chunks = cursor_agent_tool_call_chunks(
        _ToolEvent("read_file", "failed", {"path": "x"}, result={"error": "not found"})
    )
    assert len(chunks) == 1
    payload = json.loads(chunks[0].removeprefix("data: ").strip())
    assert payload["type"] == "tool_output"
    assert payload["exit_code"] == 1
    assert "not found" in payload["output"]


def test_cursor_agent_generate_image_without_workspace_is_generic():
    """No workspace -> generic tool card (no gallery), still a valid tool_output."""
    chunks = cursor_agent_tool_call_chunks(
        _ToolEvent("generateImage", "completed", {"prompt": "a cat"}, result={"status": "ok"})
    )
    assert len(chunks) == 1
    payload = json.loads(chunks[0].removeprefix("data: ").strip())
    assert payload["type"] == "tool_output"
    assert payload["tool"] == "generateImage"
    assert "image_url" not in payload


def test_cursor_agent_generate_image_publishes_gallery_url(tmp_path, monkeypatch):
    """With a workspace, generateImage is delegated to the shared gallery path (B2a)."""
    monkeypatch.setenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", str(tmp_path))
    img = tmp_path / "gen.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    chunks = cursor_agent_tool_call_chunks(
        _ToolEvent("generateImage", "completed", {"prompt": "blue square"}, result={"path": str(img)}),
        workspace=str(tmp_path),
        model="composer-2.5",
    )
    assert len(chunks) == 1
    payload = json.loads(chunks[0].removeprefix("data: ").strip())
    assert payload["type"] == "tool_output"
    assert payload["tool"] == "generate_image"
    assert payload["image_url"].startswith("/api/generated-image/")
    filename = payload["image_url"].rsplit("/", 1)[-1]
    assert (Path("data/generated_images") / filename).is_file()


def test_heartbeat_interval_sec_invalid_env(monkeypatch):
    from src.providers import cursor_agent as ca

    monkeypatch.setenv("CURSOR_STREAM_HEARTBEAT_SEC", "not-a-number")
    assert ca._heartbeat_interval_sec() == 15.0


def test_heartbeat_interval_sec_non_positive_env(monkeypatch):
    from src.providers import cursor_agent as ca

    monkeypatch.setenv("CURSOR_STREAM_HEARTBEAT_SEC", "0")
    assert ca._heartbeat_interval_sec() == 15.0
    monkeypatch.setenv("CURSOR_STREAM_HEARTBEAT_SEC", "-1")
    assert ca._heartbeat_interval_sec() == 15.0
