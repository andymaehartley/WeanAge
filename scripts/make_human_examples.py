"""Make the SYNTHETIC human examples: dental stages, enamel hypoplasia, a cemetery, and mobility.

    python scripts/make_human_examples.py

All values are invented; the truth is in each row's notes. Dental stages are drawn from the
(placeholder) formation ages in data/dental_stages.json, so the dental example checks the method,
not the ages themselves.
"""

import csv
from pathlib import Path

import numpy as np

from weanage import config
from weanage.dental_age import stage_ages
from weanage.lifetable import survival
from weanage.schema import MOORREES_STAGES

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "src" / "weanage" / "data" / "examples"  # bundled: no published data of this kind found
TEST_DATA = ROOT / "tests" / "data"  # published examples exist; these simulated ones check the methods


def write(name, rows, folder=EXAMPLES):
    with (folder / name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {name}")


def dental(rng):
    """24 children; each tooth's stage is the one reached at its own 'developmental age' (true age ± 8%)."""
    table = config.dental_stages()
    rows = []
    for i, age in enumerate(np.sort(rng.uniform(3, 150, 24))):
        for tooth in ("dm2", "M1", "I1", "C", "PM2", "M2"):
            ages = stage_ages(tooth, table)
            own = age * rng.normal(1, 0.08)
            reached = [s for s in MOORREES_STAGES if ages[s] <= own]
            if reached:  # a tooth not yet initiated is not scored
                rows.append({"specimen_id": f"C{i + 1:02d}", "site": "Site A", "species": "human", "tooth": tooth,
                             "stage": reached[-1], "notes": f"SYNTHETIC; true age {age:.1f} months"})
    write("synthetic_dental_example.csv", rows)


def hypoplasia(rng):
    """15 people with defects on I1 and C; most were formed at 2-4 years (around weaning)."""
    table = config.dental_stages()["teeth"]
    heights = {"I1": 11.0, "C": 11.5}
    rows = []
    for i in range(15):
        for k in range(rng.integers(1, 4)):
            tooth = ("I1", "C")[k % 2]
            t = table[tooth]
            age = rng.uniform(24, 48) if rng.random() < 0.7 else rng.uniform(t["initiation"] + 6, t["crown"] - 3)
            share = (age - t["initiation"]) / (t["crown"] - t["initiation"])
            defect = round((1 - share) * heights[tooth] + rng.normal(0, 0.2), 1)
            if 0 <= defect <= heights[tooth]:
                rows.append({"specimen_id": f"H{i + 1:02d}", "site": "Site A", "species": "human", "tooth": tooth,
                             "defect_mm": defect, "crown_height_mm": heights[tooth], "defect_id": k + 1,
                             "notes": f"SYNTHETIC; true age {age:.1f} months"})
    write("synthetic_hypoplasia_example.csv", rows)


def cemetery(rng):
    """Two cemeteries drawn from Siler hazards; ages are estimated as narrow ranges for children,
    10-14-year ranges for adults and 50+ for the oldest. Site B lost most of its infant burials."""
    grid = np.linspace(0, 100, 20001)
    rows = []
    for site, params, n, keep_infants in (("Site A", (0.25, 1.0, 0.01, 0.0004, 0.09), 160, 1.0),
                                          ("Site B", (0.15, 0.9, 0.012, 0.0006, 0.085), 160, 0.3)):
        s = survival(grid, *params)
        k = 0
        for age in np.interp(-rng.random(n), -s, grid):
            if age < 1 and rng.random() > keep_infants:
                continue
            k += 1
            if age < 15:
                low, high = max(age - 0.5 - 0.1 * age, 0), age + 0.5 + 0.1 * age
            elif age < 50:
                low = max(15, 5 * np.floor(age / 5) - 5)
                high = low + 14
            else:
                low, high = 50, None
            rows.append({"specimen_id": f"{site[-1]}{k:03d}", "site": site, "species": "human",
                         "age_min_years": round(low, 1), "age_max_years": "" if high is None else round(high, 1),
                         "sex": "", "notes": f"SYNTHETIC; true age {age:.1f} years"})
    write("synthetic_cemetery_example.csv", rows, TEST_DATA)


def mobility(rng):
    """A site on chalk (local 87Sr/86Sr about 0.708) with 12 animals as baseline and 30 people, 5 of them
    raised on older rocks in a colder climate (drinking water about 4‰ lower)."""
    rows = []
    for i in range(12):
        rows.append({"specimen_id": f"F{i + 1:02d}", "site": "Site A", "species": "pig", "tooth": "M2", "d18O": "",
                     "d18O_material": "", "sr87_86": round(rng.normal(0.7080, 0.0003), 5), "role": "baseline",
                     "notes": "SYNTHETIC; local fauna"})
    for i in range(30):
        incomer = i >= 25
        water = rng.normal(-10.0 if incomer else -6.0, 0.4)  # drinking water, ‰ VSMOW
        carbonate = ((water + 48.634) / 1.590 - 30.91) / 1.03091  # back to enamel carbonate, ‰ VPDB
        rows.append({"specimen_id": f"P{i + 1:02d}", "site": "Site A", "species": "human", "tooth": "M2",
                     "d18O": round(carbonate + rng.normal(0, 0.1), 2), "d18O_material": "carbonate",
                     "sr87_86": round(rng.normal(0.7125 if incomer else 0.7081, 0.0002), 5), "role": "sample",
                     "notes": "SYNTHETIC; " + ("raised elsewhere" if incomer else "local")})
    write("synthetic_mobility_example.csv", rows, TEST_DATA)


def main():
    rng = np.random.default_rng(12)
    dental(rng)
    hypoplasia(rng)
    cemetery(rng)
    mobility(rng)


if __name__ == "__main__":
    main()
