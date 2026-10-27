"""Make the SYNTHETIC diet-mixing example: human bone collagen from two invented sites.

    python scripts/make_mixing_example.py

Each person's diet shares are drawn around a site mean; their collagen is the share-weighted
food values (each food drawn from its spread) plus the collagen-diet offsets and measurement
noise, using the placeholder values in data/diet_sources.json. The true shares are in each
row's notes. These are not real measurements.
"""

import csv
from pathlib import Path

import numpy as np

from weanage import config

OUT = Path(__file__).resolve().parents[1] / "src" / "weanage" / "data" / "examples" / "synthetic_mixing_example.csv"
SITES = {"Inland": [0.70, 0.0, 0.30, 0.0], "Coast": [0.40, 0.0, 0.20, 0.40]}  # C3, C4, terrestrial, marine
N, CONCENTRATION, NOISE = 15, 60, 0.2


def main():
    rng = np.random.default_rng(3)
    stored = config.diet_sources()
    sources = stored["sources"]
    rows = []
    for site, mean in SITES.items():
        for i in range(N):
            shares = rng.dirichlet(np.array(mean) * CONCENTRATION + 0.01)
            values = {}
            for iso in ("d13C", "d15N", "d34S"):
                foods = np.array([rng.normal(s[iso], s[f"{iso}_sd"]) for s in sources])
                values[iso] = shares @ foods + stored[f"offset_{iso}"] + rng.normal(0, NOISE)
            truth = ", ".join(f"{s['name']} {p:.2f}" for s, p in zip(sources, shares))
            rows.append({"specimen_id": f"{site[0]}{i + 1:02d}", "site": site, "species": "human", "period": "",
                         **{iso: round(v, 2) for iso, v in values.items()}, "notes": f"SYNTHETIC; true shares {truth}"})
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} samples to {OUT}")


if __name__ == "__main__":
    main()
