"""Turns a position on the tooth into the age at which that dentine formed."""

import numpy as np


def position_to_age(positions_mm, table=None, override=None):
    """Returns (ages in months, True/False for "outside the table").

    A simple linear override wins over the table. Outside the table's first and
    last points the end lines are continued, and those ages are flagged.
    """
    pos = np.asarray(positions_mm, dtype=float)
    if override is not None:
        ages = override.initiation_age_months + pos / override.extension_rate_mm_per_month
        return ages, np.zeros(len(pos), dtype=bool)
    knot_pos = np.array([k.position_mm for k in table.knots])
    knot_age = np.array([k.age_months for k in table.knots])
    ages = np.interp(pos, knot_pos, knot_age)
    below, above = pos < knot_pos[0], pos > knot_pos[-1]
    first_slope = (knot_age[1] - knot_age[0]) / (knot_pos[1] - knot_pos[0])
    last_slope = (knot_age[-1] - knot_age[-2]) / (knot_pos[-1] - knot_pos[-2])
    ages[below] = knot_age[0] + (pos[below] - knot_pos[0]) * first_slope
    ages[above] = knot_age[-1] + (pos[above] - knot_pos[-1]) * last_slope
    return ages, below | above
