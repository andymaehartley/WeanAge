"""Build tooth growth tables from known-age reference measurements.

Input is a set of ``(position_mm, age_months)`` pairs for one species and tooth,
e.g. the position of the forming edge in animals of known age at death, or ages
from incremental-line counts in thin sections. The fitted relation is resampled
to knots so it slots into the normal piecewise-linear age model, and the residual
SD becomes the table's ``age_uncertainty_months``.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import isotonic_regression

from .schema import GrowthKnot, GrowthTable

Method = Literal["linear", "quadratic", "isotonic"]


class CalibrationPoint(BaseModel):
    position_mm: float = Field(ge=0)
    age_months: float


class CalibrationResult(BaseModel):
    table: GrowthTable
    method: Method
    n: int
    residual_sd: float
    r2: float | None
    fitted: list[float]
    warnings: list[str] = Field(default_factory=list)


def calibrate_growth_table(
    species: str,
    tooth: str,
    points: list[CalibrationPoint],
    method: Method = "linear",
    n_knots: int = 6,
    source: str = "",
) -> CalibrationResult:
    if len(points) < 3:
        raise ValueError("at least 3 reference points are needed")
    pos = np.array([p.position_mm for p in points], dtype=float)
    age = np.array([p.age_months for p in points], dtype=float)
    order = np.argsort(pos)
    pos, age = pos[order], age[order]
    if np.ptp(pos) == 0:
        raise ValueError("reference points must span more than one position")
    warnings: list[str] = []

    if method == "isotonic":
        fitted = isotonic_regression(age, increasing=True).x
        # Knots at the distinct positions, averaging tied fitted values.
        knot_pos, inverse = np.unique(pos, return_inverse=True)
        knot_age = np.bincount(inverse, fitted) / np.bincount(inverse)
        # Effective degrees of freedom of isotonic regression = number of fitted steps.
        n_params = len(np.unique(np.round(fitted, 9)))
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

    resid = age - fitted
    dof = max(len(points) - n_params, 1)
    residual_sd = float(np.sqrt(np.sum(resid**2) / dof))
    sst = float(np.sum((age - age.mean()) ** 2))
    r2 = float(1 - np.sum(resid**2) / sst) if sst > 0 else None
    if len(points) < 8:
        warnings.append(f"Only {len(points)} reference points: treat the uncertainty estimate with caution")

    # Strictly increasing positions are required; drop duplicates from isotonic ties.
    keep = np.concatenate([[True], np.diff(knot_pos) > 0])
    table = GrowthTable(
        species=species.lower(),
        tooth=tooth,
        label=f"{species.capitalize()} - {tooth} (calibrated, {method})",
        knots=[GrowthKnot(position_mm=round(float(p), 3), age_months=round(float(a), 3))
               for p, a in zip(knot_pos[keep], knot_age[keep])],
        age_uncertainty_months=round(residual_sd, 3),
        source=source or f"Calibrated from {len(points)} known-age reference points ({method} fit)",
        placeholder=False,
    )
    return CalibrationResult(
        table=table, method=method, n=len(points), residual_sd=residual_sd, r2=r2,
        fitted=[float(v) for v in fitted], warnings=warnings,
    )
