"""Make the SYNTHETIC enamel example: cattle M2 from two invented sites with known birth seasons.

    python scripts/make_enamel_example.py

Each tooth's enamel δ18O follows a yearly cosine and its δ13C rises once as the rumen develops,
on top of a weaker seasonal wave. Both are smoothed over 8 mm of crown, as enamel mineralisation
smooths them, and measurement noise is added. Site A calved within about two months and ate C3
plants; Site B calved over about seven months and ate about a third C4 plants (e.g. millet). Three
Site B animals moved from older rocks (87Sr/86Sr 0.7125) to the local 0.7095 as calves. The true
values are in each row's notes. These are not real measurements.
"""

import csv
from pathlib import Path

import numpy as np

from weanage.enamel import cosine, rumen_step

OUT = Path(__file__).resolve().parents[1] / "src" / "weanage" / "data" / "examples" / "synthetic_enamel_example.csv"
PERIOD = 46.0  # mm of M2 crown formed in a year
CROWN = 52.0  # the highest sample, mm above the enamel-root junction
SITES = {"Site A": (0.30, 0.38), "Site B": (0.10, 0.68)}  # range of true birth indices (x0/X)
C4_SHARE = {"Site A": 0.0, "Site B": 0.33}  # share of C4 plants in the diet once the rumen works
SPACING, C3, C4 = 14.1, -27.0, -11.0  # the analysis defaults (enamel-diet spacing, plant end members)
SMOOTH_MM, NOISE_O, NOISE_C, NOISE_SR = 8.0, 0.15, 0.12, 0.00008
LOCAL_SR, FOREIGN_SR = 0.7095, 0.7125


def smoothed(f, x):
    """The mean of f over SMOOTH_MM of crown around each position (mineralisation blurs the signal)."""
    offsets = np.linspace(-SMOOTH_MM / 2, SMOOTH_MM / 2, 17)
    return np.array([f(xi + offsets).mean() for xi in x])


def main():
    rng = np.random.default_rng(7)
    sr_rng = np.random.default_rng(11)  # separate, so the δ18O and δ13C values do not change
    rows = []
    for site, (low, high) in SITES.items():
        for i, index in enumerate(np.linspace(low, high, 6)):
            sid = f"{site[-1]}{i + 1:02d}"
            x = np.round(np.arange(CROWN, 1, -2.5) + rng.normal(0, 0.2, 21), 1)
            transition = rng.uniform(41, 46)
            d18o = smoothed(lambda xx, x0=index * PERIOD: cosine(xx, -4.8, 2.4, PERIOD, x0), x) + rng.normal(0, NOISE_O, x.size)
            weaned = C3 + C4_SHARE[site] * (C4 - C3) + SPACING  # enamel δ13C on the adult diet
            d13c = smoothed(lambda xx, middle=transition, top=weaned: top - 1.4 + 1.4 * rumen_step(xx, middle, 1.5)
                            + 0.35 * np.sin(2 * np.pi * xx / PERIOD), x) + rng.normal(0, NOISE_C, x.size)
            move = sr_rng.uniform(18, 34) if site == "Site B" and i < 3 else None
            sr = (smoothed(lambda xx, at=move: np.where(xx > at, FOREIGN_SR, LOCAL_SR), x) if move else np.full(x.size, LOCAL_SR))
            sr = sr + sr_rng.normal(0, NOISE_SR, x.size)
            moved = f"true Sr shift {move:.1f} mm" if move else "no Sr shift"
            for k, (xi, o, c, s) in enumerate(zip(x, d18o, d13c, sr), start=1):
                rows.append({"specimen_id": sid, "site": site, "species": "cattle", "tooth": "M2", "sample_index": k,
                             "erj_distance_mm": xi, "d18O": round(o, 2), "d13C": round(c, 2), "sr87_86": round(s, 5),
                             "notes": f"SYNTHETIC; true birth index {index:.2f}; true rumen transition {transition:.1f} mm; "
                                      f"true C4 share {C4_SHARE[site]:.2f}; {moved}"})
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} samples to {OUT}")


if __name__ == "__main__":
    main()
