/* Buzzer Studio — client-side poster renderer.
 *
 * A faithful JavaScript port of src/buzzer/render/{court,text,palettes,
 * renderer}.py and src/buzzer/scoring.py, so the gallery and Designer
 * render the same posters as the print pipeline. Cross-checked against
 * the Python content firewall in CI (scripts/check_js_render.mjs).
 *
 * Facts objects use the same snake_case keys as MomentFacts.
 */
(function (root) {
  "use strict";

  // ---- court geometry (tenths of feet, hoop at origin) -------------------
  const COURT = {
    HALF_WIDTH: 250.0,
    BASELINE_Y: -52.5,
    HALFCOURT_Y: 417.5,
    HOOP_RADIUS: 7.5,
    BACKBOARD_Y: -12.5,
    BACKBOARD_HALF_WIDTH: 30.0,
    THREE_RADIUS: 237.5,
    CORNER_THREE_X: 220.0,
    KEY_HALF_WIDTH: 80.0,
    FT_LINE_Y: 137.5,
    FT_CIRCLE_RADIUS: 60.0,
    RESTRICTED_RADIUS: 40.0,
  };
  COURT.CORNER_BREAK_Y = Math.sqrt(
    COURT.THREE_RADIUS ** 2 - COURT.CORNER_THREE_X ** 2
  );

  const px = (v) => Number(v).toFixed(1);
  const esc = (s) =>
    String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function courtMap(hoopX, hoopY, scale) {
    const X = (cx) => hoopX + cx * scale;
    const Y = (cy) => hoopY - cy * scale;
    const L = (len) => len * scale;
    const P = (cx, cy) => [X(cx), Y(cy)];
    return {
      x: X,
      y: Y,
      length: L,
      pt: P,
      threePointPath() {
        const [x0, y0] = P(-COURT.CORNER_THREE_X, COURT.BASELINE_Y);
        const [x1, y1] = P(-COURT.CORNER_THREE_X, COURT.CORNER_BREAK_Y);
        const [x2, y2] = P(COURT.CORNER_THREE_X, COURT.CORNER_BREAK_Y);
        const [x3, y3] = P(COURT.CORNER_THREE_X, COURT.BASELINE_Y);
        const r = L(COURT.THREE_RADIUS);
        return `M ${px(x0)} ${px(y0)} L ${px(x1)} ${px(y1)} A ${px(r)} ${px(r)} 0 0 1 ${px(x2)} ${px(y2)} L ${px(x3)} ${px(y3)}`;
      },
      keyPath() {
        const [x0, y0] = P(-COURT.KEY_HALF_WIDTH, COURT.BASELINE_Y);
        const [x1, y1] = P(-COURT.KEY_HALF_WIDTH, COURT.FT_LINE_Y);
        const [x2, y2] = P(COURT.KEY_HALF_WIDTH, COURT.FT_LINE_Y);
        const [x3, y3] = P(COURT.KEY_HALF_WIDTH, COURT.BASELINE_Y);
        return `M ${px(x0)} ${px(y0)} L ${px(x1)} ${px(y1)} L ${px(x2)} ${px(y2)} L ${px(x3)} ${px(y3)}`;
      },
      ftCirclePath() {
        const r = L(COURT.FT_CIRCLE_RADIUS);
        const [x0, y0] = P(-COURT.FT_CIRCLE_RADIUS, COURT.FT_LINE_Y);
        const [x1, y1] = P(COURT.FT_CIRCLE_RADIUS, COURT.FT_LINE_Y);
        return `M ${px(x0)} ${px(y0)} A ${px(r)} ${px(r)} 0 0 1 ${px(x1)} ${px(y1)}`;
      },
      restrictedPath() {
        const r = L(COURT.RESTRICTED_RADIUS);
        const [x0, y0] = P(-COURT.RESTRICTED_RADIUS, 0);
        const [x1, y1] = P(COURT.RESTRICTED_RADIUS, 0);
        return `M ${px(x0)} ${px(y0)} A ${px(r)} ${px(r)} 0 0 1 ${px(x1)} ${px(y1)}`;
      },
      baselineLine() {
        return [...P(-COURT.HALF_WIDTH, COURT.BASELINE_Y), ...P(COURT.HALF_WIDTH, COURT.BASELINE_Y)];
      },
      backboardLine() {
        return [
          ...P(-COURT.BACKBOARD_HALF_WIDTH, COURT.BACKBOARD_Y),
          ...P(COURT.BACKBOARD_HALF_WIDTH, COURT.BACKBOARD_Y),
        ];
      },
      sidelinePath() {
        const [x0, y0] = P(-COURT.HALF_WIDTH, COURT.HALFCOURT_Y);
        const [x1, y1] = P(-COURT.HALF_WIDTH, COURT.BASELINE_Y);
        const [x2, y2] = P(COURT.HALF_WIDTH, COURT.BASELINE_Y);
        const [x3, y3] = P(COURT.HALF_WIDTH, COURT.HALFCOURT_Y);
        return `M ${px(x0)} ${px(y0)} L ${px(x1)} ${px(y1)} L ${px(x2)} ${px(y2)} L ${px(x3)} ${px(y3)} Z`;
      },
      halfcourtCirclePath() {
        const r = L(COURT.FT_CIRCLE_RADIUS);
        const [x0, y0] = P(-COURT.FT_CIRCLE_RADIUS, COURT.HALFCOURT_Y);
        const [x1, y1] = P(COURT.FT_CIRCLE_RADIUS, COURT.HALFCOURT_Y);
        return `M ${px(x0)} ${px(y0)} A ${px(r)} ${px(r)} 0 0 0 ${px(x1)} ${px(y1)}`;
      },
    };
  }

  // ---- palettes (mirror of render/palettes.py) -----------------------------
  const PALETTES = [
    { name: "dusk", ink: "#1A1B26", paper: "#F2E9DC", accent: "#FF6B4A", accent2: "#FFC15E" },
    { name: "garden", ink: "#1E3A2F", paper: "#F4EBDD", accent: "#E8A33D", accent2: "#D6532B" },
    { name: "clay", ink: "#2B1D1A", paper: "#F4E7D3", accent: "#E2725B", accent2: "#9CAD7F" },
    { name: "midnight", ink: "#10151F", paper: "#E9E4D8", accent: "#4D9DE0", accent2: "#E15554" },
    { name: "royal", ink: "#221C35", paper: "#F2ECDF", accent: "#9B8CFF", accent2: "#FFB17A" },
    { name: "petrol", ink: "#0E2430", paper: "#EDE9DC", accent: "#5FC8BA", accent2: "#F2B33D" },
  ];

  function paletteFor(city) {
    let key = 0;
    for (const ch of city || "") key += ch.codePointAt(0);
    return PALETTES[key % PALETTES.length];
  }

  function darken(hex, factor) {
    const c = (i) =>
      Math.round(parseInt(hex.slice(i, i + 2), 16) * factor)
        .toString(16)
        .padStart(2, "0");
    return `#${c(1)}${c(3)}${c(5)}`.toUpperCase();
  }

  // ---- text derivation (port of render/text.py) ---------------------------
  const MONTHS = [
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
  ];

  function periodDisplay(period) {
    if (period <= 4) return `Q${period}`;
    const ot = period - 4;
    return ot === 1 ? "OT" : `${ot}OT`;
  }

  function dateDisplay(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return `${MONTHS[m - 1]} ${d}, ${y}`;
  }

  function posterText(f) {
    const away = (f.away_city || "AWAY").toUpperCase();
    const home = (f.home_city || "HOME").toUpperCase();
    return {
      date_line: dateDisplay(f.game_date),
      period_line: periodDisplay(f.period),
      clock_line: f.clock,
      cities_line: `${away} AT ${home}`,
      score_line: `${away} ${f.away_score} — ${home} ${f.home_score}`,
      stakes_line: f.is_playoff ? "PLAYOFFS" : "REGULAR SEASON",
      distance_line:
        f.shot_distance_ft != null ? `${f.shot_distance_ft.toFixed(0)} FT` : "",
      series_line:
        f.playoff_round != null && f.series_game != null
          ? `ROUND ${f.playoff_round} — GAME ${f.series_game}`
          : "",
      deficit_value:
        f.deficit_overcome >= 5 && (f.takes_lead || f.ties_game)
          ? String(f.deficit_overcome)
          : "",
      clock_value: f.clock,
    };
  }

  // ---- scoring (port of scoring.py) ---------------------------------------
  function clutchPoints(period, t) {
    if (period < 4) return 0;
    if (t <= 10) return 35 + (5 * (10 - t)) / 10;
    if (t <= 60) return 20 + (15 * (60 - t)) / 50;
    if (t <= 300) return (20 * (300 - t)) / 240;
    return 0;
  }

  function marginFactor(marginBefore) {
    const m = Math.abs(marginBefore);
    if (m <= 3) return 1.0;
    if (m <= 6) return 0.5;
    return 0.15;
  }

  function parseClock(clock) {
    const [m, s] = clock.split(":");
    return Number(m) * 60 + Number(s);
  }

  function scoreMoment(f) {
    const t = parseClock(f.clock);
    let score = clutchPoints(f.period, t) * marginFactor(f.margin_before);
    const late = f.period >= 4 ? 1.0 : 0.4;
    if (f.takes_lead) score += 20 * late;
    else if (f.ties_game) score += 10 * late;
    score += Math.max(0, 5 - Math.abs(f.margin_before));
    if (f.is_playoff) score += 15;
    if (f.period > 4) score += 5;
    if (f.takes_lead || f.ties_game)
      score += Math.min(f.deficit_overcome, 15) * late;
    if (f.shot_distance_ft != null) {
      if (f.shot_distance_ft >= 30) score += 8;
      else if (f.shot_distance_ft >= 25) score += 5;
    }
    if (f.playoff_round != null) score += (f.playoff_round - 1) * 2;
    if (f.series_game === 7) score += 8;
    return Math.max(0, Math.min(100, Math.round(score)));
  }

  // ---- shared layout -------------------------------------------------------
  const SIZES = { "12x16": [12, 16], "18x24": [18, 24], "24x36": [24, 36] };
  const DISPLAY = "Anton, Impact, Arial Narrow, sans-serif";
  const SANS = "Space Grotesk, Helvetica, Arial, sans-serif";
  const MONO = "Space Mono, DejaVu Sans Mono, Courier New, monospace";
  const ANTON_GLYPH_W = 0.54;

  function fitDisplay(text, maxWidth, cap) {
    return Math.min(cap, maxWidth / (ANTON_GLYPH_W * Math.max(text.length, 2)));
  }

  function shotCourtXY(f) {
    if (f.shot_x != null && f.shot_y != null) return [f.shot_x, f.shot_y];
    if (f.shot_distance_ft != null) return [0, f.shot_distance_ft * 10];
    return [0, COURT.FT_LINE_Y];
  }

  // ---- style: trajectory ---------------------------------------------------
  function trajectorySVG(f, w, h) {
    const text = posterText(f);
    const pal = paletteFor(f.home_city);
    const margin = 0.075 * w;
    const hair = Math.max(1.5, 0.0016 * w);
    const [sx, sy] = shotCourtXY(f);

    const hoopX = w / 2;
    const hoopY = 0.555 * h;
    const courtTop = 0.055 * h;
    const courtBottom = 0.735 * h;
    let scale = (0.86 * w) / (2 * COURT.HALF_WIDTH);
    if (sy * scale > hoopY - 0.09 * h) scale = (hoopY - 0.09 * h) / sy;

    const m = courtMap(hoopX, hoopY, scale);
    const [pxx, pyy] = m.pt(sx, sy);
    const distPx = Math.hypot(pxx - hoopX, pyy - hoopY);
    const arcPath = (lift) => {
      const mx = (pxx + hoopX) / 2;
      const my = (pyy + hoopY) / 2 - lift * distPx;
      return `M ${px(pxx)} ${px(pyy)} Q ${px(mx)} ${px(my)} ${px(hoopX)} ${px(hoopY)}`;
    };

    const shotRing = f.shot_distance_ft != null ? m.length(f.shot_distance_ft * 10) : null;
    const glowR = Math.max(shotRing || 0, m.length(220));
    const ringEls = [10, 20, 30]
      .map((ft, i) => {
        const tone = i % 2 ? pal.accent2 : pal.paper;
        const op = i % 2 ? 0.3 : 0.12;
        return `<circle cx="${px(hoopX)}" cy="${px(hoopY)}" r="${px(m.length(ft * 10))}" fill="none" stroke="${tone}" stroke-width="${px(hair)}" opacity="${op}"/>`;
      })
      .join("\n    ");
    const echoes = [
      { lift: 0.52, tone: pal.accent, width: 0.005 * w, alpha: 0.55 },
      { lift: 0.59, tone: pal.accent2, width: 0.0035 * w, alpha: 0.35 },
      { lift: 0.66, tone: pal.paper, width: 0.0025 * w, alpha: 0.16 },
    ]
      .map(
        (e) =>
          `<path d="${arcPath(e.lift)}" fill="none" stroke="${e.tone}" stroke-width="${px(e.width)}" opacity="${e.alpha}" stroke-linecap="round"/>`
      )
      .join("\n    ");

    const ruleY = 0.76 * h;
    const clockFs = fitDisplay(text.clock_line, 0.46 * w, 0.2 * w);
    const scoreFs = 0.034 * w;
    const footerFs = 0.016 * w;
    const bl = m.baselineLine();
    const bb = m.backboardLine();
    const footerRight = [
      text.period_line,
      text.series_line || text.stakes_line,
      text.distance_line,
    ]
      .filter(Boolean)
      .join(" — ");

    return `<svg xmlns="http://www.w3.org/2000/svg" width="${px(w)}" height="${px(h)}" viewBox="0 0 ${px(w)} ${px(h)}">
  <defs>
    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="${pal.accent}" stop-opacity="0.42"/>
      <stop offset="62%" stop-color="${pal.accent}" stop-opacity="0.16"/>
      <stop offset="100%" stop-color="${pal.accent}" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="court-zone">
      <rect x="0" y="${px(courtTop)}" width="${px(w)}" height="${px(courtBottom - courtTop)}"/>
    </clipPath>
  </defs>
  <rect x="0" y="0" width="${px(w)}" height="${px(h)}" fill="${pal.ink}"/>
  <g clip-path="url(#court-zone)">
    <circle cx="${px(hoopX)}" cy="${px(hoopY)}" r="${px(glowR)}" fill="url(#glow)"/>
    ${ringEls}
    ${shotRing ? `<circle cx="${px(hoopX)}" cy="${px(hoopY)}" r="${px(shotRing)}" fill="none" stroke="${pal.accent}" stroke-width="${px(hair * 1.8)}" opacity="0.85"/>` : ""}
    <path d="${m.threePointPath()}" fill="none" stroke="${pal.paper}" stroke-width="${px(hair)}" opacity="0.12"/>
    <line x1="${px(bl[0])}" y1="${px(bl[1])}" x2="${px(bl[2])}" y2="${px(bl[3])}" stroke="${pal.paper}" stroke-width="${px(hair)}" opacity="0.30"/>
    ${echoes}
    <path d="${arcPath(0.45)}" fill="none" stroke="${pal.paper}" stroke-width="${px(0.0085 * w)}" stroke-linecap="round"/>
    <line x1="${px(bb[0])}" y1="${px(bb[1])}" x2="${px(bb[2])}" y2="${px(bb[3])}" stroke="${pal.paper}" stroke-width="${px(hair * 2.4)}"/>
    <circle cx="${px(hoopX)}" cy="${px(hoopY)}" r="${px(m.length(COURT.HOOP_RADIUS))}" fill="none" stroke="${pal.paper}" stroke-width="${px(hair * 2)}"/>
    <circle cx="${px(pxx)}" cy="${px(pyy)}" r="${px(0.015 * w * 1.9)}" fill="none" stroke="${pal.accent2}" stroke-width="${px(hair)}" opacity="0.8"/>
    <circle cx="${px(pxx)}" cy="${px(pyy)}" r="${px(0.015 * w)}" fill="${pal.accent2}" stroke="${pal.ink}" stroke-width="${px(hair)}"/>
  </g>
  <line x1="${px(margin)}" y1="${px(ruleY)}" x2="${px(w - margin)}" y2="${px(ruleY)}" stroke="${pal.accent}" stroke-width="${px(hair * 3)}"/>
  <text x="${px(margin)}" y="${px(ruleY + 0.018 * h + clockFs * 0.8)}" font-family="${DISPLAY}" font-size="${px(clockFs)}" fill="${pal.paper}">${esc(text.clock_line)}</text>
  <text x="${px(w - margin)}" y="${px(ruleY + 0.052 * h)}" font-family="${SANS}" font-weight="700" font-size="${px(scoreFs)}" fill="${pal.paper}" text-anchor="end" letter-spacing="${px(scoreFs * 0.05)}">${esc((f.away_city || "AWAY").toUpperCase())} ${f.away_score}</text>
  <text x="${px(w - margin)}" y="${px(ruleY + 0.052 * h + 0.046 * w)}" font-family="${SANS}" font-weight="700" font-size="${px(scoreFs)}" fill="${pal.accent2}" text-anchor="end" letter-spacing="${px(scoreFs * 0.05)}">${esc((f.home_city || "HOME").toUpperCase())} ${f.home_score}</text>
  <text x="${px(margin)}" y="${px(0.948 * h)}" font-family="${MONO}" font-size="${px(footerFs)}" fill="${pal.paper}" opacity="0.65" letter-spacing="${px(footerFs * 0.18)}">${esc(text.date_line)}</text>
  <text x="${px(w - margin)}" y="${px(0.948 * h)}" font-family="${MONO}" font-size="${px(footerFs)}" fill="${pal.accent2}" text-anchor="end" letter-spacing="${px(footerFs * 0.18)}">${esc(footerRight)}</text>
</svg>`;
  }

  // ---- style: blueprint ----------------------------------------------------
  function blueprintSVG(f, w, h) {
    const text = posterText(f);
    const pal = paletteFor(f.home_city);
    const mark = darken(pal.accent2, 0.62);
    const margin = 0.075 * w;
    const hair = Math.max(1.5, 0.0016 * w);
    let [sx, sy] = shotCourtXY(f);
    sy = Math.min(sy, COURT.HALFCOURT_Y - 10);

    const scale = (0.78 * w) / (2 * COURT.HALF_WIDTH);
    const hoopY = 0.165 * h + COURT.HALFCOURT_Y * scale;
    const m = courtMap(w / 2, hoopY, scale);
    const [pxx, pyy] = m.pt(sx, sy);
    const [hx, hy] = m.pt(0, 0);

    const gridStep = w / 28;
    const blockTop = m.y(COURT.BASELINE_Y) + 0.052 * h;
    const blockH = h - margin * 0.85 - blockTop;
    const drawnRatio = Math.round((50 * 12) / (0.78 * (w / 100)));

    let title;
    if (f.takes_lead) title = "GO-AHEAD FIELD GOAL";
    else if (f.ties_game) title = "GAME-TIED FIELD GOAL";
    else title = "FIELD GOAL";

    const cells = [
      ["TITLE", title],
      ["SCORE", text.score_line],
      ["DATE", text.date_line],
      ["LOCATION", (f.home_city || "HOME").toUpperCase()],
      ["TIME", `${text.period_line} — ${f.clock} REMAINING`],
      ["SCALE", `1:${drawnRatio} — SHEET 1 OF 1`],
    ];
    const cellW = (w - 2 * margin) / 3;
    const cellH = blockH / 2;
    const labelFs = 0.0115 * w, valueFs = 0.0155 * w, monoFs = 0.014 * w;
    const headFs = 0.05 * w, subFs = 0.017 * w;
    const courtStroke = Math.max(2, 0.0028 * w);
    const bb = m.backboardLine();
    const cross = 0.016 * w;
    const reg = 0.011 * w;
    const coordX = Math.min(Math.max(pxx, 0.17 * w), 0.83 * w);
    const cwY = m.y(COURT.BASELINE_Y) + 0.03 * h;
    const cl = m.x(-COURT.HALF_WIDTH), cr = m.x(COURT.HALF_WIDTH);
    const coordLabel = `X ${sx >= 0 ? "+" : ""}${(sx / 10).toFixed(1)} FT — Y ${sy >= 0 ? "+" : ""}${(sy / 10).toFixed(1)} FT`;
    const dimLabel = text.distance_line || `${f.points} POINTS`;

    const gridLines = [];
    for (let gx = gridStep; gx < w; gx += gridStep)
      gridLines.push(`<line x1="${px(gx)}" y1="0" x2="${px(gx)}" y2="${px(h)}" stroke="${pal.ink}" stroke-width="${px(hair * 0.45)}" opacity="0.10"/>`);
    for (let gy = gridStep; gy < h; gy += gridStep)
      gridLines.push(`<line x1="0" y1="${px(gy)}" x2="${px(w)}" y2="${px(gy)}" stroke="${pal.ink}" stroke-width="${px(hair * 0.45)}" opacity="0.10"/>`);

    const regPts = [
      [margin * 0.45, margin * 0.45],
      [w - margin * 0.45, margin * 0.45],
      [margin * 0.45, h - margin * 0.45],
      [w - margin * 0.45, h - margin * 0.45],
    ];
    const regEls = regPts
      .map(
        ([rx, ry]) => `<line x1="${px(rx - reg)}" y1="${px(ry)}" x2="${px(rx + reg)}" y2="${px(ry)}" stroke="${mark}" stroke-width="${px(hair)}"/>
  <line x1="${px(rx)}" y1="${px(ry - reg)}" x2="${px(rx)}" y2="${px(ry + reg)}" stroke="${mark}" stroke-width="${px(hair)}"/>`
      )
      .join("\n  ");

    const cellEls = cells
      .map(([label, value], i) => {
        const cx = margin + (i % 3) * cellW;
        const cy = blockTop + Math.floor(i / 3) * cellH;
        return `<text x="${px(cx + labelFs)}" y="${px(cy + cellH * 0.34)}" font-family="${MONO}" font-size="${px(labelFs)}" fill="${pal.ink}" opacity="0.55" letter-spacing="${px(labelFs * 0.2)}">${esc(label)}</text>
    <text x="${px(cx + labelFs)}" y="${px(cy + cellH * 0.72)}" font-family="${SANS}" font-weight="700" font-size="${px(valueFs)}" fill="${pal.ink}">${esc(value)}</text>`;
      })
      .join("\n    ");

    return `<svg xmlns="http://www.w3.org/2000/svg" width="${px(w)}" height="${px(h)}" viewBox="0 0 ${px(w)} ${px(h)}">
  <rect x="0" y="0" width="${px(w)}" height="${px(h)}" fill="${pal.paper}"/>
  ${gridLines.join("\n  ")}
  ${regEls}
  <text x="${px(margin)}" y="${px(margin + 0.046 * w)}" font-family="${DISPLAY}" font-size="${px(headFs)}" fill="${pal.ink}">HALF COURT — PLAN VIEW</text>
  <text x="${px(margin)}" y="${px(margin + 0.08 * w)}" font-family="${MONO}" font-size="${px(subFs)}" fill="${mark}" letter-spacing="${px(subFs * 0.18)}">${esc([text.stakes_line, text.series_line, text.cities_line].filter(Boolean).join(" — "))}</text>
  <g fill="none" stroke="${pal.ink}" stroke-width="${px(courtStroke)}" stroke-linejoin="round" stroke-linecap="round">
    <path d="${m.sidelinePath()}"/>
    <path d="${m.halfcourtCirclePath()}"/>
    <path d="${m.threePointPath()}"/>
    <path d="${m.keyPath()}"/>
    <path d="${m.ftCirclePath()}"/>
    <path d="${m.restrictedPath()}"/>
    <line x1="${px(bb[0])}" y1="${px(bb[1])}" x2="${px(bb[2])}" y2="${px(bb[3])}"/>
    <circle cx="${px(hx)}" cy="${px(hy)}" r="${px(m.length(COURT.HOOP_RADIUS))}"/>
  </g>
  <line x1="${px(pxx)}" y1="${px(pyy)}" x2="${px(hx)}" y2="${px(hy)}" stroke="${mark}" stroke-width="${px(hair * 1.4)}" stroke-dasharray="${px(hair * 6)} ${px(hair * 4)}"/>
  <circle cx="${px(hx)}" cy="${px(hy)}" r="${px(hair * 2.6)}" fill="${mark}"/>
  <circle cx="${px(pxx)}" cy="${px(pyy)}" r="${px(hair * 2.6)}" fill="${mark}"/>
  <line x1="${px(pxx - cross)}" y1="${px(pyy)}" x2="${px(pxx + cross)}" y2="${px(pyy)}" stroke="${mark}" stroke-width="${px(hair)}"/>
  <line x1="${px(pxx)}" y1="${px(pyy - cross)}" x2="${px(pxx)}" y2="${px(pyy + cross)}" stroke="${mark}" stroke-width="${px(hair)}"/>
  <circle cx="${px(pxx)}" cy="${px(pyy)}" r="${px(cross * 0.62)}" fill="none" stroke="${mark}" stroke-width="${px(hair)}"/>
  <text x="${px(coordX)}" y="${px(pyy - 0.026 * w)}" font-family="${MONO}" font-size="${px(monoFs)}" fill="${mark}" text-anchor="middle">${esc(coordLabel)}</text>
  <text x="${px((pxx + hx) / 2 + 0.03 * w)}" y="${px((pyy + hy) / 2)}" font-family="${MONO}" font-weight="700" font-size="${px(monoFs * 1.35)}" fill="${mark}">${esc(dimLabel)}</text>
  <line x1="${px(cl)}" y1="${px(cwY)}" x2="${px(cr)}" y2="${px(cwY)}" stroke="${pal.ink}" stroke-width="${px(hair * 0.8)}"/>
  <line x1="${px(cl)}" y1="${px(cwY - hair * 5)}" x2="${px(cl)}" y2="${px(cwY + hair * 5)}" stroke="${pal.ink}" stroke-width="${px(hair * 0.8)}"/>
  <line x1="${px(cr)}" y1="${px(cwY - hair * 5)}" x2="${px(cr)}" y2="${px(cwY + hair * 5)}" stroke="${pal.ink}" stroke-width="${px(hair * 0.8)}"/>
  <text x="${px(w / 2)}" y="${px(cwY - monoFs * 0.6)}" font-family="${MONO}" font-size="${px(monoFs)}" fill="${pal.ink}" text-anchor="middle">50 FT</text>
  <g>
    <rect x="${px(margin)}" y="${px(blockTop)}" width="${px(w - margin * 2)}" height="${px(blockH)}" fill="none" stroke="${pal.ink}" stroke-width="${px(hair * 1.6)}"/>
    <line x1="${px(margin)}" y1="${px(blockTop + cellH)}" x2="${px(w - margin)}" y2="${px(blockTop + cellH)}" stroke="${pal.ink}" stroke-width="${px(hair * 0.8)}"/>
    <line x1="${px(margin + cellW)}" y1="${px(blockTop)}" x2="${px(margin + cellW)}" y2="${px(blockTop + blockH)}" stroke="${pal.ink}" stroke-width="${px(hair * 0.8)}"/>
    <line x1="${px(margin + cellW * 2)}" y1="${px(blockTop)}" x2="${px(margin + cellW * 2)}" y2="${px(blockTop + blockH)}" stroke="${pal.ink}" stroke-width="${px(hair * 0.8)}"/>
    ${cellEls}
  </g>
</svg>`;
  }

  // ---- style: type -----------------------------------------------------------
  function typeSVG(f, w, h) {
    const text = posterText(f);
    const pal = paletteFor(f.home_city);
    const margin = 0.075 * w;
    const cw = w - 2 * margin;
    const footerFs = 0.0165 * w;

    const stack = [[text.clock_value, pal.paper]];
    if (f.series_game === 7) stack.push(["GAME 7", pal.accent]);
    if (text.deficit_value) stack.push([`DOWN ${text.deficit_value}`, pal.accent]);
    if (f.shot_distance_ft != null && f.shot_distance_ft >= 1)
      stack.push([`FROM ${f.shot_distance_ft.toFixed(0)} FEET`, pal.paper]);
    if (f.takes_lead) stack.push(["FOR THE LEAD", pal.accent2]);
    else if (f.ties_game) stack.push(["TIES THE GAME", pal.accent2]);
    else stack.push([`${f.points} POINTS`, pal.accent2]);

    let sizes = stack.map(([value]) => fitDisplay(value, cw, 0.175 * h));
    let natural = sizes.reduce((acc, fs) => acc + fs * 1.04, 0);
    const stackTop = 0.07 * h, stackBottom = 0.715 * h;
    const zone = stackBottom - stackTop;
    if (natural > zone) {
      sizes = sizes.map((fs) => (fs * zone) / natural);
      natural = zone;
    }
    const gapExtra = Math.max(0, zone - natural) / Math.max(stack.length, 1);

    let cursor = stackTop;
    const lineEls = stack
      .map(([value, tone], i) => {
        const fs = sizes[i];
        cursor += fs * 0.84;
        const el = `<text x="${px(margin)}" y="${px(cursor)}" font-family="${DISPLAY}" font-size="${px(fs)}" fill="${tone}">${esc(value)}</text>`;
        cursor += fs * 0.2 + gapExtra;
        return el;
      })
      .join("\n  ");

    const bandTop = 0.755 * h;
    const bandH = 0.085 * h;
    const bandText = text.score_line;
    const bandFs = Math.min(bandH * 0.56, (cw * 0.94) / (ANTON_GLYPH_W * Math.max(bandText.length, 2)));

    return `<svg xmlns="http://www.w3.org/2000/svg" width="${px(w)}" height="${px(h)}" viewBox="0 0 ${px(w)} ${px(h)}">
  <rect x="0" y="0" width="${px(w)}" height="${px(h)}" fill="${pal.ink}"/>
  ${lineEls}
  <rect x="0" y="${px(bandTop)}" width="${px(w)}" height="${px(bandH)}" fill="${pal.accent}"/>
  <text x="${px(w / 2)}" y="${px(bandTop + bandH / 2 + bandFs * 0.34)}" font-family="${DISPLAY}" font-size="${px(bandFs)}" fill="${pal.ink}" text-anchor="middle" letter-spacing="${px(bandFs * 0.02)}">${esc(bandText)}</text>
  <text x="${px(margin)}" y="${px(0.945 * h)}" font-family="${MONO}" font-size="${px(footerFs)}" fill="${pal.paper}" opacity="0.7" letter-spacing="${px(footerFs * 0.16)}">${esc(text.date_line)}</text>
  <text x="${px(w / 2)}" y="${px(0.945 * h)}" font-family="${MONO}" font-size="${px(footerFs)}" fill="${pal.accent2}" text-anchor="middle" letter-spacing="${px(footerFs * 0.16)}">${esc(text.series_line || text.stakes_line)}</text>
  <text x="${px(w - margin)}" y="${px(0.945 * h)}" font-family="${MONO}" font-size="${px(footerFs)}" fill="${pal.paper}" opacity="0.7" text-anchor="end" letter-spacing="${px(footerFs * 0.16)}">${esc(text.period_line)} — ${esc(f.clock)}</text>
</svg>`;
  }

  // ---- public API -------------------------------------------------------------
  const RENDERERS = { trajectory: trajectorySVG, blueprint: blueprintSVG, type: typeSVG };

  function renderPoster(facts, style, size) {
    const dims = SIZES[size];
    if (!dims) throw new Error(`unknown size ${size}`);
    const fn = RENDERERS[style];
    if (!fn) throw new Error(`unknown style ${style}`);
    return fn(facts, dims[0] * 100, dims[1] * 100);
  }

  const api = {
    renderPoster,
    scoreMoment,
    parseClock,
    periodDisplay,
    dateDisplay,
    courtMap,
    paletteFor,
    COURT,
    SIZES,
    STYLES: ["trajectory", "blueprint", "type"],
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.BuzzerRender = api;
})(typeof window !== "undefined" ? window : globalThis);
