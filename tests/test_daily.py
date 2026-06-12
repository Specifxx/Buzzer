from dataclasses import dataclass, field
from pathlib import Path

import pytest

from buzzer.daily import run_daily
from buzzer.datasource import CachedSource
from buzzer.notify import GitHubIssueNotifier, build_notifier
from buzzer.publish.printify import PrintifyError
from buzzer.publish.state import PublishState

from .conftest import requires_cairo
from .fake_printify import FakePrintifyTransport, FakeResponse
from .test_publish import CONFIG, make_client

GAME_NIGHT = "2026-06-04"  # fixture finals game finished on this date
QUIET_NIGHT = "2025-11-05"  # fixture blowout, nothing above threshold
OFF_SEASON = "2026-07-01"  # no games at all


@dataclass
class FakeNotifier:
    messages: list[tuple[str, str]] = field(default_factory=list)

    def notify(self, subject: str, body: str) -> None:
        self.messages.append((subject, body))


@requires_cairo
def test_daily_drafts_and_notifies(source: CachedSource, tmp_path: Path) -> None:
    state = PublishState.load(tmp_path / "state.json")
    transport = FakePrintifyTransport()
    notifier = FakeNotifier()

    result = run_daily(
        GAME_NIGHT,
        source=source,
        config=CONFIG,
        state=state,
        out_dir=tmp_path / "renders",
        notifier=notifier,
        client=make_client(transport),
    )

    assert result.games_scanned == 1
    assert len(result.moments) == 1
    assert len(result.drafted_keys) == 3  # one per style
    assert transport.published == []  # NEVER publishes
    assert result.notified

    subject, body = notifier.messages[0]
    assert "await approval" in subject
    assert "buzzer approve --moment 0042500401:350" in body
    assert "96/100" in body
    assert "NOT published" in body


@requires_cairo
def test_daily_render_only_without_credentials(source: CachedSource, tmp_path: Path) -> None:
    notifier = FakeNotifier()
    result = run_daily(
        GAME_NIGHT,
        source=source,
        config=CONFIG,
        state=PublishState.load(tmp_path / "state.json"),
        out_dir=tmp_path / "renders",
        notifier=notifier,
        client=None,
    )
    assert result.drafted_keys == []
    assert result.drafts_skipped_reason is not None
    assert result.notified  # still tells the operator about the moment
    assert "No drafts were created" in notifier.messages[0][1]
    # renders exist on disk regardless
    assert list((tmp_path / "renders").rglob("*_preview.png"))


def test_daily_quiet_night_stays_silent(source: CachedSource, tmp_path: Path) -> None:
    notifier = FakeNotifier()
    result = run_daily(
        QUIET_NIGHT,
        source=source,
        config=CONFIG,
        state=PublishState.load(tmp_path / "state.json"),
        out_dir=tmp_path / "renders",
        notifier=notifier,
        client=make_client(FakePrintifyTransport()),
    )
    assert result.games_scanned == 1
    assert result.moments == []
    assert not result.notified
    assert notifier.messages == []


def test_daily_off_season(source: CachedSource, tmp_path: Path) -> None:
    result = run_daily(
        OFF_SEASON,
        source=source,
        config=CONFIG,
        state=PublishState.load(tmp_path / "state.json"),
        out_dir=tmp_path / "renders",
        notifier=FakeNotifier(),
        client=make_client(FakePrintifyTransport()),
    )
    assert result.games_scanned == 0
    assert not result.notified


@requires_cairo
def test_daily_is_idempotent(source: CachedSource, tmp_path: Path) -> None:
    state = PublishState.load(tmp_path / "state.json")
    transport = FakePrintifyTransport()
    for _ in range(2):
        run_daily(
            GAME_NIGHT,
            source=source,
            config=CONFIG,
            state=state,
            out_dir=tmp_path / "renders",
            notifier=FakeNotifier(),
            client=make_client(transport),
        )
    assert len(transport.products) == 3  # re-run updates, never duplicates
    assert len(transport.uploads) == 6  # 3 styles x 2 ratios, uploaded once


# --- notifier ----------------------------------------------------------------


@dataclass
class FakeGitHubTransport:
    calls: list[tuple[str, str, dict[str, str], object]] = field(default_factory=list)
    status: int = 201

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: object = None,
        timeout: float = 0,
    ) -> FakeResponse:
        self.calls.append((method, url, headers, json))
        return FakeResponse(self.status, {"html_url": "https://github.com/x/y/issues/1"})


def test_github_issue_notifier_payload() -> None:
    transport = FakeGitHubTransport()
    GitHubIssueNotifier("owner/repo", token="tok", transport=transport).notify(
        "subject line", "body text"
    )
    method, url, headers, payload = transport.calls[0]
    assert (method, url) == ("POST", "https://api.github.com/repos/owner/repo/issues")
    assert headers["Authorization"] == "Bearer tok"
    assert payload == {"title": "subject line", "body": "body text", "labels": ["buzzer-approval"]}


def test_github_issue_notifier_error() -> None:
    transport = FakeGitHubTransport(status=401)
    notifier = GitHubIssueNotifier("owner/repo", token="bad", transport=transport)
    with pytest.raises(PrintifyError, match="401"):
        notifier.notify("s", "b")


def test_build_notifier_falls_back_to_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("BUZZER_NOTIFY_REPO", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    notifier = build_notifier("github")
    notifier.notify("works", "without crashing")  # LogNotifier


def test_build_notifier_uses_github_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("BUZZER_NOTIFY_REPO", "owner/repo")
    assert isinstance(build_notifier("github"), GitHubIssueNotifier)


# --- approve command ---------------------------------------------------------


@requires_cairo
def test_approve_publishes_drafts(
    source: CachedSource, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    from buzzer.cli import main

    state_path = tmp_path / "state.json"
    state = PublishState.load(state_path)
    transport = FakePrintifyTransport()
    run_daily(
        GAME_NIGHT,
        source=source,
        config=CONFIG,
        state=state,
        out_dir=tmp_path / "renders",
        notifier=FakeNotifier(),
        client=make_client(transport),
    )

    monkeypatch.setenv("PRINTIFY_API_TOKEN", "tok")
    monkeypatch.setenv("PRINTIFY_SHOP_ID", "111")
    monkeypatch.setattr("buzzer.publish.printify._default_transport", lambda: transport)
    result = CliRunner().invoke(
        main,
        ["approve", "--moment", "0042500401:350", "--yes", "--state-file", str(state_path)],
    )
    assert result.exit_code == 0, result.output
    assert len(transport.published) == 3

    reloaded = PublishState.load(state_path)
    for style in ("trajectory", "blueprint", "type"):
        record = reloaded.product(f"0042500401:350|{style}")
        assert record is not None and record["published"]

    # approving again is a no-op, not a re-publish
    again = CliRunner().invoke(
        main,
        ["approve", "--moment", "0042500401:350", "--yes", "--state-file", str(state_path)],
    )
    assert "already published" in again.output
    assert len(transport.published) == 3


def test_approve_unknown_moment_fails(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from buzzer.cli import main

    result = CliRunner().invoke(
        main,
        [
            "approve",
            "--moment",
            "0049999999:1",
            "--yes",
            "--state-file",
            str(tmp_path / "state.json"),
        ],
    )
    assert result.exit_code == 1
