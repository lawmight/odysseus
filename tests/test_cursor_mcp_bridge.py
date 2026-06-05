"""Optional Odysseus MCP DB to Cursor SDK bridge."""

import json
from types import SimpleNamespace

import pytest

from src.providers import cursor_agent, cursor_mcp


def test_cursor_mcp_setting_defaults_disabled():
    assert cursor_mcp._truthy(False) is False
    assert cursor_mcp._truthy("true") is True


def test_serialize_stdio_mcp_server():
    key, cfg = cursor_mcp.serialize_cursor_mcp_server(
        SimpleNamespace(
            id="srv1",
            name="Local Files",
            is_enabled=True,
            transport="stdio",
            command="npx",
            args=json.dumps(["-y", "@modelcontextprotocol/server-filesystem", "."]),
            env=json.dumps({"TOKEN": "secret"}),
            disabled_tools=None,
        )
    )

    assert key == "Local_Files"
    assert cfg == {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "env": {"TOKEN": "secret"},
    }


def test_serialize_sse_mcp_server():
    key, cfg = cursor_mcp.serialize_cursor_mcp_server(
        SimpleNamespace(
            id="srv2",
            name="docs",
            is_enabled=True,
            transport="sse",
            url="https://example.test/sse",
            disabled_tools=None,
        )
    )

    assert key == "docs"
    assert cfg == {"type": "sse", "url": "https://example.test/sse"}


def test_serialize_skips_per_tool_disabled_server():
    assert cursor_mcp.serialize_cursor_mcp_server(
        SimpleNamespace(
            id="srv3",
            name="hidden",
            is_enabled=True,
            transport="stdio",
            command="cmd",
            args="[]",
            env="{}",
            disabled_tools=json.dumps(["dangerous_tool"]),
        )
    ) is None


def test_load_cursor_agent_mcp_servers_dedupes_names(monkeypatch):
    servers = [
        SimpleNamespace(
            id="a",
            name="same",
            is_enabled=True,
            transport="sse",
            url="https://one.test/sse",
            disabled_tools=None,
        ),
        SimpleNamespace(
            id="b",
            name="same",
            is_enabled=True,
            transport="sse",
            url="https://two.test/sse",
            disabled_tools=None,
        ),
    ]

    class _Query:
        def all(self):
            return servers

    class _Db:
        def query(self, _model):
            return _Query()

        def close(self):
            pass

    import core.database as database

    monkeypatch.setattr(database, "SessionLocal", lambda: _Db())

    assert cursor_mcp.load_cursor_agent_mcp_servers() == {
        "same": {"type": "sse", "url": "https://one.test/sse"},
        "same_2": {"type": "sse", "url": "https://two.test/sse"},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("mcp_servers,expected_present", [({"docs": {"type": "sse", "url": "u"}}, True), (None, False)])
async def test_stream_cursor_agent_loop_passes_mcp_send_options(monkeypatch, tmp_path, mcp_servers, expected_present):
    monkeypatch.setattr(cursor_agent, "CURSOR_SDK_AVAILABLE", True)
    monkeypatch.setattr(cursor_agent._ca, "validate_cursor_cwd", lambda cwd: str(tmp_path))
    monkeypatch.setattr(cursor_agent._ca, "LocalAgentOptions", lambda cwd: {"cwd": cwd})

    captured = {}

    class _Run:
        async def messages(self):
            yield SimpleNamespace(type="assistant", message=SimpleNamespace(content="done"))

        async def cancel(self):
            pass

    class _Agent:
        agent_id = "agent-mcp"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def send(self, _payload, options):
            captured["options"] = dict(options)
            return _Run()

    class _Agents:
        async def create(self, **_kwargs):
            return _Agent()

    class _Client:
        agents = _Agents()

    async def _bridge(_workspace):
        return _Client()

    monkeypatch.setattr(cursor_agent._ca, "_get_bridge_client", _bridge)

    chunks = [
        chunk
        async for chunk in cursor_agent.stream_cursor_agent_loop(
            "cursor://local",
            "composer-2.5",
            [{"role": "user", "content": "hello"}],
            api_key="cur-key",
            cwd=str(tmp_path),
            mcp_servers=mcp_servers,
        )
    ]

    assert any("done" in chunk for chunk in chunks)
    assert captured["options"]["mode"] == "agent"
    assert ("mcp_servers" in captured["options"]) is expected_present
    if expected_present:
        assert captured["options"]["mcp_servers"] == mcp_servers


def test_chat_routes_wires_cursor_mcp_bridge():
    source = __import__("inspect").getsource(__import__("routes.chat_routes").chat_routes.setup_chat_routes)
    assert "cursor_agent_mcp_from_db_enabled" in source
    assert "load_cursor_agent_mcp_servers" in source
    assert "mcp_servers=_cursor_mcp_servers" in source
