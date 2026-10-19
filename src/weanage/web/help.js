// Plain-language glossary and a guided first-run tour for non-specialist users.
import { $, esc } from "./util.js";

export const GLOSSARY = {
  position: ["Position (mm)", "Distance from the cusp apex (the tip of the tooth crown, where dentine forms first) to the middle of the sampled slice. If you measured from the cervix (crown base), set position_reference = cervix and give crown_height_mm; the app converts it."],
  growth_table: ["Age model / growth table", "Converts position along the tooth into the age at which that dentine formed. Values between table points are interpolated. The bundled tables are placeholders until real tooth-formation data are entered."],
  calibrate: ["Calibration", "Builds a growth table from reference measurements of known age, e.g. the forming edge of teeth from animals of known age at death, or incremental-line counts."],
  qc: ["Collagen quality control", "Degraded or contaminated collagen gives unreliable isotope values. Samples outside the C:N, %C, %N or yield limits are flagged and, by default, left out of the fit."],
  milestone: ["Weaning milestones", "Onset: δ¹⁵N starts to fall (solid food begins). Midpoint: half of the fall has happened. Completion: δ¹⁵N reaches the adult level (suckling has stopped). Completion is what most studies call 'weaning age'."],
  threshold: ["Transition threshold", "For smooth curves there is no exact start or end, so onset is defined as the point where this share of the δ¹⁵N fall has happened, and completion where all but this share has (5% → 5% / 95%)."],
  analytical_sd: ["Analytical precision", "How reproducible the mass spectrometer is for δ¹⁵N (1 standard deviation of repeated standards). Used to weight the fit and size the uncertainty."],
  min_drop: ["Minimum weaning drop", "Suckling raises δ¹⁵N by roughly one food-chain step. A fall smaller than this is treated as 'no clear weaning signal'."],
  montecarlo: ["Monte Carlo draws", "Uncertainty is estimated by re-computing the weaning age many times with plausible variations of the fitted curve. More draws = smoother intervals, slower."],
  bootstrap: ["Bootstrap", "A more robust way to get uncertainty: the curve is re-fitted many times to resampled versions of the data. Slower, but does not assume the uncertainty is symmetric."],
  time_averaging: ["Time averaging", "A 1 mm slice holds dentine laid down over weeks, so measured values blur the true diet change. With this on, the model accounts for the blur and estimates the underlying change."],
  layer_offset: ["Growth-layer offset", "Dentine layers grow at an angle, so a horizontal slice also contains some later-formed inner dentine. This is how much extra growth (mm) a slice captures."],
  inner_weight: ["Inner dentine weight", "How much the latest-formed (innermost) dentine in a slice counts relative to the earliest. 1 = equal; smaller values = the tooth narrows towards the pulp so there is less of it."],
  seasonal: ["Seasonal term", "Livestock diets change with the seasons (pasture, fodder), which can make δ¹⁵N and δ¹³C rise and fall every year. Adding a seasonal term lets the fit separate that cycle from weaning."],
  baseline: ["Adult-female baseline", "δ¹⁵N of adult females (the mothers' population). The nursing level minus this value is the nursing enrichment; it can also anchor the adult plateau."],
  enrichment: ["Nursing enrichment", "How much higher the nursing δ¹⁵N is than the adult females' value; typically about one food-chain step."],
  two_phase: ["Two-phase weaning", "A two-step decline: supplementary feeding while still suckling, then final weaning. Expected where people took part of the milk (dairying)."],
  elbow: ["Elbow method", "The method of the WEAN tool: a smooth polynomial is fitted and weaning is placed where the curve bends most sharply."],
  aicc: ["AICc", "A score of how well a model fits, penalised for complexity. Lower is better; differences (ΔAICc) under ~2 mean the models are about equally supported."],
  weight: ["Akaike weight", "The relative support for each model among those fitted (they sum to 1)."],
  average: ["Model average", "An estimate that combines all models, weighted by their support. More honest than picking one model when several fit similarly well."],
  random_effects: ["Random-effects mean", "A group average that allows animals to genuinely differ from each other, on top of each estimate's own uncertainty."],
  tau: ["τ (between-animal SD)", "How much real variation in weaning age there is between animals in a group, beyond measurement uncertainty."],
  holm: ["Holm correction", "Adjusts p-values when many pairs of groups are compared, so chance differences are less likely to look significant."],
  permutation: ["Permutation test", "Shuffles the group labels thousands of times to see how often differences as large as the observed ones arise by chance."],
  bayes: ["Hierarchical Bayesian model", "Each animal's estimate is pulled slightly towards its group's average, in proportion to its uncertainty. It gives direct probabilities, e.g. 'the chance that pigs were weaned earlier than cattle'."],
  rhat: ["R̂ (convergence)", "Checks the Bayesian sampler has settled: values close to 1.00 (below 1.05) are fine."],
  coverage: ["Interval coverage", "How often the 95% interval contains the true value. Close to 95% means the uncertainty is well calibrated."],
  mae: ["MAE", "Mean absolute error: the average size of the error, in months."],
  bias: ["Bias", "The average signed error: positive means estimates are systematically too late."],
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
  { view: "data", sel: "#dropzone", title: "1 · Load your data", text: "Drop a CSV or Excel file with one row per dentine slice, or press 'Load synthetic example' to explore with simulated data." },
  { view: "data", sel: "#manual-form", title: "Or type samples in", text: "Specimen details are remembered between entries and the position steps forward automatically." },
  { view: "settings", sel: "#model-options", title: "2 · Choose curve models", text: "Every model is fitted to every specimen so you can see how much the method matters. Leave them all on if unsure." },
  { view: "settings", sel: "#growth-list", title: "Age models", text: "These convert tooth position to age. Yellow ones are placeholders: edit them, calibrate them from reference data, or save your own." },
  { view: "settings", sel: "#btn-run", title: "Run the analysis", text: "A progress bar shows while curves are fitted. Larger datasets are processed in parallel." },
  { view: "plan", sel: "#plan-form", title: "Plan your sampling", text: "Before cutting teeth, simulate how accurate different sampling intervals or numbers of animals would be." },
  { view: null, sel: "#btn-save", title: "Save your work", text: "Save the whole project (data, settings and results) to a file and reopen it later. Your work is also kept in this browser automatically." },
  { view: null, sel: "#btn-help", title: "Need a reminder?", text: "Press ? next to any term for a plain-language explanation, or reopen this tour here." },
];

export function startTour(show) {
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
    const step = TOUR[i];
    if (step.view) show(step.view);
    const target = $(step.sel);
    overlay.querySelector("#tour-title").textContent = step.title;
    overlay.querySelector(".tour-text").textContent = step.text;
    overlay.querySelector(".tour-count").textContent = `${i + 1} of ${TOUR.length}`;
    overlay.querySelector('[data-act="back"]').disabled = i === 0;
    overlay.querySelector('[data-act="next"]').textContent = i === TOUR.length - 1 ? "Finish" : "Next";
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
      if (i === TOUR.length - 1) finish();
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
