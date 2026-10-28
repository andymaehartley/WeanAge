# Lab work checklist

What has to be measured or checked before WeanAge's results can be treated as more than
illustrative. Each item names the value, what to do, and where the result goes. The app lists
the same placeholders in its yellow banner (21 at present); see
[`LAB_DATA_TBD.md`](LAB_DATA_TBD.md) for how to replace one. Tick items off here as they are
done, and record the source of each value in its JSON entry.

Most important first: without 1 and 2, tooth ages are only as good as guesses; without 4, the
bone calculation is illustrative for every species except humans.

## 1. Tooth growth: position to age (`data/growth_tables.json`)

For each tooth: the crown height of unworn teeth, the age at which dentine starts and stops
forming, and whether growth is even along the crown. Ideally from known-age animals
(radiographs or fluorochrome-labelled teeth), otherwise from published formation chronologies.

- [ ] **Cattle M2**: crown height of unworn M2 (45 mm is a guess); confirm the start (~1 month)
      and end (12–13 months) ages of Brown et al. (1960) for dentine, not only enamel; check
      whether extension is even along the crown; ages of root dentine.
- [ ] **Cattle M1**: age at which M1 dentine starts before birth (−2 months is a guess);
      crown height (40 mm is a guess); root ages.
- [ ] **Pig M1**: full formation chronology (current table is a placeholder).
- [ ] **Horse M1**: full formation chronology; the hypsodont crown probably grows unevenly,
      so several points along the crown are needed, not just start and end.
- [ ] **Human M1**: check crown completion (~3 years), crown length (7 mm) and total length
      (21 mm) against the London Atlas (AlQahtani et al. 2010), or measure the teeth sampled.
- [ ] **Sheep and goat** (no table yet): M1/M2 formation chronologies, if caprine teeth are
      to be analysed. Díez-Canseco et al. (2022) tested sequential dentine sampling in modern sheep.
- [ ] For each table, estimate the **age uncertainty** (1 SD, months) between animals.
- [ ] If known-age reference teeth are available, use *Settings → Age models → Calibrate*
      to build the table from (position, age) pairs.

## 2. Slice geometry and protocol (`data/lab_parameters.json`)

Only needed if time averaging is switched on, but always worth recording.

- [ ] **Slice height** actually cut (mm), and whether slices are contiguous.
- [ ] **Growth-layer offset** (mm) for each tooth type: dentine thickness ÷ tan(angle of the
      growth layers to the tooth axis), measured on thin sections. The MDSS values are for
      human teeth only.
- [ ] **Inner dentine weight**: inner-to-outer radius of a slice, from thin-section geometry
      (1 = equal volume; currently 1).
- [ ] Whether each slice samples the full dentine thickness or only the outer dentine
      (outer dentine gives a sharper weaning signal; Winter-Schuh et al., *J. Archaeol. Sci.*).
- [ ] How **position** is recorded: from the cusp apex (WeanAge's default) or from the cervix
      (then record `crown_height_mm`), and to the middle of each slice.
- [ ] Note **cusp wear**: worn cusps lose the earliest (nursing) dentine.

## 3. Laboratory measurement (`data/lab_parameters.json`, `data/qc_thresholds.json`)

- [ ] **Analytical precision** for δ15N (1 SD of replicate standards and check samples, ‰).
      WeanAge uses it to weight curve fits; currently blank.
- [ ] **Collagen quality limits** used by the lab (C:N, %C, %N, yield). Defaults are DeNiro
      (1985) and van Klinken (1999); use Guiry & Szpak (2020) for modern reference animals.
- [ ] Report **%C and %N** (or atomic C:N) and **collagen yield** for every sample, so the
      checks can run.
- [ ] Record the **reference materials** and normalisation (δ15N vs AIR, δ13C vs VPDB).

## 4. Bone collagen turnover (`data/bone_turnover.json`)

The share of bone collagen renewed each month at each age, for the bone calculation. No
values are published for livestock; the current tables are anchored to young fur seals.

- [ ] **Cattle**, **sheep**, **goat**, **pig**: monthly turnover from birth to adulthood,
      derived as WARN derived the human values: skeletal growth (bone mass gain with age)
      plus remodelling, corrected for the delay in mineralisation.
- [ ] Record which **skeletal element** the values describe (WARN's are for rib, a fast-turnover
      bone) and sample the same element in the study.

## 5. Bone model priors (`data/bone_priors.json`)

From known-age young animals and their mothers, ideally from the same herds.

- [ ] **Nursing enrichment** (nursing young minus mother, bone collagen δ15N, ‰) for cattle,
      sheep, goat and pig. Current placeholders: 2.5–3.0 ± 1.0‰.
- [ ] **Newborn offset** (newborn minus mother, ‰) for the same species. Current placeholder
      1.0 ± 1.0‰; the reported 2.6–2.7‰ for calf and sheep foetal bone needs its primary
      source checked.
- [ ] **Latest plausible end of weaning** for each species, as an upper bound.

## 6. Site baselines (entered per project in Settings)

- [ ] **Adult-female δ15N** (mean and SD) for each site and species, from bone collagen of
      sexed adult females. Used for nursing enrichment and the bone calculation's mothers' mean.
- [ ] Where females cannot be sexed, note that all adults stand in for the mothers.

## 7. Validation against known ages (`data/lab_parameters.json → reference_dataset`)

- [ ] Assemble a **reference set** of animals with known weaning ages (modern, managed herds),
      sampled with the same protocol, with `known_weaning_age_months` filled in.
- [ ] Run `weanage validate` (or *Compare → Validation*) and record bias, error and 95%
      interval coverage for each model.
- [ ] From the reference set, set the **minimum weaning drop** (currently 1‰) that separates a
      real weaning signal from noise.
- [ ] From the reference set, decide the **transition threshold** (currently 5% / 95%) and which
      milestone (onset, midpoint or completion) best matches the known weaning ages.
- [ ] For the bone calculation, check against at least one site with known or independently
      estimated weaning (as Wharram Percy is for humans).

## 8. Enamel: season and rumen (cattle)

- [ ] Record each sample's **distance from the enamel-root junction** (to the middle of the
      sample) and the sample height; record crown wear.
- [ ] **Reference materials** and normalisation for enamel carbonate δ¹⁸O and δ¹³C (VPDB),
      pretreatment, and analytical precision.
- [ ] **Crown length formed in a year** (X) for the cattle teeth sampled, to check the default
      range of 25–80 mm; from modern known-age teeth if possible.
- [ ] **Reference birth indices**: modern cattle of known birth date, sampled the same way, to
      turn x₀/X into a season and to check the "spread × 12 months" approximation.
- [ ] **Rumen δ¹³C rise** in known-age calves (size and timing), to check the 0.5‰ and 3‰ limits.
- [ ] **Local drinking-water δ¹⁸O seasonality**: the method needs a clear yearly cycle.
- [ ] **Local plant δ¹³C**: C3 and C4 plants (or herbivores of known diet) from the region and
      period, to replace the default end members (−27‰ and −11‰, pre-industrial); check whether
      C4 plants (millet, maize, C4 grasses) grew there at all.
- [ ] **Enamel-diet spacing** for the species sampled (14.1‰ is for large ruminants).
- [ ] **Local bioavailable ⁸⁷Sr/⁸⁶Sr** (plants, water, snails or small mammals from the region) for
      the local range, and **Sr reference material** (e.g. NIST SRM 987) values and precision.
- [ ] **Month of the δ¹⁸O maximum** in local drinking water (or in modern teeth of known birth date).
- [ ] **Enamel maturation length** (mm of crown) for the teeth sampled, if the smoothing correction
      is used.

## 8a. Dentine: stress and δ³⁴S

- [ ] **δ³⁴S** reference materials (VCDT) and the collagen %S and C:S, N:S ratios used for QC.
- [ ] Check the stress thresholds (0.5‰ δ¹⁵N, 0.3‰ δ¹³C) against analytical precision.

## 8b. Kill-off profiles

- [ ] **Ageing method** for each species: Payne (1973) stages are for sheep and goats; cattle and pigs
      need their own wear stages converted to age ranges (with the source). Enter these under Settings →
      *Another wear-stage system* (e.g. Grant 1982 mandible wear stages with the age equivalents of a
      published study); WeanAge does not supply them.
- [ ] Record mandibles that can only be put in two stages as such ("D/E"), rather than guessing one.
- [ ] Note taphonomy (gnawing, fragmentation) and recovery (sieving), which affect young mandibles most.

## 8c. Diet mixing (`data/diet_sources.json`)

- [ ] **Food values** (mean and SD of δ¹³C, δ¹⁵N, δ³⁴S) from plants, animal bones and fish of the
      same site and period, converted to the edible part where needed.
- [ ] **Collagen-diet offsets** for the species studied (humans: δ¹⁵N about 6‰, O'Connell et al. 2012).
- [ ] Decide which food groups to include; more groups than isotopes + 1 cannot be told apart.
- [ ] If foods differ much in protein (e.g. cereals and meat), their **C, N and S concentrations** (% of
      dry weight of the edible part), for concentration-dependent mixing.
- [ ] Any **prior evidence** for the share of a food (faunal, archaeobotanical, residue), if prior weights
      other than 1 are used; record why.

## 8d. People (`data/dental_stages.json` and Settings)

- [ ] **Tooth formation ages**: replace the placeholder initiation, crown, root and apex ages with stage
      ages and SDs from a published standard (e.g. AlQahtani et al. 2010; Smith 1991), ideally one
      suited to the population; add **cuspal formation times** (Reid & Dean 2006) for hypoplasia timing.
- [ ] Record each child's **Moorrees stages** per tooth (from radiographs or loose teeth), scored blind
      to other age evidence; note inter-observer checks.
- [ ] For hypoplasia: measure the **defect height above the CEJ** and the **unworn crown height** on the
      same face, with calipers or a microscope; note wear.
- [ ] **Adult-female δ¹⁵N and δ¹³C** for each site, for the breast-milk share; check the **nursing
      enrichment** (humans: WARN's 1.9 ± 0.9‰; δ¹³C about 1‰, Fuller et al. 2006).
- [ ] For life tables: the **ageing methods** used for adults and children, open-ended ranges, and how
      infants were recovered (sieving, cemetery coverage).
- [ ] For mobility: whether δ¹⁸O is **carbonate (VPDB) or phosphate (VSMOW)**, the pretreatment, the
      **local drinking-water δ¹⁸O** range, and **local bioavailable ⁸⁷Sr/⁸⁶Sr** (fauna, plants, snails).
- [ ] Prefer **later-forming teeth** (PM2, M2, M3) for mobility: M1 and deciduous teeth may carry a
      breastfeeding δ¹⁸O signal.
- [ ] For *possible origins*: published ⁸⁷Sr/⁸⁶Sr and drinking-water δ¹⁸O (mean and SD) of the candidate
      regions, from isoscapes or local baselines, with sources.
- [ ] For the life-table infant correction: the **expected share of infant deaths** for a comparable
      population (model life table or historical records), with the source.
- [ ] Use the **same specimen IDs** in every table (tooth, bone, dental, mobility, life table), so the
      Individuals page and the dental-age hand-offs can match them.

## 9. Example data assumptions

The bundled real examples rely on assumptions that should be checked against the original
publications or the authors before they are used in a thesis or paper.

- [ ] **Khami and Bornais cattle** (IsoArcH): slice order (cervix first was assumed) and slice
      spacing (8 mm over the crown was assumed for Bornais).
- [ ] **Mikulčice human teeth** (CIMA): section positions (ten equal sections over 21 mm were
      assumed).
- [ ] **CIMA human bone sites**: age-at-death ranges and sex of the adults, as recorded in CIMA.
- [ ] **Mikulčice mobility and dentine** (CIMA): that the grave numbers of Vytlačil et al. (2021) and
      Kaupová et al. (2024) refer to the same burials.
- [ ] **Münsingen-Rain** (mortAAR): the conversion of the published age text to ranges; these 71 are the
      individuals sampled for isotopes, not the whole cemetery.
- [ ] **Marj Rabba** (zooaRch): that age classes 1–9 are Payne's A–I.

## When an item is done

1. Put the value and its source in the JSON file and set `"placeholder": false`.
2. Run the tests (`pytest`) and the bundled examples to see how results change.
3. Note the change in `CHANGELOG.md`.
