import numpy as np
import pytest

from weanage.schema import IsotopeSample


def logistic_series(t_mid=7.0, scale=0.8, post=5.5, drop=3.0, ages=None, noise=0.1, seed=0):
    rng = np.random.default_rng(seed)
    ages = np.arange(1, 16, 0.333) if ages is None else np.asarray(ages)
    y = post + drop / (1 + np.exp((ages - t_mid) / scale)) + rng.normal(0, noise, ages.size)
    return ages, y


@pytest.fixture
def make_samples():
    def _make(specimen_id="T1", site="Site A", species="cattle", tooth="M2", n=40, **kwargs):
        # The placeholder cattle M2 table is linear: age = 1 + position / 3.
        positions = np.arange(0.5, n, 1.0)
        ages = 1 + positions / 3
        _, y = logistic_series(ages=ages, **kwargs)
        return [
            IsotopeSample(
                specimen_id=specimen_id, site=site, species=species, tooth=tooth,
                position_mm=float(p), d15N=float(v), cn_ratio=3.2,
            )
            for p, v in zip(positions, y)
        ]

    return _make
