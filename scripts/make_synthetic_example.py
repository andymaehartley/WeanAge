"""Generate the bundled SYNTHETIC example dataset.

The values are simulated from known logistic weaning curves pushed through the
(placeholder) growth tables; they are NOT real measurements. They exist so the app
and tests can be exercised before lab data are available.

    python scripts/make_synthetic_example.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "weanage" / "data" / "examples" / "synthetic_example.csv"

# specimen, site, species, tooth, n_mm, months/mm (inverse of placeholder table),
# start age, weaning midpoint (months), scale, adult d15N, drop
SPECIMENS = [
    ("SYN-C01", "Site A", "cattle", "M2", 40, 1 / 3, 1, 7.0, 0.8, 5.5, 3.0),
    ("SYN-C02", "Site A", "cattle", "M2", 40, 1 / 3, 1, 8.0, 0.9, 5.0, 2.8),
    ("SYN-C03", "Site A", "cattle", "M2", 38, 1 / 3, 1, 6.5, 0.7, 6.0, 3.2),
    ("SYN-C04", "Site B", "cattle", "M2", 40, 1 / 3, 1, 4.5, 0.6, 5.8, 2.5),
    ("SYN-C05", "Site B", "cattle", "M2", 39, 1 / 3, 1, 4.0, 0.5, 6.2, 2.6),
    ("SYN-C06", "Site B", "cattle", "M2", 40, 1 / 3, 1, 5.0, 0.7, 5.6, 2.9),
    ("SYN-P01", "Site A", "pig", "M1", 15, 0.25, 0, 2.2, 0.35, 6.5, 2.4),
    ("SYN-P02", "Site A", "pig", "M1", 15, 0.25, 0, 1.9, 0.3, 7.0, 2.2),
    ("SYN-H01", "Site B", "horse", "M1", 55, 0.2667, 0, 7.5, 1.0, 4.0, 2.5),
]


def main() -> None:
    rng = np.random.default_rng(2027)
    rows = []
    for sid, site, species, tooth, n_mm, rate, a0, t_mid, scale, post, drop in SPECIMENS:
        positions = np.arange(0.5, n_mm, 1.0)
        ages = a0 + positions * rate
        d15n = post + drop / (1 + np.exp((ages - t_mid) / scale)) + rng.normal(0, 0.15, ages.size)
        for i, (p, d) in enumerate(zip(positions, d15n), start=1):
            pct_c = rng.normal(42, 1.5)
            cn = rng.normal(3.25, 0.06)
            pct_n = pct_c / cn * 14.007 / 12.011
            rows.append(
                {
                    "specimen_id": sid,
                    "site": site,
                    "species": species,
                    "tooth": tooth,
                    "sample_index": i,
                    "position_mm": round(float(p), 2),
                    "d15N": round(float(d), 2),
                    "d13C": round(float(rng.normal(-22, 0.3)), 2),
                    "pct_C": round(float(pct_c), 1),
                    "pct_N": round(float(pct_n), 1),
                    "cn_ratio": round(float(cn), 2),
                    "period": "Synthetic",
                    "notes": "SYNTHETIC - not real data",
                }
            )
    df = pd.DataFrame(rows)
    # One deliberately degraded sample to demonstrate QC flagging.
    bad = df.index[(df.specimen_id == "SYN-C01") & (df.sample_index == 12)]
    df.loc[bad, ["cn_ratio", "d15N", "notes"]] = [4.1, 11.9, "SYNTHETIC - degraded sample (fails C:N QC)"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"wrote {len(df)} rows to {OUT}")


if __name__ == "__main__":
    main()
