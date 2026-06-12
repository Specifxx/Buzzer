// Render a spread of facts through the JS port and write the SVGs out so
// scripts/validate_js_render.py can push them through the Python content
// firewall. Exits non-zero on any render error.
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const R = require(join(here, "..", "site", "buzzer-render.js"));

const base = {
  game_date: "2026-06-04",
  home_city: "Boston",
  away_city: "Denver",
  period: 4,
  clock: "0:01",
  home_score: 101,
  away_score: 100,
  scoring_side: "home",
  points: 3,
  margin_before: -2,
  takes_lead: true,
  ties_game: false,
  deficit_overcome: 13,
  is_playoff: true,
  shot_distance_ft: 27.0,
  shot_x: -221.0,
  shot_y: 155.0,
};

const variants = {
  flagship: base,
  overtime_tie: {
    ...base, period: 5, clock: "0:04", takes_lead: false, ties_game: true,
    home_score: 118, away_score: 118, shot_distance_ft: 18.0, shot_x: 110.0,
    shot_y: 120.0, home_city: "Phoenix", away_city: "Dallas",
  },
  heave: {
    ...base, period: 2, clock: "0:00", takes_lead: false, deficit_overcome: 0,
    is_playoff: false, shot_distance_ft: 52.0, shot_x: -40.0, shot_y: 520.0,
    home_score: 58, away_score: 55, home_city: "Cleveland", away_city: "Orlando",
  },
  no_coords: { ...base, shot_x: null, shot_y: null, shot_distance_ft: null },
};

const outDir = process.argv[2] || "/tmp/js_render_check";
mkdirSync(outDir, { recursive: true });

let count = 0;
for (const [name, facts] of Object.entries(variants)) {
  for (const style of R.STYLES) {
    for (const size of ["18x24", "24x36"]) {
      const svg = R.renderPoster(facts, style, size);
      if (!svg.startsWith("<svg")) throw new Error(`bad svg for ${name}/${style}`);
      writeFileSync(join(outDir, `${name}_${style}_${size}.svg`), svg);
      count += 1;
    }
  }
}
const score = R.scoreMoment(base);
if (score < 90) throw new Error(`flagship JS score ${score}, expected >= 90`);
console.log(`js render check: ${count} SVGs written to ${outDir}, flagship score ${score}`);
