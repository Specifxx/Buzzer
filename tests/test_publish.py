import json
from pathlib import Path

import pytest

from buzzer.datasource import CachedSource
from buzzer.publish.config import ConfigError, PublishConfig, load_config
from buzzer.publish.pricing import achieved_margin, retail_price_usd, to_cents
from buzzer.publish.printify import PrintifyClient, PrintifyError
from buzzer.publish.ship import execute_plan, plan_ship
from buzzer.publish.state import PublishState, product_key

from .conftest import FINALS_GAME, requires_cairo
from .fake_printify import FakePrintifyTransport

CONFIG = PublishConfig(
    blueprint_id=282,
    print_provider_id=99,
    variant_ids={"12x16": 1001, "18x24": 1002, "24x36": 1003},
    print_costs_usd={"12x16": 9.50, "18x24": 13.75, "24x36": 19.00},
    target_margin=0.60,
    round_ending=0.95,
    sales_channel="shopify",
)


def make_client(transport: FakePrintifyTransport) -> PrintifyClient:
    return PrintifyClient(token="test-token", shop_id="111", transport=transport, retries=2)


# --- pricing -----------------------------------------------------------------


def test_retail_price_targets_60_percent_margin() -> None:
    assert retail_price_usd(13.75, 0.60) == 34.95
    assert retail_price_usd(9.50, 0.60) == 23.95
    assert retail_price_usd(19.00, 0.60) == 47.95
    # rounding goes UP, so the achieved margin is never below target
    for cost in (9.50, 13.75, 19.00, 7.13, 22.01):
        price = retail_price_usd(cost, 0.60)
        assert achieved_margin(price, cost) >= 0.60


def test_pricing_rejects_nonsense() -> None:
    with pytest.raises(ValueError):
        retail_price_usd(10.0, 1.0)
    with pytest.raises(ValueError):
        retail_price_usd(0.0, 0.5)
    assert to_cents(34.95) == 3495


# --- config ------------------------------------------------------------------


def test_load_config_from_repo_toml() -> None:
    config = load_config(Path("config/buzzer.toml"))
    assert config.target_margin == 0.60
    assert set(config.print_costs_usd) == {"12x16", "18x24", "24x36"}
    # the committed config has placeholder ids and must refuse to go live
    with pytest.raises(ConfigError, match="blueprint_id"):
        config.require_catalogue_ids()


def test_config_missing_file() -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(Path("/nonexistent/buzzer.toml"))


# --- client ------------------------------------------------------------------


def test_client_error_surfaces() -> None:
    transport = FakePrintifyTransport(fail_next_with=403)
    with pytest.raises(PrintifyError, match="403"):
        make_client(transport).shops()


def test_client_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    transport = FakePrintifyTransport(fail_next_with=429)
    shops = make_client(transport).shops()
    assert shops[0]["id"] == 111
    assert len(transport.calls) == 2  # one 429, one success


# --- ship: dry run -----------------------------------------------------------


@requires_cairo
def test_plan_ship_makes_no_api_calls(source: CachedSource, tmp_path: Path) -> None:
    state = PublishState.load(tmp_path / "state.json")
    plan = plan_ship(
        FINALS_GAME, source=source, config=CONFIG, state=state, out_dir=tmp_path / "renders"
    )
    assert len(plan.items) == 3  # top 1 moment x 3 styles
    item = plan.items[0]
    assert "Buzzer-Beater" in item.title
    assert item.title.endswith("Style")
    assert item.existing_product_id is None
    prices = {v.size: v.price_usd for v in item.variants}
    assert prices == {"12x16": 23.95, "18x24": 34.95, "24x36": 47.95}
    # local previews were rendered for both aspect ratios
    renders = list((tmp_path / "renders").rglob("*_preview.png"))
    assert len(renders) == 6  # 3 styles x 2 aspect-group sizes


def test_plan_ship_quiet_game_warns(source: CachedSource, tmp_path: Path) -> None:
    state = PublishState.load(tmp_path / "state.json")
    plan = plan_ship(
        "0022500123", source=source, config=CONFIG, state=state, out_dir=tmp_path / "r"
    )
    assert plan.items == []
    assert any("nothing to ship" in w for w in plan.warnings)


# --- ship: execution ---------------------------------------------------------


def _plan(source: CachedSource, tmp_path: Path, state: PublishState) -> object:
    return plan_ship(
        FINALS_GAME,
        source=source,
        config=CONFIG,
        state=state,
        out_dir=tmp_path / "renders",
        styles=("type",),  # one style keeps the test fast (2 print PNG exports)
    )


@requires_cairo
def test_execute_creates_drafts_and_is_idempotent(source: CachedSource, tmp_path: Path) -> None:
    state = PublishState.load(tmp_path / "state.json")
    transport = FakePrintifyTransport()
    client = make_client(transport)

    plan = plan_ship(
        FINALS_GAME,
        source=source,
        config=CONFIG,
        state=state,
        out_dir=tmp_path / "renders",
        styles=("type",),
    )
    report = execute_plan(plan, client, CONFIG, state, confirm=lambda m: True)
    assert len(report.created) == 1
    assert report.published == []
    assert transport.published == []  # drafts only
    assert len(transport.uploads) == 2  # one per aspect ratio

    product = next(iter(transport.products.values()))
    assert product["blueprint_id"] == 282
    assert {v["id"]: v["price"] for v in product["variants"]} == {
        1001: 2395,
        1002: 3495,
        1003: 4795,
    }
    assert len(product["print_areas"]) == 2
    # 3:4 print area covers both 3:4 sizes
    by_len = sorted(product["print_areas"], key=lambda a: len(a["variant_ids"]))
    assert by_len[1]["variant_ids"] == [1001, 1002]

    # Second run: same plan -> update, not duplicate; uploads deduped by sha.
    plan2 = plan_ship(
        FINALS_GAME,
        source=source,
        config=CONFIG,
        state=state,
        out_dir=tmp_path / "renders",
        styles=("type",),
    )
    assert plan2.items[0].existing_product_id is not None
    report2 = execute_plan(plan2, client, CONFIG, state, confirm=lambda m: True)
    assert report2.created == []
    assert len(report2.updated) == 1
    assert len(transport.products) == 1  # still exactly one product
    assert len(transport.uploads) == 2  # no re-uploads


@requires_cairo
def test_execute_respects_confirmation_refusal(source: CachedSource, tmp_path: Path) -> None:
    state = PublishState.load(tmp_path / "state.json")
    transport = FakePrintifyTransport()
    plan = plan_ship(
        FINALS_GAME,
        source=source,
        config=CONFIG,
        state=state,
        out_dir=tmp_path / "renders",
        styles=("type",),
    )
    report = execute_plan(plan, make_client(transport), CONFIG, state, confirm=lambda m: False)
    assert report.aborted
    assert transport.calls == []  # nothing was sent at all


@requires_cairo
def test_publish_needs_second_confirmation(source: CachedSource, tmp_path: Path) -> None:
    state = PublishState.load(tmp_path / "state.json")
    transport = FakePrintifyTransport()
    plan = plan_ship(
        FINALS_GAME,
        source=source,
        config=CONFIG,
        state=state,
        out_dir=tmp_path / "renders",
        styles=("type",),
    )
    answers = iter([True, False])  # yes to drafts, NO to publish
    report = execute_plan(
        plan,
        make_client(transport),
        CONFIG,
        state,
        confirm=lambda m: next(answers),
        publish=True,
    )
    assert len(report.created) == 1
    assert report.aborted
    assert transport.published == []

    # And with both confirmations the product goes live and is marked.
    plan2 = plan_ship(
        FINALS_GAME,
        source=source,
        config=CONFIG,
        state=state,
        out_dir=tmp_path / "renders",
        styles=("type",),
    )
    report2 = execute_plan(
        plan2, make_client(transport), CONFIG, state, confirm=lambda m: True, publish=True
    )
    assert len(report2.published) == 1
    assert len(transport.published) == 1
    key = product_key(plan2.items[0].moment.moment_id, "type")
    record = state.product(key)
    assert record is not None and record["published"] is True


@requires_cairo
def test_execute_refuses_placeholder_config(source: CachedSource, tmp_path: Path) -> None:
    state = PublishState.load(tmp_path / "state.json")
    placeholder = load_config(Path("config/buzzer.toml"))
    plan = plan_ship(
        FINALS_GAME,
        source=source,
        config=placeholder,
        state=state,
        out_dir=tmp_path / "renders",
        styles=("type",),
    )
    with pytest.raises(ConfigError):
        execute_plan(
            plan, make_client(FakePrintifyTransport()), placeholder, state, confirm=lambda m: True
        )


def test_state_survives_reload(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = PublishState.load(path)
    state.record_product("a|type", "prod-9", "Title")
    state.record_upload("sha123", "img-7")

    reloaded = PublishState.load(path)
    record = reloaded.product("a|type")
    assert record is not None and record["product_id"] == "prod-9"
    assert reloaded.upload_id_for("sha123") == "img-7"
    assert json.loads(path.read_text())["products"]["a|type"]["published"] is False
