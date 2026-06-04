"""Plan B: Cursor SDK engine for Odysseus Agent mode."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from src.providers import cursor_adapter as _ca
from src.providers.cursor_adapter import (
    CURSOR_SDK_AVAILABLE,
    CURSOR_SDK_MISSING,
    CursorAdapterError,
    cancel_cursor_run,
    extract_cursor_api_key,
    is_cursor_url,
)

logger = logging.getLogger(__name__)

__all__ = [
    "stream_cursor_agent_loop",
    "cursor_agent_tool_call_chunks",
    "cancel_cursor_run",
]

_FAILURE_STATUSES = frozenset({"failed", "error", "cancelled", "canceled"})


def _heartbeat_interval_sec() -> float:
    try:
        value = float(os.getenv("CURSOR_STREAM_HEARTBEAT_SEC", "15") or "15")
        return value if value > 0 else 15.0
    except ValueError:
        return 15.0


def _format_tool_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        text = result.strip()
        return text[:4000] if text else ""
    try:
        return json.dumps(result, default=str)[:4000]
    except (TypeError, ValueError):
        return str(result)[:4000]


def _exit_code_from_result(result: Any, *, default: int = 0) -> int:
    if isinstance(result, dict):
        for key in ("exit_code", "exit", "code"):
            val = result.get(key)
            if isinstance(val, bool):
                continue
            if isinstance(val, int):
                return val
            if isinstance(val, str) and val.lstrip("-").isdigit():
                return int(val)
    return default


def cursor_agent_tool_call_chunks(
    event: Any,
    *,
    workspace: str | None = None,
    model: str = "",
    session_id: Optional[str] = None,
    owner: Optional[str] = None,
) -> List[str]:
    """Map SDK tool_call events to Agent tab tool_start / tool_output SSE.

    When the workspace is known, ``generateImage`` is delegated to the shared
    Chat mapper so the Agent thread gets a gallery image_url (Plan B backlog
    B2a / decision D1), matching Chat behavior. All other tools map to generic
    tool_start / tool_output cards.
    """
    name = str(_ca._get_attr(event, "name", "") or "")
    if not name:
        return []

    if name == "generateImage" and workspace:
        return _ca.cursor_tool_call_chunks(
            event,
            workspace=workspace,
            model=model,
            session_id=session_id,
            owner=owner,
        )

    status = str(_ca._get_attr(event, "status", "") or "").lower()
    args = _ca._get_attr(event, "args")
    command = _ca._tool_command_summary(name, args)
    chunks: List[str] = []

    if status == "running":
        chunks.append(
            _ca._sse_data({
                "type": "tool_start",
                "tool": name,
                "command": command,
            })
        )
        return chunks

    if status in ("completed", "complete"):
        result = _ca._get_attr(event, "result")
        output = _format_tool_result(result) or f"{name} completed."
        chunks.append(
            _ca._sse_data({
                "type": "tool_output",
                "tool": name,
                "command": command,
                "output": output,
                "exit_code": _exit_code_from_result(result, default=0),
            })
        )
        return chunks

    if status in _FAILURE_STATUSES:
        result = _ca._get_attr(event, "result")
        output = _format_tool_result(result) or f"{name} failed ({status})."
        chunks.append(
            _ca._sse_data({
                "type": "tool_output",
                "tool": name,
                "command": command,
                "output": output,
                "exit_code": _exit_code_from_result(result, default=1),
            })
        )
        return chunks

    return chunks


def _sse_error_from_exception(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    lower = message.lower()
    status = 401 if "unauthorized" in lower or "api key" in lower else 502
    if "429" in lower or "rate limit" in lower:
        status = 429
        message = "Cursor rate limit reached. Wait a moment and try again."
    if ("bridge" in lower or "cursor" in lower) and "not found" in lower:
        message = f"{message}. Ensure the Cursor SDK bridge can run on the Odysseus host."
    return f"event: error\ndata: {json.dumps({'status': status, 'text': message, 'error': message})}\n\n"


async def stream_cursor_agent_loop(
    endpoint_url: str,
    model: str,
    messages: List[Dict[str, Any]],
    *,
    api_key: str = "",
    cwd: str | None = None,
    session_id: str | None = None,
    temperature: float = 0.3,
    max_tool_calls: int = 0,
    owner: str | None = None,
    cursor_agent_id: str | None = None,
    headers: Optional[Dict[str, str]] = None,
) -> AsyncGenerator[str, None]:
    """Stream Cursor agent run as Odysseus Agent-mode SSE (tools + text).

    temperature is accepted for call-site parity with stream_agent_loop but is
    not passed to the Cursor SDK in v1. owner is used only to attribute
    generateImage gallery saves.
    """
    del temperature
    if not is_cursor_url(endpoint_url):
        yield (
            "event: error\ndata: "
            + json.dumps({
                "status": 400,
                "text": "Not a Cursor endpoint",
                "error": "Not a Cursor endpoint",
            })
            + "\n\n"
        )
        return
    if not CURSOR_SDK_AVAILABLE:
        yield (
            "event: error\ndata: "
            + json.dumps({
                "status": 503,
                "text": CURSOR_SDK_MISSING,
                "error": CURSOR_SDK_MISSING,
            })
            + "\n\n"
        )
        return

    start = time.time()
    run = None
    tool_calls_used = 0
    try:
        key = (api_key or "").strip() or extract_cursor_api_key(headers)
        if not key:
            raise CursorAdapterError("Cursor API key required.", status=401)
        workspace = _ca.validate_cursor_cwd(cwd)
        client = await _ca._get_bridge_client(workspace)
        resume = bool((cursor_agent_id or "").strip())
        payload, _ = _ca.build_cursor_user_message(messages, resume=resume)
        local_opts = _ca.LocalAgentOptions(cwd=workspace)  # type: ignore[misc]
        resume_opts = {"apiKey": key, "local": {"cwd": workspace}}
        send_opts: Dict[str, Any] = {"model": model, "mode": "agent"}

        if resume:
            agent = await client.agents.resume(cursor_agent_id.strip(), resume_opts)
        else:
            agent = await client.agents.create(
                model=model,
                api_key=key,
                local=local_opts,
            )
        async with agent:
            if not resume and getattr(agent, "agent_id", None):
                yield _ca.cursor_agent_id_event(str(agent.agent_id))
            run = await agent.send(payload, send_opts)
            if session_id:
                await _ca.register_cursor_run(session_id, run)
            _msg_iter = run.messages().__aiter__()
            _heartbeat_s = _heartbeat_interval_sec()
            _pending_msg: asyncio.Task[Any] = asyncio.create_task(_msg_iter.__anext__())
            try:
                while True:
                    _done, _ = await asyncio.wait({_pending_msg}, timeout=_heartbeat_s)
                    if not _done:
                        yield ": heartbeat\n\n"
                        continue
                    try:
                        event = _pending_msg.result()
                    except StopAsyncIteration:
                        break
                    _pending_msg = asyncio.create_task(_msg_iter.__anext__())
                    async with _ca._active_cursor_runs_lock:
                        entry = _ca._active_cursor_runs.get(session_id or "")
                        if entry and entry.get("cancelled"):
                            break
                    event_type = str(_ca._get_attr(event, "type", "") or "")
                    if event_type == "assistant":
                        for block in _ca._iter_content_blocks(event):
                            if isinstance(block, str):
                                text = block
                            else:
                                block_type = str(_ca._get_attr(block, "type", "text") or "text")
                                if block_type != "text":
                                    continue
                                text = str(_ca._get_attr(block, "text", "") or "")
                            if text:
                                yield f"data: {json.dumps({'delta': text})}\n\n"
                    elif event_type == "thinking":
                        text = str(
                            _ca._get_attr(event, "text", "")
                            or _ca._get_attr(event, "content", "")
                            or ""
                        )
                        if text:
                            yield f"data: {json.dumps({'delta': text, 'thinking': True})}\n\n"
                    elif event_type == "tool_call":
                        status = str(_ca._get_attr(event, "status", "") or "").lower()
                        if (
                            status == "running"
                            and max_tool_calls > 0
                            and tool_calls_used >= max_tool_calls
                        ):
                            yield _ca._sse_data({
                                "type": "budget_exceeded",
                                "limit": max_tool_calls,
                                "used": tool_calls_used,
                            })
                            break
                        for chunk in cursor_agent_tool_call_chunks(
                            event,
                            workspace=workspace,
                            model=model,
                            session_id=session_id,
                            owner=owner,
                        ):
                            yield chunk
                        if status == "running":
                            tool_calls_used += 1
                    elif event_type == "error":
                        text = str(
                            _ca._get_attr(event, "message", "")
                            or _ca._get_attr(event, "error", "")
                            or "Cursor run failed"
                        )
                        raise CursorAdapterError(text, status=502)
            finally:
                if not _pending_msg.done():
                    _pending_msg.cancel()
                    try:
                        await _pending_msg
                    except (asyncio.CancelledError, StopAsyncIteration):
                        pass
        elapsed = max(time.time() - start, 0.0)
        yield f"data: {json.dumps({'type': 'usage', 'data': {'total_time': round(elapsed, 3)}})}\n\n"
        yield "data: [DONE]\n\n"
    except CursorAdapterError as exc:
        yield f"event: error\ndata: {json.dumps({'status': exc.status, 'text': str(exc), 'error': str(exc)})}\n\n"
    except Exception as exc:
        logger.exception("Unexpected Cursor agent stream failure")
        yield _sse_error_from_exception(exc)
    finally:
        if session_id:
            async with _ca._active_cursor_runs_lock:
                _ca._active_cursor_runs.pop(session_id, None)
