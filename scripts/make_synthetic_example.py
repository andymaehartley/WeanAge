"""Generate the bundled SYNTHETIC example dataset.

The values are simulated from known weaning curves pushed through the
(placeholder) growth tables; they are NOT real measurements. They exist so the app
and tests can be exercised before lab data are available, and include one case of
each situation the app should recognise:

* SYN-C01 - one degraded sample that fails collagen QC
* SYN-C07 - staged (two-phase) weaning, as expected under dairying
* SYN-H01 - an annual δ13C/δ15N cycle (seasonal diet) on top of weaning
* SYN-IND1 - one animal sampled on two teeth (M1 + M2) joined into one timeline

    python scripts/make_synthetic_example.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "weanage" / "data" / "examples" / "synthetic_example.csv"


def logistic(t_mid, scale, post, drop):
    return lambda a: post + drop / (1 + np.exp((a - t_mid) / scale))


def two_phase(t1, t2, scale, post, drop, first_fraction):
    return lambda a: post + drop * (
        first_fraction / (1 + np.exp((a - t1) / scale)) + (1 - first_fraction) / (1 + np.exp((a - t2) / scale))
    )


# (specimen, individual, site, species, tooth, n_mm, months/mm, start age, δ15N curve,
#  seasonal amplitude ‰ for δ15N and δ13C)
CATTLE_M2 = (1 / 3, 1)  # placeholder cattle M2: age = 1 + position / 3
CATTLE_M1 = (1 / 4, -2)  # placeholder cattle M1: age = -2 + position / 4
SPECIMENS = [
    ("SYN-C01", None, "Site A", "cattle", "M2", 40, *CATTLE_M2, logistic(7.0, 0.8, 5.5, 3.0), 0, 0),
    ("SYN-C02", None, "Site A", "cattle", "M2", 40, *CATTLE_M2, logistic(8.0, 0.9, 5.0, 2.8), 0, 0),
    ("SYN-C03", None, "Site A", "cattle", "M2", 38, *CATTLE_M2, logistic(6.5, 0.7, 6.0, 3.2), 0, 0),
    ("SYN-C04", None, "Site B", "cattle", "M2", 40, *CATTLE_M2, logistic(4.5, 0.6, 5.8, 2.5), 0, 0),
    ("SYN-C05", None, "Site B", "cattle", "M2", 39, *CATTLE_M2, logistic(4.0, 0.5, 6.2, 2.6), 0, 0),
    ("SYN-C06", None, "Site B", "cattle", "M2", 40, *CATTLE_M2, logistic(5.0, 0.7, 5.6, 2.9), 0, 0),
    ("SYN-C07", None, "Site C", "cattle", "M2", 44, *CATTLE_M2, two_phase(3.5, 10.0, 0.5, 5.4, 3.0, 0.45), 0, 0),
    ("SYN-M1", "SYN-IND1", "Site C", "cattle", "M1", 36, *CATTLE_M1, logistic(6.0, 0.7, 5.6, 2.8), 0, 0),
    ("SYN-M2", "SYN-IND1", "Site C", "cattle", "M2", 40, *CATTLE_M2, logistic(6.0, 0.7, 5.6, 2.8), 0, 0),
    ("SYN-P01", None, "Site A", "pig", "M1", 15, 0.25, 0, logistic(2.2, 0.35, 6.5, 2.4), 0, 0),
    ("SYN-P02", None, "Site A", "pig", "M1", 15, 0.25, 0, logistic(1.9, 0.3, 7.0, 2.2), 0, 0),
    ("SYN-H01", None, "Site B", "horse", "M1", 55, 0.2667, 0, logistic(7.5, 1.0, 4.0, 2.5), 0.35, 0.8),
]


def main(seed: int = 2027) -> None:
    rng = np.random.default_rng(seed)
    rows = []
    for sid, ind, site, species, tooth, n_mm, rate, a0, curve, s15, s13 in SPECIMENS:
        positions = np.arange(0.5, n_mm, 1.0)
        ages = a0 + positions * rate
        season = np.sin(2 * np.pi * ages / 12)
        d15n = curve(ages) + s15 * season + rng.normal(0, 0.15, ages.size)
        d13c = -22 + s13 * season + rng.normal(0, 0.15, ages.size)
        for i, (p, d, c) in enumerate(zip(positions, d15n, d13c), start=1):
            pct_c = rng.normal(42, 1.5)
            cn = rng.normal(3.25, 0.06)
            rows.append(
                {
                    "specimen_id": sid,
                    "individual_id": ind or "",
                    "site": site,
                    "species": species,
                    "tooth": tooth,
                    "sample_index": i,
                    "position_mm": round(float(p), 2),
                    "d15N": round(float(d), 2),
                    "d13C": round(float(c), 2),
                    "pct_C": round(float(pct_c), 1),
                    "pct_N": round(float(pct_c / cn * 14.007 / 12.011), 1),
                    "cn_ratio": round(float(cn), 2),
                    "period": "Synthetic",
                    "notes": "SYNTHETIC - not real data",
                }
            )
    df = pd.DataFrame(rows)
    bad = df.index[(df.specimen_id == "SYN-C01") & (df.sample_index == 12)]
    df.loc[bad, ["cn_ratio", "d15N", "notes"]] = [4.1, 11.9, "SYNTHETIC - degraded sample (fails C:N QC)"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"wrote {len(df)} rows to {OUT}")


if __name__ == "__main__":
    main()
