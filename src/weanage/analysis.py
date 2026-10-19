"""Specimen-level analysis: QC -> age model -> curve fits -> weaning estimates.

A "specimen" is one tooth, or - when ``individual_id`` is given - every tooth
sampled from one animal (e.g. M1 + M2 + M3 from one mandible). Each tooth is
converted to age with its own growth table, so the teeth join into one timeline.
"""

from __future__ import annotations

import atexit
import multiprocessing
import os
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from typing import Callable

import numpy as np
from scipy import stats

from .config import find_growth_table
from .growth import position_to_age
from .models import FitSettings, compare_fits, fit_model, model_average, seasonal_test
from .qc import passes_qc, qc_flags
from .schema import (
    AnalysisOptions, EstimateRow, GrowthTable, IsotopeSample, LinearGrowthOverride,
    SamplePoint, SpecimenResult,
)

# Sub-samples per increment used to average the curve across its age window.
WINDOW_STEPS = 15
# Below this many specimens a process pool costs more than it saves.
PARALLEL_MIN_SPECIMENS = 6

Progress = Callable[[int, int], None]


def group_key(sample: IsotopeSample) -> str:
    return sample.individual_id or sample.specimen_id


def group_by_specimen(samples: list[IsotopeSample]) -> "OrderedDict[str, list[IsotopeSample]]":
    groups: OrderedDict[str, list[IsotopeSample]] = OrderedDict()
    for s in samples:
        groups.setdefault(group_key(s), []).append(s)
    return groups


def window_weights(options: AnalysisOptions) -> np.ndarray:
    """Linear weights from 1 (earliest dentine in a section) to ``inner_dentine_weight``."""
    return np.linspace(1.0, options.inner_dentine_weight, WINDOW_STEPS)


def age_windows(rows, models, options: AnalysisOptions) -> np.ndarray:
    """Ages spanned by each sample's increment (n × WINDOW_STEPS).

    A horizontal section of height ``w`` centred on ``p`` cuts dentine formed while
    the growth front passed ``p ± w/2``; oblique growth layers mean it also holds
    later-formed inner dentine, modelled as a further ``growth_layer_offset_mm`` of
    growth. Sub-samples are spaced evenly along the tooth and mapped through the
    (possibly non-linear) growth table; ``window_weights`` sets their contribution.
    """
    out = np.empty((len(rows), WINDOW_STEPS))
    frac = np.linspace(0, 1, WINDOW_STEPS)
    for i, row in enumerate(rows):
        table, override = models[row.tooth]
        width = row.increment_width_mm or options.increment_width_mm
        lo = max(row.position_mm - width / 2, 0.0)
        hi = row.position_mm + width / 2 + options.growth_layer_offset_mm
        out[i], _ = position_to_age(lo + frac * (hi - lo), table, override)
    return out


def rising_profile_warning(t: np.ndarray, y: np.ndarray) -> str | None:
    """Flag δ15N series that rise with age instead of falling (cf. WEAN)."""
    if t.size < 5 or np.ptp(y) == 0:
        return None
    rho, p = stats.spearmanr(t, y)
    if rho > 0.3 and p < 0.05:
        return (
            f"δ15N rises with age (Spearman ρ = {rho:.2f}), unlike a typical weaning decline: "
            "consider physiological stress, a diet change or sampling order before interpreting"
        )
    return None


def seasonality_checks(t, d15n, residuals, d13c, period: float) -> tuple[list[str], dict[str, float]]:
    """Warn when an annual cycle could be masquerading as (or distorting) weaning.

    Livestock δ15N and δ13C can follow seasonal pasture and fodder changes. A
    significant annual sinusoid in the residuals of the best fit, or in δ13C, is a
    sign that part of the "weaning" signal may be seasonal.
    """
    warnings: list[str] = []
    diag: dict[str, float] = {}
    res = seasonal_test(t, residuals, period, detrend=0) if residuals is not None else None
    if res is not None:
        amp, p = res
        diag.update(residual_seasonal_amplitude=amp, residual_seasonal_p=p)
        if p < 0.05 and amp >= 0.2:
            warnings.append(
                f"Residuals show an annual cycle ({amp:.2f}‰, p = {p:.3f}): consider enabling the "
                "seasonal term, as seasonal diet change may be distorting the weaning estimate"
            )
    if d13c is not None and np.isfinite(d13c).sum() >= 6:
        mask = np.isfinite(d13c)
        res13 = seasonal_test(t[mask], d13c[mask], period, detrend=1)
        if res13 is not None:
            amp, p = res13
            diag.update(d13C_seasonal_amplitude=amp, d13C_seasonal_p=p)
            if p < 0.05 and amp >= 0.3:
                warnings.append(
                    f"δ13C oscillates annually ({amp:.2f}‰, p = {p:.3f}), suggesting seasonal diet "
                    "change; check whether the δ15N decline coincides with a season rather than weaning"
                )
        if np.ptp(d13c[mask]) > 0 and np.ptp(d15n[mask]) > 0:
            rho, _ = stats.spearmanr(d13c[mask], d15n[mask])
            diag.update(d13C_d15N_spearman=float(rho))
    return warnings, diag


def _age_models(rows, options) -> tuple[dict, list[str], bool, float] | str:
    """Resolve the age model for every tooth; returns an error message if one is missing."""
    models: dict[str, tuple[GrowthTable | None, LinearGrowthOverride | None]] = {}
    labels, placeholder, age_sd = [], False, 0.0
    species = rows[0].species
    for tooth in OrderedDict.fromkeys(r.tooth for r in rows):
        override = options.override_for(species, tooth)
        table = find_growth_table(species, tooth, options.growth_tables)
        if override is not None:
            labels.append(
                f"{tooth}: custom linear {override.initiation_age_months:g} mo + "
                f"position / {override.extension_rate_mm_per_month:g} mm·mo⁻¹"
            )
        elif table is not None:
            labels.append(table.label)
            placeholder |= table.placeholder
            age_sd = max(age_sd, table.age_uncertainty_months)
        else:
            return f"No growth table for {species} {tooth}; supply a custom age model"
        models[tooth] = (None if override else table, override)
    return models, labels, placeholder, age_sd


def analyze_specimen(samples: list[IsotopeSample], options: AnalysisOptions) -> SpecimenResult:
    first = samples[0]
    rows = sorted(samples, key=lambda s: (s.tooth, s.position_mm))
    teeth = list(OrderedDict.fromkeys(r.tooth for r in rows))
    warnings: list[str] = []
    base = dict(
        specimen_id=group_key(first), site=first.site, species=first.species,
        tooth="+".join(teeth), period=first.period,
        known_weaning_age_months=first.known_weaning_age_months,
        published_weaning_age_months=first.published_weaning_age_months,
    )

    resolved = _age_models(rows, options)
    if isinstance(resolved, str):
        return SpecimenResult(**base, growth_table="none", growth_placeholder=False,
                              points=[], fits=[], warnings=[resolved])
    models, labels, placeholder, age_sd = resolved
    if placeholder:
        warnings.append("Ages use a PLACEHOLDER growth table (TBD-LAB); estimates are illustrative only")
    if len(teeth) > 1:
        warnings.append(f"{len(teeth)} teeth ({', '.join(teeth)}) combined into one timeline")

    ages = np.empty(len(rows))
    extrapolated = np.zeros(len(rows), dtype=bool)
    for tooth, (table, override) in models.items():
        idx = [i for i, r in enumerate(rows) if r.tooth == tooth]
        a, e = position_to_age([rows[i].position_mm for i in idx], table, override)
        ages[idx], extrapolated[idx] = a, e
    if extrapolated.any():
        warnings.append(
            f"{int(extrapolated.sum())} sample(s) lie beyond the growth table; their ages are extrapolated"
        )

    windows = age_windows(rows, models, options) if options.time_averaging else None
    points: list[SamplePoint] = []
    for i, row in enumerate(rows):
        flags = qc_flags(row, options.qc)
        points.append(
            SamplePoint(
                position_mm=row.position_mm,
                age_months=round(float(ages[i]), 4),
                age_min=round(float(windows[i, 0]), 4) if windows is not None else None,
                age_max=round(float(windows[i, -1]), 4) if windows is not None else None,
                d15N=row.d15N, d13C=row.d13C, tooth=row.tooth,
                extrapolated=bool(extrapolated[i]),
                qc_flags=flags,
                used_in_fit=passes_qc(flags) or not options.qc.exclude_failed,
            )
        )
    order = np.argsort(ages, kind="stable")
    points = [points[i] for i in order]
    if windows is not None:
        windows = windows[order]
    excluded = sum(not p.used_in_fit for p in points)
    if excluded:
        warnings.append(f"{excluded} sample(s) failed collagen QC and were excluded from fitting")

    used = np.array([p.used_in_fit for p in points], dtype=bool)
    fit_t = np.array([p.age_months for p in points])[used]
    fit_y = np.array([p.d15N for p in points])[used]
    if (msg := rising_profile_warning(fit_t, fit_y)) is not None:
        warnings.append(msg)

    baseline = options.baseline_for(first.site, first.species)
    post_range = None
    if baseline is not None and options.constrain_adult_plateau:
        post_range = (baseline.mean - 2 * baseline.sd, baseline.mean + 2 * baseline.sd)
    if windows is not None:
        warnings.append(
            "Time averaging on: curves show the underlying diet signal, which is sharper than the sampled values"
        )

    settings = FitSettings(
        threshold=options.transition_threshold,
        analytical_sd=options.analytical_sd_permil,
        min_drop=options.min_weaning_drop_permil,
        draws=options.monte_carlo_draws,
        seed=options.random_seed,
        age_uncertainty=age_sd,
        age_windows=windows[used] if windows is not None else None,
        window_weights=window_weights(options),
        post_range=post_range,
        adult_baseline=baseline.mean if baseline is not None else None,
        elbow_normalise=options.elbow_normalise,
        seasonal=options.seasonal_term,
        season_period=options.season_period_months,
        uncertainty=options.uncertainty,
        bootstrap_draws=options.bootstrap_draws,
    )
    fits = [fit_model(name, fit_t, fit_y, settings) for name in options.models]
    best = compare_fits(fits)
    averaged = model_average(fits, seed=options.random_seed) if len([f for f in fits if f.akaike_weight]) > 1 else {}

    diagnostics: dict[str, float] = {}
    best_fit = next((f for f in fits if f.model == best), None)
    if best_fit is not None and best_fit.curve_age:
        resid = fit_y - np.interp(fit_t, best_fit.curve_age, best_fit.curve_d15N)
        d13c = np.array([np.nan if p.d13C is None else p.d13C for p in points])[used]
        extra, diagnostics = seasonality_checks(
            fit_t, fit_y, None if options.seasonal_term else resid, d13c, options.season_period_months
        )
        warnings.extend(extra)

    return SpecimenResult(
        **base,
        growth_table="; ".join(labels),
        growth_placeholder=placeholder,
        points=points,
        fits=fits,
        best_model=best,
        model_average=averaged,
        diagnostics=diagnostics,
        warnings=warnings,
        adult_baseline=baseline,
    )


_POOL: tuple[int, ProcessPoolExecutor] | None = None


def _pool(workers: int) -> ProcessPoolExecutor:
    """A long-lived worker pool, so repeated analyses skip process start-up.

    "spawn" is safe from the threaded web server (fork can deadlock there) and
    matches the default on macOS and Windows.
    """
    global _POOL
    if _POOL is None or _POOL[0] != workers:
        _shutdown_pool()
        ctx = multiprocessing.get_context("spawn")
        _POOL = (workers, ProcessPoolExecutor(max_workers=workers, mp_context=ctx))
    return _POOL[1]


def _shutdown_pool() -> None:
    global _POOL
    if _POOL is not None:
        _POOL[1].shutdown(wait=False, cancel_futures=True)
        _POOL = None


atexit.register(_shutdown_pool)


def analyze(
    samples: list[IsotopeSample],
    options: AnalysisOptions,
    progress: Progress | None = None,
    workers: int | None = None,
) -> list[SpecimenResult]:
    """Analyse every specimen, in parallel processes for larger datasets."""
    groups = list(group_by_specimen(samples).values())
    total = len(groups)
    workers = workers if workers is not None else min(os.cpu_count() or 1, 8)
    results: list[SpecimenResult | None] = [None] * total
    if workers > 1 and total >= PARALLEL_MIN_SPECIMENS:
        try:
            pool = _pool(workers)
            futures = {pool.submit(analyze_specimen, g, options): i for i, g in enumerate(groups)}
            for done, fut in enumerate(as_completed(futures), start=1):
                results[futures[fut]] = fut.result()
                if progress:
                    progress(done, total)
            return results  # type: ignore[return-value]
        except (OSError, RuntimeError, ImportError, BrokenProcessPool):
            _shutdown_pool()  # e.g. sandboxed environments without process support
    for i, rows in enumerate(groups):
        results[i] = analyze_specimen(rows, options)
        if progress:
            progress(i + 1, total)
    return results  # type: ignore[return-value]


def estimate_rows(results: list[SpecimenResult]) -> list[EstimateRow]:
    """Flatten results to one row per specimen × model (plus the model average)."""
    rows: list[EstimateRow] = []
    for res in results:
        common = dict(
            specimen_id=res.specimen_id, site=res.site, species=res.species, period=res.period,
            known_weaning_age_months=res.known_weaning_age_months,
            published_weaning_age_months=res.published_weaning_age_months,
        )
        for fit in res.fits:
            if not fit.converged:
                continue
            rows.append(
                EstimateRow(
                    **common,
                    model=fit.model,
                    is_best=fit.model == res.best_model,
                    onset=fit.onset.estimate if fit.onset else None,
                    midpoint=fit.midpoint.estimate if fit.midpoint else None,
                    completion=fit.completion.estimate if fit.completion else None,
                    completion_ci_low=fit.completion.ci_low if fit.completion else None,
                    completion_ci_high=fit.completion.ci_high if fit.completion else None,
                    akaike_weight=fit.akaike_weight,
                )
            )
        if res.model_average:
            avg = res.model_average
            comp = avg.get("completion")
            rows.append(
                EstimateRow(
                    **common,
                    model="average",
                    onset=avg["onset"].estimate if "onset" in avg else None,
                    midpoint=avg["midpoint"].estimate if "midpoint" in avg else None,
                    completion=comp.estimate if comp else None,
                    completion_ci_low=comp.ci_low if comp else None,
                    completion_ci_high=comp.ci_high if comp else None,
                )
            )
    return rows
