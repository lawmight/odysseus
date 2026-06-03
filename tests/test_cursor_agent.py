import json

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
