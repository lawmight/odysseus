"""Optional Odysseus MCP DB bridge for Cursor Agent mode.

The default Cursor Agent path relies on Cursor's own workspace/user MCP
configuration (for example ``.cursor/mcp.json``). This module is deliberately
opt-in: serializing Odysseus MCP rows into Cursor SDK ``mcp_servers`` hands
server commands, URLs, and stdio environment values to the Cursor bridge.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, Optional, Tuple

logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def cursor_agent_mcp_from_db_enabled() -> bool:
    """Return whether Cursor Agent should receive Odysseus MCP DB configs."""
    try:
        from src.settings import get_setting

        return _truthy(get_setting("cursor_agent_mcp_from_db", False))
    except Exception:
        logger.debug("Could not read cursor_agent_mcp_from_db setting", exc_info=True)
        return False


def _json_list(raw: Any) -> Optional[list]:
    if raw in (None, ""):
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def _json_dict(raw: Any) -> Optional[dict]:
    if raw in (None, ""):
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _mcp_key(server: Any) -> str:
    raw = str(getattr(server, "name", "") or getattr(server, "id", "") or "mcp").strip()
    key = _SAFE_NAME_RE.sub("_", raw).strip("._-")
    return key or "mcp"


def _server_label(server: Any) -> str:
    return str(getattr(server, "id", "") or getattr(server, "name", "") or "unknown")


def serialize_cursor_mcp_server(server: Any) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Convert one enabled Odysseus ``McpServer`` row into a Cursor SDK config.

    Returns ``None`` when the server cannot be represented safely. In
    particular, rows with per-tool disabled lists are skipped because the Cursor
    SDK inline config cannot carry Odysseus' per-tool hiding policy.
    """
    if getattr(server, "is_enabled", True) is False:
        return None

    disabled_tools = _json_list(getattr(server, "disabled_tools", None))
    if disabled_tools is None:
        logger.warning("Skipping MCP server %s: invalid disabled_tools JSON", _server_label(server))
        return None
    if disabled_tools:
        logger.info(
            "Skipping MCP server %s for Cursor Agent: per-tool disabled policy cannot be represented",
            _server_label(server),
        )
        return None

    transport = str(getattr(server, "transport", "") or "").strip().lower()
    if transport == "stdio":
        command = str(getattr(server, "command", "") or "").strip()
        if not command:
            logger.warning("Skipping MCP server %s: stdio command is missing", _server_label(server))
            return None
        args = _json_list(getattr(server, "args", None))
        env = _json_dict(getattr(server, "env", None))
        if args is None:
            logger.warning("Skipping MCP server %s: invalid args JSON", _server_label(server))
            return None
        if env is None:
            logger.warning("Skipping MCP server %s: invalid env JSON", _server_label(server))
            return None
        config: Dict[str, Any] = {
            "type": "stdio",
            "command": command,
        }
        if args:
            config["args"] = [str(arg) for arg in args]
        if env:
            # Values may be secrets; never log this mapping.
            config["env"] = {str(k): str(v) for k, v in env.items() if v is not None}
        return _mcp_key(server), config

    if transport in {"sse", "http"}:
        url = str(getattr(server, "url", "") or "").strip()
        if not url:
            logger.warning("Skipping MCP server %s: %s URL is missing", _server_label(server), transport)
            return None
        return _mcp_key(server), {"type": transport, "url": url}

    logger.warning("Skipping MCP server %s: unsupported transport %r", _server_label(server), transport)
    return None


def _dedupe_key(key: str, existing: Iterable[str]) -> str:
    if key not in existing:
        return key
    idx = 2
    while f"{key}_{idx}" in existing:
        idx += 1
    return f"{key}_{idx}"


def load_cursor_agent_mcp_servers() -> Dict[str, Dict[str, Any]]:
    """Load enabled MCP DB rows as Cursor SDK ``mcp_servers`` configs."""
    from core.database import McpServer, SessionLocal

    db = SessionLocal()
    try:
        servers = db.query(McpServer).all()
        configs: Dict[str, Dict[str, Any]] = {}
        for server in servers:
            item = serialize_cursor_mcp_server(server)
            if not item:
                continue
            key, config = item
            configs[_dedupe_key(key, configs.keys())] = config
        return configs
    finally:
        db.close()
