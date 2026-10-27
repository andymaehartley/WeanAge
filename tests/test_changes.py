"""Level shifts (87Sr/86Sr, δ34S) and stress episodes (opposing δ15N and δ13C)."""

import numpy as np

from weanage.analysis import analyze_specimen
from weanage.changes import find_shifts, stress_episodes
from weanage.models import logistic
from weanage.schema import AnalysisOptions, IsotopeSample


def test_shifts_are_found_only_when_supported():
    rng = np.random.default_rng(0)
    x = np.arange(20.0)
    flat = find_shifts(x, 0.7095 + rng.normal(0, 0.0001, 20), 0.0005)
    assert flat == []
    step = np.where(x < 12, 0.7090, 0.7120) + rng.normal(0, 0.0001, 20)
    (shift,) = find_shifts(x, step, 0.0005)
    assert 11 <= shift["position"] <= 12 and abs(shift["size"] - 0.003) < 0.0005
    # Statistically clear but smaller than the minimum: not reported.
    assert find_shifts(x, np.where(x < 12, 0.0, 0.0003) + rng.normal(0, 0.00001, 20), 0.0005) == []


def test_stress_needs_opposing_runs():
    t = np.arange(10.0)
    n_ex = np.array([0, 0, 1, 1, 1, 0, 0, 1, 0, 0.0])
    c_ex = np.array([0, 0, -0.5, -0.6, -0.4, 0, 0, -0.5, 0, 0.0])
    episodes, rho = stress_episodes(t, n_ex, c_ex, 0.5, 0.3)
    assert [(e["from_age"], e["to_age"]) for e in episodes] == [(2.0, 4.0)]  # the lone sample at 7 is not a run
    assert rho < 0
    same_way, _ = stress_episodes(t, n_ex, -c_ex, 0.5, 0.3)  # both rise: a diet change, not stress
    assert same_way == []


def test_specimen_reports_stress_and_sulphur():
    rng = np.random.default_rng(1)
    pos = np.arange(0.5, 40, 1.0)
    age = 1 + pos * 11.5 / 45
    d15n = logistic(age, 5.5, 2.8, 5, 0.6) + rng.normal(0, 0.1, age.size)
    d13c = -22 + 0.5 * (age > 6) + rng.normal(0, 0.05, age.size)
    episode = (age > 8.5) & (age < 9.6)
    d15n[episode] += 1.2
    d13c[episode] -= 0.8
    d34s = np.where(age < 7, 10.0, 4.0) + rng.normal(0, 0.3, age.size)
    samples = [IsotopeSample(specimen_id="S1", site="X", species="cattle", tooth="M2", position_mm=p, d15N=n, d13C=c,
                             d34S=s, cn_ratio=3.2) for p, n, c, s in zip(pos, d15n, d13c, d34s)]
    d = analyze_specimen(samples, AnalysisOptions(monte_carlo_draws=50))["diagnostics"]
    assert d["stress_episodes"] and all(8 < e["from_age"] < 10 for e in d["stress_episodes"])
    (shift,) = d["d34S_shifts"]
    assert 6 < shift["position"] < 8 and shift["size"] < -5
