"""Idempotency state for publishing.

A small JSON file maps product keys (``moment_id|style``) to Printify
product ids, and content hashes of uploaded files to Printify image ids.
Re-running a sync therefore updates instead of duplicating, and uploads
are deduplicated by content. The file is written after every mutation so
a crash mid-run never loses what was already created.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path("state/printify_products.json")


def product_key(moment_id: str, style: str) -> str:
    return f"{moment_id}|{style}"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class PublishState:
    path: Path
    data: dict[str, Any]

    @classmethod
    def load(cls, path: Path = DEFAULT_STATE_PATH) -> PublishState:
        empty: dict[str, Any] = {"products": {}, "uploads": {}}
        data = json.loads(path.read_text()) if path.exists() else empty
        return cls(path=path, data=data)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True))

    # -- products -----------------------------------------------------------

    def product(self, key: str) -> dict[str, Any] | None:
        record: dict[str, Any] | None = self.data["products"].get(key)
        return record

    def record_product(self, key: str, product_id: str, title: str) -> None:
        existing = self.data["products"].get(key, {})
        self.data["products"][key] = {
            **existing,
            "product_id": product_id,
            "title": title,
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "published": existing.get("published", False),
        }
        self._save()
        logger.info("state: %s -> product %s", key, product_id)

    def mark_published(self, key: str) -> None:
        self.data["products"][key]["published"] = True
        self.data["products"][key]["published_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        self._save()

    # -- uploads ------------------------------------------------------------

    def upload_id_for(self, sha: str) -> str | None:
        upload_id: str | None = self.data["uploads"].get(sha)
        return upload_id

    def record_upload(self, sha: str, image_id: str) -> None:
        self.data["uploads"][sha] = image_id
        self._save()
