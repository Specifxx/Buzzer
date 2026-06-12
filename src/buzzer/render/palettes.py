"""Curated poster colorways.

Each moment gets a palette keyed deterministically off its home city, so
a wall of catalogue posters varies instead of repeating one scheme. The
same hash runs in the browser renderer (site/buzzer-render.js) — keep
them in sync.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    ink: str  # deep background (dark styles) / line work (light styles)
    paper: str  # cream foreground / light background
    accent: str
    accent2: str


PALETTES: tuple[Palette, ...] = (
    Palette("dusk", "#1A1B26", "#F2E9DC", "#FF6B4A", "#FFC15E"),
    Palette("garden", "#1E3A2F", "#F4EBDD", "#E8A33D", "#D6532B"),
    Palette("clay", "#2B1D1A", "#F4E7D3", "#E2725B", "#9CAD7F"),
    Palette("midnight", "#10151F", "#E9E4D8", "#4D9DE0", "#E15554"),
    Palette("royal", "#221C35", "#F2ECDF", "#9B8CFF", "#FFB17A"),
    Palette("petrol", "#0E2430", "#EDE9DC", "#5FC8BA", "#F2B33D"),
)


def palette_for(city: str | None) -> Palette:
    """Stable city -> palette mapping (mirrored in JS: sum of char codes)."""
    key = sum(ord(ch) for ch in (city or ""))
    return PALETTES[key % len(PALETTES)]


def darken(hex_color: str, factor: float) -> str:
    """Scale an #RRGGBB colour toward black (for marks on light paper)."""
    r = round(int(hex_color[1:3], 16) * factor)
    g = round(int(hex_color[3:5], 16) * factor)
    b = round(int(hex_color[5:7], 16) * factor)
    return f"#{r:02X}{g:02X}{b:02X}"
