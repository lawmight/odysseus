"""Cursor provider adapter for Odysseus chat mode."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional

import httpx

CURSOR_LOCAL_URL = "cursor://local"
CURSOR_MODELS_URL = "https://api.cursor.com/v1/models"
_CURSOR_CWD_HEADER = "X-Odysseus-Cursor-Cwd"

try:
    from cursor_sdk import AsyncClient, LocalAgentOptions  # type: ignore

    CURSOR_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised through the public flag
    AsyncClient = None  # type: ignore
    LocalAgentOptions = None  # type: ignore
    CURSOR_SDK_AVAILABLE = False


class CursorAdapterError(Exception):
    """Error that can be rendered as a friendly SSE error."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


_bridge_lock = asyncio.Lock()
_bridge_clients: Dict[str, Dict[str, Any]] = {}


def is_cursor_url(url: str | None) -> bool:
    return (url or "").strip().lower().startswith("cursor://")


def cursor_provider_config(cwd: str | None = None) -> str:
    data = {}
    if cwd:
        data["cwd"] = cwd
    return json.dumps(data) if data else ""


def parse_provider_config(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def cursor_headers(api_key: str | None, provider_config: Any = None) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    cwd = parse_provider_config(provider_config).get("cwd")
    if cwd:
        headers[_CURSOR_CWD_HEADER] = str(cwd)
    return headers


def extract_cursor_api_key(headers: Optional[Dict[str, str]]) -> str:
    if not headers:
        return ""
    auth = ""
    for key, value in headers.items():
        if key.lower() == "authorization":
            auth = value or ""
            break
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    if auth.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth[6:].strip()).decode("utf-8", errors="replace")
            return decoded.split(":", 1)[0].strip()
        except Exception:
            return ""
    return ""


def extract_cursor_cwd(headers: Optional[Dict[str, str]]) -> str:
    if headers:
        for key, value in headers.items():
            if key.lower() == _CURSOR_CWD_HEADER.lower() and value:
                return str(value)
    return os.getcwd()


def _allowed_roots() -> List[str]:
    configured = os.getenv("CURSOR_ALLOWED_WORKSPACE_ROOTS", "")
    roots = [p for p in configured.split(os.pathsep) if p.strip()]
    if not roots:
        roots = [os.getcwd()]
    return [os.path.realpath(os.path.abspath(p)) for p in roots]


def validate_cursor_cwd(cwd: str | None) -> str:
    path = os.path.realpath(os.path.abspath(cwd or os.getcwd()))
    roots = _allowed_roots()
    if not any(path == root or path.startswith(root + os.sep) for root in roots):
        allowed = ", ".join(roots)
        raise CursorAdapterError(
            f"Cursor workspace directory must be inside CURSOR_ALLOWED_WORKSPACE_ROOTS ({allowed}).",
            status=400,
        )
    if not os.path.isdir(path):
        raise CursorAdapterError(f"Cursor workspace directory does not exist: {path}", status=400)
    return path


def _cursor_auth_headers(api_key: str) -> Dict[str, str]:
    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def list_cursor_models(api_key: str | None, timeout: float = 5.0) -> List[str]:
    """Return live Cursor model IDs from the public models endpoint."""
    if not api_key:
        raise CursorAdapterError("Cursor API key is required.", status=401)
    try:
        response = httpx.get(CURSOR_MODELS_URL, headers=_cursor_auth_headers(api_key), timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        if status in (401, 403):
            raise CursorAdapterError("Cursor rejected the API key. Re-paste it in Model Endpoints.", status=status)
        raise CursorAdapterError(f"Cursor models request failed with HTTP {status}.", status=status)
    except Exception as exc:
        raise CursorAdapterError(f"Could not reach Cursor models API: {exc}", status=503)

    data = response.json()
    items = data.get("items") or data.get("data") or []
    models: List[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            models.append(str(item["id"]))
    return models


async def _get_bridge_client(cwd: str) -> Any:
    if not CURSOR_SDK_AVAILABLE:
        raise CursorAdapterError(
            "Cursor SDK is not installed. Run `pip install -r requirements-cursor.txt` on the Odysseus host.",
            status=503,
        )
    async with _bridge_lock:
        cached = _bridge_clients.get(cwd)
        if cached and cached.get("client"):
            return cached["client"]
        ctx = await AsyncClient.launch_bridge(workspace=cwd)  # type: ignore[union-attr]
        client = await ctx.__aenter__()
        _bridge_clients[cwd] = {"ctx": ctx, "client": client}
        return client


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text") or block.get("content")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def build_cursor_prompt(messages: Iterable[Dict[str, Any]]) -> str:
    """Serialize Odysseus' OpenAI-shaped history into one Cursor prompt."""
    system_parts: List[str] = []
    transcript: List[str] = []
    for msg in messages:
        role = (msg.get("role") or "user").lower()
        text = _message_text(msg.get("content")).strip()
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
        elif role == "assistant":
            transcript.append(f"Assistant:\n{text}")
        else:
            transcript.append(f"User:\n{text}")
    sections = []
    if system_parts:
        sections.append("System instructions:\n" + "\n\n".join(system_parts))
    if transcript:
        sections.append("Conversation so far:\n" + "\n\n".join(transcript))
    return "\n\n---\n\n".join(sections).strip() or "Continue the conversation."


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _iter_content_blocks(message: Any) -> Iterable[Any]:
    payload = _get_attr(message, "message", message)
    content = _get_attr(payload, "content", None)
    if content is None:
        text = _get_attr(message, "text", None)
        return [text] if text else []
    if isinstance(content, list):
        return content
    return [content]


async def stream_cursor_chat(
    model: str,
    messages: List[Dict[str, Any]],
    api_key: str,
    cwd: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream Cursor assistant text as Odysseus SSE chunks."""
    start = time.time()
    try:
        if not api_key:
            raise CursorAdapterError("Cursor API key is required.", status=401)
        workspace = validate_cursor_cwd(cwd)
        client = await _get_bridge_client(workspace)
        prompt = build_cursor_prompt(messages)
        async with await client.agents.create(
            model=model,
            api_key=api_key,
            local=LocalAgentOptions(cwd=workspace),  # type: ignore[misc]
        ) as agent:
            run = await agent.send(prompt)
            async for event in run.messages():
                event_type = str(_get_attr(event, "type", "") or "")
                if event_type == "assistant":
                    for block in _iter_content_blocks(event):
                        if isinstance(block, str):
                            text = block
                        else:
                            block_type = str(_get_attr(block, "type", "text") or "text")
                            if block_type != "text":
                                continue
                            text = str(_get_attr(block, "text", "") or "")
                        if text:
                            yield f"data: {json.dumps({'delta': text})}\n\n"
                elif event_type == "thinking":
                    text = str(_get_attr(event, "text", "") or _get_attr(event, "content", "") or "")
                    if text:
                        yield f"data: {json.dumps({'delta': text, 'thinking': True})}\n\n"
                elif event_type == "error":
                    text = str(_get_attr(event, "message", "") or _get_attr(event, "error", "") or "Cursor run failed")
                    raise CursorAdapterError(text, status=502)
        elapsed = max(time.time() - start, 0.0)
        yield f"data: {json.dumps({'type': 'usage', 'data': {'total_time': round(elapsed, 3)}})}\n\n"
        yield "data: [DONE]\n\n"
    except CursorAdapterError as exc:
        yield f"event: error\ndata: {json.dumps({'status': exc.status, 'text': str(exc), 'error': str(exc)})}\n\n"
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        lower = message.lower()
        status = 401 if "unauthorized" in lower or "api key" in lower else 502
        if "bridge" in lower or "cursor" in lower and "not found" in lower:
            message = f"{message}. Ensure the Cursor SDK bridge can run on the Odysseus host."
        yield f"event: error\ndata: {json.dumps({'status': status, 'text': message, 'error': message})}\n\n"
