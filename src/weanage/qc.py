"""Collagen quality-control flags for individual samples."""

from __future__ import annotations

from .schema import IsotopeSample, QCThresholds

# Flags that make a sample unreliable; "qc_not_assessed" is informational only.
FAILING_FLAGS = {"cn_out_of_range", "pct_C_low", "pct_N_low", "yield_low"}

FLAG_DESCRIPTIONS = {
    "cn_out_of_range": "Atomic C:N outside the accepted range (possible contamination or degradation)",
    "pct_C_low": "%C below the minimum for well-preserved collagen",
    "pct_N_low": "%N below the minimum for well-preserved collagen",
    "yield_low": "Collagen yield below the minimum",
    "qc_not_assessed": "No C:N, %C or %N supplied, so collagen quality could not be checked",
}


def qc_flags(sample: IsotopeSample, thresholds: QCThresholds) -> list[str]:
    flags: list[str] = []
    if sample.cn_ratio is not None and not thresholds.cn_min <= sample.cn_ratio <= thresholds.cn_max:
        flags.append("cn_out_of_range")
    if sample.pct_C is not None and sample.pct_C < thresholds.pct_C_min:
        flags.append("pct_C_low")
    if sample.pct_N is not None and sample.pct_N < thresholds.pct_N_min:
        flags.append("pct_N_low")
    if (
        sample.collagen_yield_pct is not None
        and sample.collagen_yield_pct < thresholds.collagen_yield_min
    ):
        flags.append("yield_low")
    if sample.cn_ratio is None and sample.pct_C is None and sample.pct_N is None:
        flags.append("qc_not_assessed")
    return flags


def passes_qc(flags: list[str]) -> bool:
    return not FAILING_FLAGS.intersection(flags)
