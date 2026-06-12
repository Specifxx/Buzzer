"""In-memory fake of the Printify REST API for tests.

Implements the ``TransportLike`` protocol and records every call so
tests can assert exactly what would have been sent to the live API.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeResponse:
    status_code: int
    payload: Any

    @property
    def text(self) -> str:
        return json.dumps(self.payload)

    def json(self) -> Any:
        return self.payload


@dataclass
class FakePrintifyTransport:
    calls: list[tuple[str, str, Any]] = field(default_factory=list)
    products: dict[str, dict[str, Any]] = field(default_factory=dict)
    uploads: list[dict[str, Any]] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    fail_next_with: int | None = None
    _counter: int = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: Any = None,
        timeout: float = 0,
    ) -> FakeResponse:
        assert headers["Authorization"].startswith("Bearer "), "auth header missing"
        path = url.split("/v1", 1)[1]
        self.calls.append((method, path, json))

        if self.fail_next_with is not None:
            status = self.fail_next_with
            self.fail_next_with = None
            return FakeResponse(status, {"error": "injected failure"})

        if method == "GET" and path == "/shops.json":
            return FakeResponse(
                200, [{"id": 111, "title": "Test Shop", "sales_channel": "shopify"}]
            )
        if method == "POST" and path == "/uploads/images.json":
            upload = {"id": self._next_id("img"), "file_name": json["file_name"]}
            self.uploads.append(upload)
            return FakeResponse(200, upload)
        if method == "POST" and re.fullmatch(r"/shops/\w+/products\.json", path):
            product_id = self._next_id("prod")
            self.products[product_id] = dict(json)
            return FakeResponse(200, {"id": product_id, **json})
        if method == "PUT" and (m := re.fullmatch(r"/shops/\w+/products/([\w-]+)\.json", path)):
            self.products[m.group(1)] = dict(json)
            return FakeResponse(200, {"id": m.group(1), **json})
        if method == "GET" and path.startswith("/shops/") and "products.json" in path:
            data = [{"id": pid, **p} for pid, p in self.products.items()]
            return FakeResponse(200, {"data": data})
        if method == "POST" and (
            m := re.fullmatch(r"/shops/\w+/products/([\w-]+)/publish\.json", path)
        ):
            self.published.append(m.group(1))
            return FakeResponse(200, {})
        raise AssertionError(f"fake transport has no route for {method} {path}")
