// Plain-language glossary and a guided first-run tour for non-specialist users.
import { $, esc } from "./util.js";

export const GLOSSARY = {
  position: ["Position (mm)", "Distance from the cusp apex (the tip of the tooth crown, where dentine forms first) to the middle of the sampled slice. If you measured from the cervix (crown base), set position_reference = cervix and give crown_height_mm; the app converts it."],
  growth_table: ["Age model / growth table", "Converts position along the tooth into the age at which that dentine formed. Values between table points are interpolated. The bundled tables are placeholders until real tooth-formation data are entered."],
  calibrate: ["Calibration", "Builds a growth table from reference measurements of known age, e.g. the forming edge of teeth from animals of known age at death, or incremental-line counts."],
  qc: ["Collagen quality control", "Degraded or contaminated collagen gives unreliable isotope values. Samples outside the C:N, %C, %N or yield limits are flagged and, by default, left out of the fit. Archaeological collagen is usually judged with C:N 2.9–3.6 (DeNiro 1985). Fresh collagen from modern reference animals should fall in the narrower 3.00–3.28 (Guiry & Szpak 2020)."],
  onestage: ["One-stage or two-stage", "Two-stage: each tooth is fitted on its own first, then the weaning ages and their uncertainties are compared. One-stage: a logistic curve for every tooth and the group comparison are estimated together from the raw δ¹⁵N values, so the uncertainty in each curve's shape and in the tooth's age model is carried all the way through. It is slower, uses the logistic curve only, and leaves out teeth whose weaning age would have to be extrapolated."],
  true_shape: ["Shape of the true curves", "The planner invents teeth whose weaning curve is known. If they were all logistic, the logistic model would look best simply because it matches how the data were made. Choose another shape, or a random mix, to see how each model copes when its shape is wrong. All shapes take about the same time to go from 5 % to 95 % of the drop."],
  stress: ["Stress episodes", "Samples where δ¹⁵N sits above the fitted weaning curve while δ¹³C sits below the level expected from its trend and the weaning step. Starvation and illness raise δ¹⁵N without raising δ¹³C, while a change of food usually moves both the same way (Beaumont & Montgomery 2016). At least two neighbouring samples must pass both thresholds (Settings → Advanced). A flag is a prompt to look, not a diagnosis."],
  sulphur: ["δ³⁴S shifts", "Where δ³⁴S changes level along the tooth, chosen by BIC among no, one or two shifts. δ³⁴S follows local geology and the sea-spray effect, so a shift suggests a move to other soils or the coast, or a change of diet (Nehlich 2015). Shifts smaller than the minimum in Settings → Advanced are not reported."],
  calcs: ["Choosing calculations", "Drop one table and WeanAge checks, for every calculation, whether the table has the columns it needs and how many rows it can use. Tick the ones to run: each keeps its own settings and results, and the buttons at the top of the page switch between them. One table can feed several calculations, for example tooth slices with δ¹³C and δ¹⁵N for both the tooth calculation and diet mixing."],
  dental: ["Dental age", "Each tooth is scored in a Moorrees et al. (1963) formation stage. A tooth in a stage is between the age it reached that stage and the age it reaches the next, so its age is the middle of that span. The teeth of one child are averaged, weighted by how precise each is; they develop together, so the combined uncertainty is that of a typical tooth, not narrowed further. Teeth far from the combined age are flagged. A tooth with a closed apex only gives a minimum age. The formation ages in data/dental_stages.json are placeholders until a published standard (e.g. AlQahtani et al. 2010) is entered."],
  leh: ["Enamel hypoplasia timing", "A linear enamel hypoplasia marks a disruption of enamel growth. Enamel grows from the cusp down to the cemento-enamel junction (CEJ), so the defect's height on the crown gives its age: initiation + (1 − height / crown height) × crown formation time (Goodman & Rose 1990). Enamel in fact forms more slowly near the CEJ (Reid & Dean 2006), so these ages are approximate. Defects are set against the weaning interval and stress episodes the tooth calculation found for the same individual."],
  lifetable: ["Life tables", "Each skeleton's age range is shared over the age classes it covers. Dx deaths, dx share of deaths, lx share alive at the start of the class, qx probability of dying in it, Lx years lived in it, Tx years still to live, ex life expectancy at that age (Chamberlain 2006). A life table describes the living population only if it was stationary and the dead are a fair sample; selective mortality and hidden frailty (the osteological paradox, Wood et al. 1992) and missing infant burials often make this doubtful."],
  siler: ["Siler model", "A hazard of death that falls in childhood, stays level, and rises with age: h(t) = a₁e^(−b₁t) + a₂ + a₃e^(b₃t) (Siler 1979). It is fitted to the age ranges directly by maximum likelihood, so skeletons need not be shared over classes. Open-ended adult ages (e.g. 50+) say little about old age, so the senescent part is often poorly fixed."],
  e0: ["Life expectancy at birth", "e₀: the mean age at death in the table. In a stationary population it equals the average lifespan; it is very sensitive to how many infants are represented."],
  juvenility: ["Juvenility index", "Deaths at 5–14 years divided by deaths at 20 years and over (Bocquet-Appel & Masset 1977). Children of 5–14 are aged precisely and their burials survive better than infants', so the index is less affected by poor adult ageing and by missing infants."],
  drinking_water: ["Drinking water δ¹⁸O", "Enamel carbonate δ¹⁸O (‰ VPDB) is put on the VSMOW scale (Coplen et al. 1983) and converted to drinking water with δ¹⁸O(dw) = 1.590 × δ¹⁸O(carbonate) − 48.634 (Chenery et al. 2012); phosphate with δ¹⁸O(dw) = 1.54 × δ¹⁸O(phosphate) − 33.72 (Daux et al. 2008). These conversions are uncertain by 1‰ or more (Pollard et al. 2011), set as the SD. First molars and deciduous teeth form partly during breastfeeding, which raises δ¹⁸O (Wright & Schwarcz 1998)."],
  local_sr: ["Local strontium range", "⁸⁷Sr/⁸⁶Sr in enamel follows the rocks and soils where a person ate as a child (Bentley 2006). The local range is taken from Settings, or as the mean ± 2 SD of baseline samples (local fauna, plants or snails, role = baseline; Price et al. 2002), or, failing both, from the people themselves with Tukey fences (1.5 × the interquartile range beyond the quartiles), which only finds the most unusual."],
  milk_share: ["Breast-milk share", "At each dentine increment, how much of the diet was breast milk. On the adult diet alone, collagen would match the adult females; on milk alone, it would be one nursing enrichment higher in δ¹⁵N (and about 1‰ higher in δ¹³C, Fuller et al. 2006). The share is estimated with its 95% interval from where the increment lies between the two, allowing for the uncertainty of both. An optional third food (e.g. animal milk or a cereal pap) needs δ¹³C too. Needs the adult-female baseline for the site."],
  transition: ["Transition analysis", "For each age, how likely each tooth is to be in the stage it was scored in: a child reaches a stage at an age spread around the stage's mean age, so the chance of being in a stage is the chance of having reached it minus the chance of having reached the next. The teeth are combined and the median age and 95% interval reported, with a flat prior over age so the answer does not take on the ages of a reference sample (Boldsen et al. 2002; Konigsberg & Frankenberg 1992). 'Independent given age' multiplies the teeth's evidence, as Boldsen et al. do; 'one tooth's worth' gives a wider, more cautious interval, since a child's teeth tend to be all early or all late together. 'Stage midpoints' is the older, simpler method."],
  concentration: ["Concentration dependence", "Foods hold different amounts of carbon, nitrogen and sulphur: meat gives far more nitrogen than the same amount of cereal, so a little meat moves collagen δ¹⁵N a lot. With the element content (% of dry weight) of every food filled in, each isotope is mixed by the share of the element each food supplies, not by the food share itself (Phillips & Koch 2002). Leave them empty to mix by food share."],
  mix_prior: ["Prior weight", "How much each food is expected beforehand (the Dirichlet prior). 1 for every food: no expectation, every mix equally likely. A larger weight for one food favours diets with more of it. Use it only with outside evidence, and say so."],
  infant_correction: ["Missing infants", "Infant burials are often missing (shallow graves, fragile bones, burial elsewhere). Given the share of deaths expected in the first year, from a comparable population or a model life table, WeanAge adds infant deaths to a second, corrected table until they reach that share, and reports its life expectancy. The correction is only as good as the share you give."],
  wear_stages: ["Other wear-stage systems", "Mandibles of cattle, pigs or other species scored in another system (for example Grant's mandible wear stages, or Halstead's cattle stages) are given in a wear_stage column. Enter the age range of each stage, in months, from the publication you follow, one per line as 'stage: from-to'. A mandible that could be in two stages is written 'C/D'. WeanAge does not bundle these tables, because their ages differ between studies."],
  origins: ["Possible origins", "For each non-local person, each place's expected ⁸⁷Sr/⁸⁶Sr and drinking-water δ¹⁸O (mean and SD) is compared with the person's values. The places are given equal prior weight and the probabilities shown sum to 100% over the places compared; a place counts only if it lies within 2.5 SD in every isotope. The other sites of the table can be used too, described by their local people. Many places share the same values, so this narrows the possibilities; it does not find a birthplace."],
  individuals: ["Individuals", "Everything WeanAge knows about one person or animal, from every calculation that has a record with this specimen ID: weaning and stress episodes from the dentine, age at death from the teeth, bone data or skeleton, enamel hypoplasia, mobility and diet. 'open' shows that calculation's own result. Teeth in the mobility table are matched to their individual when the ID starts with the individual's ID followed by a space (for example '04/293 C')."],
  killoff: ["Kill-off profiles", "Each mandible is aged by its tooth wear (Payne 1973 stages A–I for sheep and goats) or given an age range. Mandibles that could belong to two stages are shared among them in proportion to the mandibles that fall in only one, as Payne did. The profile is the share killed in each age class; survivorship is the share still alive after each. Payne modelled herds kept for milk (most young males killed before about 6 months), meat (killed at 6 months to about 3 years, near full weight) and wool (many kept for years). Real herds mix aims, and young mandibles are lost to dogs, trampling and excavation more often, so read profiles alongside other evidence (Vigne & Helmer 2007)."],
  killoff_difference: ["Difference between profiles", "Half the summed absolute difference between the two groups' shares in each class: 0% for identical profiles, 100% when they share no class. The p value is the share of random reshufflings of mandibles between the two groups that differ at least this much."],
  mixing: ["Diet mixing model", "Collagen δ values are a mix of the foods eaten, shifted by a collagen-diet offset. Many possible diets are drawn (all mixes equally likely beforehand) and each is weighted by how well it explains the sample, giving each food group's share with a 95% interval, as in FRUITS (Fernandes et al. 2014). Foods are mixed by their protein; with more food groups than isotopes + 1, several diets fit equally well and the intervals stay wide (Phillips et al. 2014). The answer is only as good as the food values, which should come from the same site and period."],
  offsets: ["Collagen-diet offsets", "How far collagen sits above the diet. For δ¹⁵N, values of about 3–6‰ are used; a controlled feeding study in humans found about 6‰ (O'Connell et al. 2012). For δ¹³C, collagen sits about 4.5–5‰ above the diet's protein. δ³⁴S changes little up the food chain (Nehlich 2015). The defaults are placeholders: choose values for your species."],
  strontium: ["Strontium shifts", "⁸⁷Sr/⁸⁶Sr in enamel follows the rocks and soils where the animal fed. A change of level along the crown, chosen by BIC among no, one or two shifts, suggests a move (Bentley 2006); a 'gradual' shift is one step blurred over several samples. Enamel averages strontium over months, so the real move was sharper and may have been earlier (Montgomery et al. 2010). Give a local range (from local plants, water or small animals) to flag values formed elsewhere."],
  calendar: ["Calendar", "Enamel δ¹⁸O peaks in summer. With the month of that maximum, any position can be placed in the year: enamel x mm below the maximum formed x/X of a year later, where X is the crown formed in a year. Birth months need a reference tooth of the same type whose birth month is known, because the birth index only orders animals; a later birth lowers the index by 1/12 per month (Balasse et al. 2012). Weaning months add each animal's weaning age, from the enamel table or from the tooth calculation's results for the same specimen ID."],
  smoothing: ["Smoothing correction", "Enamel at any position matures over months, so each sample averages a stretch of crown (Passey & Cerling 2002; Zazzo et al. 2005). Treating that as a moving average over L mm, the cosine amplitude is divided by sinc(L/X), and the width of the rumen step is narrowed by L²/(4π²) in variance. This is a rough correction: the real maturation geometry is not a simple average."],
  carbon: ["δ¹³C across weaning", "The average δ¹³C of samples formed after weaning ended, minus the average before it began. In known-age calves δ¹³C rose as δ¹⁵N fell at weaning (Balasse et al. 2001), so a rise supports the weaning interpretation. For cattle, a fall of 0.5‰ or more raises a warning."],
  milestone: ["Weaning milestones", "Onset: δ¹⁵N starts to fall (solid food begins). Midpoint: half of the fall has happened. Completion: 95% of the fall has happened. The midpoint is the default because the curve is steepest there, so it is dated most precisely. Completion depends on how slowly δ¹⁵N levels off and can fall long after suckling stopped. An age later than the last sample is shown as 'after' that sample's age, because the curve beyond it is not measured."],
  threshold: ["Transition threshold", "For smooth curves there is no exact start or end, so onset is defined as the point where this share of the δ¹⁵N fall has happened, and completion where all but this share has (5% → 5% / 95%)."],
  analytical_sd: ["Analytical precision", "How reproducible the mass spectrometer is for δ¹⁵N (1 standard deviation of repeated standards). Used to weight the fit and size the uncertainty."],
  max_drop: ["Largest believable drop", "Suckling raises δ¹⁵N by about one food-chain step, 3–4‰ (DeNiro & Epstein 1981; Minagawa & Wada 1984); measured nursing enrichment is usually 2–3‰ (Balasse et al. 2001; Fuller et al. 2006). A fitted drop larger than this is flagged, because something besides weaning is probably involved."],
  min_drop: ["Minimum weaning drop", "Suckling raises δ¹⁵N by roughly one food-chain step. A fall smaller than this is treated as 'no clear weaning signal'."],
  montecarlo: ["Monte Carlo draws", "Uncertainty is estimated by re-computing the weaning age many times with plausible variations of the fitted curve. More draws = smoother intervals, slower."],
  bootstrap: ["Bootstrap", "A more robust way to get uncertainty: the curve is re-fitted many times to resampled versions of the data. Slower, but does not assume the uncertainty is symmetric."],
  time_averaging: ["Time averaging", "A 1 mm slice holds dentine laid down over weeks, so measured values blur the true diet change. With this on, the model accounts for the blur and estimates the underlying change."],
  layer_offset: ["Growth-layer offset", "Dentine layers grow at an angle, so a horizontal slice also contains some later-formed inner dentine. This is how much extra growth (mm) a slice captures."],
  inner_weight: ["Inner dentine weight", "How much the latest-formed (innermost) dentine in a slice counts relative to the earliest. 1 = equal; smaller values = the tooth narrows towards the pulp so there is less of it."],
  seasonal: ["Seasonal term", "Livestock diets change with the seasons (pasture, fodder), which can make δ¹⁵N and δ¹³C rise and fall every year. Adding a seasonal term lets the fit separate that cycle from weaning."],
  baseline: ["Adult-female baseline", "δ¹⁵N of adult females (the mothers' population). The nursing level minus this value is the nursing enrichment; it can also anchor the adult plateau."],
  elbow: ["Elbow method", "The method of the WEAN tool: a smooth polynomial is fitted and weaning is placed where the curve bends most sharply."],
  aicc: ["AICc", "A score of how well a model fits, penalised for complexity. Lower is better; differences (ΔAICc) under ~2 mean the models are about equally supported."],
  weight: ["Akaike weight", "The relative support for each model among those fitted (they sum to 1)."],
  average: ["Model average", "An estimate that combines all models, weighted by their support. More honest than picking one model when several fit similarly well."],
  random_effects: ["Random-effects mean", "A group average that allows animals to genuinely differ from each other, on top of each estimate's own uncertainty."],
  tau: ["τ (between-animal SD)", "How much real variation in weaning age there is between animals in a group, beyond measurement uncertainty."],
  holm: ["Holm correction", "Adjusts p-values when many pairs of groups are compared, so chance differences are less likely to look significant."],
  permutation: ["Permutation test", "Shuffles the group labels thousands of times to see how often differences as large as the observed ones arise by chance."],
  bayes: ["Hierarchical Bayesian model", "Each animal's estimate is pulled slightly towards its group's average, in proportion to its uncertainty. It gives direct probabilities, e.g. 'the chance that pigs were weaned earlier than cattle'."],
  erj: ["Distance from the enamel-root junction", "Measured from the enamel-root junction (ERJ), where the crown meets the root, up to the middle of each enamel sample, in mm. Enamel high on the crown formed first, so larger distances are earlier in life."],
  birth_index: ["Birth index (x₀/X)", "Enamel δ¹⁸O follows drinking water, which is higher in summer. A cosine is fitted along the crown: X is the crown length formed in a year and x₀ the position of the δ¹⁸O maximum. x₀/X (0–1) places that summer on the tooth. Between teeth of the same type, differences in x₀/X reflect differences in season of birth (Balasse et al. 2012). It is a relative index, not a calendar date."],
  c4: ["C3 or C4 diet", "Most temperate plants are C3; C4 plants (millet, maize, sorghum and many tropical and dry-country grasses) have δ¹³C about 15‰ higher. Enamel δ¹³C is about 14‰ above the diet's in cattle (Cerling & Harris 1999), so the diet's δ¹³C places it between a C3 and a C4 end member. The share of C4 plants has a wide interval, because C3 plants vary by several ‰ with water stress and shade (Kohn 2010). Only enamel formed after the rumen transition is used, as milk lowers δ¹³C. For modern animals use modern plant values: fossil-fuel CO2 has lowered plant δ¹³C by about 1.5–2‰ since 1850."],
  rumen: ["Rumen development", "A suckling calf's rumen is not yet working. As it develops, fermentation enriches the carbon reaching the enamel in ¹³C, so enamel δ¹³C rises (Passey et al. 2005; Towers et al. 2014). WeanAge fits a rising step plus a seasonal wave to δ¹³C and reports the step only if it fits clearly better (AICc) than the wave alone. Enamel mineralises slowly, so the real change was sharper than it appears."],
  bone_model: ["Bone calculation", "After WARN (Tsutaya & Yoneda 2013). Young animals' bone δ¹⁵N is fitted against age at death. The diet is milk until weaning starts, then changes steadily to weaning food until weaning ends. Bone starts at the mother's value and is gradually rebuilt from the current diet, so it lags behind the diet. The weaning ages, the nursing enrichment and the weaning-food δ¹⁵N are estimated together."],
  bone_age: ["Age at death", "In months. Give a single best estimate (age_months) or, better, the range your ageing method gives (age_min_months and age_max_months), e.g. from tooth eruption and wear or epiphyseal fusion. The model samples each animal's age within its range, so that uncertainty is carried into the result."],
  weaning_form: ["Shape of weaning", "How quickly milk gives way to other food between the start and end of weaning. Parabolic (WARN's default, after Millard 2000): slowly at first, then faster. Linear: at a steady rate. Reverse parabolic: quickly at first, then slower."],
  bone_enrichment: ["Nursing enrichment prior", "How much higher, in ‰, collagen made from milk is than the mother's. WARN's default is 1.9 ± 0.9‰, from human archaeological populations (Waters-Rist & Katzenberg 2010). Across 11 mammal species, offspring plasma was only about 0.9‰ above the mothers' (Jenkins et al. 2001), while about 3–3.5‰ is reported between nursing calves and cows in collagen. Each species has its own starting values (Species priors); set them from known-age animals if you can."],
  newborn_offset: ["Newborn offset", "How far a newborn's bone δ¹⁵N sits above its mother's. WARN assumes 0 for humans. In other mammals foetal tissue is enriched over the mother (about 1.7‰, range 0.9–2.7‰, in a marine mammal; 2.6–2.7‰ has been reported for calf and sheep foetuses), so for livestock it is estimated, starting from a placeholder prior."],
  nursing_check: ["Nursing signal check", "Before trusting a fit, the youngest third of the young animals are compared with the mothers (one-sided Welch t-test). If they are not clearly higher, the data may hold no suckling signal: the model would still return ages (Reynard & Tuross 2015; Tsutaya & Yoneda 2013)."],
  bone_planner: ["Planning a bone study", "Invents sites whose end of suckling is known, gives each the number of young animals, the ages, the age precision and the measurement scatter you plan, runs the bone calculation, and scores it: how wide the 95% interval is, how far off the estimate is, how often the interval contains the truth, and how often the nursing signal is found at all. Compare one setting at a time, e.g. 20, 40 and 80 young animals."],
  turnover: ["Bone collagen turnover", "The share of bone collagen newly made each month. It is high in fast-growing young animals and falls with age. WARN estimated it for humans; for livestock the values are placeholders until bone growth and remodelling data are compiled."],
  rhat: ["R̂ (convergence)", "Checks the Bayesian sampler has settled: values close to 1.00 (below 1.05) are fine."],
  coverage: ["Interval coverage", "How often the 95% interval contains the true value. Close to 95% means the uncertainty is well calibrated."],
  simulation: ["Sampling planner", "Simulates teeth with known weaning ages, samples them as your protocol would, runs the analysis and shows how accurate the results are. Use it to choose sampling intervals before cutting teeth."],
};

export function initGlossary() {
  const pop = document.createElement("div");
  pop.className = "help-pop";
  pop.setAttribute("role", "dialog");
  pop.hidden = true;
  document.body.appendChild(pop);
  const close = () => {
    pop.hidden = true;
  };
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".help-btn");
    if (!btn) {
      if (!e.target.closest(".help-pop")) close();
      return;
    }
    e.preventDefault();
    const [title, text] = GLOSSARY[btn.dataset.help] || [btn.dataset.help, "No description yet."];
    pop.innerHTML = `<strong>${esc(title)}</strong><p>${esc(text)}</p><button type="button" class="ghost tiny" data-close>Close</button>`;
    pop.hidden = false;
    const r = btn.getBoundingClientRect();
    pop.style.top = `${window.scrollY + r.bottom + 6}px`;
    pop.style.left = `${Math.max(8, Math.min(window.scrollX + r.left - 20, window.scrollX + innerWidth - 340))}px`;
    pop.querySelector("[data-close]").focus();
    pop.querySelector("[data-close]").addEventListener("click", () => {
      close();
      btn.focus();
    });
  });
  document.addEventListener("keydown", (e) => e.key === "Escape" && close());
}

const TOUR = [
  { view: "data", sel: "#dropzone", title: "1 · Load your data", text: "Drop a CSV or Excel file, then tick the calculations to run with it below: WeanAge shows which ones the table can be used for. Or choose an example and press 'Load example'." },
  { view: "data", sel: "#manual-form", mode: "tooth", title: "Or type samples in", text: "Specimen details are remembered between entries and the position steps forward automatically." },
  { view: "settings", sel: "#model-options", mode: "tooth", title: "2 · Choose curve models", text: "Every model is fitted to every specimen so you can see how much the method matters. Leave them all on if unsure." },
  { view: "settings", sel: "#growth-list", mode: "tooth", title: "Age models", text: "These convert tooth position to age. Yellow ones are placeholders: edit them, calibrate them from reference data, or save your own." },
  { view: "settings", sel: "#btn-run", mode: "tooth", title: "Run the analysis", text: "A progress bar shows while curves are fitted." },
  { view: "plan", sel: "#plan-form", mode: "tooth", title: "Plan your sampling", text: "Before cutting teeth, simulate how accurate different sampling intervals or numbers of animals would be." },
  { view: null, sel: "#btn-save", title: "Save your work", text: "Save the whole project (data, settings and results) to a file and reopen it later. Your work is also kept in this browser automatically." },
  { view: null, sel: "#btn-help", title: "Need a reminder?", text: "Press ? next to any term for a plain-language explanation. The Help menu reopens this tour and links to the user guide." },
];

export function startTour(show, mode = "tooth") {
  const steps = TOUR.filter((step) => !step.mode || step.mode === mode); // bone mode hides the tooth-only parts
  let i = 0;
  const overlay = document.createElement("div");
  overlay.className = "tour";
  overlay.innerHTML = `<div class="tour-ring"></div>
    <div class="tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      <h3 id="tour-title"></h3><p class="tour-text"></p>
      <div class="row between"><span class="tour-count muted"></span>
        <span class="row gap"><button type="button" class="ghost" data-act="skip">Skip tour</button>
        <button type="button" class="secondary" data-act="back">Back</button>
        <button type="button" data-act="next">Next</button></span></div>
    </div>`;
  document.body.appendChild(overlay);
  const ring = overlay.querySelector(".tour-ring");
  const card = overlay.querySelector(".tour-card");

  const finish = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
    try {
      localStorage.setItem("weanage-tour-done", "1");
    } catch {}
  };
  const render = () => {
    const step = steps[i];
    if (step.view) show(step.view);
    const target = $(step.sel);
    overlay.querySelector("#tour-title").textContent = step.title;
    overlay.querySelector(".tour-text").textContent = step.text;
    overlay.querySelector(".tour-count").textContent = `${i + 1} of ${steps.length}`;
    overlay.querySelector('[data-act="back"]').disabled = i === 0;
    overlay.querySelector('[data-act="next"]').textContent = i === steps.length - 1 ? "Finish" : "Next";
    if (target) {
      target.scrollIntoView({ block: "center" });
      const r = target.getBoundingClientRect();
      Object.assign(ring.style, { top: `${r.top - 6}px`, left: `${r.left - 6}px`, width: `${r.width + 12}px`, height: `${r.height + 12}px` });
      const below = r.bottom + 220 < innerHeight;
      card.style.top = `${below ? r.bottom + 14 : Math.max(12, r.top - 200)}px`;
      card.style.left = `${Math.max(12, Math.min(r.left, innerWidth - 380))}px`;
    }
    overlay.querySelector('[data-act="next"]').focus();
  };
  const onKey = (e) => {
    if (e.key === "Escape") finish();
    if (e.key === "ArrowRight") overlay.querySelector('[data-act="next"]').click();
    if (e.key === "ArrowLeft" && i > 0) overlay.querySelector('[data-act="back"]').click();
  };
  overlay.addEventListener("click", (e) => {
    const act = e.target.dataset.act;
    if (act === "skip") finish();
    if (act === "back" && i > 0) {
      i -= 1;
      render();
    }
    if (act === "next") {
      if (i === steps.length - 1) finish();
      else {
        i += 1;
        render();
      }
    }
  });
  document.addEventListener("keydown", onKey);
  render();
}

export function tourSeen() {
  try {
    return localStorage.getItem("weanage-tour-done") === "1";
  } catch {
    return true;
  }
}

// The Help menu: the tour, and the PDF user guide
const GUIDE_PDF = "guide/WeanAge_user_guide.pdf";

/** A drop-down menu opened by `button`: arrow keys move, Escape closes, choosing an item closes it. */
export function bindMenu(button, menu) {
  const items = () => [...menu.querySelectorAll("button, a[href]")];
  const close = (refocus) => {
    menu.hidden = true;
    button.setAttribute("aria-expanded", "false");
    if (refocus) button.focus();
  };
  const open = () => {
    menu.hidden = false;
    button.setAttribute("aria-expanded", "true");
    items()[0].focus();
  };
  button.addEventListener("click", () => (menu.hidden ? open() : close(false)));
  menu.addEventListener("click", (e) => { if (e.target.closest("button, a[href]")) close(false); });
  menu.addEventListener("keydown", (e) => {
    const list = items();
    const at = list.indexOf(document.activeElement);
    if (e.key === "Escape") close(true);
    if (e.key === "ArrowDown") list[(at + 1) % list.length].focus();
    if (e.key === "ArrowUp") list[(at - 1 + list.length) % list.length].focus();
    if (["ArrowDown", "ArrowUp"].includes(e.key)) e.preventDefault();
  });
  document.addEventListener("click", (e) => {
    if (!menu.hidden && !button.parentElement.contains(e.target)) close(false);
  });
}

export function initHelpMenu(show, mode) {
  bindMenu($("#btn-help"), $("#help-menu"));
  bindMenu($("#btn-view"), $("#view-menu"));
  $("#menu-tour").addEventListener("click", () => startTour(show, mode()));
  markGuideIfMissing();
}

/** The PDF guide is not written yet: until it exists, show the entry as unavailable rather than a broken link. */
async function markGuideIfMissing() {
  let found = false;
  try {
    found = (await fetch(GUIDE_PDF, { method: "HEAD" })).ok;
  } catch {}
  if (found) return;
  const link = $("#menu-guide");
  link.removeAttribute("href");
  link.setAttribute("aria-disabled", "true");
  link.textContent = "User guide (PDF): coming soon";
}
