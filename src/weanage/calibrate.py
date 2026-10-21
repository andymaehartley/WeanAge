"""Build a growth table from reference points of known age.

Each point is (position on the tooth in mm, age in months), e.g. the forming edge
of a tooth from an animal of known age at death. We fit a line, a curve or an
"any increasing shape" (isotonic) fit, and the scatter around it becomes the
table's age uncertainty.
"""

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import isotonic_regression

from .schema import GrowthTable

Method = Literal["linear", "quadratic", "isotonic"]


class CalibrationPoint(BaseModel):
    position_mm: float = Field(ge=0)
    age_months: float


def calibrate_growth_table(species, tooth, points, method="linear", n_knots=6, source=""):
    if len(points) < 3:
        raise ValueError("at least 3 reference points are needed")
    pos = np.array([p.position_mm for p in points], dtype=float)
    age = np.array([p.age_months for p in points], dtype=float)
    order = np.argsort(pos)
    pos, age = pos[order], age[order]
    if np.ptp(pos) == 0:
        raise ValueError("reference points must span more than one position")
    warnings = []

    if method == "isotonic":
        fitted = isotonic_regression(age, increasing=True).x
        knot_pos = np.unique(pos)
        knot_age = np.array([fitted[pos == p].mean() for p in knot_pos])
        n_params = len(np.unique(np.round(fitted, 9)))  # one per step of the fitted staircase
        warnings.append("Isotonic fits follow the points closely, so their uncertainty is usually too small")
    else:
        degree = 1 if method == "linear" else 2
        if len(points) < degree + 2:
            raise ValueError(f"{method} calibration needs at least {degree + 2} points")
        coef = np.polyfit(pos, age, degree)
        fitted = np.polyval(coef, pos)
        knot_pos = np.linspace(pos.min(), pos.max(), max(n_knots, 2))
        knot_age = np.polyval(coef, knot_pos)
        if np.any(np.diff(knot_age) < 0):
            warnings.append("Fitted curve decreases within the range; ages were made non-decreasing")
            knot_age = np.maximum.accumulate(knot_age)
        n_params = degree + 1

    leftovers = age - fitted
    residual_sd = float(np.sqrt(np.sum(leftovers ** 2) / max(len(points) - n_params, 1)))
    spread = np.sum((age - age.mean()) ** 2)
    r2 = float(1 - np.sum(leftovers ** 2) / spread) if spread > 0 else None
    if len(points) < 8:
        warnings.append(f"Only {len(points)} reference points: treat the uncertainty estimate with caution")

    table = GrowthTable(
        species=species, tooth=tooth,
        label=f"{species.capitalize()} - {tooth} (calibrated, {method})",
        knots=[{"position_mm": round(float(p), 3), "age_months": round(float(a), 3)} for p, a in zip(knot_pos, knot_age)],
        age_uncertainty_months=round(residual_sd, 3),
        source=source or f"Calibrated from {len(points)} known-age reference points ({method} fit)",
        placeholder=False,
    )
    return {"table": table.model_dump(), "method": method, "n": len(points), "residual_sd": residual_sd,
            "r2": r2, "fitted": [float(v) for v in fitted], "warnings": warnings}
