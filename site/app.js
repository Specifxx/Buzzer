/* Buzzer Studio app: gallery, product modal, and the live designer. */
(function () {
  "use strict";
  const R = window.BuzzerRender;
  const CAT = window.BUZZER_CATALOGUE || { moments: [], prices_usd: {}, sizes: [] };
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const CITIES = [
    "Atlanta", "Boston", "Brooklyn", "Charlotte", "Chicago", "Cleveland",
    "Dallas", "Denver", "Detroit", "Houston", "Indianapolis", "Los Angeles",
    "Memphis", "Miami", "Milwaukee", "Minneapolis", "New Orleans", "New York",
    "Oklahoma City", "Orlando", "Philadelphia", "Phoenix", "Portland",
    "Sacramento", "Salt Lake City", "San Antonio", "San Francisco",
    "Toronto", "Washington",
  ];

  /* ---------------- tabs ---------------- */
  $$(".tab").forEach((btn) =>
    btn.addEventListener("click", () => {
      $$(".tab").forEach((b) => b.classList.toggle("active", b === btn));
      $$(".tabpane").forEach((p) =>
        p.classList.toggle("active", p.id === `tab-${btn.dataset.tab}`)
      );
    })
  );

  /* ---------------- catalogue grid ---------------- */
  let galleryStyle = "trajectory";
  const filter = { type: "all", city: "all", decade: "all", sort: "score", q: "" };

  function matchesFilter(entry) {
    if (filter.type === "GAME-7" && !entry.badges.includes("GAME-7")) return false;
    if (filter.type !== "all" && filter.type !== "GAME-7" &&
        !entry.badges.some((b) => b.startsWith(filter.type))) return false;
    if (filter.city !== "all" && entry.city !== filter.city) return false;
    if (filter.decade !== "all" &&
        Math.floor(entry.year / 10) * 10 !== Number(filter.decade)) return false;
    if (filter.q) {
      const haystack = `${entry.title} ${entry.city}`.toLowerCase();
      if (!haystack.includes(filter.q)) return false;
    }
    return true;
  }

  const SORTS = {
    score: (a, b) => b.score - a.score,
    new: (a, b) => b.facts.game_date.localeCompare(a.facts.game_date),
    old: (a, b) => a.facts.game_date.localeCompare(b.facts.game_date),
    city: (a, b) => (a.city || "").localeCompare(b.city || ""),
  };

  function renderGrid() {
    const grid = $("#grid");
    grid.innerHTML = "";
    const shown = CAT.moments.filter(matchesFilter).sort(SORTS[filter.sort]);
    const count = $("#result-count");
    if (count) count.textContent =
      `${shown.length} of ${CAT.moments.length} moments`;
    shown.forEach((entry) => {
      const card = document.createElement("div");
      card.className = "card";
      const badges = entry.badges
        .map((b) => `<span class="badge">${b}</span>`)
        .join("");
      card.innerHTML = `
        <div class="card-art">${R.renderPoster(entry.facts, galleryStyle, "18x24")}</div>
        <div class="card-body">
          <div class="card-title">${entry.title}</div>
          <div class="card-meta">
            <span class="card-score">${entry.score}/100</span>
            <span>from $${Math.min(...Object.values(CAT.prices_usd)).toFixed(2)}</span>
          </div>
          <div class="badge-row">${badges}</div>
        </div>`;
      card.addEventListener("click", () => openModal(entry));
      grid.appendChild(card);
    });
    if (!grid.children.length) {
      grid.innerHTML = '<p style="color:#9a968c">No moments match this filter.</p>';
    }
  }

  $("#filter-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    filter.type = chip.dataset.filter;
    $$("#filter-chips .chip").forEach((c) => c.classList.toggle("active", c === chip));
    renderGrid();
  });
  // populate the city dropdown from the catalogue itself
  {
    const cities = [...new Set(CAT.moments.map((m) => m.city).filter(Boolean))].sort();
    $("#f-city").innerHTML =
      '<option value="all">All cities</option>' +
      cities.map((c) => `<option>${c}</option>`).join("");
  }
  $("#f-city").addEventListener("input", (e) => { filter.city = e.target.value; renderGrid(); });
  $("#f-decade").addEventListener("input", (e) => { filter.decade = e.target.value; renderGrid(); });
  $("#f-sort").addEventListener("input", (e) => { filter.sort = e.target.value; renderGrid(); });
  $("#f-search").addEventListener("input", (e) => {
    filter.q = e.target.value.trim().toLowerCase();
    renderGrid();
  });
  $("#style-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    galleryStyle = chip.dataset.style;
    $$("#style-chips .chip").forEach((c) => c.classList.toggle("active", c === chip));
    renderGrid();
  });

  /* ---------------- product modal ---------------- */
  let modalEntry = null;
  let modalStyle = "trajectory";
  let modalSize = "18x24";

  function refreshModal() {
    const file = modalEntry.files[modalStyle][modalSize];
    $("#modal-poster-holder").innerHTML = R.renderPoster(
      modalEntry.facts, modalStyle, modalSize
    );
    $("#modal-download").href = file;
    $("#modal-download").download = file.split("/").pop();
    $$("#modal-styles .chip").forEach((c) =>
      c.classList.toggle("active", c.dataset.style === modalStyle)
    );
    $$("#modal-sizes .chip").forEach((c) =>
      c.classList.toggle("active", c.dataset.size === modalSize)
    );
  }

  function openModal(entry) {
    modalEntry = entry;
    modalStyle = galleryStyle;
    modalSize = "18x24";
    $("#modal-score").textContent = entry.score;
    $("#modal-title").textContent = entry.title;
    $("#modal-desc").textContent = entry.description;
    $("#modal-tags").textContent = entry.tags.join(" · ");
    $("#modal-prices").innerHTML = Object.entries(CAT.prices_usd)
      .map(([size, price]) => `${size.replace("x", " × ")} in — <b>$${price.toFixed(2)}</b>`)
      .join("<br/>");
    $("#modal-styles").innerHTML = R.STYLES.map(
      (s) => `<button class="chip" data-style="${s}">${s[0].toUpperCase() + s.slice(1)}</button>`
    ).join("");
    $("#modal-sizes").innerHTML = CAT.sizes
      .map((s) => `<button class="chip" data-size="${s}">${s.replace("x", " × ")} in</button>`)
      .join("");
    refreshModal();
    $("#modal").hidden = false;
  }

  $("#modal-styles").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip) { modalStyle = chip.dataset.style; refreshModal(); }
  });
  $("#modal-sizes").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip) { modalSize = chip.dataset.size; refreshModal(); }
  });
  $("#modal-close").addEventListener("click", () => ($("#modal").hidden = true));
  $("#modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") $("#modal").hidden = true;
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $("#modal").hidden = true;
  });

  /* ---------------- designer ---------------- */
  const state = {
    style: "trajectory",
    size: "18x24",
    shot_x: -221.0,
    shot_y: 155.0,
    clockSeconds: 1,
    period: 4,
    home_score: 101,
    away_score: 100,
    scoring_side: "home",
    points: 3,
    deficit: 13,
    home_city: "Boston",
    away_city: "Denver",
    date: "2026-06-04",
    playoffs: true,
    round: "",
    seriesGame: "",
    isTip: false,
  };

  function clockString(total) {
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }

  function currentFacts() {
    const dist = Math.hypot(state.shot_x, state.shot_y) / 10;
    const teamAfter = state.scoring_side === "home" ? state.home_score : state.away_score;
    const oppAfter = state.scoring_side === "home" ? state.away_score : state.home_score;
    const marginAfter = teamAfter - oppAfter;
    const marginBefore = marginAfter - state.points;
    return {
      game_date: state.date || "2026-06-04",
      home_city: state.home_city,
      away_city: state.away_city,
      period: state.period,
      clock: clockString(state.clockSeconds),
      home_score: state.home_score,
      away_score: state.away_score,
      scoring_side: state.scoring_side,
      points: state.points,
      margin_before: marginBefore,
      takes_lead: marginBefore <= 0 && marginAfter > 0,
      ties_game: marginAfter === 0,
      deficit_overcome: state.deficit,
      is_playoff: state.playoffs,
      shot_distance_ft: Math.round(dist * 10) / 10,
      shot_x: state.shot_x,
      shot_y: state.shot_y,
      playoff_round: state.playoffs && state.round ? Number(state.round) : null,
      series_game: state.playoffs && state.seriesGame ? Number(state.seriesGame) : null,
      is_tip: state.isTip,
    };
  }

  function describe(facts) {
    const bits = [];
    if (facts.series_game === 7) bits.push("GAME 7");
    if (facts.is_tip) bits.push("TIP-IN");
    if (R.parseClock(facts.clock) <= 1 && facts.period >= 4) bits.push("BUZZER");
    if (facts.takes_lead) bits.push("GO-AHEAD");
    else if (facts.ties_game) bits.push("TIES IT");
    if (facts.deficit_overcome >= 8 && (facts.takes_lead || facts.ties_game))
      bits.push(`COMEBACK ${facts.deficit_overcome}`);
    if ((facts.shot_distance_ft || 0) >= 30) bits.push("DEEP");
    if (facts.period > 4) bits.push("OVERTIME");
    return bits.join(" · ") || "regular play";
  }

  let lastSVG = "";
  function renderDesigner() {
    const facts = currentFacts();
    lastSVG = R.renderPoster(facts, state.style, state.size);
    $("#poster-holder").innerHTML = lastSVG;
    const score = R.scoreMoment(facts);
    $("#iconic-score").textContent = score;
    $("#iconic-bar").style.width = `${score}%`;
    $("#iconic-note").textContent = describe(facts);
    $("#dist-readout").textContent = `${facts.shot_distance_ft.toFixed(1)} ft`;
    $("#clock-readout").textContent = facts.clock;
    $("#deficit-readout").textContent = String(state.deficit);
    drawMiniCourt();
  }

  /* mini court */
  const mini = $("#mini-court");
  const cm = R.courtMap(250, 417.5, 1.0); // viewBox 0..500 x 0..470

  function drawMiniCourt() {
    const bb = cm.backboardLine();
    const bl = cm.baselineLine();
    const sx = cm.x(state.shot_x);
    const sy = cm.y(state.shot_y);
    const [hx, hy] = cm.pt(0, 0);
    mini.innerHTML = `
      <g fill="none" stroke="#4a4f5a" stroke-width="2">
        <path d="${cm.sidelinePath()}"/>
        <path d="${cm.halfcourtCirclePath()}"/>
        <path d="${cm.threePointPath()}"/>
        <path d="${cm.keyPath()}"/>
        <path d="${cm.ftCirclePath()}"/>
        <line x1="${bb[0]}" y1="${bb[1]}" x2="${bb[2]}" y2="${bb[3]}"/>
        <line x1="${bl[0]}" y1="${bl[1]}" x2="${bl[2]}" y2="${bl[3]}"/>
        <circle cx="${hx}" cy="${hy}" r="7.5"/>
      </g>
      <line x1="${sx}" y1="${sy}" x2="${hx}" y2="${hy}" stroke="#d96f4e" stroke-width="2" stroke-dasharray="7 5" opacity="0.7"/>
      <circle cx="${sx}" cy="${sy}" r="16" fill="rgba(217,111,78,0.18)" stroke="#d96f4e" stroke-width="1.5"/>
      <circle cx="${sx}" cy="${sy}" r="7" fill="#d96f4e"/>`;
  }

  function pointToCourt(evt) {
    const pt = mini.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    const p = pt.matrixTransform(mini.getScreenCTM().inverse());
    const cx = Math.max(-245, Math.min(245, p.x - 250));
    const cy = Math.max(-45, Math.min(410, 417.5 - p.y));
    return [Math.round(cx * 10) / 10, Math.round(cy * 10) / 10];
  }

  let dragging = false;
  function handleDrag(evt) {
    const [cx, cy] = pointToCourt(evt);
    state.shot_x = cx;
    state.shot_y = cy;
    const dist = Math.hypot(cx, cy) / 10;
    state.points = dist >= 22 ? 3 : 2; // auto, still overridable below
    $("#c-points").value = String(state.points);
    renderDesigner();
  }
  mini.addEventListener("pointerdown", (e) => {
    dragging = true;
    mini.setPointerCapture(e.pointerId);
    handleDrag(e);
  });
  mini.addEventListener("pointermove", (e) => dragging && handleDrag(e));
  mini.addEventListener("pointerup", () => (dragging = false));

  /* control bindings */
  function bind(id, fn) {
    $(id).addEventListener("input", (e) => { fn(e.target); renderDesigner(); });
  }
  // populate city dropdowns
  for (const id of ["#c-homecity", "#c-awaycity"]) {
    $(id).innerHTML = CITIES.map((c) => `<option>${c}</option>`).join("");
  }
  $("#c-homecity").value = state.home_city;
  $("#c-awaycity").value = state.away_city;

  bind("#c-style", (el) => (state.style = el.value));
  bind("#c-size", (el) => (state.size = el.value));
  bind("#c-period", (el) => (state.period = Number(el.value)));
  bind("#c-clock", (el) => (state.clockSeconds = Number(el.value)));
  bind("#c-home", (el) => (state.home_score = Number(el.value) || 0));
  bind("#c-away", (el) => (state.away_score = Number(el.value) || 0));
  bind("#c-side", (el) => (state.scoring_side = el.value));
  bind("#c-points", (el) => (state.points = Number(el.value)));
  bind("#c-deficit", (el) => (state.deficit = Number(el.value)));
  bind("#c-homecity", (el) => (state.home_city = el.value));
  bind("#c-awaycity", (el) => (state.away_city = el.value));
  bind("#c-date", (el) => (state.date = el.value));
  bind("#c-playoffs", (el) => (state.playoffs = el.checked));
  bind("#c-round", (el) => (state.round = el.value));
  bind("#c-seriesgame", (el) => (state.seriesGame = el.value));
  bind("#c-tip", (el) => (state.isTip = el.checked));

  /* downloads */
  let fontCSSPromise = null;
  function fontCSS() {
    if (!fontCSSPromise) {
      const faces = [
        ["Anton", 400, "fonts/anton-latin-400-normal.woff2"],
        ["Space Grotesk", 500, "fonts/space-grotesk-latin-500-normal.woff2"],
        ["Space Grotesk", 700, "fonts/space-grotesk-latin-700-normal.woff2"],
        ["Space Mono", 400, "fonts/space-mono-latin-400-normal.woff2"],
        ["Space Mono", 700, "fonts/space-mono-latin-700-normal.woff2"],
      ];
      fontCSSPromise = Promise.all(
        faces.map(async ([family, weight, url]) => {
          const buf = await (await fetch(url)).arrayBuffer();
          let bin = "";
          for (const b of new Uint8Array(buf)) bin += String.fromCharCode(b);
          return `@font-face{font-family:'${family}';font-weight:${weight};` +
            `src:url(data:font/woff2;base64,${btoa(bin)}) format('woff2');}`;
        })
      ).then((rules) => rules.join(""), () => "");
    }
    return fontCSSPromise;
  }
  async function withEmbeddedFonts(svg) {
    const css = await fontCSS();
    return css ? svg.replace(/(<svg[^>]*>)/, `$1<style>${css}</style>`) : svg;
  }
  function downloadBlob(blob, name) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
  $("#dl-svg").addEventListener("click", async () => {
    const svg = await withEmbeddedFonts(lastSVG);
    downloadBlob(new Blob([svg], { type: "image/svg+xml" }), `buzzer-${state.style}-${state.size}.svg`);
  });
  $("#dl-png").addEventListener("click", async () => {
    const svg = await withEmbeddedFonts(lastSVG);
    const img = new Image();
    const [iw, ih] = R.SIZES[state.size];
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const width = 1440;
      canvas.width = width;
      canvas.height = Math.round((width * ih) / iw);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => downloadBlob(blob, `buzzer-${state.style}-${state.size}.png`), "image/png");
    };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  });

  /* boot */
  renderGrid();
  renderDesigner();
})();
