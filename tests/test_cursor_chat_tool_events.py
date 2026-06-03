"""Cursor Chat: tool_events persistence for Plan C+ polish."""

import ast
from pathlib import Path

from routes.chat_helpers import tool_event_from_chat_tool_output

_CHAT_ROUTES = Path(__file__).resolve().parent.parent / "routes" / "chat_routes.py"


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
