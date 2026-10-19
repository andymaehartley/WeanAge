"""Collagen quality-control flags for single samples."""

FLAG_DESCRIPTIONS = {
    "cn_out_of_range": "Atomic C:N outside the accepted range (possible contamination or degradation)",
    "pct_C_low": "%C below the minimum for well-preserved collagen",
    "pct_N_low": "%N below the minimum for well-preserved collagen",
    "yield_low": "Collagen yield below the minimum",
    "qc_not_assessed": "No C:N, %C or %N supplied, so collagen quality could not be checked",
}
FAILING = {"cn_out_of_range", "pct_C_low", "pct_N_low", "yield_low"}  # "not assessed" is only a note


def qc_flags(s, limits):
    flags = []
    if s.cn_ratio is not None and not limits.cn_min <= s.cn_ratio <= limits.cn_max:
        flags.append("cn_out_of_range")
    if s.pct_C is not None and s.pct_C < limits.pct_C_min:
        flags.append("pct_C_low")
    if s.pct_N is not None and s.pct_N < limits.pct_N_min:
        flags.append("pct_N_low")
    if s.collagen_yield_pct is not None and s.collagen_yield_pct < limits.collagen_yield_min:
        flags.append("yield_low")
    if s.cn_ratio is None and s.pct_C is None and s.pct_N is None:
        flags.append("qc_not_assessed")
    return flags


def passes_qc(flags):
    return not FAILING & set(flags)
