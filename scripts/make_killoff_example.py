"""Make the SYNTHETIC kill-off example: sheep/goat mandibles from two invented sites.

    python scripts/make_killoff_example.py

Site A was drawn with most deaths in stages A–B (as Payne's milk model), Site B with most in
C–D (as his meat model). About a fifth of the mandibles can only be put in two neighbouring
stages ("C/D"), as often happens. The true stage is in each row's notes. These are not real data.
"""

import csv
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "src" / "weanage" / "data" / "examples" / "synthetic_killoff_example.csv"
STAGES = "ABCDEFGHI"
DEATHS = {  # share of the herd dying in each stage
    "Site A": [0.25, 0.30, 0.10, 0.08, 0.07, 0.06, 0.07, 0.05, 0.02],
    "Site B": [0.04, 0.08, 0.30, 0.28, 0.10, 0.07, 0.07, 0.04, 0.02],
}
N = 60


def main():
    rng = np.random.default_rng(5)
    rows = []
    for site, deaths in DEATHS.items():
        for i, k in enumerate(rng.choice(9, size=N, p=deaths)):
            stage = STAGES[k]
            if rng.random() < 0.2:  # only narrowed to two neighbouring stages
                pair = (k - 1, k) if k == 8 or (k > 0 and rng.random() < 0.5) else (k, k + 1)
                stage = f"{STAGES[pair[0]]}/{STAGES[pair[1]]}"
            rows.append({"specimen_id": f"{site[-1]}{i + 1:03d}", "site": site, "species": "sheep/goat",
                         "payne_stage": stage, "period": "", "notes": f"SYNTHETIC; true stage {STAGES[k]}"})
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} mandibles to {OUT}")


if __name__ == "__main__":
    main()
