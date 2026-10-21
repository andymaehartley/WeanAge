# Contributing to WeanAge

WeanAge is research software for zooarchaeology and bioarchaeology. Data and method checks
are as useful as code.

## Ways to help

* Report a problem or ask a question: open an issue (choose *Bug report* or *Method or data
  question*). Include the steps, what you expected, and if possible a small CSV that shows it.
* Supply real values for a placeholder: anything marked TBD-LAB (tooth growth tables, bone
  turnover, priors) needs published or measured values. Open an issue with the values and their
  source, or edit the file in `src/weanage/data/` directly.
* Share known-age reference data: animals with recorded weaning dates are the best test of the
  method. See `docs/VALIDATION.md` for the format.
* Improve the code or documentation: pull requests are welcome.

## Working on the code

```bash
git clone https://github.com/andymaehartley/repotest.git weanage
cd weanage
pip install -e . pytest httpx playwright ruff mypy pandas-stubs
pytest -q                      # all tests (the browser test needs Playwright's Chromium)
ruff check src tests scripts   # style
mypy src                       # types
weanage                        # run the app
```

Please keep to the project's habits:

* Plain code: simple functions and comments in everyday language.
* Cite sources: every value or method from the literature names its paper, in the code
  comment and in `docs/METHODS.md`.
* Do not invent numbers: if a value is not known, mark it as a placeholder (TBD-LAB).
* Accessible interface: text contrast of at least 7:1 (checked by `tests/test_contrast.py`),
  everything usable with the keyboard, and colour never the only cue.
* Tests: add or update a test for each change, and make sure `pytest`, `ruff` and `mypy` pass.

Work on a branch and open a pull request against `main`; the checks run automatically.

## Writing style

For the interface, messages and documentation:

* British English (*colour*, *licence*, *modelling*); sentence case for headings and buttons.
* Plain words. Explain statistics in everyday language.
* Numbers carry units (9.3 months, 2.5‰, 1 mm) and, where possible, an interval.
* State assumptions and missing values plainly ("Slice positions are assumed",
  "12 placeholder values are in use").
* Buttons say what happens: *Run analysis*, *Load example*, *Copy citation*.
* No exclamation marks or emoji.

Use one word for each thing:

| use | not |
|---|---|
| slice | increment, sample section |
| 95% interval | CI, CrI, confidence/credible interval (in interface text) |
| onset, midpoint, completion (tooth milestones) | start, end, weaned age |
| animal | individual (column names such as `individual_id` stay as they are) |
| cusp apex, cervix, growth table, nursing plateau | |

## Data licences

WeanAge's code is MIT-licensed. Example data keep their own licences (IsoArcH: CC BY 4.0; CIMA:
CC BY-SA); see `src/weanage/data/examples/README.md`. Do not add data you are not allowed to share.

## Conduct

Be kind and constructive; see [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
