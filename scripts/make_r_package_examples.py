"""Make two WeanAge examples from published data shipped with R packages (needs `pip install pyreadr`).

    python scripts/make_r_package_examples.py muensingen.rda marjRab.RData

* muensingen.rda, from mortAAR (Müller-Scheeßel et al., GPL-3; github.com/ISAAKiel/mortAAR, data/):
  ages at death, sex, phase and grave goods of 71 Late Iron Age burials from Münsingen-Rain
  (Switzerland), from Moghaddam et al. 2016, Archaeol. Anthropol. Sci. 8: 149-160.
  -> data/examples/muensingen_lifetable.csv (life tables)
* marjRab.RData, from zooaRch (Otárola-Castillo, Wolfhagen & Price, GPL >= 2; CRAN): Payne (1973) age
  classes of 42 sheep/goat mandibles from Chalcolithic Marj Rabba (Israel), from Price et al. 2013,
  Paléorient 39(2): 183-200.
  -> data/examples/marj_rabba_killoff.csv (kill-off profiles)

Both files are GPL like the packages they come from; cite the original studies and the packages.
"""

import argparse
import re
from pathlib import Path

import pandas as pd
import pyreadr

OUT = Path(__file__).resolve().parents[1] / "src" / "weanage" / "data" / "examples"
STAGES = "ABCDEFGHI"


def age_range(text):
    """'25-35' -> (25, 35); '>60' -> (60, None); '10+/-1' -> (9, 11); '10' -> (10, 11)."""
    text = text.strip()
    if m := re.fullmatch(r"(\d+)-(\d+)", text):
        return float(m[1]), float(m[2])
    if m := re.fullmatch(r">(\d+)", text):
        return float(m[1]), None
    if m := re.fullmatch(r"(\d+)\+/-(\d+)", text):
        return float(m[1]) - float(m[2]), float(m[1]) + float(m[2])
    if m := re.fullmatch(r"(\d+)", text):
        return float(m[1]), float(m[1]) + 1  # a single year of age
    raise ValueError(f"unknown age {text!r}")


def muensingen(path):
    data = pyreadr.read_r(path)["muensingen"]
    rows = []
    for grave, r in data.iterrows():
        low, high = age_range(r["age"])
        rows.append({"specimen_id": grave, "site": "Münsingen-Rain", "species": "human", "age_min_years": low,
                     "age_max_years": high, "sex": {"female": "f", "male": "m"}.get(r["sex"], ""),
                     "period": "Late Iron Age", "latene_phase": "" if r["latene_phase"] == "n.d." else r["latene_phase"],
                     "grave_goods": r["grave_goods"],
                     "notes": f"age as published: {r['age']}; Moghaddam et al. 2016 via mortAAR (GPL-3)"})
    return pd.DataFrame(rows)


def marj_rabba(path):
    data = pyreadr.read_r(path)["marjRab"]
    return pd.DataFrame([{"specimen_id": f"MR{i + 1:02d}", "site": "Marj Rabba", "species": "sheep/goat",
                          "payne_stage": STAGES[int(r["Ageclass"]) - 1], "period": "Chalcolithic",
                          "notes": "Price et al. 2013 via zooaRch (GPL >= 2); mandible ages in Payne (1973) classes"}
                         for i, (_, r) in enumerate(data.iterrows())])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("muensingen", help="mortAAR data/muensingen.rda")
    parser.add_argument("marj_rabba", help="zooaRch data/marjRab.RData")
    args = parser.parse_args()
    life = muensingen(args.muensingen)
    life.to_csv(OUT / "muensingen_lifetable.csv", index=False)
    mandibles = marj_rabba(args.marj_rabba)
    mandibles.to_csv(OUT / "marj_rabba_killoff.csv", index=False)
    print(f"muensingen_lifetable.csv: {len(life)} burials; marj_rabba_killoff.csv: {len(mandibles)} mandibles")


if __name__ == "__main__":
    main()
