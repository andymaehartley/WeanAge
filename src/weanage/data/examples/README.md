# Example datasets

## `synthetic_example.csv`

Simulated teeth made by `scripts/make_synthetic_example.py`. **Not real measurements.**

## `synthetic_bone_example.csv`

Simulated bone collagen δ¹⁵N for young and adult cattle at two invented sites, made by
`scripts/make_bone_example.py` with the bone model itself. Site A weans at 3–9 months and
Site B at 1–4 months; ages at death are ranges, as tooth wear gives them. **Not real
measurements.**

## `isoarch_cattle_khami_bornais.csv`

Real sequential dentine-collagen δ¹⁵N and δ¹³C values from 11 archaeological cattle,
taken from the IsoArcH database and converted with `weanage isoarch`:

```bash
weanage isoarch isoarch-export.xlsx --site Khami --site Bornais --species cattle \
    -o src/weanage/data/examples/isoarch_cattle_khami_bornais.csv
```

| site | date | animals | teeth | original study | IsoArcH dataset |
|---|---|---|---|---|---|
| Khami, Zimbabwe | AD 1475–1650 | 6 | one M1 or M2 each (15–22 slices) | Dyvart, Sealy & Fredriksen 2018, *Azania* 53, 507–527, doi:10.1080/0067270X.2018.1540215 | Hluke, Hagarová & Salesse, doi:10.48530/isoarch.2025.004 |
| Bornais, South Uist (Outer Hebrides), Norse | AD 1000–1400 | 5 | M1 + M2 of each animal (4–6 slices per tooth) | Griffith & Mulville 2020, in Sharples (ed.), *The Economy of a Norse Settlement in the Outer Hebrides*, Oxbow, 367–381; Griffith 2019 (MSc dissertation, Cardiff) | Griffith, James, Cheung & Snoeck, doi:10.48530/isoarch.2021.014 |

**Licence.** Both IsoArcH datasets are published under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Please cite the original
studies and the IsoArcH datasets above when using these values.

**What was changed.** IsoArcH gives each slice's order (zone 1, 2, 3… or a, b, c…) but not
where it was cut, so positions were **assumed**, and each row's `notes` says so:

* **Zone order: zone 1 / "a" is at the cervix** (`cervix_first`), so later letters move
  towards the crown tip. This was chosen because it is the only reading under which the
  series behave like weaning. Read the other way, δ¹⁵N rises with age in every Khami tooth
  (Spearman ρ 0.56–0.96), with no nursing plateau at all. Read cervix-first, 8 of the 11
  animals show a 1–3‰ fall, the expected size of a weaning signal. This fits the "early
  weaning" Griffith & Mulville report for Bornais.
* **Spacing: slices spread evenly over the crown**, using the length of WeanAge's cattle
  growth tables (M1 40 mm, M2 45 mm). For Khami this gives slices about 2–3 mm apart; for
  Bornais, with only 4–6 slices per tooth, about 7–10 mm.

Both assumptions should be checked against the original publications. Re-run
`weanage isoarch` with `--zone-order` and `--spacing` once the sampling details are known.
The cattle growth tables themselves are still partly placeholders (`TBD-LAB`), so the
weaning ages from this example are illustrative.

The same export also holds sequential series for Khami sheep/goat (5 animals, M1–M3) and
several wild species; sheep/goat can be converted the same way once a sheep/goat growth
table is added.
