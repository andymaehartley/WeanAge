"""Shifts and episodes along a tooth: where a series changes level, and when δ15N and δ13C part ways.

* Shifts (find_shifts). The series is split into up to three flat stretches at the points that fit
  best, and the number of stretches is chosen by BIC, so a shift is only reported when it is
  supported. Used for 87Sr/86Sr along enamel (moves between geologies; Bentley 2006) and δ34S along
  dentine (moves or a change of diet).
* Stress episodes (stress_episodes). Starvation and illness raise δ15N while δ13C stays level or
  falls, whereas a diet change usually moves both the same way (Beaumont & Montgomery 2016). An
  episode is a run of samples whose δ15N is above the fitted weaning curve while their δ13C is
  below its own expected level.
"""

import math

import numpy as np
from scipy import stats


def segment_cost(y, cuts):
    """Sum of squares around the mean of each stretch between the cuts (indices where a stretch starts)."""
    edges = [0, *cuts, len(y)]
    return sum(float(np.sum((y[a:b] - y[a:b].mean()) ** 2)) for a, b in zip(edges, edges[1:]))


def find_shifts(x, y, min_shift, noise_sd=None, max_shifts=2, min_run=2):
    """Level shifts in y along x, in the order of x. Returns [{position, between, from_value, to_value, size}].

    noise_sd: the analytical precision if known; otherwise the scatter is estimated from the data.
    A shift smaller than min_shift is not reported even if it is statistically supported. Two steps
    the same way with at most min_run + 1 samples between them are one gradual shift (a blurred step).
    """
    order = np.argsort(x)
    x, y = np.asarray(x, dtype=float)[order], np.asarray(y, dtype=float)[order]
    n = len(y)
    if n < 2 * min_run:
        return []
    candidates = [[]]
    places = range(min_run, n - min_run + 1)
    candidates += [[c] for c in places]
    if max_shifts >= 2:
        candidates += [[a, b] for a in places for b in places if b - a >= min_run]

    def bic(cuts):
        sse = max(segment_cost(y, cuts), 1e-12)
        k = 2 * len(cuts) + 1  # a mean per stretch and a position per shift
        fit = sse / noise_sd ** 2 if noise_sd else n * math.log(sse / n)
        return fit + k * math.log(n)

    best = min(candidates, key=bic)
    edges = [0, *best, n]
    means = [float(y[a:b].mean()) for a, b in zip(edges, edges[1:])]
    if len(best) == 2 and (means[1] - means[0]) * (means[2] - means[1]) > 0 and best[1] - best[0] <= min_run + 1:
        start, end = best  # one gradual shift (a blurred step)
        size = means[2] - means[0]
        if abs(size) < min_shift:
            return []
        return [{"position": float((x[start - 1] + x[end]) / 2), "between": [float(x[start - 1]), float(x[end])],
                 "from_value": means[0], "to_value": means[2], "size": size, "gradual": True}]
    shifts = []
    for i, cut in enumerate(best):
        size = means[i + 1] - means[i]
        if abs(size) >= min_shift:
            shifts.append({"position": float((x[cut - 1] + x[cut]) / 2), "between": [float(x[cut - 1]), float(x[cut])],
                           "from_value": means[i], "to_value": means[i + 1], "size": size, "gradual": False})
    return shifts


def stress_episodes(t, d15n_excess, d13c_excess, min_d15n, min_d13c, min_run=2):
    """Runs of samples with δ15N above the weaning curve and δ13C below its expected level.

    d15n_excess, d13c_excess: observed minus expected values, in age order.
    Returns the episodes and the Spearman correlation of the two (negative = opposing covariance).
    """
    t, n_ex, c_ex = (np.asarray(a, dtype=float) for a in (t, d15n_excess, d13c_excess))
    flagged = (n_ex >= min_d15n) & (c_ex <= -min_d13c)
    episodes, start = [], None
    for i, on in enumerate([*flagged, False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= min_run:
                episodes.append({"from_age": float(t[start]), "to_age": float(t[i - 1]), "n_samples": i - start,
                                 "d15N_above_permil": float(n_ex[start:i].mean()),
                                 "d13C_below_permil": float(-c_ex[start:i].mean())})
            start = None
    rho = float(stats.spearmanr(n_ex, c_ex)[0]) if len(t) >= 5 and np.ptp(n_ex) > 0 and np.ptp(c_ex) > 0 else None
    return episodes, rho
