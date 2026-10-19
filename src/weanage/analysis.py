"""Specimen-level analysis: QC -> age model -> curve fits -> weaning estimates."""

from __future__ import annotations

from collections import OrderedDict

import numpy as np

from .config import find_growth_table
from .growth import position_to_age
from .models import compare_fits, fit_model
from .qc import passes_qc, qc_flags
from .schema import AnalysisOptions, EstimateRow, IsotopeSample, SamplePoint, SpecimenResult


def group_by_specimen(samples: list[IsotopeSample]) -> "OrderedDict[str, list[IsotopeSample]]":
    groups: OrderedDict[str, list[IsotopeSample]] = OrderedDict()
    for s in samples:
        groups.setdefault(s.specimen_id, []).append(s)
    return groups


def analyze_specimen(samples: list[IsotopeSample], options: AnalysisOptions) -> SpecimenResult:
    first = samples[0]
    rows = sorted(samples, key=lambda s: s.position_mm)
    warnings: list[str] = []

    table = find_growth_table(first.species, first.tooth)
    override = options.override_for(first.species, first.tooth)
    if override is not None:
        table_label = (
            f"Custom linear: {override.initiation_age_months:g} mo + "
            f"position / {override.extension_rate_mm_per_month:g} mm·mo⁻¹"
        )
        placeholder = False
        age_sd = 0.0
    elif table is not None:
        table_label, placeholder, age_sd = table.label, table.placeholder, table.age_uncertainty_months
        if placeholder:
            warnings.append(
                "Ages use a PLACEHOLDER growth table (TBD-LAB); estimates are illustrative only"
            )
    else:
        return SpecimenResult(
            specimen_id=first.specimen_id,
            site=first.site,
            species=first.species,
            tooth=first.tooth,
            period=first.period,
            growth_table="none",
            growth_placeholder=False,
            points=[],
            fits=[],
            warnings=[f"No growth table for {first.species} {first.tooth}; supply a custom age model"],
            known_weaning_age_months=first.known_weaning_age_months,
        )

    ages, extrapolated = position_to_age(
        [r.position_mm for r in rows], table, override
    )
    if extrapolated.any():
        warnings.append(
            f"{int(extrapolated.sum())} sample(s) lie beyond the growth table; their ages are extrapolated"
        )

    points: list[SamplePoint] = []
    for row, age, extra in zip(rows, ages, extrapolated):
        flags = qc_flags(row, options.qc)
        used = passes_qc(flags) or not options.qc.exclude_failed
        points.append(
            SamplePoint(
                position_mm=row.position_mm,
                age_months=round(float(age), 4),
                d15N=row.d15N,
                extrapolated=bool(extra),
                qc_flags=flags,
                used_in_fit=used,
            )
        )
    excluded = sum(not p.used_in_fit for p in points)
    if excluded:
        warnings.append(f"{excluded} sample(s) failed collagen QC and were excluded from fitting")

    fit_t = np.array([p.age_months for p in points if p.used_in_fit])
    fit_y = np.array([p.d15N for p in points if p.used_in_fit])
    fits = [
        fit_model(
            name,
            fit_t,
            fit_y,
            threshold=options.transition_threshold,
            analytical_sd=options.analytical_sd_permil,
            min_drop=options.min_weaning_drop_permil,
            draws=options.monte_carlo_draws,
            seed=options.random_seed,
            age_uncertainty=age_sd,
        )
        for name in options.models
    ]
    best = compare_fits(fits)

    return SpecimenResult(
        specimen_id=first.specimen_id,
        site=first.site,
        species=first.species,
        tooth=first.tooth,
        period=first.period,
        growth_table=table_label,
        growth_placeholder=placeholder,
        points=points,
        fits=fits,
        best_model=best,
        warnings=warnings,
        known_weaning_age_months=first.known_weaning_age_months,
    )


def analyze(samples: list[IsotopeSample], options: AnalysisOptions) -> list[SpecimenResult]:
    return [analyze_specimen(rows, options) for rows in group_by_specimen(samples).values()]


def estimate_rows(results: list[SpecimenResult]) -> list[EstimateRow]:
    """Flatten results to one row per specimen × model."""
    rows: list[EstimateRow] = []
    for res in results:
        for fit in res.fits:
            if not fit.converged:
                continue
            rows.append(
                EstimateRow(
                    specimen_id=res.specimen_id,
                    site=res.site,
                    species=res.species,
                    period=res.period,
                    model=fit.model,
                    is_best=fit.model == res.best_model,
                    onset=fit.onset.estimate if fit.onset else None,
                    midpoint=fit.midpoint.estimate if fit.midpoint else None,
                    completion=fit.completion.estimate if fit.completion else None,
                    completion_ci_low=fit.completion.ci_low if fit.completion else None,
                    completion_ci_high=fit.completion.ci_high if fit.completion else None,
                    known_weaning_age_months=res.known_weaning_age_months,
                )
            )
    return rows
