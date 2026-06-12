# Buzzer

Automated print-on-demand poster business around iconic basketball moments,
rendered as **original minimalist data-art** — never photos, logos, team
marks, player names, or likenesses.

## The legal constraint (read this before "improving" anything)

Posters sell on the drama of a moment, but almost everything recognisable
about pro basketball is someone else's intellectual property:

* **Team names, nicknames, logos, marks** — trademarks of the league/teams.
* **Player names and likenesses** — protected by right-of-publicity law.
* **Photos and broadcast stills** — copyrighted.

What is *not* protectable: **facts**. Scores, dates, times, city names,
distances, and shot coordinates are facts, and original artwork built only
from facts is ours. That line is the entire business model, so it is
enforced in code, not in a style guide:

* `MomentFacts` (renderable) and `MomentContext` (operator-only, contains
  tricodes and raw play-by-play text) are separate types — see
  `src/buzzer/models.py`. Templates only ever receive `MomentFacts`.
* Phase 2 adds a hard validation step that rejects rendered output
  containing anything beyond factual text.
* Tests assert that player names and team codes never leak into facts.

If a change makes a poster more recognisable by adding a name, a nickname,
an arena, or a logo — it is not an improvement, it is a lawsuit.

## Phase 1 — Moment engine (current)

Pulls play-by-play and shot-chart data via [`nba_api`](https://github.com/swar/nba_api)
and flags poster-worthy plays: made field goals scored 0–100 for
"iconic-ness" based on time remaining, lead changes, score margin, playoff
stakes, comeback size, and shot distance. Scoring weights live in
`src/buzzer/scoring.py` and every score is explainable.

## Quickstart

```bash
uv sync
uv run buzzer scan --season 2025-26 --playoffs          # rank a whole season
uv run buzzer scan --game 0042500401                    # rank one game
uv run buzzer scan --game 0042500401 --as-json          # machine-readable
```

API responses are cached as JSON under `.buzzer_cache/` (configurable with
`--cache-dir`); `--offline` never touches the network. stats.nba.com
throttles aggressively — calls are rate-limited and retried automatically.

## Development

```bash
uv run pytest          # offline: tests use fixtures in tests/fixtures/
uv run mypy
uv run ruff check
```

Fixtures are synthetic games produced by
`tests/fixtures/generate_fixtures.py` (fictional player names, scripted
scores) in the exact shape of cached nba_api responses, so the whole test
suite runs without network access.

## Layout

```
src/buzzer/
  models.py      # Moment, MomentFacts (renderable) vs MomentContext (operator-only)
  datasource.py  # DataSource protocol + JSON file cache (offline/fixture source)
  nba_source.py  # live stats.nba.com client (rate-limited, retried)
  pbp.py         # play-by-play parsing with running score
  scoring.py     # transparent 0-100 iconic-ness scoring
  detect.py      # detect_moments / scan_season
  cli.py         # `buzzer` CLI
```

## Roadmap

1. **Moment engine** — this phase.
2. **Poster renderer** — SVG templates (trajectory / blueprint / type) with
   a content-safety validator; print-ready 300-DPI exports.
3. **Catalogue generation** — top 100 moments of the last 30 playoff seasons.
4. **Publishing automation** — Printify/Shopify sync, idempotent, dry-run first.
5. **Hands-off operation** — morning cron scan, draft products, human approval.
