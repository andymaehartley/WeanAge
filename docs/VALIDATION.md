# Checking WeanAge against animals of known weaning age

How to test WeanAge on animals whose weaning age is known, and which published data to use.

## How to run it

1. Make a CSV in the usual format (see the README), one row per dentine slice.
2. Add a column `known_weaning_age_months` with each animal's real weaning age.
   (Or `published_weaning_age_months` to compare with another study's estimate.)
3. Run:

   ```bash
   weanage validate reference.csv
   ```

   or load the file in the app and open *Compare → Validation*.

For each model you get:

| column | meaning |
|---|---|
| `n` | number of animals |
| `bias` | average of (estimate − true age); positive means the model guesses too late |
| `mae` | average size of the error, in months |
| `rmse` | like `mae` but punishes big misses more |
| `pearson_r` | how well estimates and true ages rise together (1 = perfectly) |
| `ci_coverage` | share of animals whose true age falls inside the 95 % interval (ideally about 0.95) |

To make a file the default, put its path in `reference_dataset` in
`src/weanage/data/lab_parameters.json`; then `weanage validate` needs no argument.

## Published series to use

The modern studies below sampled dentine from animals whose weaning was recorded (use
`known_weaning_age_months`). For archaeological series, put the authors' estimate in
`published_weaning_age_months` instead. Their values
can be typed in from the papers' tables and figures (with permission and citation),
or requested from the authors. None are bundled here, because the numbers have to be
copied from the original publications.

| study | animals | why it is useful |
|---|---|---|
| Balasse et al. 2001, *J. Archaeol. Sci.* 28:235–245 | modern cattle, weaning date known | the first experimental test; δ¹⁵N fell and δ¹³C rose exactly at weaning |
| Balasse & Tresset 2002, *J. Archaeol. Sci.* 29:853–859 | Neolithic cattle (Bercy) | an archaeological comparison using the same method |
| Díez-Canseco, Aguilera & Tornero 2022, *Int. J. Osteoarchaeol.* 32:962–975 | modern experimental sheep | high-crowned teeth; a sampling protocol matched to dentine growth |
| Díez-Canseco & Tornero 2026, *J. Archaeol. Sci.: Reports* 71: 105651 | modern early-weaned sheep | dentine sequences from known-age animals |

Known-age animals sampled by your own lab with its usual protocol make the best
validation set, because they share its sampling and growth tables.

## What else the validation is used for

* choosing the `transition_threshold` (the % of the drop that counts as "weaned"),
* choosing `min_weaning_drop_permil`,
* checking that the age-model uncertainty is realistic (coverage near 0.95).
