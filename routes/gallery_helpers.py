""" Backward-compat shim - canonical location is routes/gallery/gallery_helpers.py.

This module is replaced in ``sys.modules`` by the canonical module object so
that ``import routes.gallery_helpers``, ``from routes.gallery_helpers import X``,
``importlib.import_module("routes.gallery_helpers")``, and
``monkeypatch.setattr(routes.gallery_helpers, ...)`` all operate on the same
object. Keeps existing import paths working after slice 2a (#4082/#4071).

Cursor SDK chat/agent generateImage persistence also imports
``save_generated_image_bytes`` from this module path — attach it onto the
canonical module before the sys.modules swap.
"""

import logging
import uuid
from pathlib import Path
from typing import Dict, Optional
import sys as _sys

from routes.gallery import gallery_helpers as _canonical  # noqa: F401
from core.database import SessionLocal, GalleryImage

logger = logging.getLogger(__name__)


def save_generated_image_bytes(
    image_bytes: bytes,
    *,
    prompt: str = "",
    model: str = "",
    session_id: Optional[str] = None,
    owner: Optional[str] = None,
    ext: str = "png",
    size: Optional[str] = None,
    quality: Optional[str] = None,
) -> Dict[str, str]:
    """Write generated image bytes to gallery storage and return chat metadata.

    Return keys match the non-streaming image path in chat_routes / do_generate_image:
    image_url, image_id, image_prompt, image_model (plus optional image_size, image_quality).
    """
    img_dir = Path("data/generated_images")
    img_dir.mkdir(parents=True, exist_ok=True)

    suffix = ext.lstrip(".") or "png"
    if suffix not in ("png", "jpg", "jpeg", "webp", "gif"):
        suffix = "png"
    filename = f"{uuid.uuid4().hex[:12]}.{suffix}"
    dest = img_dir / filename
    dest.write_bytes(image_bytes)

    image_url = f"/api/generated-image/{filename}"
    image_id = str(uuid.uuid4())
    display_prompt = (prompt or "Generated image")[:500]
    display_model = model or ""

    try:
        db = SessionLocal()
        try:
            db.add(
                GalleryImage(
                    id=image_id,
                    filename=filename,
                    prompt=display_prompt,
                    model=display_model,
                    size=size,
                    quality=quality,
                    session_id=session_id,
                    owner=owner,
                    file_size=len(image_bytes),
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.warning("Failed to save generated image to gallery", exc_info=True)
        image_id = ""

    out: Dict[str, str] = {
        "image_url": image_url,
        "image_id": image_id,
        "image_prompt": prompt or "Generated image",
        "image_model": display_model,
    }
    if size:
        out["image_size"] = size
    if quality:
        out["image_quality"] = quality
    return out


_canonical.save_generated_image_bytes = save_generated_image_bytes
_sys.modules[__name__] = _canonical
