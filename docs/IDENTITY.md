# WeanAge identity

<img src="../src/weanage/web/logo.svg" width="64" alt="WeanAge logo: five bars falling like a weaning curve">

## What WeanAge is

**WeanAge: weaning ages from teeth and bones.**
Open software that turns δ¹⁵N measured along a tooth, or in the bones of many young
individuals, into a weaning age with an honest uncertainty, so results from different labs,
sites and species can be compared. *WeanAge* is the final name.

## Character

* **Careful.** A research instrument, not a gadget. Every number comes with its
  uncertainty, and every assumption is shown.
* **Plain-spoken.** Explains statistics in everyday words, without talking down.
* **Open.** Free to use, methods documented and cited, data and figures credited.

## Voice and writing

* British English (*colour*, *licence*, *modelling*), sentence case for headings and buttons.
* Use the lab's words: *slice*, *cusp apex*, *cervix*, *growth table*, *nursing plateau*.
* Numbers always carry units (9.3 months, 2.5‰, 1 mm) and, where possible, an interval.
* Say what is assumed or still missing, plainly: "Slice positions are assumed",
  "12 placeholder values are in use".
* Buttons say what happens: *Run analysis*, *Load example*, *Copy citation*.
* No exclamation marks or emoji in the interface.

## Logo

Five dentine slices whose heights fall like a weaning curve: high while the animal suckles,
then down to the adult level. It is the method in one picture.

| | |
|---|---|
| Construction | 32 × 32 grid; five bars 4 units wide with 2-unit gaps, heights 23, 22, 15, 8, 7, bottom-aligned, corner radius 1 |
| Files | `src/weanage/web/logo.svg` (colour); in the app it is drawn inline in the current accent colour |
| Wordmark | "WeanAge" in Atkinson Hyperlegible Bold, set to the right of the mark, vertically centred |
| Clear space | at least one bar width (4 units) on every side |
| Smallest size | 16 px (favicon); below that, use the wordmark alone |
| Colours | teal `#0b5a70` on light backgrounds, `#8fd0e0` on dark; or one solid colour (black or white) |
| Don't | add gradients, shadows or outlines; change the bar heights; rotate it; put it in a rounded tile |

## Colour

Warm neutrals, like ink on paper rather than a code editor, with one accent colour that marks
what can be clicked or is selected. Yellow is reserved for TBD-LAB placeholders and warnings.

| role | dark theme | light theme |
|---|---|---|
| background | `#161512` | `#f2f0eb` |
| surface | `#1d1c19` | `#fdfcf9` |
| text | `#eeeae2` | `#1a1815` |
| secondary text | `#c9c3b8` | `#3d3933` |
| accent (links, focus, the logo) | `#8fd0e0` | `#094b5d` |
| placeholder (TBD-LAB) | `#ffe39b` on `#3a2e08` | `#3b2a00` on `#fff0b0` |

All text meets WCAG AAA (7:1) contrast; `tests/test_contrast.py` checks it. Model curves use
a colour-blind-safe set plus a distinct line pattern for each model, so colour is never
the only cue.

## Layout

* Each page shows its main choices; the rest sit under **Advanced settings** in the same box.
* At 1440 × 860 every page fits without scrolling; tables and charts size themselves to the
  window, and the Run button stays in view.
* Each result starts with one large figure (the weaning age, with its unit and 95% interval),
  then a sentence that explains it, then the chart.
* Spacing comes from a 4 px scale (4, 8, 12, 16, 24, 32). Corners are 3 px everywhere.
* Charts: no shaded bands that overlap; intervals are thin bars above the age axis. Every
  colour in a chart means something.
* Avoided on purpose: decorative gradients, emoji, coloured left-border "callout" blocks,
  cards inside cards, and figures that are not real data.

## Type

* **Atkinson Hyperlegible** (Braille Institute) for all text. It was designed for readers
  with low vision, which suits a tool that puts accessibility first.
* **IBM Plex Mono** for numbers, specimen IDs, units and code, so columns of figures line up.
* Both are bundled with the app under the SIL Open Font License, so it looks the same offline.

## Figures

* Use real, credited illustrations: published figures in the public domain or under an open
  licence. Never AI-generated images.
* Data charts use the app's own chart style; exported charts and reports use the light theme.

## Where it appears

App header and browser tab, the About panel, the printed methods brief (`docs/brief/`),
the README, posters and slides.
