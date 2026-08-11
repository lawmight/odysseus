"""Cursor /v1/models capability reader.

Cursor's models list exposes identity metadata via `items`, legacy `models`,
or OpenAI-style `data`. Those fields prove availability, not capabilities, so
this reader keeps capabilities unknown unless Cursor adds explicit capability
fields later.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src import model_capabilities as mc
from src.model_capability_readers.base import (
    ModelCapabilityRecord,
    VENDOR_CURSOR,
    as_list,
    as_mapping,
    compact_str,
    model_id_from,
    stable_model_id_for,
)


vendor = VENDOR_CURSOR


def _non_empty_sequence(value: Any) -> list[Any] | None:
    if value is None:
        return None
    items = as_list(value)
    return items if items else None


def _normalize_cursor_item(item: Any) -> Mapping[str, Any] | None:
    if isinstance(item, Mapping):
        return item
    text = compact_str(item)
    if text:
        return {"id": text}
    return None


def cursor_model_items(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    payload = as_mapping(payload)
    candidates: list[Any] | None = None
    for key in ("items", "models", "data"):
        candidates = _non_empty_sequence(payload.get(key))
        if candidates is not None:
            break
    if candidates is None:
        return ()

    out: list[Mapping[str, Any]] = []
    for item in candidates:
        normalized = _normalize_cursor_item(item)
        if normalized is not None:
            out.append(normalized)
    return tuple(out)


def record_from_model(
    raw: Mapping[str, Any],
    *,
    endpoint_id: Any = "",
    base_url: Any = "",
) -> ModelCapabilityRecord | None:
    model_id = model_id_from(raw, "id")
    if not model_id:
        return None

    display_name = compact_str(raw.get("displayName") or raw.get("display_name") or raw.get("name"))

    return ModelCapabilityRecord(
        vendor=VENDOR_CURSOR,
        model_id=model_id,
        stable_model_id=stable_model_id_for(VENDOR_CURSOR, model_id, endpoint_id=endpoint_id, base_url=base_url),
        display_name=display_name or model_id,
        capability=mc.unknown_capability(
            source=mc.SOURCE_PROVIDER_READER,
            confidence=mc.CONFIDENCE_UNKNOWN,
        ),
        raw=raw,
    )


def records_from_payload(
    payload: Mapping[str, Any],
    *,
    endpoint_id: Any = "",
    base_url: Any = "",
) -> tuple[ModelCapabilityRecord, ...]:
    records: list[ModelCapabilityRecord] = []
    for item in cursor_model_items(payload):
        record = record_from_model(item, endpoint_id=endpoint_id, base_url=base_url)
        if record:
            records.append(record)
    return tuple(records)
