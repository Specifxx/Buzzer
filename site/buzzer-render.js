/* Buzzer Studio — client-side poster renderer.
 *
 * A faithful JavaScript port of src/buzzer/render/{court,text,renderer}.py
 * and src/buzzer/scoring.py, so the Designer tab can re-render posters
 * live in the browser. The Python pipeline remains the source of truth
 * for anything that ships; this port exists for interactive preview and
 * is cross-checked against the Python validator in CI
 * (scripts/check_js_render.mjs).
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
    return Math.max(0, Math.min(100, Math.round(score)));
  }

  // ---- shared layout -------------------------------------------------------
  const SIZES = { "12x16": [12, 16], "18x24": [18, 24], "24x36": [24, 36] };
  const SANS = "DejaVu Sans, Helvetica, Arial, sans-serif";
  const MONO = "DejaVu Sans Mono, Courier New, monospace";

  function shotCourtXY(f) {
    if (f.shot_x != null && f.shot_y != null) return [f.shot_x, f.shot_y];
    if (f.shot_distance_ft != null) return [0, f.shot_distance_ft * 10];
    return [0, COURT.FT_LINE_Y];
  }

  // ---- style: trajectory ---------------------------------------------------
  function trajectorySVG(f, w, h) {
    const text = posterText(f);
    const margin = 0.07 * w;
    const hair = Math.max(1.5, 0.0016 * w);
    const [sx, sy] = shotCourtXY(f);

    const hoopX = w / 2;
    const hoopY = 0.66 * h;
    const topSafe = 0.34 * h;
    let scale = (0.86 * w) / (2 * COURT.HALF_WIDTH);
    const maxCourtY = (hoopY - topSafe) / scale;
    if (sy > maxCourtY) scale = (hoopY - topSafe) / sy;

    const m = courtMap(hoopX, hoopY, scale);
    const [pxx, pyy] = m.pt(sx, sy);
    const distPx = Math.hypot(pxx - hoopX, pyy - hoopY);
    const midX = (pxx + hoopX) / 2;
    const midY = (pyy + hoopY) / 2 - 0.45 * distPx;

    const rings = [m.length(100), m.length(200), m.length(300)];
    const shotRing =
      f.shot_distance_ft != null ? m.length(f.shot_distance_ft * 10) : null;
    const clockFs = 0.2 * w;
    const headFs = 0.026 * w;
    const scoreFs = 0.03 * w;
    const footerFs = 0.018 * w;
    const bl = m.baselineLine();
    const bb = m.backboardLine();
    const ink = "#ece7db", faint = "#33363e", accent = "#d96f4e";

    const ringEls = rings
      .map(
        (r) =>
          `<circle cx="${px(hoopX)}" cy="${px(hoopY)}" r="${px(r)}" fill="none" stroke="${faint}" stroke-width="${px(hair)}" stroke-dasharray="${px(hair * 3)} ${px(hair * 7)}"/>`
      )
      .join("\n    ");
    const shotRingEl = shotRing
      ? `<circle cx="${px(hoopX)}" cy="${px(hoopY)}" r="${px(shotRing)}" fill="none" stroke="${accent}" stroke-width="${px(hair)}" opacity="0.45" stroke-dasharray="${px(hair * 5)} ${px(hair * 5)}"/>`
      : "";
    const distLabel = text.distance_line
      ? `<text x="${px(pxx + (pxx < w / 2 ? 0.03 * w : -0.03 * w))}" y="${px(pyy - 0.03 * w)}" font-family="${MONO}" font-size="${px(footerFs)}" fill="${accent}" text-anchor="${pxx < w / 2 ? "start" : "end"}" letter-spacing="${px(footerFs * 0.25)}">${esc(text.distance_line)}</text>`
      : "";

    return `<svg xmlns="http://www.w3.org/2000/svg" width="${px(w)}" height="${px(h)}" viewBox="0 0 ${px(w)} ${px(h)}">
  <defs>
    <clipPath id="court-zone">
      <rect x="0" y="${px(topSafe)}" width="${px(w)}" height="${px(0.85 * h - topSafe)}"/>
    </clipPath>
  </defs>
  <rect x="0" y="0" width="${px(w)}" height="${px(h)}" fill="#101115"/>
  <g clip-path="url(#court-zone)">
    ${ringEls}
    ${shotRingEl}
    <path d="${m.threePointPath()}" fill="none" stroke="${faint}" stroke-width="${px(hair)}"/>
    <line x1="${px(bl[0])}" y1="${px(bl[1])}" x2="${px(bl[2])}" y2="${px(bl[3])}" stroke="${ink}" stroke-width="${px(hair)}" opacity="0.6"/>
    <line x1="${px(bb[0])}" y1="${px(bb[1])}" x2="${px(bb[2])}" y2="${px(bb[3])}" stroke="${ink}" stroke-width="${px(hair * 2)}"/>
    <circle cx="${px(hoopX)}" cy="${px(hoopY)}" r="${px(m.length(COURT.HOOP_RADIUS))}" fill="none" stroke="${ink}" stroke-width="${px(hair * 1.6)}"/>
    <path d="M ${px(pxx)} ${px(pyy)} Q ${px(midX)} ${px(midY)} ${px(hoopX)} ${px(hoopY)}" fill="none" stroke="${accent}" stroke-width="${px(hair * 2.4)}" stroke-dasharray="${px(hair * 7)} ${px(hair * 5)}" stroke-linecap="round"/>
    <circle cx="${px(pxx)}" cy="${px(pyy)}" r="${px(0.022 * w)}" fill="none" stroke="${accent}" stroke-width="${px(hair)}" opacity="0.6"/>
    <circle cx="${px(pxx)}" cy="${px(pyy)}" r="${px(0.011 * w)}" fill="${accent}"/>
  </g>
  ${distLabel}
  <text x="${px(margin)}" y="${px(margin + clockFs * 0.92)}" font-family="${SANS}" font-weight="bold" font-size="${px(clockFs)}" fill="${ink}">${esc(text.clock_line)}</text>
  <text x="${px(w - margin)}" y="${px(margin + 0.03 * w)}" font-family="${SANS}" font-weight="bold" font-size="${px(headFs)}" fill="${ink}" text-anchor="end" letter-spacing="${px(headFs * 0.2)}">${esc(text.period_line)}</text>
  <text x="${px(w - margin)}" y="${px(margin + 0.064 * w)}" font-family="${SANS}" font-size="${px(headFs * 0.62)}" fill="${accent}" text-anchor="end" letter-spacing="${px(headFs * 0.16)}">${esc(text.stakes_line)}</text>
  <text x="${px(w / 2)}" y="${px(0.895 * h)}" font-family="${SANS}" font-weight="bold" font-size="${px(scoreFs)}" fill="${ink}" text-anchor="middle" letter-spacing="${px(scoreFs * 0.08)}">${esc(text.score_line)}</text>
  <text x="${px(w / 2)}" y="${px(0.932 * h)}" font-family="${MONO}" font-size="${px(footerFs)}" fill="${ink}" text-anchor="middle" opacity="0.75" letter-spacing="${px(footerFs * 0.2)}">${esc(text.date_line)}</text>
</svg>`;
  }

  // ---- style: blueprint ----------------------------------------------------
  function blueprintSVG(f, w, h) {
    const text = posterText(f);
    const margin = 0.07 * w;
    const hair = Math.max(1.5, 0.0016 * w);
    let [sx, sy] = shotCourtXY(f);
    sy = Math.min(sy, COURT.HALFCOURT_Y - 10);

    const scale = (0.78 * w) / (2 * COURT.HALF_WIDTH);
    const hoopY = 0.15 * h + COURT.HALFCOURT_Y * scale;
    const m = courtMap(w / 2, hoopY, scale);
    const [pxx, pyy] = m.pt(sx, sy);
    const [hx, hy] = m.pt(0, 0);

    const gridStep = w / 24;
    const titleTop = m.y(COURT.BASELINE_Y) + 0.05 * h;
    const titleH = h - margin - titleTop;
    const drawnRatio = Math.round((50 * 12) / (0.78 * (w / 100)));

    let title;
    if (f.takes_lead) title = `GO-AHEAD FIELD GOAL — ${f.points} POINTS`;
    else if (f.ties_game)
      title = `FIELD GOAL TIES THE GAME — ${f.points} POINTS`;
    else title = `FIELD GOAL — ${f.points} POINTS`;

    const rows = [
      ["TITLE", title],
      ["DATE", text.date_line],
      ["LOCATION", (f.home_city || "HOME").toUpperCase()],
      ["SCORE", text.score_line],
      ["TIME", `${text.period_line} — ${f.clock} REMAINING`],
      ["SCALE", `1:${drawnRatio} — SHEET 1 OF 1`],
    ];
    const rowH = titleH / rows.length;
    const labelFs = 0.0135 * w, valueFs = 0.019 * w, monoFs = 0.014 * w;
    const headFs = 0.03 * w, subFs = 0.0165 * w;
    const courtStroke = Math.max(2, 0.0022 * w);
    const ink = "#21405f", faint = "#b9c4d2", accent = "#b3402e";
    const bb = m.backboardLine();
    const cross = 0.016 * w;
    const coordX = Math.min(Math.max(pxx, 0.16 * w), 0.84 * w);
    const cwY = m.y(COURT.BASELINE_Y) + 0.03 * h;
    const cl = m.x(-COURT.HALF_WIDTH), cr = m.x(COURT.HALF_WIDTH);
    const coordLabel = `X ${sx >= 0 ? "+" : ""}${(sx / 10).toFixed(1)} FT — Y ${sy >= 0 ? "+" : ""}${(sy / 10).toFixed(1)} FT`;
    const dimLabel = text.distance_line || `${f.points} POINTS`;

    const gridLines = [];
    for (let gx = gridStep; gx < w; gx += gridStep)
      gridLines.push(
        `<line x1="${px(gx)}" y1="0" x2="${px(gx)}" y2="${px(h)}" stroke="${faint}" stroke-width="${px(hair * 0.5)}" opacity="0.45"/>`
      );
    for (let gy = gridStep; gy < h; gy += gridStep)
      gridLines.push(
        `<line x1="0" y1="${px(gy)}" x2="${px(w)}" y2="${px(gy)}" stroke="${faint}" stroke-width="${px(hair * 0.5)}" opacity="0.45"/>`
      );

    const rowEls = rows
      .map(([label, value], i) => {
        const rowY = titleTop + i * rowH;
        const rule =
          i === 0
            ? ""
            : `<line x1="${px(margin)}" y1="${px(rowY)}" x2="${px(w - margin)}" y2="${px(rowY)}" stroke="${ink}" stroke-width="${px(hair * 0.7)}"/>`;
        return `${rule}
    <text x="${px(margin + labelFs)}" y="${px(rowY + rowH * 0.62)}" font-family="${MONO}" font-size="${px(labelFs)}" fill="${ink}" opacity="0.7" letter-spacing="${px(labelFs * 0.2)}">${esc(label)}</text>
    <text x="${px(margin + (w - margin * 2) * 0.22)}" y="${px(rowY + rowH * 0.64)}" font-family="${MONO}" font-weight="bold" font-size="${px(valueFs)}" fill="${ink}" letter-spacing="${px(valueFs * 0.06)}">${esc(value)}</text>`;
      })
      .join("\n    ");

    return `<svg xmlns="http://www.w3.org/2000/svg" width="${px(w)}" height="${px(h)}" viewBox="0 0 ${px(w)} ${px(h)}">
  <rect x="0" y="0" width="${px(w)}" height="${px(h)}" fill="#f3f0e8"/>
  ${gridLines.join("\n  ")}
  <rect x="${px(margin * 0.5)}" y="${px(margin * 0.5)}" width="${px(w - margin)}" height="${px(h - margin)}" fill="none" stroke="${ink}" stroke-width="${px(hair * 1.4)}"/>
  <text x="${px(margin)}" y="${px(margin + 0.02 * w)}" font-family="${MONO}" font-weight="bold" font-size="${px(headFs)}" fill="${ink}" letter-spacing="${px(headFs * 0.18)}">HALF COURT — PLAN VIEW</text>
  <text x="${px(margin)}" y="${px(margin + 0.052 * w)}" font-family="${MONO}" font-size="${px(subFs)}" fill="${ink}" opacity="0.8" letter-spacing="${px(subFs * 0.2)}">${esc(text.stakes_line)} — ${esc(text.cities_line)}</text>
  <g fill="none" stroke="${ink}" stroke-width="${px(courtStroke)}">
    <path d="${m.sidelinePath()}"/>
    <path d="${m.halfcourtCirclePath()}"/>
    <path d="${m.threePointPath()}"/>
    <path d="${m.keyPath()}"/>
    <path d="${m.ftCirclePath()}"/>
    <path d="${m.restrictedPath()}"/>
    <line x1="${px(bb[0])}" y1="${px(bb[1])}" x2="${px(bb[2])}" y2="${px(bb[3])}"/>
    <circle cx="${px(hx)}" cy="${px(hy)}" r="${px(m.length(COURT.HOOP_RADIUS))}"/>
  </g>
  <line x1="${px(pxx)}" y1="${px(pyy)}" x2="${px(hx)}" y2="${px(hy)}" stroke="${accent}" stroke-width="${px(hair * 1.3)}" stroke-dasharray="${px(hair * 6)} ${px(hair * 4)}"/>
  <circle cx="${px(hx)}" cy="${px(hy)}" r="${px(hair * 2.5)}" fill="${accent}"/>
  <circle cx="${px(pxx)}" cy="${px(pyy)}" r="${px(hair * 2.5)}" fill="${accent}"/>
  <line x1="${px(pxx - cross)}" y1="${px(pyy)}" x2="${px(pxx + cross)}" y2="${px(pyy)}" stroke="${accent}" stroke-width="${px(hair)}"/>
  <line x1="${px(pxx)}" y1="${px(pyy - cross)}" x2="${px(pxx)}" y2="${px(pyy + cross)}" stroke="${accent}" stroke-width="${px(hair)}"/>
  <circle cx="${px(pxx)}" cy="${px(pyy)}" r="${px(cross * 0.62)}" fill="none" stroke="${accent}" stroke-width="${px(hair)}"/>
  <text x="${px(coordX)}" y="${px(pyy - 0.024 * w)}" font-family="${MONO}" font-size="${px(monoFs)}" fill="${accent}" text-anchor="middle" letter-spacing="${px(monoFs * 0.08)}">${esc(coordLabel)}</text>
  <text x="${px((pxx + hx) / 2 + 0.03 * w)}" y="${px((pyy + hy) / 2)}" font-family="${MONO}" font-weight="bold" font-size="${px(monoFs * 1.3)}" fill="${accent}" letter-spacing="${px(monoFs * 0.12)}">${esc(dimLabel)}</text>
  <line x1="${px(cl)}" y1="${px(cwY)}" x2="${px(cr)}" y2="${px(cwY)}" stroke="${ink}" stroke-width="${px(hair * 0.8)}"/>
  <line x1="${px(cl)}" y1="${px(cwY - hair * 5)}" x2="${px(cl)}" y2="${px(cwY + hair * 5)}" stroke="${ink}" stroke-width="${px(hair * 0.8)}"/>
  <line x1="${px(cr)}" y1="${px(cwY - hair * 5)}" x2="${px(cr)}" y2="${px(cwY + hair * 5)}" stroke="${ink}" stroke-width="${px(hair * 0.8)}"/>
  <text x="${px(w / 2)}" y="${px(cwY - monoFs * 0.6)}" font-family="${MONO}" font-size="${px(monoFs)}" fill="${ink}" text-anchor="middle">50 FT</text>
  <g>
    <rect x="${px(margin)}" y="${px(titleTop)}" width="${px(w - margin * 2)}" height="${px(titleH)}" fill="none" stroke="${ink}" stroke-width="${px(hair * 1.4)}"/>
    ${rowEls}
  </g>
</svg>`;
  }

  // ---- style: type -----------------------------------------------------------
  function typeSVG(f, w, h) {
    const text = posterText(f);
    const margin = 0.07 * w;
    const hair = Math.max(1.5, 0.0016 * w);
    const ink = "#16161a", accent = "#c2391f";

    const rows = [[text.clock_value, `${text.period_line} — ON THE CLOCK`]];
    if (text.deficit_value) rows.push([text.deficit_value, "POINT DEFICIT"]);
    if (f.shot_distance_ft != null)
      rows.push([f.shot_distance_ft.toFixed(0), "FOOT SHOT"]);
    if (f.takes_lead) rows.push([String(f.points), "POINTS FOR THE LEAD"]);
    else if (f.ties_game) rows.push([String(f.points), "POINTS TO TIE THE GAME"]);
    else rows.push([String(f.points), "POINTS"]);

    const zoneTop = 0.135 * h, zoneBottom = 0.82 * h;
    const rowH = (zoneBottom - zoneTop) / rows.length;
    const headFs = 0.024 * w, captionFs = 0.02 * w;
    const scoreFs = 0.03 * w, footerFs = 0.0175 * w;

    const rowEls = rows
      .map(([value, caption], i) => {
        const fs = Math.min(rowH * 0.66, (0.82 * w) / (0.62 * Math.max(value.length, 2)));
        const y = zoneTop + i * rowH;
        return `<line x1="${px(margin)}" y1="${px(y)}" x2="${px(w - margin)}" y2="${px(y)}" stroke="${ink}" stroke-width="${px(hair * 1.2)}"/>
  <text x="${px(margin)}" y="${px(y + rowH * 0.3 + fs * 0.36)}" font-family="${SANS}" font-weight="bold" font-size="${px(fs)}" fill="${ink}" letter-spacing="${px(fs * -0.02)}">${esc(value)}</text>
  <text x="${px(w - margin)}" y="${px(y + rowH * 0.86)}" font-family="${MONO}" font-size="${px(captionFs)}" fill="${accent}" text-anchor="end" letter-spacing="${px(captionFs * 0.22)}">${esc(caption)}</text>`;
      })
      .join("\n  ");

    return `<svg xmlns="http://www.w3.org/2000/svg" width="${px(w)}" height="${px(h)}" viewBox="0 0 ${px(w)} ${px(h)}">
  <rect x="0" y="0" width="${px(w)}" height="${px(h)}" fill="#efe9dc"/>
  <text x="${px(margin)}" y="${px(0.075 * h)}" font-family="${SANS}" font-weight="bold" font-size="${px(headFs)}" fill="${ink}" letter-spacing="${px(headFs * 0.18)}">${esc(text.stakes_line)}</text>
  <text x="${px(w - margin)}" y="${px(0.075 * h)}" font-family="${SANS}" font-size="${px(headFs)}" fill="${accent}" text-anchor="end" letter-spacing="${px(headFs * 0.14)}">${esc(text.period_line)}</text>
  ${rowEls}
  <line x1="${px(margin)}" y1="${px(zoneBottom)}" x2="${px(w - margin)}" y2="${px(zoneBottom)}" stroke="${ink}" stroke-width="${px(hair * 1.2)}"/>
  <text x="${px(margin)}" y="${px(0.875 * h)}" font-family="${SANS}" font-weight="bold" font-size="${px(scoreFs)}" fill="${ink}" letter-spacing="${px(scoreFs * 0.04)}">${esc(text.score_line)}</text>
  <text x="${px(margin)}" y="${px(0.915 * h)}" font-family="${MONO}" font-size="${px(footerFs)}" fill="${ink}" opacity="0.8" letter-spacing="${px(footerFs * 0.2)}">${esc(text.date_line)}</text>
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
    COURT,
    SIZES,
    STYLES: ["trajectory", "blueprint", "type"],
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.BuzzerRender = api;
})(typeof window !== "undefined" ? window : globalThis);
