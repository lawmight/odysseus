"""Cursor provider adapter for Odysseus chat mode."""

from __future__ import annotations

import asyncio
import base64
import binascii
import re
from collections import OrderedDict
import json
import logging
import os
import sys
import time
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional, Tuple

import httpx

CURSOR_LOCAL_URL = "cursor://local"
CURSOR_MODELS_URL = "https://api.cursor.com/v1/models"
_CURSOR_CWD_HEADER = "X-Odysseus-Cursor-Cwd"
_BRIDGE_CACHE_MAX = int(os.getenv("CURSOR_BRIDGE_CACHE_MAX", "4") or "4")
logger = logging.getLogger(__name__)

try:
    from cursor_sdk import AsyncClient, LocalAgentOptions, SDKImage, UserMessage  # type: ignore

    CURSOR_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised through the public flag
    AsyncClient = None  # type: ignore
    LocalAgentOptions = None  # type: ignore
    SDKImage = None  # type: ignore
    UserMessage = None  # type: ignore
    CURSOR_SDK_AVAILABLE = False


class CursorAdapterError(Exception):
    """Error that can be rendered as a friendly SSE error."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


_bridge_lock = asyncio.Lock()
_bridge_clients: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

# session_id -> {"run": AsyncRun, "cancelled": bool}
_active_cursor_runs: Dict[str, Dict[str, Any]] = {}
_active_cursor_runs_lock = asyncio.Lock()

_DATA_URL_RE = re.compile(
    r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$",
    re.DOTALL,
)


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
    if not any(os.path.commonpath([path, root]) == root for root in roots):
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


def list_cursor_model_entries(api_key: str | None, timeout: float = 5.0) -> List[Dict[str, str]]:
    """Return Cursor models as {id, displayName} from the public models API."""
    if not api_key:
        raise CursorAdapterError("Cursor API key required.", status=401)
    try:
        response = httpx.get(CURSOR_MODELS_URL, headers=_cursor_auth_headers(api_key), timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        if status in (401, 403):
            raise CursorAdapterError("Cursor rejected the API key. Re-paste it in Model Endpoints.", status=status) from exc
        if status == 429:
            raise CursorAdapterError("Cursor rate limit reached. Wait a moment and try again.", status=429) from exc
        raise CursorAdapterError(f"Cursor models request failed with HTTP {status}.", status=status) from exc
    except httpx.RequestError as exc:
        raise CursorAdapterError(f"Could not reach Cursor models API: {exc}", status=503) from exc

    data = response.json()
    items = data.get("items") or data.get("data") or []
    models: List[Dict[str, str]] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            mid = str(item["id"])
            display = str(item.get("displayName") or item.get("name") or mid)
            models.append({"id": mid, "displayName": display})
    return models


def list_cursor_models(api_key: str | None, timeout: float = 5.0) -> List[str]:
    """Return live Cursor model IDs from the public models endpoint."""
    return [entry["id"] for entry in list_cursor_model_entries(api_key, timeout=timeout)]


def normalize_cached_cursor_models(raw: Any) -> List[Dict[str, str]]:
    """Accept legacy string lists or Plan C {id, displayName} objects."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict) and item.get("id"):
            mid = str(item["id"])
            out.append({
                "id": mid,
                "displayName": str(item.get("displayName") or item.get("name") or mid),
            })
        elif isinstance(item, str) and item.strip():
            mid = item.strip()
            out.append({"id": mid, "displayName": mid})
    return out


def cached_model_ids(raw: Any) -> List[str]:
    return [entry["id"] for entry in normalize_cached_cursor_models(raw)]


async def _close_bridge_entry(entry: Dict[str, Any]) -> None:
    ctx = entry.get("ctx")
    client = entry.get("client")
    try:
        if ctx is not None:
            await ctx.__aexit__(None, None, None)
        elif client is not None and hasattr(client, "aclose"):
            await client.aclose()
    except Exception:
        logger.warning("Failed to close Cursor bridge client", exc_info=True)


async def close_cursor_bridges() -> None:
    """Close cached Cursor SDK bridge clients during application shutdown."""
    async with _bridge_lock:
        entries = list(_bridge_clients.values())
        _bridge_clients.clear()
    for entry in entries:
        await _close_bridge_entry(entry)


async def _get_bridge_client(cwd: str) -> Any:
    if not CURSOR_SDK_AVAILABLE:
        raise CursorAdapterError(
            "Cursor SDK is not installed. Run `pip install -r requirements-cursor.txt` on the Odysseus host.",
            status=503,
        )
    evicted: List[Dict[str, Any]] = []
    async with _bridge_lock:
        cached = _bridge_clients.get(cwd)
        if cached and cached.get("client"):
            _bridge_clients.move_to_end(cwd)
            return cached["client"]
        ctx = await AsyncClient.launch_bridge(workspace=cwd)  # type: ignore[union-attr]
        try:
            client = await ctx.__aenter__()
        except Exception:
            await ctx.__aexit__(*sys.exc_info())
            raise
        _bridge_clients[cwd] = {"ctx": ctx, "client": client}
        while _BRIDGE_CACHE_MAX > 0 and len(_bridge_clients) > _BRIDGE_CACHE_MAX:
            _, entry = _bridge_clients.popitem(last=False)
            evicted.append(entry)
    for entry in evicted:
        await _close_bridge_entry(entry)
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
    """Serialize Odysseus' OpenAI-shaped history into one Cursor prompt (first turn only)."""
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


def _collect_system_prefix(messages: Iterable[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for msg in messages:
        if (msg.get("role") or "").lower() != "system":
            continue
        text = _message_text(msg.get("content")).strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def _last_user_message(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for msg in reversed(messages):
        if (msg.get("role") or "").lower() == "user":
            return msg
    return None


def _sdk_images_from_content(content: Any) -> List[Any]:
    """Build SDKImage list from OpenAI-style multimodal user content."""
    if not CURSOR_SDK_AVAILABLE or SDKImage is None:
        return []
    images: List[Any] = []
    blocks = content if isinstance(content, list) else []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "image_url":
            continue
        image_url = block.get("image_url") or {}
        url = image_url.get("url") if isinstance(image_url, dict) else str(image_url or "")
        if not url:
            continue
        if url.startswith("data:"):
            match = _DATA_URL_RE.match(url.strip())
            if not match:
                continue
            mime_type, b64 = match.group(1), match.group(2)
            try:
                raw = base64.b64decode(b64, validate=True)
            except (binascii.Error, ValueError):
                continue
            try:
                images.append(SDKImage.from_data(raw, mime_type=mime_type))
            except Exception:
                logger.warning("Cursor SDK could not load inline image", exc_info=True)
        elif os.path.isfile(url):
            try:
                images.append(SDKImage.from_file(url))
            except Exception:
                logger.warning("Cursor SDK could not load image file %s", url, exc_info=True)
    return images


def build_cursor_user_message(messages: List[Dict[str, Any]], *, resume: bool) -> Tuple[Any, str]:
    """Return (UserMessage|str payload, optional new_agent_id placeholder)."""
    system_prefix = _collect_system_prefix(messages)
    last_user = _last_user_message(messages)
    if not last_user:
        text = build_cursor_prompt(messages)
        return text, ""

    user_text = _message_text(last_user.get("content")).strip()
    images = _sdk_images_from_content(last_user.get("content"))

    if resume:
        parts = []
        if system_prefix:
            parts.append(f"System instructions:\n{system_prefix}")
        if user_text:
            parts.append(user_text)
        prompt = "\n\n".join(parts).strip() or "Continue the conversation."
        if CURSOR_SDK_AVAILABLE and UserMessage is not None:
            return UserMessage(text=prompt, images=images or None), ""
        return prompt, ""

    # First turn: include full history in one prompt when no prior agent exists.
    if not images and not system_prefix:
        return build_cursor_prompt(messages), ""
    prompt = build_cursor_prompt(messages)
    if CURSOR_SDK_AVAILABLE and UserMessage is not None:
        return UserMessage(text=prompt, images=images or None), ""
    return prompt, ""


async def register_cursor_run(odysseus_session_id: str | None, run: Any) -> None:
    if not odysseus_session_id:
        return
    async with _active_cursor_runs_lock:
        _active_cursor_runs[odysseus_session_id] = {"run": run, "cancelled": False}


async def cancel_cursor_run(odysseus_session_id: str) -> bool:
    """Cancel an in-flight Cursor SDK run for a chat session."""
    async with _active_cursor_runs_lock:
        entry = _active_cursor_runs.get(odysseus_session_id)
        if not entry or entry.get("cancelled"):
            return False
        entry["cancelled"] = True
        run = entry.get("run")
    if run is None:
        return False
    try:
        await run.cancel()
        return True
    except Exception:
        logger.warning("Cursor run.cancel failed for session %s", odysseus_session_id, exc_info=True)
        return False
    finally:
        async with _active_cursor_runs_lock:
            _active_cursor_runs.pop(odysseus_session_id, None)


def cursor_agent_id_event(agent_id: str) -> str:
    return f"data: {json.dumps({'type': 'cursor_agent_id', 'agent_id': agent_id})}\n\n"


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
    if isinstance(content, (list, tuple)):
        return content
    return [content]


async def stream_cursor_chat(
    model: str,
    messages: List[Dict[str, Any]],
    api_key: str,
    cwd: str | None = None,
    *,
    cursor_agent_id: str | None = None,
    odysseus_session_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream Cursor assistant text as Odysseus SSE chunks."""
    start = time.time()
    run = None
    try:
        if not api_key:
            raise CursorAdapterError("Cursor API key required.", status=401)
        workspace = validate_cursor_cwd(cwd)
        client = await _get_bridge_client(workspace)
        resume = bool((cursor_agent_id or "").strip())
        payload, _ = build_cursor_user_message(messages, resume=resume)
        local_opts = LocalAgentOptions(cwd=workspace)  # type: ignore[misc]
        resume_opts = {"apiKey": api_key, "local": {"cwd": workspace}}

        if resume:
            agent = await client.agents.resume(cursor_agent_id.strip(), resume_opts)
        else:
            agent = await client.agents.create(
                model=model,
                api_key=api_key,
                local=local_opts,
            )
        async with agent:
            if not resume and getattr(agent, "agent_id", None):
                yield cursor_agent_id_event(str(agent.agent_id))
            run = await agent.send(payload)
            if odysseus_session_id:
                await register_cursor_run(odysseus_session_id, run)
            async for event in run.messages():
                async with _active_cursor_runs_lock:
                    entry = _active_cursor_runs.get(odysseus_session_id or "")
                    if entry and entry.get("cancelled"):
                        break
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
        logger.exception("Unexpected Cursor stream failure")
        message = str(exc) or exc.__class__.__name__
        lower = message.lower()
        status = 401 if "unauthorized" in lower or "api key" in lower else 502
        if "429" in lower or "rate limit" in lower:
            status = 429
            message = "Cursor rate limit reached. Wait a moment and try again."
        if ("bridge" in lower or "cursor" in lower) and "not found" in lower:
            message = f"{message}. Ensure the Cursor SDK bridge can run on the Odysseus host."
        yield f"event: error\ndata: {json.dumps({'status': status, 'text': message, 'error': message})}\n\n"
    finally:
        if odysseus_session_id:
            async with _active_cursor_runs_lock:
                _active_cursor_runs.pop(odysseus_session_id, None)
