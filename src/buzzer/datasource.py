"""Data source abstraction.

Everything external goes through the ``DataSource`` protocol so that:
  * tests run fully offline against fixture files,
  * bulk catalogue runs (Phase 3) are resumable via the same file cache,
  * the live nba_api client is swappable/mockable.

``CachedSource`` is a plain JSON file cache. With ``upstream=None`` it is the
offline fixture source used by the test suite; with a live upstream it is a
write-through cache. Cache files are exactly what the source methods return,
so a cache directory produced by a live run doubles as a fixture directory.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from buzzer.models import GameInfo

logger = logging.getLogger(__name__)

Row = dict[str, Any]


class MissingDataError(Exception):
    """Raised when offline mode is asked for data that is not cached."""


class DataSource(Protocol):
    def play_by_play(self, game_id: str) -> list[Row]:
        """Raw play-by-play rows (nba_api PlayByPlayV2 column names)."""
        ...

    def shot_chart(self, game_id: str) -> list[Row]:
        """Raw shot chart rows (nba_api ShotChartDetail column names)."""
        ...

    def game_summary(self, game_id: str) -> GameInfo:
        """Teams, date and playoff flag for one game."""
        ...

    def season_games(self, season: str, playoffs: bool) -> list[GameInfo]:
        """All games of a season (one entry per game, not per team)."""
        ...


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


class CachedSource:
    """JSON-file-backed DataSource, optionally backed by a live upstream."""

    def __init__(self, cache_dir: Path, upstream: DataSource | None = None) -> None:
        self.cache_dir = cache_dir
        self.upstream = upstream
        cache_dir.mkdir(parents=True, exist_ok=True)

    # -- generic cache plumbing -------------------------------------------

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{_safe_name(key)}.json"

    def _load(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        logger.debug("cache hit: %s", path)
        with path.open() as f:
            return json.load(f)

    def _store(self, key: str, payload: Any) -> None:
        path = self._path(key)
        with path.open("w") as f:
            json.dump(payload, f, indent=1)
        logger.debug("cache write: %s", path)

    def _get(self, key: str, fetch_name: str, *args: Any) -> Any:
        cached = self._load(key)
        if cached is not None:
            return cached
        if self.upstream is None:
            raise MissingDataError(
                f"no cached data for '{key}' in {self.cache_dir} and no live source "
                "configured (offline mode)"
            )
        payload = getattr(self.upstream, fetch_name)(*args)
        if isinstance(payload, GameInfo):
            self._store(key, asdict(payload))
        elif payload and isinstance(payload[0], GameInfo):
            self._store(key, [asdict(g) for g in payload])
        else:
            self._store(key, payload)
        return self._load(key)

    # -- DataSource implementation ----------------------------------------

    def play_by_play(self, game_id: str) -> list[Row]:
        rows: list[Row] = self._get(f"pbp_{game_id}", "play_by_play", game_id)
        return rows

    def shot_chart(self, game_id: str) -> list[Row]:
        rows: list[Row] = self._get(f"shots_{game_id}", "shot_chart", game_id)
        return rows

    def game_summary(self, game_id: str) -> GameInfo:
        raw: Row = self._get(f"summary_{game_id}", "game_summary", game_id)
        return GameInfo(**raw)

    def season_games(self, season: str, playoffs: bool) -> list[GameInfo]:
        kind = "playoffs" if playoffs else "regular"
        raw: list[Row] = self._get(f"games_{season}_{kind}", "season_games", season, playoffs)
        return [GameInfo(**row) for row in raw]
