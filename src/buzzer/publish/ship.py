"""Ship pipeline: detect -> render -> validate -> publish, idempotently.

``plan_ship`` is pure planning: it detects moments, renders previews,
prices variants and reports exactly what would happen. ``execute_plan``
is the only function that talks to Printify, and the CLI gates it behind
explicit confirmation. Products are created UNPUBLISHED (drafts on the
Printify side); publishing to the connected Shopify store is a separate,
separately-confirmed step.

Poster sizes have two aspect ratios, so each product carries two print
files: the largest render of each ratio (18x24 covers 12x16; 24x36
stands alone).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from buzzer.datasource import DataSource
from buzzer.detect import detect_moments
from buzzer.listing import description_for, tags_for, title_for
from buzzer.models import Moment
from buzzer.publish.config import PublishConfig
from buzzer.publish.pricing import retail_price_usd, to_cents
from buzzer.publish.printify import PrintifyClient
from buzzer.publish.state import PublishState, file_sha256, product_key
from buzzer.render import STYLES, render_moment
from buzzer.render.validate import validate_listing_text

logger = logging.getLogger(__name__)

# aspect group -> (sizes sharing the ratio, size whose render is uploaded)
ASPECT_GROUPS: dict[str, tuple[tuple[str, ...], str]] = {
    "3x4": (("12x16", "18x24"), "18x24"),
    "2x3": (("24x36",), "24x36"),
}
DEFAULT_SHIP_MIN_SCORE = 60

ConfirmFn = Callable[[str], bool]


@dataclass(frozen=True)
class ShipVariant:
    size: str
    variant_id: int
    cost_usd: float
    price_usd: float

    @property
    def price_cents(self) -> int:
        return to_cents(self.price_usd)


@dataclass(frozen=True)
class ShipItem:
    moment: Moment
    style: str
    title: str
    description: str
    tags: list[str]
    variants: tuple[ShipVariant, ...]
    existing_product_id: str | None

    @property
    def key(self) -> str:
        return product_key(self.moment.moment_id, self.style)


@dataclass
class ShipPlan:
    game_id: str
    out_dir: Path
    items: list[ShipItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExecutionReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    aborted: bool = False


def _style_title(style: str, moment: Moment) -> str:
    title = f"{title_for(moment.facts)} — {style.title()} Style"
    validate_listing_text(title, allowed_cities=(moment.facts.home_city, moment.facts.away_city))
    return title


def plan_ship(
    game_id: str,
    source: DataSource,
    config: PublishConfig,
    state: PublishState,
    out_dir: Path,
    top: int = 1,
    styles: tuple[str, ...] = STYLES,
    min_score: int = DEFAULT_SHIP_MIN_SCORE,
) -> ShipPlan:
    """Build the full plan (and local previews) without any API calls."""
    plan = ShipPlan(game_id=game_id, out_dir=out_dir)
    moments = detect_moments(game_id, source=source, min_score=min_score)[:top]
    if not moments:
        plan.warnings.append(f"no moments scored >= {min_score} in game {game_id}; nothing to ship")
        return plan

    variants = tuple(
        ShipVariant(
            size=size,
            variant_id=config.variant_ids.get(size, 0),
            cost_usd=config.print_costs_usd[size],
            price_usd=retail_price_usd(
                config.print_costs_usd[size], config.target_margin, config.round_ending
            ),
        )
        for size in sorted(config.print_costs_usd)
    )

    for moment in moments:
        for style in styles:
            for _sizes, upload_size in ASPECT_GROUPS.values():
                render_moment(moment, style, upload_size, out_dir, print_file=False)
            plan.items.append(
                ShipItem(
                    moment=moment,
                    style=style,
                    title=_style_title(style, moment),
                    description=description_for(moment.facts),
                    tags=tags_for(moment.facts),
                    variants=variants,
                    existing_product_id=(
                        state.product(product_key(moment.moment_id, style)) or {}
                    ).get("product_id"),
                )
            )
    return plan


def _print_file(item: ShipItem, upload_size: str, out_dir: Path) -> Path:
    """Render (or reuse) the print PNG for one aspect group."""
    stem = f"{item.moment.moment_id.replace(':', '-')}_{item.style}_{upload_size}"
    path = out_dir / item.moment.moment_id.replace(":", "-") / f"{stem}.png"
    if not path.exists():
        render_moment(item.moment, item.style, upload_size, out_dir, print_file=True)
    return path


def _upload_print_files(
    item: ShipItem, client: PrintifyClient, state: PublishState, out_dir: Path
) -> dict[str, str]:
    """aspect group -> Printify image id, deduplicated by content hash."""
    image_ids: dict[str, str] = {}
    for group, (_sizes, upload_size) in ASPECT_GROUPS.items():
        path = _print_file(item, upload_size, out_dir)
        sha = file_sha256(path)
        image_id = state.upload_id_for(sha)
        if image_id is None:
            uploaded = client.upload_image(path)
            image_id = str(uploaded["id"])
            state.record_upload(sha, image_id)
        else:
            logger.info("upload reused for %s (%s)", path.name, image_id)
        image_ids[group] = image_id
    return image_ids


def _product_payload(
    item: ShipItem, config: PublishConfig, image_ids: dict[str, str]
) -> dict[str, object]:
    print_areas = []
    for group, (sizes, _upload_size) in ASPECT_GROUPS.items():
        variant_ids = [v.variant_id for v in item.variants if v.size in sizes]
        if not variant_ids:
            continue
        print_areas.append(
            {
                "variant_ids": variant_ids,
                "placeholders": [
                    {
                        "position": "front",
                        "images": [
                            {
                                "id": image_ids[group],
                                "x": 0.5,
                                "y": 0.5,
                                "scale": 1.0,
                                "angle": 0,
                            }
                        ],
                    }
                ],
            }
        )
    return {
        "title": item.title,
        "description": item.description,
        "tags": item.tags,
        "blueprint_id": config.blueprint_id,
        "print_provider_id": config.print_provider_id,
        "variants": [
            {"id": v.variant_id, "price": v.price_cents, "is_enabled": True} for v in item.variants
        ],
        "print_areas": print_areas,
    }


def execute_plan(
    plan: ShipPlan,
    client: PrintifyClient,
    config: PublishConfig,
    state: PublishState,
    confirm: ConfirmFn,
    publish: bool = False,
) -> ExecutionReport:
    """Create/update products as DRAFTS; optionally publish (extra confirm)."""
    report = ExecutionReport()
    config.require_catalogue_ids()
    if not plan.items:
        return report

    to_create = [i for i in plan.items if not i.existing_product_id]
    to_update = [i for i in plan.items if i.existing_product_id]
    if not confirm(
        f"About to create {len(to_create)} and update {len(to_update)} Printify "
        f"product(s) as drafts. Proceed?"
    ):
        logger.warning("execution aborted by operator before product creation")
        report.aborted = True
        return report

    for item in plan.items:
        image_ids = _upload_print_files(item, client, state, plan.out_dir)
        payload = _product_payload(item, config, image_ids)
        if item.existing_product_id:
            client.update_product(item.existing_product_id, payload)
            state.record_product(item.key, item.existing_product_id, item.title)
            report.updated.append(item.key)
            logger.info("updated draft %s (%s)", item.existing_product_id, item.key)
        else:
            created = client.create_product(payload)
            product_id = str(created["id"])
            state.record_product(item.key, product_id, item.title)
            report.created.append(item.key)
            logger.info("created draft %s (%s)", product_id, item.key)

    if publish:
        if not confirm(
            f"Publish {len(plan.items)} product(s) LIVE to the connected "
            f"{config.sales_channel} store?"
        ):
            logger.warning("publish step aborted by operator; drafts remain")
            report.aborted = True
            return report
        for item in plan.items:
            record = state.product(item.key)
            assert record is not None  # recorded just above
            client.publish_product(record["product_id"])
            state.mark_published(item.key)
            report.published.append(item.key)
            logger.info("published %s (%s)", record["product_id"], item.key)

    return report
