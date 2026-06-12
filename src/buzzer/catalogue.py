"""Catalogue generation: bulk-scan seasons, render the best moments,
write an organised folder with a manifest.

The manifest is potentially customer-facing (titles, descriptions, SEO
tags), so it carries ONLY validated listing copy and renderable facts —
never operator context (no team codes, no play-by-play text). The
operator can always recover the game via the moment_id.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from buzzer.datasource import DataSource, MissingDataError
from buzzer.detect import DEFAULT_MIN_SCORE, scan_season
from buzzer.listing import description_for, tags_for, title_for
from buzzer.models import Moment
from buzzer.render import STYLES, render_moment

logger = logging.getLogger(__name__)

MANIFEST_SCHEMA_VERSION = 1


def current_season(today: date | None = None) -> str:
    """Season string for today; a season starting in YYYY runs Oct-Jun."""
    today = today or date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def seasons_back(count: int, latest: str | None = None) -> list[str]:
    """The last ``count`` seasons, oldest first, e.g. 30 -> 1996-97..2025-26."""
    latest = latest or current_season()
    latest_start = int(latest.split("-")[0])
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(latest_start - count + 1, latest_start + 1)]


@dataclass
class CatalogueResult:
    out_dir: Path
    manifest_path: Path
    moments: list[Moment] = field(default_factory=list)
    seasons_scanned: list[str] = field(default_factory=list)
    seasons_skipped: list[str] = field(default_factory=list)


def _manifest_entry(
    rank: int, moment: Moment, files: dict[str, dict[str, dict[str, str]]]
) -> dict[str, Any]:
    facts = moment.facts
    return {
        "rank": rank,
        "moment_id": moment.moment_id,
        "score": moment.score,
        "title": title_for(facts),
        "description": description_for(facts),
        "tags": tags_for(facts),
        "facts": facts.to_dict(),
        "files": files,
    }


def build_catalogue(
    seasons: list[str],
    top_n: int,
    out_dir: Path,
    source: DataSource,
    styles: tuple[str, ...] = STYLES,
    sizes: tuple[str, ...] = ("18x24",),
    print_files: bool = False,
    min_score: int = DEFAULT_MIN_SCORE,
) -> CatalogueResult:
    """Scan playoff seasons, render the top moments, write manifest.json."""
    result = CatalogueResult(out_dir=out_dir, manifest_path=out_dir / "manifest.json")

    all_moments: list[Moment] = []
    for season in seasons:
        try:
            found = scan_season(season, playoffs=True, source=source, min_score=min_score)
        except MissingDataError:
            logger.warning("season %s: no cached data and offline — skipped", season)
            result.seasons_skipped.append(season)
            continue
        logger.info("season %s: %d candidate moments", season, len(found))
        result.seasons_scanned.append(season)
        all_moments.extend(found)

    all_moments.sort(key=lambda m: (m.score, m.facts.game_date), reverse=True)
    result.moments = all_moments[:top_n]

    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for rank, moment in enumerate(result.moments, start=1):
        subdir = f"{rank:03d}_{moment.moment_id.replace(':', '-')}"
        files: dict[str, dict[str, dict[str, str]]] = {}
        for style in styles:
            files[style] = {}
            for size in sizes:
                outputs = render_moment(
                    moment, style, size, out_dir, print_file=print_files, subdir=subdir
                )
                file_map: dict[str, str] = {}
                for path in outputs:
                    if path.name.endswith("_preview.png"):
                        file_map["preview"] = str(path.relative_to(out_dir))
                    elif path.suffix == ".png":
                        file_map["print"] = str(path.relative_to(out_dir))
                    else:
                        file_map["svg"] = str(path.relative_to(out_dir))
                files[style][size] = file_map
        entries.append(_manifest_entry(rank, moment, files))
        logger.info("catalogue %03d/%d: %s", rank, len(result.moments), moment.moment_id)

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seasons_requested": seasons,
        "seasons_scanned": result.seasons_scanned,
        "seasons_skipped": result.seasons_skipped,
        "styles": list(styles),
        "sizes": list(sizes),
        "min_score": min_score,
        "count": len(entries),
        "moments": entries,
    }
    result.manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info("manifest written: %s (%d moments)", result.manifest_path, len(entries))
    return result
