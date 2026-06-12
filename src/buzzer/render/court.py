"""Half-court geometry in nba_api shot-chart units.

Units are tenths of feet. Origin is the centre of the hoop, +x to the
right looking at the basket, +y away from the baseline toward halfcourt
(exactly the LOC_X/LOC_Y convention of the shot chart endpoint).

These are the published dimensions of a regulation court — plain facts,
fine to draw. ``CourtMap`` converts court points into canvas (SVG)
coordinates, where y grows downward and the hoop sits near the bottom.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Regulation dimensions, tenths of feet.
COURT_HALF_WIDTH = 250.0  # court is 50 ft wide
BASELINE_Y = -52.5  # hoop centre is 5.25 ft inside the baseline
HALFCOURT_Y = 417.5  # half court is 47 ft from the baseline
HOOP_RADIUS = 7.5  # 18-inch rim
BACKBOARD_Y = -12.5  # backboard 4 ft from the baseline
BACKBOARD_HALF_WIDTH = 30.0  # 6 ft wide
THREE_RADIUS = 237.5  # 23 ft 9 in arc
CORNER_THREE_X = 220.0  # 22 ft corner three
KEY_HALF_WIDTH = 80.0  # 16 ft key
FT_LINE_Y = 137.5  # free-throw line 19 ft from baseline
FT_CIRCLE_RADIUS = 60.0
RESTRICTED_RADIUS = 40.0

# y where the corner-three straight lines meet the arc.
CORNER_BREAK_Y = math.sqrt(THREE_RADIUS**2 - CORNER_THREE_X**2)


@dataclass(frozen=True)
class CourtMap:
    """Maps court coordinates to canvas coordinates (y flipped)."""

    hoop_x: float  # canvas position of the hoop centre
    hoop_y: float
    scale: float  # canvas units per court unit

    def x(self, cx: float) -> float:
        return self.hoop_x + cx * self.scale

    def y(self, cy: float) -> float:
        return self.hoop_y - cy * self.scale

    def pt(self, cx: float, cy: float) -> tuple[float, float]:
        return self.x(cx), self.y(cy)

    def length(self, court_len: float) -> float:
        return court_len * self.scale

    # -- path builders (canvas coordinates, ready for an SVG ``d=``) -------

    def three_point_path(self) -> str:
        """Corner lines plus the arc, baseline to baseline."""
        x0, y0 = self.pt(-CORNER_THREE_X, BASELINE_Y)
        x1, y1 = self.pt(-CORNER_THREE_X, CORNER_BREAK_Y)
        x2, y2 = self.pt(CORNER_THREE_X, CORNER_BREAK_Y)
        x3, y3 = self.pt(CORNER_THREE_X, BASELINE_Y)
        r = self.length(THREE_RADIUS)
        # Left corner up, arc over the top of the key, right corner down.
        return (
            f"M {x0:.1f} {y0:.1f} L {x1:.1f} {y1:.1f} "
            f"A {r:.1f} {r:.1f} 0 0 1 {x2:.1f} {y2:.1f} "
            f"L {x3:.1f} {y3:.1f}"
        )

    def key_path(self) -> str:
        x0, y0 = self.pt(-KEY_HALF_WIDTH, BASELINE_Y)
        x1, y1 = self.pt(-KEY_HALF_WIDTH, FT_LINE_Y)
        x2, y2 = self.pt(KEY_HALF_WIDTH, FT_LINE_Y)
        x3, y3 = self.pt(KEY_HALF_WIDTH, BASELINE_Y)
        return f"M {x0:.1f} {y0:.1f} L {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f} L {x3:.1f} {y3:.1f}"

    def ft_circle_path(self) -> str:
        """Free-throw circle, top half solid (the half outside the key)."""
        r = self.length(FT_CIRCLE_RADIUS)
        x0, y0 = self.pt(-FT_CIRCLE_RADIUS, FT_LINE_Y)
        x1, y1 = self.pt(FT_CIRCLE_RADIUS, FT_LINE_Y)
        return f"M {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 0 1 {x1:.1f} {y1:.1f}"

    def restricted_path(self) -> str:
        r = self.length(RESTRICTED_RADIUS)
        x0, y0 = self.pt(-RESTRICTED_RADIUS, 0)
        x1, y1 = self.pt(RESTRICTED_RADIUS, 0)
        return f"M {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 0 1 {x1:.1f} {y1:.1f}"

    def baseline_line(self) -> tuple[float, float, float, float]:
        x0, y0 = self.pt(-COURT_HALF_WIDTH, BASELINE_Y)
        x1, y1 = self.pt(COURT_HALF_WIDTH, BASELINE_Y)
        return x0, y0, x1, y1

    def backboard_line(self) -> tuple[float, float, float, float]:
        x0, y0 = self.pt(-BACKBOARD_HALF_WIDTH, BACKBOARD_Y)
        x1, y1 = self.pt(BACKBOARD_HALF_WIDTH, BACKBOARD_Y)
        return x0, y0, x1, y1

    def sideline_path(self) -> str:
        """Baseline + both sidelines + halfcourt line, one open rectangle."""
        x0, y0 = self.pt(-COURT_HALF_WIDTH, HALFCOURT_Y)
        x1, y1 = self.pt(-COURT_HALF_WIDTH, BASELINE_Y)
        x2, y2 = self.pt(COURT_HALF_WIDTH, BASELINE_Y)
        x3, y3 = self.pt(COURT_HALF_WIDTH, HALFCOURT_Y)
        return f"M {x0:.1f} {y0:.1f} L {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f} L {x3:.1f} {y3:.1f} Z"

    def halfcourt_circle_path(self) -> str:
        r = self.length(FT_CIRCLE_RADIUS)
        x0, y0 = self.pt(-FT_CIRCLE_RADIUS, HALFCOURT_Y)
        x1, y1 = self.pt(FT_CIRCLE_RADIUS, HALFCOURT_Y)
        return f"M {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 0 0 {x1:.1f} {y1:.1f}"
