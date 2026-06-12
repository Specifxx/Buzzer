import json

from click.testing import CliRunner

from buzzer.cli import main

from .conftest import FINALS_GAME, FIXTURES_DIR, QUIET_GAME

OFFLINE = ["--offline", "--cache-dir", str(FIXTURES_DIR)]


def test_scan_single_game_table() -> None:
    result = CliRunner().invoke(main, ["scan", "--game", FINALS_GAME, *OFFLINE])
    assert result.exit_code == 0, result.output
    assert "GO-AHEAD" in result.output
    assert "BUZZER" in result.output
    assert "COMEBACK-13" in result.output
    assert "PLAYOFFS" in result.output
    assert "27FT" in result.output


def test_scan_season_playoffs() -> None:
    result = CliRunner().invoke(main, ["scan", "--season", "2025-26", "--playoffs", *OFFLINE])
    assert result.exit_code == 0, result.output
    assert FINALS_GAME in result.output


def test_scan_json_output() -> None:
    result = CliRunner().invoke(main, ["scan", "--game", FINALS_GAME, "--as-json", *OFFLINE])
    assert result.exit_code == 0, result.output
    moments = json.loads(result.output)
    assert moments[0]["score"] >= 90
    assert moments[0]["facts"]["clock"] == "0:01"


def test_scan_quiet_game_exits_nonzero() -> None:
    result = CliRunner().invoke(main, ["scan", "--game", QUIET_GAME, *OFFLINE])
    assert result.exit_code == 1


def test_scan_requires_exactly_one_target() -> None:
    assert CliRunner().invoke(main, ["scan", *OFFLINE]).exit_code != 0
    both = CliRunner().invoke(
        main, ["scan", "--game", FINALS_GAME, "--season", "2025-26", *OFFLINE]
    )
    assert both.exit_code != 0


def test_scan_rejects_bad_season_format() -> None:
    result = CliRunner().invoke(main, ["scan", "--season", "2026", *OFFLINE])
    assert result.exit_code != 0
    assert "2025-26" in result.output


def test_scan_offline_without_cached_data_fails_cleanly() -> None:
    result = CliRunner().invoke(main, ["scan", "--game", "0049900999", *OFFLINE])
    assert result.exit_code != 0
