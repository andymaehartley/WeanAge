import numpy as np
import pytest

from weanage.schema import AnalysisOptions, IsotopeSample


def logistic_series(t_mid=7.0, scale=0.8, post=5.5, drop=3.0, ages=None, noise=0.1, seed=0):
    """A made-up δ15N series following a logistic weaning curve, with some noise."""
    rng = np.random.default_rng(seed)
    ages = np.arange(1, 16, 0.333) if ages is None else np.asarray(ages)
    return ages, post + drop / (1 + np.exp((ages - t_mid) / scale)) + rng.normal(0, noise, len(ages))


def opts(**settings):
    """Analysis settings; few random draws by default so the tests run fast."""
    return AnalysisOptions(**{"monte_carlo_draws": 200, **settings})


@pytest.fixture
def make_samples():
    def make(specimen_id="T1", site="Site A", species="cattle", tooth="M2", n=40, **curve):
        positions = np.arange(0.5, n, 1.0)
        _, y = logistic_series(ages=1 + positions * 11.5 / 45, **curve)  # cattle M2 table: 1 to 12.5 months over 45 mm
        return [IsotopeSample(specimen_id=specimen_id, site=site, species=species, tooth=tooth,
                              position_mm=float(p), d15N=float(v), cn_ratio=3.2) for p, v in zip(positions, y)]

    return make
