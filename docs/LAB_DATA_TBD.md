# Placeholder values (`TBD-LAB`)

Some values that WeanAge needs have not yet been measured or checked against published
sources: tooth growth tables, livestock bone turnover, some priors and lab parameters.
Each is a placeholder. It is marked `TBD-LAB` in the data file, has `"placeholder": true` in
its JSON entry, and is highlighted in yellow in the app. Results that depend on a placeholder
are illustrative.

For what to measure for each one, see the [lab work checklist](LAB_CHECKLIST.md).

## Finding them

The yellow banner at the top of the app counts the placeholders in use. Click it to list
each one, what is needed and which file it is in. The same list can be found with:

```bash
grep -rn TBD-LAB src/weanage/data
```

## Replacing one

* Edit the entry in the JSON file in `src/weanage/data/`, give its source, and set
  `"placeholder": false`. The highlight then disappears.
* Growth tables can also be edited, or calibrated from known-age reference points, in the
  app (*Settings → Age models*). Saved tables go to `~/.weanage/growth_tables.json` (in the
  browser version, to that browser) and replace the bundled table. Give each table an
  `age_uncertainty_months` (1 SD) and a `source`.

Values typed in Settings (for example adult-female baselines) apply to that project only.
To contribute a value for everyone, see [`CONTRIBUTING.md`](../CONTRIBUTING.md).
