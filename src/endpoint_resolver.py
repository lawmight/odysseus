# src/endpoint_resolver.py
"""Unified endpoint resolution for all backend services.

Consolidates the 4+ copies of normalize_base / resolve_endpoint logic into one place.
"""

import json
import logging
import socket
import subprocess
from typing import Optional, Tuple, Dict
from urllib.parse import urlparse, urlunparse

from core.database import SessionLocal, ModelEndpoint
from src.llm_core import _detect_provider, _host_match
from src.providers.cursor_adapter import (
    CURSOR_LOCAL_URL,
    cached_model_ids,
    cursor_headers,
    is_cursor_url,
    normalize_cached_cursor_models,
)

logger = logging.getLogger(__name__)

_HTTP_ONLY_PREFIXES = frozenset({"utility", "task", "research", "vision"})


def _http_safe_fallback(
    setting_prefix: str,
    fallback_url: Optional[str],
    fallback_model: Optional[str],
    fallback_headers: Optional[Dict],
) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
    """Background HTTP callers cannot POST to cursor:// — drop that fallback."""
    if setting_prefix in _HTTP_ONLY_PREFIXES and is_cursor_url(fallback_url or ""):
        return None, None, None
    return fallback_url, fallback_model, fallback_headers


# Model-name substrings that are NOT chat/generation models. When an endpoint
# has no explicit model configured we pick the first CHAT model from its list —
# never an embedding/tts/etc. (an OpenAI-style endpoint often lists
# `text-embedding-ada-002` first, which silently broke email-summarize and
# other resolve_endpoint callers with "Cannot reach model").
_NON_CHAT_MODEL = (
    "text-embedding", "embedding", "tts-", "whisper", "dall-e",
    "moderation", "rerank", "reranker", "clip", "stable-diffusion",
)


def _model_id_from_cached(m) -> str:
    if isinstance(m, dict):
        return str(m.get("id") or m.get("model") or "")
    return str(m or "")


def _first_chat_model(models) -> Optional[str]:
    """First model that isn't an embedding/tts/etc.; falls back to models[0]."""
    for m in (models or []):
        mid = _model_id_from_cached(m)
        if mid and not any(p in mid.lower() for p in _NON_CHAT_MODEL):
            return mid
    raw = models or []
    return _model_id_from_cached(raw[0]) if raw else None


def _endpoint_cached_models(ep) -> list:
    """Return cached model ids from the current or legacy endpoint field."""
    raw = getattr(ep, "cached_models", None) or getattr(ep, "models", None)
    if not raw:
        return []
    try:
        models = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []
    if not isinstance(models, list):
        return []
    if (getattr(ep, "provider", "") or "").strip() == "cursor":
        return normalize_cached_cursor_models(models)
    return models


def _endpoint_hidden_models(ep) -> set:
    """Model ids the admin disabled on this endpoint (the UI's hidden list)."""
    raw = getattr(ep, "hidden_models", None)
    if not raw:
        return set()
    try:
        hidden = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return set()
    return set(hidden) if isinstance(hidden, list) else set()


def _endpoint_enabled_models(ep) -> list:
    """Cached models minus the ones disabled on the endpoint, order preserved.

    The auto-pick fallback must never select a model the user disabled — a
    Groq endpoint can list 16 models with only 1 enabled, and picking the
    raw first one resolves to a model that 400s ("requires terms acceptance").
    """
    hidden = _endpoint_hidden_models(ep)
    return [m for m in _endpoint_cached_models(ep) if m not in hidden]


# Cache for Tailscale hostname → IP resolution
_tailscale_cache: Dict[str, Optional[str]] = {}


def _resolve_tailscale_host(hostname: str) -> Optional[str]:
    """Try to resolve a hostname via 'tailscale status' if DNS fails."""
    if hostname in _tailscale_cache:
        return _tailscale_cache[hostname]

    # First check if normal DNS works
    try:
        socket.getaddrinfo(hostname, None, socket.AF_INET)
        _tailscale_cache[hostname] = None  # DNS works, no override needed
        return None
    except socket.gaierror:
        pass

    # DNS failed — try tailscale
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            import json as _json
            data = _json.loads(result.stdout)
            peers = data.get("Peer", {})
            for _id, peer in peers.items():
                peer_name = (peer.get("HostName") or "").lower()
                dns_name = (peer.get("DNSName") or "").split(".")[0].lower()
                if peer_name == hostname.lower() or dns_name == hostname.lower():
                    addrs = peer.get("TailscaleIPs", [])
                    if addrs:
                        ip = addrs[0]
                        logger.info(f"Resolved '{hostname}' via Tailscale → {ip}")
                        _tailscale_cache[hostname] = ip
                        return ip
    except Exception as e:
        logger.debug(f"Tailscale resolution failed for '{hostname}': {e}")

    _tailscale_cache[hostname] = None
    return None


def resolve_url(url: str) -> str:
    """If a URL's hostname can't be resolved via DNS, try Tailscale."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return url
    ip = _resolve_tailscale_host(hostname)
    if ip:
        # Replace hostname with IP in the URL
        netloc = ip
        if parsed.port:
            netloc = f"{ip}:{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def normalize_base(url: str) -> str:
    """Strip known API path suffixes from a base URL."""
    url = (url or "").strip().rstrip("/")
    for suffix in ["/models", "/chat/completions", "/completions", "/v1/messages"]:
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
    for suffix in ["/chat", "/tags", "/generate"]:
        if url.endswith("/api" + suffix):
            url = url[: -len(suffix)].rstrip("/")
    return url


def _anthropic_api_root(base: str) -> str:
    """Return Anthropic's API root, preserving /v1 for OpenAI-compatible APIs elsewhere."""
    base = (base or "").strip().rstrip("/")
    if _host_match(base, "anthropic.com") and base.endswith("/v1"):
        return base[:-3].rstrip("/")
    return base


def _ollama_api_root(base: str) -> str:
    """Return the native Ollama API root, adding /api for ollama.com hosts."""
    base = (base or "").strip().rstrip("/")
    parsed = urlparse(base)
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/api"):
        return base
    if _host_match(base, "ollama.com"):
        root = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else "https://ollama.com"
        return root.rstrip("/") + "/api"
    return base


def build_chat_url(base: str) -> str:
    """Return the correct chat endpoint URL for a given base."""
    if is_cursor_url(base):
        return base.rstrip("/")
    base = resolve_url(base)
    provider = _detect_provider(base)
    if provider == "anthropic":
        return _anthropic_api_root(base) + "/v1/messages"
    if provider == "ollama":
        return _ollama_api_root(base) + "/chat"
    return base + "/chat/completions"


def build_models_url(base: str) -> str:
    """Return the provider-specific model-list endpoint URL for a base."""
    base = resolve_url(base)
    provider = _detect_provider(base)
    if provider == "anthropic":
        return _anthropic_api_root(base) + "/v1/models"
    if provider == "ollama":
        return _ollama_api_root(base) + "/tags"
    return base + "/models"


def build_headers(api_key: Optional[str], base: str, provider_config: Optional[str] = None) -> Dict[str, str]:
    """Build auth headers for an endpoint."""
    if is_cursor_url(base):
        if not api_key:
            return {}
        return cursor_headers(api_key, provider_config)
    provider = _detect_provider(base)
    headers: Dict[str, str] = {}
    if provider == "anthropic":
        if api_key:
            headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        return headers
    if not api_key:
        return {}
    headers["Authorization"] = f"Bearer {api_key}"
    if provider == "openrouter":
        headers.setdefault("HTTP-Referer", "https://github.com/pewdiepie-archdaemon/odysseus")
        headers.setdefault("X-OpenRouter-Title", "Odysseus")
    return headers


def resolve_endpoint(
    setting_prefix: str,
    fallback_url: Optional[str] = None,
    fallback_model: Optional[str] = None,
    fallback_headers: Optional[Dict] = None,
    owner: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
    """Resolve an endpoint/model from settings, with fallback.

    Args:
        setting_prefix: Settings key prefix, e.g. "research", "task", "utility", "default".
                       Reads ``{prefix}_endpoint_id`` and ``{prefix}_model`` from settings.
        fallback_url:    URL to use if settings are empty or endpoint missing.
        fallback_model:  Model to use if settings are empty.
        fallback_headers: Headers to use if using fallback.

    Returns:
        (endpoint_url, model, headers) — resolved or fallback values.
    """
    try:
        from src.settings import get_user_setting, load_settings
        settings = load_settings()
    except Exception:
        return _http_safe_fallback(setting_prefix, fallback_url, fallback_model, fallback_headers)

    owner_str = owner or ""
    def _stg(key: str) -> str:
        return (get_user_setting(key, owner_str, settings.get(key, "")) or "").strip()

    ep_id = _stg(f"{setting_prefix}_endpoint_id")
    model = _stg(f"{setting_prefix}_model")

    # If the specific endpoint is not configured, but the caller provided a
    # valid fallback (e.g. the active session model), use that immediately.
    # This prevents background tasks from jumping to the global default_model
    # when the user is mid-conversation with a different model.
    if not ep_id and fallback_url and fallback_model:
        return _http_safe_fallback(setting_prefix, fallback_url, fallback_model, fallback_headers)

    # Unset Utility means "same as Default Chat Model".
    if setting_prefix == "utility" and not ep_id:
        ep_id = _stg("default_endpoint_id")
        model = _stg("default_model")

    # Fall back to utility model for task/research/auto-naming if not specifically configured.
    # If Utility itself is unset, the block above makes that resolve to Default Chat.
    if not ep_id and setting_prefix != "utility":
        ep_id = _stg("utility_endpoint_id")
        model = _stg("utility_model")
        if not ep_id:
            ep_id = _stg("default_endpoint_id")
            model = _stg("default_model")

    if not ep_id:
        return _http_safe_fallback(setting_prefix, fallback_url, fallback_model, fallback_headers)

    db = SessionLocal()
    try:
        ep = db.query(ModelEndpoint).filter(
            ModelEndpoint.id == ep_id,
            ModelEndpoint.is_enabled == True,
        )
        if owner:
            from src.auth_helpers import owner_filter
            ep = owner_filter(ep, ModelEndpoint, owner).first()
        else:
            ep = ep.first()
        if not ep:
            return _http_safe_fallback(setting_prefix, fallback_url, fallback_model, fallback_headers)

        ep_provider = (getattr(ep, "provider", "") or "").strip()
        if ep_provider == "cursor" and setting_prefix in _HTTP_ONLY_PREFIXES:
            return _http_safe_fallback(setting_prefix, fallback_url, fallback_model, fallback_headers)
        base = CURSOR_LOCAL_URL if ep_provider == "cursor" else normalize_base(ep.base_url)
        chat_url = build_chat_url(base)
        headers = build_headers(ep.api_key, base, getattr(ep, "provider_config", None))

        # Discard a configured model the user has since disabled on the
        # endpoint (e.g. a stale `default_model` left pointing at a now-hidden
        # model). Treat it as unset so the picker below selects a live one
        # instead of dispatching to a disabled model that 400s.
        if model and model in _endpoint_hidden_models(ep):
            model = ""
        # If no (usable) model specified, pick the first enabled chat model.
        if not model:
            model = _first_chat_model(_endpoint_enabled_models(ep)) or ""
        if not model and not fallback_model:
            logger.warning('[resolve_endpoint] no usable model (all models hidden or list empty)')

        return chat_url, model or fallback_model, headers
    except Exception as e:
        logger.debug(f"Could not resolve {setting_prefix} endpoint: {e}")
        return _http_safe_fallback(setting_prefix, fallback_url, fallback_model, fallback_headers)
    finally:
        db.close()


def resolve_endpoint_by_id(
    ep_id: str, model: Optional[str] = None, owner: Optional[str] = None
) -> Optional[Tuple[str, str, Dict]]:
    """Resolve a specific endpoint id (+ optional model) to (chat_url, model, headers).

    Returns None if the endpoint doesn't exist or is disabled. Used to turn
    a configured fallback entry ({endpoint_id, model}) into a dispatch target.
    """
    if not ep_id:
        return None
    db = SessionLocal()
    try:
        q = db.query(ModelEndpoint).filter(
            ModelEndpoint.id == ep_id,
            ModelEndpoint.is_enabled == True,
        )
        if owner:
            from src.auth_helpers import owner_filter
            q = owner_filter(q, ModelEndpoint, owner)
        ep = q.first()
        if not ep:
            return None
        ep_provider = (getattr(ep, "provider", "") or "").strip()
        base = CURSOR_LOCAL_URL if ep_provider == "cursor" else normalize_base(ep.base_url)
        chat_url = build_chat_url(base)
        headers = build_headers(ep.api_key, base, getattr(ep, "provider_config", None))
        m = (model or "").strip()
        # Drop a model the user disabled on the endpoint, then pick the first
        # enabled chat model rather than a hidden one.
        if m and m in _endpoint_hidden_models(ep):
            m = ""
        if not m:
            m = _first_chat_model(_endpoint_enabled_models(ep)) or ""
        if not m:
            return None
        return chat_url, m, headers
    except Exception as e:
        logger.debug(f"Could not resolve endpoint {ep_id}: {e}")
        return None
    finally:
        db.close()


def resolve_chat_fallback_candidates(owner: Optional[str] = None) -> list:
    """Build the configured default-chat fallback chain as a list of
    (chat_url, model, headers) tuples, skipping any that can't resolve.

    The primary model is NOT included — callers prepend their session's
    current (url, model, headers) so per-session model overrides are honored.
    """
    return _resolve_fallback_candidates("default_model_fallbacks", owner=owner)


def resolve_utility_fallback_candidates(owner: Optional[str] = None) -> list:
    """Configured fallback chain for the Utility model (`utility_model_fallbacks`)."""
    try:
        from src.settings import get_user_setting, load_settings
        settings = load_settings()
        utility_ep = (get_user_setting("utility_endpoint_id", owner or "", settings.get("utility_endpoint_id", "")) or "").strip()
        if not utility_ep:
            return _resolve_fallback_candidates("default_model_fallbacks", owner=owner)
    except Exception:
        pass
    return _resolve_fallback_candidates("utility_model_fallbacks", owner=owner, exclude_cursor=True)


def resolve_vision_fallback_candidates(owner: Optional[str] = None) -> list:
    """Configured fallback chain for the Vision model (`vision_model_fallbacks`)."""
    return _resolve_fallback_candidates(
        "vision_model_fallbacks", owner=owner, exclude_cursor=True
    )


def _resolve_fallback_candidates(
    setting_key: str,
    owner: Optional[str] = None,
    *,
    exclude_cursor: bool = False,
) -> list:
    out = []
    try:
        from src.settings import get_user_setting, load_settings
        settings = load_settings()
        chain = get_user_setting(setting_key, owner or "", settings.get(setting_key) or []) or []
    except Exception:
        return out
    for entry in chain:
        if not isinstance(entry, dict):
            continue
        ep_id = (entry.get("endpoint_id") or "").strip()
        if exclude_cursor and ep_id:
            db = SessionLocal()
            try:
                ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == ep_id).first()
                if ep and (getattr(ep, "provider", "") or "").strip() == "cursor":
                    continue
            finally:
                db.close()
        resolved = resolve_endpoint_by_id(ep_id, entry.get("model", ""), owner=owner)
        if resolved:
            out.append(resolved)
    return out
