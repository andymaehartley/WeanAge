"""Make the SYNTHETIC bone example: cattle from two invented sites with known weaning ages.

    python scripts/make_bone_example.py

Each calf's bone δ15N is simulated with the bone model itself (src/weanage/bone.py), so the
true answers are known: Site A weans late (3 to 9 months), Site B early, as in dairying
(1 to 4 months). Ages at death are given as ranges, as tooth wear would give them.
These are not real measurements.
"""

import csv
from pathlib import Path

import numpy as np

from weanage import config
from weanage.bone import STEP, bone_curve, renewal

OUT = Path(__file__).resolve().parents[1] / "src" / "weanage" / "data" / "examples" / "synthetic_bone_example.csv"
SITES = {"Site A": (3.0, 9.0), "Site B": (1.0, 4.0)}  # true weaning start and end (months)
FEMALE_MEAN, ENRICHMENT, WEANING_FOOD, SCATTER = 6.0, 2.8, 5.6, 0.35  # weaning follows WARN's parabolic form
NEWBORN_OFFSET = 0.8  # newborn bone above the mothers' mean


def age_range(age):
    """Wider ranges for older animals, as wear stages are."""
    half = 1.0 if age < 6 else 3.0 if age < 18 else 6.0
    return max(0.0, age - half), age + half


def main():
    rng = np.random.default_rng(7)
    table = config.find_turnover_table("cattle")
    grid = np.arange(0, 60 + STEP, STEP)
    rows = []
    for site, (t1, t2) in SITES.items():
        bone, _ = bone_curve(grid, renewal(table, grid), t1, t2, ENRICHMENT, WEANING_FOOD, FEMALE_MEAN,
                             newborn_offset=NEWBORN_OFFSET)
        ages = np.sort(np.concatenate([rng.uniform(0, 12, 26), rng.uniform(12, 36, 14)]))
        for i, age in enumerate(ages, start=1):
            low, high = age_range(age)
            d15n = np.interp(age, grid, bone) + rng.normal(0, SCATTER)
            rows.append([f"{site[-1]}-C{i:02d}", site, "cattle", "rib", "non-adult", "",
                         round(low, 1), round(high, 1), round(d15n, 2), round(rng.normal(-21.8, 0.3), 2),
                         round(rng.normal(3.25, 0.06), 2), "SYNTHETIC - not real data"])
        for i in range(1, 15):
            sex = "F" if i <= 10 else "M"
            rows.append([f"{site[-1]}-A{i:02d}", site, "cattle", "rib", "adult", sex, "", "",
                         round(FEMALE_MEAN + rng.normal(0, 0.4) + (0.3 if sex == "M" else 0), 2),
                         round(rng.normal(-22.0, 0.3), 2), round(rng.normal(3.25, 0.06), 2),
                         "SYNTHETIC - not real data"])
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["specimen_id", "site", "species", "element", "age_class", "sex", "age_min_months",
                         "age_max_months", "d15N", "d13C", "cn_ratio", "notes"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
