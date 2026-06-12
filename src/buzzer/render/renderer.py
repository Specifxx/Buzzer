"""Render MomentFacts into SVG posters and print-ready PNGs.

Layout math lives here in typed Python; the Jinja templates only place
precomputed values. Canvas units are inches*100, exports are 300 DPI.

The renderer accepts ONLY ``MomentFacts`` — passing operator context with
team codes or player names is impossible at the type level, and the
rendered SVG is still validated token-by-token afterwards (defense in
depth, see ``buzzer.render.validate``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader

from buzzer.models import Moment, MomentFacts
from buzzer.render import court
from buzzer.render.text import PosterText, poster_text
from buzzer.render.validate import validate_svg, validate_text_value

logger = logging.getLogger(__name__)

STYLES = ("trajectory", "blueprint", "type")
SIZES: dict[str, tuple[int, int]] = {"12x16": (12, 16), "18x24": (18, 24), "24x36": (24, 36)}
DPI = 300
PREVIEW_WIDTH_PX = 900

SANS = "DejaVu Sans, Helvetica, Arial, sans-serif"
MONO = "DejaVu Sans Mono, Courier New, monospace"

_env = Environment(loader=PackageLoader("buzzer.render", "templates"), autoescape=True)
_env.filters["px"] = lambda v: f"{float(v):.1f}"


@dataclass(frozen=True)
class ShotPoint:
    """Canvas-space shot location; synthesized down the middle if the
    shot chart had no x/y for this event."""

    x: float
    y: float
    distance_ft: float | None
    synthesized: bool


def _shot_court_xy(facts: MomentFacts) -> tuple[float, float, bool]:
    if facts.shot_x is not None and facts.shot_y is not None:
        return facts.shot_x, facts.shot_y, False
    if facts.shot_distance_ft is not None:
        return 0.0, facts.shot_distance_ft * 10.0, True
    return 0.0, court.FT_LINE_Y, True


def _common_ctx(facts: MomentFacts, w: float, h: float) -> dict[str, Any]:
    text = poster_text(facts)
    for field_name, value in vars(text).items():
        values = value if isinstance(value, tuple) else (value,)
        for item in values:
            validate_text_value(item, field=field_name)
    return {
        "w": w,
        "h": h,
        "margin": 0.07 * w,
        "sans": SANS,
        "mono": MONO,
        "text": text,
        "hairline": max(1.5, 0.0016 * w),
    }


# --- style: trajectory ------------------------------------------------------


def _ctx_trajectory(facts: MomentFacts, w: float, h: float) -> dict[str, Any]:
    ctx = _common_ctx(facts, w, h)
    sx, sy, synthesized = _shot_court_xy(facts)

    hoop_x, hoop_y = w / 2.0, 0.66 * h
    top_safe = 0.34 * h
    scale = 0.86 * w / (2 * court.COURT_HALF_WIDTH)
    # Long bombs: shrink so the shot point stays inside the court zone.
    max_court_y = (hoop_y - top_safe) / scale
    if sy > max_court_y:
        scale = (hoop_y - top_safe) / sy

    cmap = court.CourtMap(hoop_x=hoop_x, hoop_y=hoop_y, scale=scale)
    px, py = cmap.pt(sx, sy)
    dist_px = ((px - hoop_x) ** 2 + (py - hoop_y) ** 2) ** 0.5
    # Quadratic "lob" control point: midpoint lifted perpendicular-ish.
    mid_x, mid_y = (px + hoop_x) / 2.0, (py + hoop_y) / 2.0 - 0.45 * dist_px

    ring_radii = [cmap.length(100.0), cmap.length(200.0), cmap.length(300.0)]
    shot_ring = (
        cmap.length(facts.shot_distance_ft * 10.0) if facts.shot_distance_ft is not None else None
    )

    clock_fs = 0.20 * w
    ctx.update(
        {
            "bg": "#101115",
            "ink": "#ece7db",
            "faint": "#33363e",
            "accent": "#d96f4e",
            "clock_fs": clock_fs,
            "clock_y": ctx["margin"] + clock_fs * 0.92,
            "head_fs": 0.026 * w,
            "head_y1": ctx["margin"] + 0.030 * w,
            "head_y2": ctx["margin"] + 0.064 * w,
            "hoop_x": hoop_x,
            "hoop_y": hoop_y,
            "hoop_r": cmap.length(court.HOOP_RADIUS),
            "baseline": cmap.baseline_line(),
            "backboard": cmap.backboard_line(),
            "three_d": cmap.three_point_path(),
            "rings": ring_radii,
            "shot_ring": shot_ring,
            "dist_label_x": px + (0.030 * w if px < w / 2 else -0.030 * w),
            "dist_label_anchor": "start" if px < w / 2 else "end",
            "dist_label_y": py - 0.030 * w,
            "arc_d": f"M {px:.1f} {py:.1f} Q {mid_x:.1f} {mid_y:.1f} {hoop_x:.1f} {hoop_y:.1f}",
            "shot_x": px,
            "shot_y": py,
            "dot_r": 0.011 * w,
            "halo_r": 0.022 * w,
            "clip_top": top_safe,
            "clip_h": 0.85 * h - top_safe,
            "score_fs": 0.030 * w,
            "score_y": 0.895 * h,
            "footer_fs": 0.018 * w,
            "footer_y": 0.932 * h,
            "show_synth_note": synthesized,
        }
    )
    return ctx


# --- style: blueprint -------------------------------------------------------


def _ctx_blueprint(facts: MomentFacts, w: float, h: float) -> dict[str, Any]:
    ctx = _common_ctx(facts, w, h)
    sx, sy, _ = _shot_court_xy(facts)
    sy = min(sy, court.HALFCOURT_Y - 10)  # clamp heaves into the plan view

    scale = 0.78 * w / (2 * court.COURT_HALF_WIDTH)
    halfcourt_top = 0.15 * h
    hoop_y = halfcourt_top + court.HALFCOURT_Y * scale
    cmap = court.CourtMap(hoop_x=w / 2.0, hoop_y=hoop_y, scale=scale)
    px, py = cmap.pt(sx, sy)
    hx, hy = cmap.pt(0, 0)

    grid_step = w / 24.0
    title_top = cmap.y(court.BASELINE_Y) + 0.05 * h
    title_h = h - ctx["margin"] - title_top
    # Real drawn scale of the plan, as a 1:n ratio (court inches per canvas inch).
    drawn_ratio = round((50.0 * 12.0) / (0.78 * (w / 100.0)))

    if facts.takes_lead:
        title = f"GO-AHEAD FIELD GOAL — {facts.points} POINTS"
    elif facts.ties_game:
        title = f"FIELD GOAL TIES THE GAME — {facts.points} POINTS"
    else:
        title = f"FIELD GOAL — {facts.points} POINTS"
    validate_text_value(title, field="blueprint_title")

    rows = [
        ("TITLE", title),
        ("DATE", ctx["text"].date_line),
        ("LOCATION", (facts.home_city or "HOME").upper()),
        ("SCORE", ctx["text"].score_line),
        ("TIME", f"{ctx['text'].period_line} — {facts.clock} REMAINING"),
        ("SCALE", f"1:{drawn_ratio} — SHEET 1 OF 1"),
    ]

    ctx.update(
        {
            "bg": "#f3f0e8",
            "ink": "#21405f",
            "faint": "#b9c4d2",
            "accent": "#b3402e",
            "grid_xs": [i * grid_step for i in range(1, int(w / grid_step))],
            "grid_ys": [i * grid_step for i in range(1, int(h / grid_step))],
            "head_fs": 0.030 * w,
            "head_y": ctx["margin"] + 0.020 * w,
            "sub_fs": 0.0165 * w,
            "sub_y": ctx["margin"] + 0.052 * w,
            "court_stroke": max(2.0, 0.0022 * w),
            "sideline_d": cmap.sideline_path(),
            "halfcircle_d": cmap.halfcourt_circle_path(),
            "three_d": cmap.three_point_path(),
            "key_d": cmap.key_path(),
            "ft_circle_d": cmap.ft_circle_path(),
            "restricted_d": cmap.restricted_path(),
            "baseline": cmap.baseline_line(),
            "backboard": cmap.backboard_line(),
            "hoop_x": hx,
            "hoop_y": hy,
            "hoop_r": cmap.length(court.HOOP_RADIUS),
            "shot_x": px,
            "shot_y": py,
            "cross": 0.016 * w,
            "dim_label": ctx["text"].distance_line or f"{facts.points} POINTS",
            "dim_label_x": (px + hx) / 2.0 + 0.030 * w,
            "dim_label_y": (py + hy) / 2.0,
            "coord_label": f"X {sx / 10.0:+.1f} FT — Y {sy / 10.0:+.1f} FT",
            "coord_x": min(max(px, 0.16 * w), 0.84 * w),
            "coord_y": py - 0.024 * w,
            "court_w_label_y": cmap.y(court.BASELINE_Y) + 0.030 * h,
            "court_left_x": cmap.x(-court.COURT_HALF_WIDTH),
            "court_right_x": cmap.x(court.COURT_HALF_WIDTH),
            "title_top": title_top,
            "title_h": title_h,
            "rows": rows,
            "row_h": title_h / len(rows),
            "label_fs": 0.0135 * w,
            "value_fs": 0.019 * w,
            "mono_fs": 0.014 * w,
        }
    )
    return ctx


# --- style: type ------------------------------------------------------------


def _ctx_type(facts: MomentFacts, w: float, h: float) -> dict[str, Any]:
    ctx = _common_ctx(facts, w, h)
    text: PosterText = ctx["text"]

    rows: list[tuple[str, str]] = [(text.clock_value, f"{text.period_line} — ON THE CLOCK")]
    if text.deficit_value:
        rows.append((text.deficit_value, "POINT DEFICIT"))
    if facts.shot_distance_ft is not None:
        rows.append((f"{facts.shot_distance_ft:.0f}", "FOOT SHOT"))
    if facts.takes_lead:
        rows.append((str(facts.points), "POINTS FOR THE LEAD"))
    elif facts.ties_game:
        rows.append((str(facts.points), "POINTS TO TIE THE GAME"))
    else:
        rows.append((str(facts.points), "POINTS"))
    for value, caption in rows:
        validate_text_value(value, "type_value")
        validate_text_value(caption, "type_caption")

    zone_top, zone_bottom = 0.135 * h, 0.82 * h
    row_h = (zone_bottom - zone_top) / len(rows)
    placed = []
    for i, (value, caption) in enumerate(rows):
        # Cap the numeral size so wide values ("0:01") still fit the column.
        fs = min(row_h * 0.66, 0.82 * w / (0.62 * max(len(value), 2)))
        y = zone_top + i * row_h
        placed.append(
            {
                "value": value,
                "caption": caption,
                "value_y": y + row_h * 0.30 + fs * 0.36,
                "caption_y": y + row_h * 0.86,
                "fs": fs,
                "rule_y": y,
            }
        )

    ctx.update(
        {
            "bg": "#efe9dc",
            "ink": "#16161a",
            "accent": "#c2391f",
            "rows": placed,
            "zone_bottom": zone_bottom,
            "head_fs": 0.024 * w,
            "head_y": 0.075 * h,
            "caption_fs": 0.020 * w,
            "score_fs": 0.030 * w,
            "score_y": 0.875 * h,
            "footer_fs": 0.0175 * w,
            "footer_y": 0.915 * h,
        }
    )
    return ctx


_CTX_BUILDERS = {
    "trajectory": _ctx_trajectory,
    "blueprint": _ctx_blueprint,
    "type": _ctx_type,
}


# --- public API --------------------------------------------------------------


def render_svg(facts: MomentFacts, style: str, size: str) -> str:
    """Render one poster to an SVG string. Validates before returning."""
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}; expected one of {STYLES}")
    if size not in SIZES:
        raise ValueError(f"unknown size {size!r}; expected one of {sorted(SIZES)}")
    inches_w, inches_h = SIZES[size]
    w, h = float(inches_w * 100), float(inches_h * 100)
    ctx = _CTX_BUILDERS[style](facts, w, h)
    svg = _env.get_template(f"{style}.svg.j2").render(ctx)
    validate_svg(svg, allowed_cities=(facts.home_city, facts.away_city))
    logger.debug("rendered %s/%s (%d bytes)", style, size, len(svg))
    return svg


def export_png(svg: str, out_path: Path, width_px: int, dpi: int | None = DPI) -> Path:
    """Rasterize the SVG to a PNG of the given pixel width (aspect kept)."""
    import cairosvg
    from PIL import Image

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out_path), output_width=width_px)
    if dpi:
        with Image.open(out_path) as image:
            image.save(out_path, dpi=(dpi, dpi))
    logger.info("wrote %s (%d px wide)", out_path, width_px)
    return out_path


def render_moment(
    moment: Moment,
    style: str,
    size: str,
    out_dir: Path,
    print_file: bool = True,
    preview: bool = True,
    subdir: str | None = None,
) -> list[Path]:
    """Render one moment/style/size to SVG + print PNG + web preview PNG."""
    svg = render_svg(moment.facts, style, size)
    stem = f"{moment.moment_id.replace(':', '-')}_{style}_{size}"
    target_dir = out_dir / (subdir or moment.moment_id.replace(":", "-"))
    target_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    svg_path = target_dir / f"{stem}.svg"
    svg_path.write_text(svg)
    outputs.append(svg_path)

    if print_file:
        inches_w, _ = SIZES[size]
        outputs.append(export_png(svg, target_dir / f"{stem}.png", inches_w * DPI))
    if preview:
        outputs.append(
            export_png(svg, target_dir / f"{stem}_preview.png", PREVIEW_WIDTH_PX, dpi=None)
        )
    return outputs
