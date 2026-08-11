"""Cursor /v1/models capability reader.

Cursor's models list currently exposes model identity metadata (`id`,
`displayName`, `name`) via an `items` array or legacy `models` array. Those
fields prove availability, not model capabilities, so this reader keeps
capabilities unknown unless Cursor adds explicit capability fields later.
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


def cursor_model_items(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    payload = as_mapping(payload)
    items = payload.get("items")
    if items is None:
        items = payload.get("models")
    return tuple(item for item in as_list(items) if isinstance(item, Mapping))


def record_from_model(
    raw: Mapping[str, Any],
    *,
    endpoint_id: Any = "",
    base_url: Any = "",
) -> ModelCapabilityRecord | None:
    model_id = model_id_from(raw, "id")
    if not model_id:
        return None

    display_name = compact_str(raw.get("displayName") or raw.get("name"))

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
