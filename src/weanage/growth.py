"""Conversion of sample position along the tooth to age at dentine formation."""

from __future__ import annotations

import numpy as np

from .schema import GrowthTable, LinearGrowthOverride


def position_to_age(
    positions_mm: np.ndarray | list[float],
    table: GrowthTable | None = None,
    override: LinearGrowthOverride | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(ages_months, extrapolated_mask)`` for each position.

    A ``LinearGrowthOverride`` takes precedence over the growth table. Outside the
    table's knots the end segments are extended linearly and the points flagged.
    """
    pos = np.asarray(positions_mm, dtype=float)
    if override is not None:
        ages = override.initiation_age_months + pos / override.extension_rate_mm_per_month
        return ages, np.zeros(pos.shape, dtype=bool)
    if table is None:
        raise ValueError("either a growth table or a linear override is required")

    kp = np.array([k.position_mm for k in table.knots])
    ka = np.array([k.age_months for k in table.knots])
    ages = np.interp(pos, kp, ka)

    below, above = pos < kp[0], pos > kp[-1]
    if below.any():
        slope = (ka[1] - ka[0]) / (kp[1] - kp[0])
        ages[below] = ka[0] + (pos[below] - kp[0]) * slope
    if above.any():
        slope = (ka[-1] - ka[-2]) / (kp[-1] - kp[-2])
        ages[above] = ka[-1] + (pos[above] - kp[-1]) * slope
    return ages, below | above
