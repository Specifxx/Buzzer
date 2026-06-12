"""Thin, typed Printify REST client.

Every call goes through ``_request`` (logging, retry on 429/5xx, error
wrapping). The HTTP transport is injectable so tests run against a fake
session and record every call — no live API is ever touched in tests.

API reference: https://developers.printify.com/
"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

BASE_URL = "https://api.printify.com/v1"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class PrintifyError(Exception):
    """A Printify API call failed."""


class ResponseLike(Protocol):
    status_code: int

    @property
    def text(self) -> str: ...

    def json(self) -> Any: ...


class TransportLike(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: Any | None,
        timeout: float,
    ) -> ResponseLike: ...


class _RequestsTransport:
    """Adapter from requests.Session to the narrow TransportLike protocol."""

    def __init__(self) -> None:
        import requests

        self._session = requests.Session()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: Any | None,
        timeout: float,
    ) -> ResponseLike:
        return self._session.request(method, url, headers=headers, json=json, timeout=timeout)


def _default_transport() -> TransportLike:
    return _RequestsTransport()


class PrintifyClient:
    def __init__(
        self,
        token: str,
        shop_id: str,
        transport: TransportLike | None = None,
        base_url: str = BASE_URL,
        timeout_s: float = 60.0,
        retries: int = 3,
    ) -> None:
        self._token = token
        self.shop_id = shop_id
        self.transport = transport if transport is not None else _default_transport()
        self.base_url = base_url
        self.timeout_s = timeout_s
        self.retries = retries

    def _request(self, method: str, path: str, payload: Any | None = None) -> Any:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "buzzer-poster-pipeline",
        }
        last_status = 0
        for attempt in range(1, self.retries + 1):
            logger.info("printify %s %s (attempt %d)", method, path, attempt)
            response = self.transport.request(
                method, url, headers=headers, json=payload, timeout=self.timeout_s
            )
            last_status = response.status_code
            if response.status_code in RETRYABLE_STATUS:
                wait = 2.0**attempt
                logger.warning("printify %s -> %d, retrying in %.0fs", path, last_status, wait)
                time.sleep(wait)
                continue
            if response.status_code >= 400:
                raise PrintifyError(f"{method} {path} -> {response.status_code}: {response.text}")
            return response.json() if response.text else {}
        raise PrintifyError(f"{method} {path} -> {last_status} after {self.retries} attempts")

    # -- endpoints ----------------------------------------------------------

    def shops(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._request("GET", "/shops.json")
        return result

    def blueprints(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._request("GET", "/catalog/blueprints.json")
        return result

    def print_providers(self, blueprint_id: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._request(
            "GET", f"/catalog/blueprints/{blueprint_id}/print_providers.json"
        )
        return result

    def variants(self, blueprint_id: int, print_provider_id: int) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "GET",
            f"/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json",
        )
        return result

    def upload_image(self, file_path: Path) -> dict[str, Any]:
        contents = base64.b64encode(file_path.read_bytes()).decode()
        result: dict[str, Any] = self._request(
            "POST",
            "/uploads/images.json",
            {"file_name": file_path.name, "contents": contents},
        )
        return result

    def list_products(self, limit: int = 100) -> list[dict[str, Any]]:
        result = self._request("GET", f"/shops/{self.shop_id}/products.json?limit={limit}")
        data: list[dict[str, Any]] = result.get("data", result if isinstance(result, list) else [])
        return data

    def get_product(self, product_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "GET", f"/shops/{self.shop_id}/products/{product_id}.json"
        )
        return result

    def create_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "POST", f"/shops/{self.shop_id}/products.json", payload
        )
        return result

    def update_product(self, product_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "PUT", f"/shops/{self.shop_id}/products/{product_id}.json", payload
        )
        return result

    def publish_product(self, product_id: str) -> dict[str, Any]:
        publish_flags = {
            "title": True,
            "description": True,
            "images": True,
            "variants": True,
            "tags": True,
            "keyFeatures": True,
            "shipping_template": True,
        }
        result: dict[str, Any] = self._request(
            "POST",
            f"/shops/{self.shop_id}/products/{product_id}/publish.json",
            publish_flags,
        )
        return result
