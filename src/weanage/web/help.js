// Plain-language glossary and a guided first-run tour for non-specialist users.
import { $, esc } from "./util.js";

export const GLOSSARY = {
  position: ["Position (mm)", "Distance from the cusp apex (the tip of the tooth crown, where dentine forms first) to the middle of the sampled slice. If you measured from the cervix (crown base), set position_reference = cervix and give crown_height_mm; the app converts it."],
  growth_table: ["Age model / growth table", "Converts position along the tooth into the age at which that dentine formed. Values between table points are interpolated. The bundled tables are placeholders until real tooth-formation data are entered."],
  calibrate: ["Calibration", "Builds a growth table from reference measurements of known age, e.g. the forming edge of teeth from animals of known age at death, or incremental-line counts."],
  qc: ["Collagen quality control", "Degraded or contaminated collagen gives unreliable isotope values. Samples outside the C:N, %C, %N or yield limits are flagged and, by default, left out of the fit. Archaeological collagen is usually judged with C:N 2.9–3.6 (DeNiro 1985). Fresh collagen from modern reference animals should fall in the narrower 3.00–3.28 (Guiry & Szpak 2020)."],
  onestage: ["One-stage or two-stage", "Two-stage: each tooth is fitted on its own first, then the weaning ages and their uncertainties are compared. One-stage: a logistic curve for every tooth and the group comparison are estimated together from the raw δ¹⁵N values, so the uncertainty in each curve's shape and in the tooth's age model is carried all the way through. It is slower, uses the logistic curve only, and leaves out teeth whose weaning age would have to be extrapolated."],
  true_shape: ["Shape of the true curves", "The planner invents teeth whose weaning curve is known. If they were all logistic, the logistic model would look best simply because it matches how the data were made. Choose another shape, or a random mix, to see how each model copes when its shape is wrong. All shapes take about the same time to go from 5 % to 95 % of the drop."],
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
  { view: "data", sel: "#dropzone", title: "1 · Load your data", text: "Drop a CSV or Excel file with one row per dentine slice, or choose an example (simulated, or real published cattle data) and press 'Load example'." },
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

export function initHelpMenu(show, mode) {
  const button = $("#btn-help");
  const menu = $("#help-menu");
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
  $("#menu-tour").addEventListener("click", () => {
    close(false);
    startTour(show, mode());
  });
  $("#menu-guide").addEventListener("click", () => close(false));
  menu.addEventListener("keydown", (e) => {
    const list = items();
    const at = list.indexOf(document.activeElement);
    if (e.key === "Escape") close(true);
    if (e.key === "ArrowDown") list[(at + 1) % list.length].focus();
    if (e.key === "ArrowUp") list[(at - 1 + list.length) % list.length].focus();
    if (["ArrowDown", "ArrowUp"].includes(e.key)) e.preventDefault();
  });
  document.addEventListener("click", (e) => {
    if (!menu.hidden && !e.target.closest(".menu-wrap")) close(false);
  });
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
