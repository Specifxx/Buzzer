"""Retail pricing from print costs.

"Margin" here is margin on the retail price: margin = (price - cost) / price.
A 60% target margin therefore means price = cost / (1 - 0.60) = 2.5x cost.
Prices are then rounded UP to the configured psychological ending (x.95).
"""

from __future__ import annotations

import math


def retail_price_usd(cost_usd: float, target_margin: float, round_ending: float = 0.95) -> float:
    """E.g. cost 13.75 at 60% margin -> raw 34.375 -> $34.95."""
    if not 0 <= target_margin < 1:
        raise ValueError(f"target_margin must be in [0, 1), got {target_margin}")
    if cost_usd <= 0:
        raise ValueError(f"cost_usd must be positive, got {cost_usd}")
    raw = cost_usd / (1.0 - target_margin)
    candidate = math.floor(raw) + round_ending
    if candidate < raw:
        candidate += 1.0
    return round(candidate, 2)


def to_cents(price_usd: float) -> int:
    return round(price_usd * 100)


def achieved_margin(price_usd: float, cost_usd: float) -> float:
    return (price_usd - cost_usd) / price_usd
