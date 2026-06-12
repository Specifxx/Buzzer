"""Publishing configuration: TOML for product/pricing, .env for secrets.

Secrets NEVER live in the TOML or in code — only in the environment
(loaded from .env via python-dotenv). The TOML holds Printify catalogue
ids and print costs, which the operator verifies once against their
account (see `buzzer printify blueprints` / `variants`).
"""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("config/buzzer.toml")


class ConfigError(Exception):
    """Configuration is missing or invalid."""


@dataclass(frozen=True)
class PublishConfig:
    blueprint_id: int
    print_provider_id: int
    variant_ids: dict[str, int]  # size -> Printify variant id
    print_costs_usd: dict[str, float]  # size -> verified print cost
    target_margin: float
    round_ending: float
    sales_channel: str

    def require_catalogue_ids(self) -> None:
        """Live publishing needs real ids; fail with instructions if unset."""
        problems = []
        if self.blueprint_id <= 0:
            problems.append("printify.blueprint_id")
        if self.print_provider_id <= 0:
            problems.append("printify.print_provider_id")
        problems.extend(
            f'printify.variant_ids."{size}"' for size, vid in self.variant_ids.items() if vid <= 0
        )
        if problems:
            raise ConfigError(
                "these config values must be set before going live: "
                + ", ".join(problems)
                + ". Find them with `buzzer printify blueprints` and "
                "`buzzer printify variants`, then edit config/buzzer.toml."
            )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> PublishConfig:
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    with path.open("rb") as f:
        raw = tomllib.load(f)
    try:
        printify = raw["printify"]
        pricing = raw["pricing"]
        return PublishConfig(
            blueprint_id=int(printify["blueprint_id"]),
            print_provider_id=int(printify["print_provider_id"]),
            variant_ids={k: int(v) for k, v in printify["variant_ids"].items()},
            print_costs_usd={k: float(v) for k, v in pricing["print_costs_usd"].items()},
            target_margin=float(pricing["target_margin"]),
            round_ending=float(pricing.get("round_ending", 0.95)),
            sales_channel=str(printify.get("sales_channel", "shopify")),
        )
    except KeyError as exc:
        raise ConfigError(f"missing config key in {path}: {exc}") from exc


def load_secrets() -> tuple[str, str]:
    """(api_token, shop_id) from the environment / .env. Never logged."""
    load_dotenv()
    token = os.environ.get("PRINTIFY_API_TOKEN", "")
    shop_id = os.environ.get("PRINTIFY_SHOP_ID", "")
    missing = [
        name
        for name, value in (("PRINTIFY_API_TOKEN", token), ("PRINTIFY_SHOP_ID", shop_id))
        if not value
    ]
    if missing:
        raise ConfigError(
            f"missing environment variables: {', '.join(missing)} "
            "(put them in .env — see .env.example)"
        )
    return token, shop_id
