# Test data

Simulated tables, made by the `scripts/make_*` scripts. **Not real measurements.** They were the app's
examples until published datasets replaced them (`src/weanage/data/examples/README.md`); the tests
use them because their true answers are known.

| file | calculation | made by |
|---|---|---|
| `synthetic_example.csv` | tooth | `make_synthetic_example.py` |
| `synthetic_bone_example.csv` | bone (Site A weans at 3–9 months, Site B at 1–4) | `make_bone_example.py` |
| `synthetic_killoff_example.csv` | kill-off profiles | `make_killoff_example.py` |
| `synthetic_mixing_example.csv` | diet mixing | `make_mixing_example.py` |
| `synthetic_cemetery_example.csv` | life tables | `make_human_examples.py` |
| `synthetic_mobility_example.csv` | mobility | `make_human_examples.py` |
