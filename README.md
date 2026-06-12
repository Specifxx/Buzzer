# Buzzer

An automated print-on-demand poster business around iconic basketball
moments, rendered as **original minimalist data-art** — never photos,
logos, team marks, player names, or likenesses.

A new iconic moment becomes a live, purchasable poster with near-zero
manual work; a human approves anything customer-facing.

```
nba_api ──> moment engine ──> SVG renderer ──> content firewall ──> Printify ──> Shopify
            (score 0-100)     (3 styles)       (allowlist, hard)    (drafts)     (approve)
```

---

## ⚖️ The legal constraints, and why they exist

**Read this before "improving" anything.** Posters sell on the drama of
a moment, but almost everything recognisable about pro basketball is
someone else's intellectual property:

| You may NOT use | Why |
| --- | --- |
| Team names, nicknames, logos, wordmarks | Trademarks of the league/teams. "Lakers", "Celtics", even "Golden State" |
| Player names, numbers + likenesses | Right of publicity. "23" alone is fine; "23 — Jordan" is a lawsuit |
| Photos, broadcast stills, traced outlines of either | Copyright (and likeness, again) |
| Arena names | Trademarks ("Madison Square Garden", "... Arena/Center") |
| League marks | "NBA", "National Basketball Association", the silhouette logo |

**What IS ours to use: facts.** Scores, dates, clock times, periods,
city names, shot distances and coordinates are uncopyrightable facts
(*Feist v. Rural*; *NBA v. Motorola* held game facts aren't owned by the
league). Original artwork built **only** from facts is original art.
That line is the entire business model, so it is enforced in code, not
in a style guide:

1. **Type level** — `MomentFacts` (renderable: numbers, dates, cities)
   and `MomentContext` (operator-only: team codes, raw play-by-play
   text) are separate types (`src/buzzer/models.py`). Templates and
   listings can only receive facts.
2. **Input firewall** — every template variable is checked against
   blocklists built from nba_api's own static data: ~5,000 player
   names, every team nickname/full name, league marks, and generic
   venue words (`src/buzzer/render/validate.py`).
3. **Output firewall** — the rendered SVG is parsed and every word of
   text must be on a hand-curated allowlist of factual vocabulary (or
   be a city name from the facts). Embedded images and external
   references are rejected outright. **Unknown words fail closed.**
4. **Listings too** — product titles, descriptions and SEO tags go
   through the same allowlist. "Vintage Bulls poster" will not pass.
5. **Tests** — adversarial tests inject player names and nicknames into
   every field and assert the render fails.

If a change makes a poster more recognisable by adding a name, a
nickname, an arena or a logo — it is not an improvement, it is a
lawsuit. Extend `ALLOWED_WORDS` only deliberately, in review.

This is engineering risk-reduction, not legal advice; before scaling
revenue, have an IP lawyer sanity-check the catalogue.

---

## Setup

```bash
git clone <this repo> && cd Buzzer
uv sync                       # Python 3.11+, installs everything
uv run pytest                 # 80 offline tests, ~5s — should be green
```

Rendering needs system Cairo (`libcairo2`), present on most Linux/macOS
(`apt install libcairo2` / `brew install cairo`).

### Secrets and config

```bash
cp .env.example .env          # then fill in:
# PRINTIFY_API_TOKEN=...      Printify -> Connections -> API tokens
# PRINTIFY_SHOP_ID=...        from: uv run buzzer printify shops
```

`config/buzzer.toml` holds the Printify catalogue ids and print costs.
The committed file has **placeholder ids (0)** and live publishing
refuses to run until you fill them:

```bash
uv run buzzer printify blueprints --search poster     # pick a poster blueprint
uv run buzzer printify variants --blueprint <id>      # pick a print provider
uv run buzzer printify variants --blueprint <id> --provider <id>  # variant ids per size
```

Secrets never go in code, config or git — `.env` is gitignored.

## Daily use

```bash
# Phase 1 — find moments (cached, resumable; --offline never hits the net)
uv run buzzer scan --season 2025-26 --playoffs
uv run buzzer scan --game 0042500401

# Phase 2 — render one moment (SVG + 300-DPI print PNG + web preview)
uv run buzzer render --moment 0042500401:350 --style trajectory --size 18x24

# Phase 3 — the back-catalogue (top 100 of the last 30 playoff seasons)
uv run buzzer catalogue --seasons-back 30 --top 100

# Phase 4 — one command from game to store, dry-run first ALWAYS
uv run buzzer ship --game 0042500401                 # dry run: shows everything
uv run buzzer ship --game 0042500401 --live          # creates DRAFTS (confirms first)
uv run buzzer ship --game 0042500401 --live --publish # publish = 2nd confirmation

# Phase 5 — the morning routine (also runs from GitHub Actions cron)
uv run buzzer daily                                   # yesterday's games -> drafts + issue
uv run buzzer approve --moment 0042500401:350         # the human yes -> live on store
```

### Hands-off operation

`.github/workflows/daily-scan.yml` runs every morning (13:30 UTC):
scans last night's finished games, renders anything scoring ≥ 70,
creates **draft** products, uploads the renders as a workflow artifact,
and opens a GitHub issue (label `buzzer-approval`) with one-command
approval instructions. **The cron can never publish** — `buzzer
approve` is the only path from draft to store, which keeps a human in
the loop for everything customer-facing.

Add `PRINTIFY_API_TOKEN` and `PRINTIFY_SHOP_ID` as repository Action
secrets. Without them the job degrades to render-and-notify.

**Caveat:** stats.nba.com aggressively throttles and sometimes blocks
datacenter IPs (GitHub runners included). All calls are rate-limited,
retried, and cached to `.buzzer_cache/` so re-runs are cheap; if the
runner IP is blocked outright, use a self-hosted runner or run `buzzer
daily` from any home machine — it is a single idempotent command.

## Costs (verify before launch — these move)

| Item | Ballpark |
| --- | --- |
| Printify poster print cost | ~$5–20 per poster by size/provider (config: $9.50/13.75/19.00) |
| Shipping (buyer-paid usually) | ~$5–10 US |
| Printify subscription | $0 (free tier is fine to start); Premium ~$29/mo for per-product discounts |
| Shopify | Basic ~$39/mo (or Starter ~$5/mo, link-only) |
| GitHub Actions | free tier covers a daily 5-minute job easily |
| Data (stats.nba.com via nba_api) | free, unofficial — expect occasional breakage |

Pricing targets **60% margin on retail** (price = cost / 0.4, rounded
up to x.95): $9.50 print → $23.95, $13.75 → $34.95, $19.00 → $47.95.
Tune in `config/buzzer.toml`.

## How it decides what's "iconic" (Phase 1)

Every made field goal is scored 0–100 by transparent, additive rules
(`src/buzzer/scoring.py`): time remaining (a final-10-seconds make in
the 4th is worth 35–40), go-ahead +20 / game-tying +10 (full weight
only late in the game), playoffs +15, comeback size up to +15, overtime
+5, deep range up to +8, closeness up to +5 — and clutch points are
dampened in blowouts, so a garbage-time buzzer shot scores ~6, not 40.
Every score is explainable from its parts; tune `ScoringWeights`, not
code.

## Project layout

```
src/buzzer/
  models.py        MomentFacts (renderable) vs MomentContext (operator-only)
  datasource.py    DataSource protocol + JSON file cache (fixtures == cache)
  nba_source.py    live stats.nba.com client: rate-limited, retried, mockable
  pbp.py           play-by-play parsing with running score
  scoring.py       0-100 iconic-ness, named weights
  detect.py        detect_moments / scan_season / find_moment
  render/
    validate.py    THE CONTENT FIREWALL (blocklists + allowlist, fails closed)
    text.py        every string a poster may carry, derived from facts
    court.py       regulation court geometry in shot-chart units
    renderer.py    layout math + cairosvg export (300 DPI + previews)
    templates/     trajectory / blueprint / type SVG templates
  listing.py       titles, descriptions, SEO tags (validated)
  catalogue.py     bulk scan -> ranked folders + manifest.json
  publish/         Printify client, pricing, idempotent state, ship pipeline
  daily.py         morning scan -> drafts + notification
  notify.py        GitHub-issue / log notifiers
  cli.py           buzzer scan|render|catalogue|ship|daily|approve|printify
tests/             offline suite; fixtures generated by tests/fixtures/generate_fixtures.py
.github/workflows/daily-scan.yml   the hands-off cron
```

## Development

```bash
uv run pytest          # offline, ~5s
uv run mypy            # strict
uv run ruff check && uv run ruff format --check
```

Conventions: boring code over clever; every external call goes through
a mockable seam (`DataSource`, `TransportLike`, `Notifier`); every
mutation of the outside world is idempotent and logged; anything
customer-facing passes the content firewall and a human approval.

## Deliberate non-goals

No custom storefront, no payment handling, no order fulfilment — that
is Shopify's and Printify's job. No scraping beyond the public stats
API. No customer data touches this codebase.
