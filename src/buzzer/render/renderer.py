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
from buzzer.render.palettes import darken, palette_for
from buzzer.render.text import PosterText, poster_text
from buzzer.render.validate import validate_svg, validate_text_value

logger = logging.getLogger(__name__)

STYLES = ("trajectory", "blueprint", "type")
SIZES: dict[str, tuple[int, int]] = {"12x16": (12, 16), "18x24": (18, 24), "24x36": (24, 36)}
DPI = 300
PREVIEW_WIDTH_PX = 900

# Bundled OFL fonts (see render/fonts/); fallbacks for exotic environments.
DISPLAY = "Anton, Impact, Arial Narrow, sans-serif"
SANS = "Space Grotesk, Helvetica, Arial, sans-serif"
MONO = "Space Mono, DejaVu Sans Mono, Courier New, monospace"
# Anton is condensed: average glyph advance for caps/digits, used to
# auto-fit display lines to the content width.
ANTON_GLYPH_W = 0.54

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
    palette = palette_for(facts.home_city)
    return {
        "w": w,
        "h": h,
        "margin": 0.075 * w,
        "display": DISPLAY,
        "sans": SANS,
        "mono": MONO,
        "text": text,
        "hairline": max(1.5, 0.0016 * w),
        "ink": palette.ink,
        "paper": palette.paper,
        "accent": palette.accent,
        "accent2": palette.accent2,
    }


def _fit_display(text_value: str, max_width: float, cap: float) -> float:
    """Font size so an Anton line of this text fills max_width, capped."""
    return min(cap, max_width / (ANTON_GLYPH_W * max(len(text_value), 2)))


def _ball_geometry(cx: float, cy: float, r: float) -> dict[str, Any]:
    """Stylised basketball: circle, cross seams, two bowed side seams.

    A generic ball drawing is plain sports imagery — no marks involved.
    """
    return {
        "cx": cx,
        "cy": cy,
        "r": r,
        "seam_left": f"M {cx:.1f} {cy - r:.1f} Q {cx - 1.15 * r:.1f} {cy:.1f} "
        f"{cx:.1f} {cy + r:.1f}",
        "seam_right": f"M {cx:.1f} {cy - r:.1f} Q {cx + 1.15 * r:.1f} {cy:.1f} "
        f"{cx:.1f} {cy + r:.1f}",
    }


# --- style: trajectory ------------------------------------------------------


def _ctx_trajectory(facts: MomentFacts, w: float, h: float) -> dict[str, Any]:
    """Retro-sun composition: warm concentric distance rings, one bold
    sweeping arc with echo trails, anchored display type at the bottom."""
    ctx = _common_ctx(facts, w, h)
    sx, sy, _ = _shot_court_xy(facts)

    hoop_x, hoop_y = w / 2.0, 0.555 * h
    court_top = 0.055 * h
    scale = 0.86 * w / (2 * court.COURT_HALF_WIDTH)
    if sy * scale > hoop_y - 0.09 * h:  # long bombs: keep the dot in frame
        scale = (hoop_y - 0.09 * h) / sy

    cmap = court.CourtMap(hoop_x=hoop_x, hoop_y=hoop_y, scale=scale)
    px, py = cmap.pt(sx, sy)
    dist_px = ((px - hoop_x) ** 2 + (py - hoop_y) ** 2) ** 0.5

    def arc_path(lift: float) -> str:
        mid_x = (px + hoop_x) / 2.0
        mid_y = (py + hoop_y) / 2.0 - lift * dist_px
        return f"M {px:.1f} {py:.1f} Q {mid_x:.1f} {mid_y:.1f} {hoop_x:.1f} {hoop_y:.1f}"

    shot_ring = (
        cmap.length(facts.shot_distance_ft * 10.0) if facts.shot_distance_ft is not None else None
    )
    rings = [
        {"r": cmap.length(ft * 10.0), "tone": ("accent2" if i % 2 else "paper")}
        for i, ft in enumerate((10, 20, 30))
    ]
    glow_r = max(shot_ring or 0.0, cmap.length(220.0))

    rule_y = 0.760 * h
    clock_fs = _fit_display(ctx["text"].clock_line, 0.46 * w, 0.20 * w)
    ctx.update(
        {
            "court_top": court_top,
            "court_bottom": 0.735 * h,
            "hoop_x": hoop_x,
            "hoop_y": hoop_y,
            "hoop_r": cmap.length(court.HOOP_RADIUS),
            "glow_r": glow_r,
            "rings": rings,
            "shot_ring": shot_ring,
            "three_d": cmap.three_point_path(),
            "baseline": cmap.baseline_line(),
            "backboard": cmap.backboard_line(),
            "arc_main": arc_path(0.45),
            "arc_echoes": [
                {"d": arc_path(0.52), "tone": "accent", "width": 0.005 * w, "alpha": 0.55},
                {"d": arc_path(0.59), "tone": "accent2", "width": 0.0035 * w, "alpha": 0.35},
                {"d": arc_path(0.66), "tone": "paper", "width": 0.0025 * w, "alpha": 0.16},
            ],
            "arc_width": 0.0085 * w,
            "shot_x": px,
            "shot_y": py,
            "dot_r": 0.015 * w,
            "ball": _ball_geometry(px, py, 0.0205 * w),
            "rule_y": rule_y,
            "clock_fs": clock_fs,
            "clock_y": rule_y + 0.018 * h + clock_fs * 0.80,
            "away_line": f"{(facts.away_city or 'AWAY').upper()} {facts.away_score}",
            "home_line": f"{(facts.home_city or 'HOME').upper()} {facts.home_score}",
            "score_fs": 0.034 * w,
            "score_y1": rule_y + 0.052 * h,
            "score_y2": rule_y + 0.052 * h + 0.046 * w,
            "footer_y": 0.948 * h,
            "footer_fs": 0.016 * w,
            "footer_right": " — ".join(
                part
                for part in (
                    ctx["text"].period_line,
                    ctx["text"].series_line or ctx["text"].stakes_line,
                    ctx["text"].distance_line,
                )
                if part
            ),
        }
    )
    return ctx


# --- style: blueprint -------------------------------------------------------


def _ctx_blueprint(facts: MomentFacts, w: float, h: float) -> dict[str, Any]:
    """Technical plan view on warm paper: palette inks, drafting marks,
    Anton header, and a compact two-row spec grid."""
    ctx = _common_ctx(facts, w, h)
    sx, sy, _ = _shot_court_xy(facts)
    sy = min(sy, court.HALFCOURT_Y - 10)  # clamp heaves into the plan view

    scale = 0.78 * w / (2 * court.COURT_HALF_WIDTH)
    halfcourt_top = 0.165 * h
    hoop_y = halfcourt_top + court.HALFCOURT_Y * scale
    cmap = court.CourtMap(hoop_x=w / 2.0, hoop_y=hoop_y, scale=scale)
    px, py = cmap.pt(sx, sy)
    hx, hy = cmap.pt(0, 0)

    grid_step = w / 28.0
    block_top = cmap.y(court.BASELINE_Y) + 0.052 * h
    block_h = h - ctx["margin"] * 0.85 - block_top
    drawn_ratio = round((50.0 * 12.0) / (0.78 * (w / 100)))

    if facts.takes_lead:
        title = "GO-AHEAD FIELD GOAL"
    elif facts.ties_game:
        title = "GAME-TIED FIELD GOAL"
    else:
        title = "FIELD GOAL"
    validate_text_value(title, field="blueprint_title")

    cells = [
        ("TITLE", title),
        ("SCORE", ctx["text"].score_line),
        ("DATE", ctx["text"].date_line),
        ("LOCATION", (facts.home_city or "HOME").upper()),
        ("TIME", f"{ctx['text'].period_line} — {facts.clock} REMAINING"),
        ("SCALE", f"1:{drawn_ratio} — SHEET 1 OF 1"),
    ]

    ctx.update(
        {
            "mark": darken(ctx["accent2"], 0.62),
            "grid_xs": [i * grid_step for i in range(1, int(w / grid_step))],
            "grid_ys": [i * grid_step for i in range(1, int(h / grid_step))],
            "head_fs": 0.050 * w,
            "head_y": ctx["margin"] + 0.046 * w,
            "sub_text": " — ".join(
                part
                for part in (
                    ctx["text"].stakes_line,
                    ctx["text"].series_line,
                    ctx["text"].cities_line,
                )
                if part
            ),
            "sub_fs": 0.017 * w,
            "sub_y": ctx["margin"] + 0.080 * w,
            "court_stroke": max(2.0, 0.0028 * w),
            "sideline_d": cmap.sideline_path(),
            "halfcircle_d": cmap.halfcourt_circle_path(),
            "three_d": cmap.three_point_path(),
            "key_d": cmap.key_path(),
            "ft_circle_d": cmap.ft_circle_path(),
            "restricted_d": cmap.restricted_path(),
            "backboard": cmap.backboard_line(),
            "hoop_x": hx,
            "hoop_y": hy,
            "hoop_r": cmap.length(court.HOOP_RADIUS),
            "shot_x": px,
            "shot_y": py,
            "cross": 0.016 * w,
            "reg": 0.011 * w,
            "reg_pts": [
                (ctx["margin"] * 0.45, ctx["margin"] * 0.45),
                (w - ctx["margin"] * 0.45, ctx["margin"] * 0.45),
                (ctx["margin"] * 0.45, h - ctx["margin"] * 0.45),
                (w - ctx["margin"] * 0.45, h - ctx["margin"] * 0.45),
            ],
            "dim_label": ctx["text"].distance_line or f"{facts.points} POINTS",
            "dim_label_x": (px + hx) / 2.0 + 0.030 * w,
            "dim_label_y": (py + hy) / 2.0,
            "coord_label": f"X {sx / 10.0:+.1f} FT — Y {sy / 10.0:+.1f} FT",
            "coord_x": min(max(px, 0.17 * w), 0.83 * w),
            "coord_y": py - 0.026 * w,
            "ball": _ball_geometry(cmap.x(160.0), cmap.y(345.0), 0.038 * w),
            "ball_label_y": cmap.y(345.0) + 0.038 * w + 0.024 * w,
            "court_w_label_y": cmap.y(court.BASELINE_Y) + 0.030 * h,
            "court_left_x": cmap.x(-court.COURT_HALF_WIDTH),
            "court_right_x": cmap.x(court.COURT_HALF_WIDTH),
            "block_top": block_top,
            "block_h": block_h,
            "cells": [
                {
                    "label": label,
                    "value": value,
                    "x": ctx["margin"] + (i % 3) * ((w - 2 * ctx["margin"]) / 3),
                    "y": block_top + (i // 3) * (block_h / 2),
                    # Space Grotesk 700 averages ~0.62em per glyph; long
                    # city pairs must not bleed into the next cell.
                    "fs": min(
                        0.0155 * w,
                        ((w - 2 * ctx["margin"]) / 3 - 0.035 * w) / (0.66 * max(len(value), 4)),
                    ),
                }
                for i, (label, value) in enumerate(cells)
            ],
            "cell_w": (w - 2 * ctx["margin"]) / 3,
            "cell_h": block_h / 2,
            "label_fs": 0.0115 * w,
            "value_fs": 0.0155 * w,
            "mono_fs": 0.014 * w,
        }
    )
    return ctx


# --- style: type ------------------------------------------------------------


def _ctx_type(facts: MomentFacts, w: float, h: float) -> dict[str, Any]:
    """Fight-poster typography: stacked Anton lines auto-fit to the full
    content width, an accent score band, and a justified mono footer."""
    ctx = _common_ctx(facts, w, h)
    text: PosterText = ctx["text"]
    cw = w - 2 * ctx["margin"]

    stack: list[tuple[str, str]] = [(text.clock_value, "paper")]
    if facts.series_game == 7:
        stack.append(("GAME 7", "accent"))
    if text.deficit_value:
        stack.append((f"DOWN {text.deficit_value}", "accent"))
    if facts.is_tip:
        stack.append(("TIP-IN", "paper"))
    elif facts.shot_distance_ft is not None and facts.shot_distance_ft >= 1:
        stack.append((f"FROM {facts.shot_distance_ft:.0f} FEET", "paper"))
    if facts.takes_lead:
        stack.append(("FOR THE LEAD", "accent2"))
    elif facts.ties_game:
        stack.append(("TIES THE GAME", "accent2"))
    else:
        stack.append((f"{facts.points} POINTS", "accent2"))
    for value, _tone in stack:
        validate_text_value(value, "type_line")

    sizes = [_fit_display(value, cw, 0.175 * h) for value, _tone in stack]
    natural = sum(fs * 1.04 for fs in sizes)
    stack_top, stack_bottom = 0.070 * h, 0.715 * h
    zone = stack_bottom - stack_top
    if natural > zone:  # many lines (e.g. Game 7 + comeback): shrink to fit
        sizes = [fs * zone / natural for fs in sizes]
        natural = zone
    gap_extra = max(0.0, zone - natural) / max(len(stack), 1)
    lines = []
    cursor = stack_top
    for (value, tone), fs in zip(stack, sizes, strict=True):
        cursor += fs * 0.84
        lines.append({"value": value, "tone": tone, "fs": fs, "y": cursor})
        cursor += fs * 0.20 + gap_extra

    band_top = 0.755 * h
    band_h = 0.085 * h
    band_text = text.score_line
    band_fs = min(band_h * 0.56, cw * 0.94 / (ANTON_GLYPH_W * max(len(band_text), 2)))

    ctx.update(
        {
            "lines": lines,
            "band_top": band_top,
            "band_h": band_h,
            "band_text": band_text,
            "band_fs": band_fs,
            "band_text_y": band_top + band_h / 2 + band_fs * 0.34,
            "ball": _ball_geometry(w / 2.0, (band_top + band_h + 0.915 * h) / 2.0, 0.030 * w),
            "footer_y": 0.945 * h,
            "footer_fs": 0.0165 * w,
            "footer_left": text.date_line,
            "footer_mid": text.series_line or text.stakes_line,
            "footer_right": f"{text.period_line} — {facts.clock}",
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
    from buzzer.render.fontsetup import ensure_fonts_registered

    ensure_fonts_registered()
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
