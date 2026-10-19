// The main page: holds the app's state and draws each of the five views.
import { api } from "./api.js";
import { curveChart, curveOptions, forestChart } from "./chart.js";
import { bindGrowthEditor, renderGrowthList } from "./growth.js";
import { initGlossary, startTour, tourSeen } from "./help.js";
import { initPlanner, renderPlan } from "./planner.js";
import { buildReport, offscreen } from "./report.js";
import { $, $$, ci, download, esc, help, MILESTONES, num, progressBar, pval, swatch, table, tbdBadge, toast, toCsv } from "./util.js";

const state = {
  config: null, // settings and lists sent by the server
  samples: [],
  report: null, // the server's check of the samples (issues, specimen list)
  overrides: {}, // "species:tooth" -> simple linear age model
  baselines: {}, // "site:species" -> adult-female δ15N {mean, sd}
  editedTables: {}, // "species:tooth" -> growth table edited in the app
  results: null,
  estimates: null,
  options: null, // the settings used for the current results
  current: null, // which specimen is shown
  visible: new Set(), // which curves are switched on
  zoom: null,
  plan: null,
};
const capital = (s) => s[0].toUpperCase() + s.slice(1);

// ───────────── switching views ─────────────
function show(view) {
  for (const b of $$(".step")) {
    const isThis = b.dataset.view === view;
    b.classList.toggle("active", isThis);
    if (isThis) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  for (const v of $$(".view")) v.classList.toggle("active", v.id === `view-${view}`);
  if (view === "settings") {
    renderGrowthList(state);
    renderBaselines();
  }
  if (view === "compare") refreshCompare();
  window.scrollTo({ top: 0 });
}

function enableResults(on) {
  for (const b of $$('.step[data-view="results"], .step[data-view="compare"], #btn-report')) b.disabled = !on;
}

// Highlight every setting that is still a placeholder (TBD-LAB).
function renderTbd() {
  const items = state.config.tbd;
  const ids = new Set(items.map((i) => i.id));
  $("#tbd-banner").hidden = !items.length;
  $("#tbd-count").textContent = items.length;
  $("#tbd-list").innerHTML = items.map((i) => `<li><strong>${esc(i.area)}:</strong> ${esc(i.label)} — ${esc(i.note)} <code>${esc(i.file)}</code></li>`).join("");
  for (const node of $$("[data-tbd]")) {
    const on = ids.has(node.dataset.tbd);
    const title = node.matches("label") ? node : node.querySelector("h2");
    node.classList.toggle("tbd", on);
    title.querySelector(".tbd-badge")?.remove();
    if (on) title.insertAdjacentHTML("beforeend", ` ${tbdBadge}`);
  }
}

async function refreshConfig() {
  state.config = await api.config();
  renderTbd();
}

// ───────────── 1. data ─────────────
function setReport(report, keepResults = false) {
  state.report = report;
  state.samples = report.samples;
  if (!keepResults) {
    state.results = state.estimates = null;
    enableResults(false);
  }
  renderData();
  autosave();
}

async function recheck(keepResults = false) {
  setReport(await api.validateRecords(state.samples), keepResults);
}

function ageModelLabel(species, tooth) {
  const key = `${species}:${tooth}`;
  if (state.overrides[key]) return "custom linear";
  const t = state.editedTables[key] || state.config.growth_tables.find((g) => `${g.species}:${g.tooth}` === key);
  return t ? `${esc(t.label)} ${t.placeholder ? tbdBadge : ""}` : '<span class="warn-text">none — add one in Settings</span>';
}

function renderData() {
  const issues = state.report ? state.report.issues : [];
  $("#issues-card").hidden = !issues.length;
  $("#issues").innerHTML = issues
    .map((i) => `<li class="${i.severity}">${i.row ? `<b>Row ${i.row}</b>${i.field ? ` (${esc(i.field)})` : ""}: ` : ""}${esc(i.message)}</li>`)
    .join("");
  $("#specimens-card").hidden = !state.samples.length;
  $("#sample-count").textContent = `· ${state.samples.length} samples`;
  table($("#specimen-table"), [
    { label: "Specimen", key: "specimen_id" },
    { label: "Animal", render: (s) => esc(s.individual_id || "—") },
    { label: "Site", key: "site" },
    { label: "Species", key: "species" },
    { label: "Tooth", key: "tooth" },
    { label: "Samples", key: "n_samples", cls: "num" },
    { label: "Age model", render: (s) => ageModelLabel(s.species, s.tooth) },
  ], state.report ? state.report.specimens : []);

  const qc = settings().qc;
  const badCN = (s) => s.cn_ratio != null && (s.cn_ratio < qc.cn_min || s.cn_ratio > qc.cn_max);
  table($("#sample-table"), [
    { label: "Specimen", key: "specimen_id" },
    { label: "Position (mm)", cls: "num", render: (s) => num(s.position_mm) + (s.position_measured_mm != null ? ` <small class="muted">(cervix ${num(s.position_measured_mm, 1)})</small>` : "") },
    { label: "δ¹⁵N", cls: "num", render: (s) => num(s.d15N) },
    { label: "δ¹³C", cls: "num", render: (s) => num(s.d13C) },
    { label: "%C", cls: "num", render: (s) => num(s.pct_C, 1) },
    { label: "%N", cls: "num", render: (s) => num(s.pct_N, 1) },
    { label: "C:N", cls: "num", render: (s) => `<span class="${badCN(s) ? "bad" : ""}">${num(s.cn_ratio)}</span>` },
    { label: "Notes", key: "notes" },
    { label: "<span class='sr-only'>Remove</span>", render: (s, i) => `<button class="ghost tiny" data-remove="${i}" aria-label="Remove sample at ${esc(s.position_mm)} mm from ${esc(s.specimen_id)}">✕</button>` },
  ], state.samples);
}

async function loadFile(file) {
  try {
    setReport(await api.uploadFile(file));
    toast(`Loaded ${state.samples.length} samples from ${file.name}`, "ok");
  } catch (e) {
    toast(e.message);
  }
}

async function addSampleByHand(event) {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form));
  const step = Number(data.step) || 1;
  delete data.step;
  const msg = $("#manual-msg");
  try {
    const check = await api.validateRecords([data]);
    const errors = check.issues.filter((i) => i.severity === "error");
    for (const input of form.elements) {
      const bad = errors.some((e) => e.field === input.name);
      input.classList.toggle("invalid", bad);
      if (bad) input.setAttribute("aria-invalid", "true");
      else input.removeAttribute("aria-invalid");
    }
    if (errors.length) {
      msg.className = "inline-msg error";
      msg.textContent = errors.map((e) => `${e.field}: ${e.message}`).join("; ");
      return;
    }
    state.samples.push(check.samples[0]);
    await recheck();
    msg.className = "inline-msg ok";
    msg.textContent = `Added ${data.specimen_id} @ ${data.position_mm} mm`;
    form.elements.position_mm.value = (Number(data.position_mm) + step).toFixed(1);
    for (const f of ["d15N", "d13C", "pct_C", "pct_N", "cn_ratio", "collagen_yield_pct"]) form.elements[f].value = "";
    form.elements.d15N.focus();
  } catch (e) {
    msg.className = "inline-msg error";
    msg.textContent = e.message;
  }
}

// ───────────── 2. settings ─────────────
// Which form control holds each setting, and what kind of value it holds.
const FIELDS = {
  reported_milestone: ["#opt-milestone", "text"],
  analytical_sd_permil: ["#opt-sd", "number"],
  min_weaning_drop_permil: ["#opt-mindrop", "number"],
  monte_carlo_draws: ["#opt-draws", "number"],
  uncertainty: ["#opt-uncertainty", "text"],
  bootstrap_draws: ["#opt-boot", "number"],
  time_averaging: ["#opt-timeavg", "tick"],
  increment_width_mm: ["#opt-incwidth", "number"],
  growth_layer_offset_mm: ["#opt-layeroffset", "number"],
  inner_dentine_weight: ["#opt-innerweight", "number"],
  seasonal_term: ["#opt-seasonal", "tick"],
  season_period_months: ["#opt-period", "number"],
  elbow_normalise: ["#opt-elbownorm", "tick"],
  constrain_adult_plateau: ["#opt-constrain", "tick"],
};

function initSettings() {
  $("#model-options").innerHTML = state.config.models
    .map((m) => `<label class="check model-opt">
        <input type="checkbox" name="model" value="${m.name}">${swatch(m.name)}
        <span><strong>${esc(m.label)}</strong> ${["two_phase", "elbow"].includes(m.name) ? help(m.name) : ""}<br><small>${esc(m.description)}</small></span>
      </label>`)
    .join("");
  for (const m of state.config.models) $("#cmp-model").insertAdjacentHTML("beforeend", `<option value="${m.name}">${esc(m.label)}</option>`);
  // Published QC limits: choosing one fills in the boxes, which can still be edited.
  const presets = state.config.qc_presets || {};
  for (const [key, p] of Object.entries(presets)) $("#qc-preset").insertAdjacentHTML("beforeend", `<option value="${key}">${esc(p.label)}</option>`);
  $("#qc-preset").addEventListener("change", (e) => {
    const { label, ...limits } = presets[e.target.value] || {};
    if (label) applySettings({ qc: limits });
  });
  applySettings(state.config.defaults);
}

/** Put a settings object (the defaults, or a saved project's) into the form. */
function applySettings(o) {
  if (o.models) for (const box of $$('input[name="model"]')) box.checked = o.models.includes(box.value);
  if (o.transition_threshold != null) $("#opt-threshold").value = Math.round(o.transition_threshold * 100);
  for (const [key, [selector, kind]] of Object.entries(FIELDS)) {
    if (!(key in o)) continue;
    if (kind === "tick") $(selector).checked = !!o[key];
    else $(selector).value = o[key] ?? "";
  }
  for (const [key, value] of Object.entries(o.qc || {})) {
    const input = $(`#qc-${key}`);
    if (input?.type === "checkbox") input.checked = value;
    else if (input) input.value = value;
  }
  if (o.growth_overrides) state.overrides = { ...o.growth_overrides };
  if (o.adult_baselines) state.baselines = { ...o.adult_baselines };
  if (o.growth_tables) state.editedTables = Object.fromEntries(o.growth_tables.map((t) => [`${t.species}:${t.tooth}`, t]));
}

/** Read the form back into a settings object for the server. */
function settings() {
  const qc = {};
  for (const key of Object.keys(state.config.defaults.qc)) {
    const input = $(`#qc-${key}`);
    qc[key] = input.type === "checkbox" ? input.checked : Number(input.value);
  }
  const out = {
    models: $$('input[name="model"]:checked').map((box) => box.value),
    transition_threshold: (Number($("#opt-threshold").value) || 5) / 100,
    random_seed: 42,
    qc,
    growth_overrides: state.overrides,
    adult_baselines: state.baselines,
    growth_tables: Object.values(state.editedTables).map(({ saved, ...t }) => t),
  };
  for (const [key, [selector, kind]] of Object.entries(FIELDS)) {
    const input = $(selector);
    if (kind === "tick") out[key] = input.checked;
    else if (kind === "text") out[key] = input.value;
    else out[key] = input.value === "" ? state.config.defaults[key] : Number(input.value);
  }
  out.analytical_sd_permil ||= null; // blank or 0 means "not known yet"
  return out;
}

function renderBaselines() {
  const keys = [...new Set(state.samples.map((s) => `${s.site}:${s.species}`))];
  $("#baseline-list").innerHTML = keys.length
    ? keys.map((key) => `<div class="baseline-row" data-key="${esc(key)}">
          <span class="key">${esc(key.replace(":", " · "))}</span>
          <label>Mean δ¹⁵N (‰)<input type="number" step="0.01" class="bl-mean" value="${state.baselines[key]?.mean ?? ""}" placeholder="TBD-LAB"></label>
          <label>SD (‰)<input type="number" step="0.01" min="0.01" class="bl-sd" value="${state.baselines[key]?.sd ?? ""}" placeholder="0.5"></label>
        </div>`).join("")
    : '<p class="muted">Load data to enter baselines for each site and species.</p>';
}

async function runAnalysis() {
  const opts = settings();
  if (!state.samples.length) return toast("Load some data first.");
  if (!opts.models.length) return toast("Choose at least one curve model.");
  $("#btn-run").disabled = true;
  progressBar($("#run-progress"), 0, 0, "Fitting specimens");
  try {
    const out = await api.analyze(state.samples, opts, (done, total) => progressBar($("#run-progress"), done, total, "Fitting specimens"));
    Object.assign(state, { results: out.results, estimates: out.estimates, options: opts, current: out.results[0]?.specimen_id, zoom: null });
    state.visible = new Set([...opts.models, "average"]);
    enableResults(true);
    renderResults();
    show("results");
    autosave();
  } catch (e) {
    toast(e.message);
  } finally {
    $("#btn-run").disabled = false;
    $("#run-progress").hidden = true;
  }
}

// ───────────── 3. results ─────────────
const isNote = (w) => /PLACEHOLDER|^Time averaging on|teeth .* combined/.test(w); // information, not a problem
const warningCount = (r) => r.warnings.filter((w) => !isNote(w)).length + r.fits.reduce((n, f) => n + f.warnings.length, 0);

function renderResults() {
  const milestone = state.options.reported_milestone;
  $("#result-list").innerHTML = state.results
    .map((r) => {
      const best = r.fits.find((f) => f.model === r.best_model)?.[milestone];
      const chosen = r.specimen_id === state.current;
      return `<li><button role="option" aria-selected="${chosen}" tabindex="${chosen ? 0 : -1}" data-specimen="${esc(r.specimen_id)}" class="${chosen ? "active" : ""}">
        <span><strong>${esc(r.specimen_id)}</strong><small>${esc(r.site)} · ${esc(r.species)} ${esc(r.tooth)}</small></span>
        <span class="pill">${best ? `${num(best.estimate, 1)} mo` : "—"}${warningCount(r) ? ` <span class="warn-dot" aria-label="${warningCount(r)} warning(s)">!</span>` : ""}</span>
      </button></li>`;
    })
    .join("");
  const res = state.results.find((r) => r.specimen_id === state.current) || state.results[0];
  if (!res) return;
  $("#res-title").textContent = res.specimen_id;
  $("#res-meta").innerHTML = `${esc(res.site)} · ${esc(res.species)} ${esc(res.tooth)}${res.period ? ` · ${esc(res.period)}` : ""} · age model: ${esc(res.growth_table)} ${res.growth_placeholder ? tbdBadge : ""}`;

  const hasAverage = Object.keys(res.model_average).length > 0;
  const toggles = res.fits.map((f) => [f.model, f.label.split(" (")[0]]).concat(hasAverage ? [["average", "Model average"]] : []);
  $("#curve-toggles").innerHTML = toggles
    .map(([m, label]) => `<label class="check toggle"><input type="checkbox" data-model="${m}" ${state.visible.has(m) ? "checked" : ""}>${swatch(m)}${esc(label)}</label>`)
    .join("");

  $("#res-summary").innerHTML = summaryText(res, milestone);
  if (res.points.length) {
    const onZoom = (range) => { state.zoom = range; renderResults(); };
    curveChart($("#res-chart"), curveOptions(res, { visible: state.visible, milestone, xRange: state.zoom, showD13C: $("#opt-show13c").checked, onZoom }));
  } else {
    $("#res-chart").innerHTML = '<p class="muted">No data points to plot.</p>';
  }
  $("#btn-zoom-reset").hidden = !state.zoom;

  const warnings = [...res.warnings, ...res.fits.flatMap((f) => f.warnings.map((w) => `${f.label}: ${w}`))];
  $("#res-warnings").innerHTML = warnings.map((w) => `<li class="${/PLACEHOLDER/.test(w) ? "tbd-li" : isNote(w) ? "info" : "warning"}">${esc(w)}</li>`).join("");
  const d = res.diagnostics;
  const checks = [
    d.residual_seasonal_p != null && `annual cycle in residuals: ${num(d.residual_seasonal_amplitude)}‰ (p ${pval(d.residual_seasonal_p)})`,
    d.d13C_seasonal_p != null && `annual cycle in δ¹³C: ${num(d.d13C_seasonal_amplitude)}‰ (p ${pval(d.d13C_seasonal_p)})`,
    d.d13C_d15N_spearman != null && `δ¹³C–δ¹⁵N correlation ρ = ${num(d.d13C_d15N_spearman)}`,
  ].filter(Boolean);
  const carbon = d.d13C_weaning_shift == null ? "" :
    `<p class="muted small">δ¹³C after weaning minus before ${help("carbon")}: ${d.d13C_weaning_shift > 0 ? "+" : ""}${num(d.d13C_weaning_shift)}‰</p>`;
  $("#res-diagnostics").innerHTML = (checks.length ? `<p class="muted small">Seasonality checks ${help("seasonal")}: ${checks.join(" · ")}</p>` : "") + carbon;

  const averageRow = hasAverage ? [{ model: "average", label: "Model average", converged: true, isAverage: true, ...res.model_average }] : [];
  table($("#fit-table"), [
    { label: "Model", render: (f) => `${swatch(f.model)}${esc(f.label)}${f.model === res.best_model ? ' <span class="pill best">best</span>' : ""}` },
    ...MILESTONES.map((k) => ({ label: capital(k), cls: "num", render: (f) => (f[k] ? `${num(f[k].estimate, 1)}<br><small>${ci(f[k])}</small>` : "—") })),
    { label: "Nursing δ¹⁵N", cls: "num", render: (f) => num(f.nursing_d15N) },
    { label: "Adult δ¹⁵N", cls: "num", render: (f) => num(f.adult_d15N) },
    { label: "Drop (‰)", cls: "num", render: (f) => num(f.drop_permil) },
    { label: "Enrichment vs ♀ (‰)", title: "Nursing δ15N minus adult-female baseline", cls: "num", render: (f) => num(f.enrichment_permil) },
    { label: "RMSE", cls: "num", render: (f) => num(f.rmse, 3) },
    { label: "ΔAICc", cls: "num", render: (f) => num(f.delta_aicc) },
    { label: "Weight", cls: "num", render: (f) => num(f.akaike_weight) },
    { label: "Notes", render: fitNotes },
  ], [...res.fits, ...averageRow], (f) => (f.model === res.best_model ? "best-row" : f.isAverage ? "avg-row" : ""));
}

function summaryText(res, milestone) {
  const best = res.fits.find((f) => f.model === res.best_model);
  const age = best?.[milestone];
  const avg = res.model_average[milestone];
  if (!best) return "No model could be fitted to this specimen.";
  if (!age) return `Best-supported model: <strong>${esc(best.label)}</strong>, which does not report a ${milestone}${avg ? `; the model average is <strong>${num(avg.estimate, 1)} months</strong>` : ""}.`;
  const staged = best.model === "two_phase"
    ? ` Staged weaning: an intermediate plateau at ${num(best.extra.intermediate_d15N, 1)}‰ lasting about ${num(best.extra.supplementation_months, 1)} months (supplementary feeding while suckling).` : "";
  return `Best-supported model: <strong>${esc(best.label)}</strong>. Estimated weaning ${milestone}: <strong>${num(age.estimate, 1)} months</strong>${age.ci_low != null ? ` (95% interval ${ci(age)})` : ""}.
    ${avg ? `Averaged over all models: <strong>${num(avg.estimate, 1)} months</strong>${avg.ci_low != null ? ` (${ci(avg)})` : ""}.` : ""}
    Nursing δ¹⁵N ≈ ${num(best.nursing_d15N, 1)}‰, adult ≈ ${num(best.adult_d15N, 1)}‰ (drop ${num(best.drop_permil, 1)}‰)${best.enrichment_permil != null ? `; ${num(best.enrichment_permil, 1)}‰ above adult females` : ""}.${staged}
    ${res.growth_placeholder ? '<span class="tbd-inline">Illustrative only: placeholder age model.</span>' : ""}`;
}

function fitNotes(f) {
  if (f.isAverage) return '<small class="muted">weighted by Akaike weight</small>';
  if (!f.converged) return `<span class="warn-text">${esc(f.message)}</span>`;
  const notes = [];
  if (f.extra.intermediate_d15N != null) notes.push(`intermediate ${num(f.extra.intermediate_d15N, 1)}‰ for ${num(f.extra.supplementation_months, 1)} mo`);
  if (f.extra.seasonal_amplitude_permil != null) notes.push(`seasonal ±${num(f.extra.seasonal_amplitude_permil)}‰`);
  return `<small>${notes.join("; ") || "fitted"}</small>`;
}

function chooseSpecimen(id) {
  state.current = id;
  state.zoom = null;
  renderResults();
  $(`[data-specimen="${CSS.escape(id)}"]`)?.focus();
}

// ───────────── 4. compare ─────────────
function compareRequest() {
  const group_by = $$('input[name="group"]:checked').map((box) => box.value);
  return { estimates: state.estimates, group_by, milestone: $("#cmp-milestone").value, model: $("#cmp-model").value || null };
}

async function refreshCompare() {
  if (!state.estimates) return;
  const body = compareRequest();
  if (!body.group_by.length) return toast("Choose at least one grouping.");
  const { group_by, milestone, model } = body;
  try {
    const out = await api.aggregate(body);
    const groupName = (row) => group_by.map((g) => row[g] ?? "—").join(" · ");
    const rows = state.estimates.filter((e) => (model ? e.model === model : e.is_best));
    const means = Object.fromEntries(out.tests.groups.map((g) => [g.group, g]));
    forestChart($("#cmp-chart"), out.summary.map((s) => ({
      label: groupName(s),
      mean: means[groupName(s)]?.mean,
      lo: means[groupName(s)]?.ci_low,
      hi: means[groupName(s)]?.ci_high,
      values: rows.filter((r) => groupName(r) === groupName(s) && r[milestone] != null)
        .map((r) => ({ v: r[milestone], label: `${esc(r.specimen_id)}: ${num(r[milestone], 1)} mo (${r.model})` })),
    })), `Weaning ${milestone} (months): random-effects mean ± 95% CI, dots = specimens`);
    table($("#cmp-table"), [
      ...group_by.map((g) => ({ label: capital(g), key: g })),
      { label: "Estimates", key: "model" },
      { label: "n", key: "n", cls: "num" },
      { label: "Mean", cls: "num", render: (r) => num(r.mean, 1) },
      { label: "SD", cls: "num", render: (r) => num(r.sd, 1) },
      { label: "Median", cls: "num", render: (r) => num(r.median, 1) },
      { label: "Range", cls: "num", render: (r) => `${num(r.min, 1)}–${num(r.max, 1)}` },
      { label: "95% CI (t)", cls: "num", render: (r) => (r.ci95_low != null ? `${num(r.ci95_low, 1)}–${num(r.ci95_high, 1)}` : "—") },
    ], out.summary);
    renderTests(out.tests);
    table($("#dis-table"), [
      { label: "Specimen", key: "specimen_id" },
      { label: "Site", key: "site" },
      { label: "Species", key: "species" },
      ...state.options.models.map((m) => ({ label: esc(m), cls: "num", render: (r) => num(r[m], 1) })),
      { label: "Range (months)", cls: "num", render: (r) => `<strong>${num(r.range, 1)}</strong>` },
    ], out.disagreement);
    renderValidation(out.validation);
  } catch (e) {
    toast(e.message);
  }
}

const range = (lo, hi) => `${num(lo, 1)}–${num(hi, 1)}`;

function renderTests(t) {
  $("#tests-body").innerHTML = `${t.q_p != null
    ? `<p class="summary">Do groups differ at all? Between-group Q = ${num(t.q_between)} on ${t.q_df} df, <strong>p = ${pval(t.q_p)}</strong>;
       permutation test p = ${pval(t.permutation_p)}. ${t.q_p < 0.05 ? "There is evidence that weaning ages differ between groups." : "No clear evidence that weaning ages differ between groups."}</p>`
    : '<p class="muted">At least two groups are needed for a comparison.</p>'}
    <div class="grid-2"><div class="table-wrap"><table id="t-groups"></table></div><div class="table-wrap"><table id="t-pairs"></table></div></div>
    ${t.notes.map((n) => `<p class="muted small">${esc(n)}</p>`).join("")}`;
  table($("#t-groups"), [
    { label: "Group", key: "group" }, { label: "n", key: "n", cls: "num" },
    { label: "Mean", cls: "num", render: (g) => num(g.mean, 1) },
    { label: "95% CI", cls: "num", render: (g) => range(g.ci_low, g.ci_high) },
    { label: "τ", cls: "num", render: (g) => num(g.tau) },
  ], t.groups);
  table($("#t-pairs"), [
    { label: "Pair", render: (p) => `${esc(p.group_a)} − ${esc(p.group_b)}` },
    { label: "Difference", cls: "num", render: (p) => num(p.difference, 1) },
    { label: "SE", cls: "num", render: (p) => num(p.se) },
    { label: "p", cls: "num", render: (p) => pval(p.p) },
    { label: "p (Holm)", cls: "num", render: (p) => `<span class="${p.p_holm < 0.05 ? "sig" : ""}">${pval(p.p_holm)}</span>` },
  ], t.pairwise);

  const b = t.bayes;
  if (!b) return ($("#bayes-body").innerHTML = '<p class="muted">Needs at least three specimens.</p>');
  $("#bayes-body").innerHTML = `<p class="muted small">Shared between-animal SD τ = ${num(b.tau_mean)} months (95% CrI ${num(b.tau_ci_low)}–${num(b.tau_ci_high)}) ·
      max R̂ ${num(b.rhat_max, 3)} ${help("rhat")} · ${b.draws} posterior draws${b.rhat_max > 1.05 ? ' · <span class="warn-text">not fully converged</span>' : ""}</p>
    <div class="grid-2"><div class="table-wrap"><table id="b-groups"></table></div><div class="table-wrap"><table id="b-pairs"></table></div></div>
    <details><summary>Specimen estimates after partial pooling</summary><div class="table-wrap"><table id="b-specimens"></table></div></details>`;
  table($("#b-groups"), [
    { label: "Group", key: "group" },
    { label: "Posterior mean", cls: "num", render: (g) => num(g.mean, 1) },
    { label: "95% CrI", cls: "num", render: (g) => range(g.ci_low, g.ci_high) },
  ], b.groups);
  table($("#b-pairs"), [
    { label: "Comparison", render: (p) => `${esc(p.group_a)} vs ${esc(p.group_b)}` },
    { label: "Probability the first weaned earlier", cls: "num", render: (p) => `${Math.round(p.prob_a_earlier * 100)}%` },
    { label: "Difference (95% CrI)", cls: "num", render: (p) => `${num(p.difference_mean, 1)} (${range(p.difference_ci_low, p.difference_ci_high)})` },
  ], b.pairs);
  table($("#b-specimens"), [
    { label: "Specimen", key: "specimen_id" }, { label: "Group", key: "group" },
    { label: "Own estimate", cls: "num", render: (s) => num(s.observed, 1) },
    { label: "Pooled estimate", cls: "num", render: (s) => num(s.shrunk, 1) },
    { label: "95% CrI", cls: "num", render: (s) => range(s.ci_low, s.ci_high) },
  ], b.specimens);
}

function renderValidation(rows) {
  if (!rows.length) {
    $("#val-body").innerHTML = `<div class="tbd tbd-block">${tbdBadge} No known-age reference animals or published estimates in this dataset. Add a
      <code>known_weaning_age_months</code> column for modern reference animals, or a <code>published_weaning_age_months</code> column to
      compare with published estimates (e.g. WEAN or visual readings), to see bias, MAE, RMSE and interval coverage for each model here.</div>`;
    return;
  }
  $("#val-body").innerHTML = '<div class="table-wrap"><table id="val-table"></table></div>';
  table($("#val-table"), [
    { label: "Reference", key: "reference" }, { label: "Model", key: "model" }, { label: "n", key: "n", cls: "num" },
    { label: "Bias", cls: "num", render: (r) => num(r.bias) },
    { label: "MAE", cls: "num", render: (r) => num(r.mae) },
    { label: "RMSE", cls: "num", render: (r) => num(r.rmse) },
    { label: "Pearson r", cls: "num", render: (r) => num(r.pearson_r) },
    { label: "95% interval coverage", cls: "num", render: (r) => (r.ci_coverage != null ? `${Math.round(r.ci_coverage * 100)}%` : "—") },
  ], rows);
}

// ───────────── saving, opening and the report ─────────────
function project() {
  return {
    format: "weanage-project", format_version: 1, app_version: state.config.version, saved_at: new Date().toISOString(),
    samples: state.samples, settings: settings(), results: state.results, estimates: state.estimates,
    analysis_options: state.options, current: state.current, plan: state.plan,
  };
}

let saveTimer = null;
function autosave() {
  // Kept in this browser so work survives a refresh; results are dropped if there is not enough room.
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      localStorage.setItem("weanage-autosave", JSON.stringify(project()));
    } catch {
      try { localStorage.setItem("weanage-autosave", JSON.stringify({ ...project(), results: null, estimates: null })); } catch {}
    }
  }, 600);
}

function openProject(p) {
  if (p.format !== "weanage-project" || !Array.isArray(p.samples)) throw new Error("This file is not a WeanAge project.");
  applySettings(p.settings || {});
  Object.assign(state, { samples: p.samples, options: p.analysis_options, plan: p.plan || null });
  state.visible = new Set([...(state.options?.models || []), "average"]);
  recheck(true).then(() => {
    if (p.results && p.analysis_options) {
      Object.assign(state, { results: p.results, estimates: p.estimates, current: p.current || p.results[0]?.specimen_id });
      enableResults(true);
      renderResults();
    }
    if (state.plan) renderPlan(state);
  });
}

function offerRestore() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("weanage-autosave")); } catch {}
  if (!saved?.samples?.length) return;
  $("#restore-when").textContent = `${saved.samples.length} samples, ${new Date(saved.saved_at).toLocaleString()}`;
  $("#restore-banner").hidden = false;
  $("#btn-restore").onclick = () => { openProject(saved); $("#restore-banner").hidden = true; };
  $("#btn-discard").onclick = () => { localStorage.removeItem("weanage-autosave"); $("#restore-banner").hidden = true; };
}

async function makeReport() {
  try {
    let compare = null;
    if (new Set(state.results.map((r) => `${r.site}:${r.species}`)).size > 1) {
      const body = compareRequest();
      if (!body.group_by.length) body.group_by = ["site", "species"];
      compare = await api.aggregate(body);
    }
    const html = buildReport({ config: state.config, state, settings: settings(), compare });
    download(`weanage_report_${new Date().toISOString().slice(0, 10)}.html`, new Blob([html], { type: "text/html" }));
    toast("Report downloaded. Open it in a browser and print to PDF if needed.", "ok");
  } catch (e) {
    toast(e.message);
  }
}

// ───────────── buttons and inputs ─────────────
function bind() {
  const on = (selector, event, handler) => $(selector).addEventListener(event, handler);
  for (const b of $$(".step")) b.addEventListener("click", () => show(b.dataset.view));
  on("#btn-to-settings", "click", () => show("settings"));

  const zone = $("#dropzone");
  on("#csv-input", "change", (e) => e.target.files[0] && loadFile(e.target.files[0]));
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("over"); e.dataTransfer.files[0] && loadFile(e.dataTransfer.files[0]); });
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#csv-input").click(); } });
  $("#btn-template").href = api.templateUrl;
  on("#btn-example", "click", async () => {
    try {
      setReport(await api.example());
      toast("Loaded SYNTHETIC example data (simulated, not real measurements).", "ok");
    } catch (e) {
      toast(e.message);
    }
  });
  on("#btn-clear", "click", () => {
    if (!state.samples.length || confirm("Remove all loaded samples?")) setReport({ samples: [], issues: [], specimens: [] });
  });
  on("#manual-form", "submit", addSampleByHand);
  on("#sample-table", "click", (e) => {
    const index = e.target.closest("[data-remove]")?.dataset.remove;
    if (index != null) { state.samples.splice(Number(index), 1); recheck(); }
  });

  bindGrowthEditor(state, { refreshConfig, onChange: autosave });
  on("#baseline-list", "input", (e) => {
    const row = e.target.closest(".baseline-row");
    const mean = row.querySelector(".bl-mean").value;
    if (mean === "") delete state.baselines[row.dataset.key];
    else state.baselines[row.dataset.key] = { mean: Number(mean), sd: Number(row.querySelector(".bl-sd").value) || 0.5 };
    autosave();
  });
  on("#view-settings", "change", autosave);
  on("#btn-run", "click", runAnalysis);

  on("#result-list", "click", (e) => { const b = e.target.closest("[data-specimen]"); if (b) chooseSpecimen(b.dataset.specimen); });
  on("#result-list", "keydown", (e) => { // arrow keys move through the specimen list
    const ids = state.results.map((r) => r.specimen_id);
    const moves = { ArrowDown: 1, ArrowUp: -1 };
    let i = ids.indexOf(state.current);
    if (e.key in moves) i = Math.min(Math.max(i + moves[e.key], 0), ids.length - 1);
    else if (e.key === "Home") i = 0;
    else if (e.key === "End") i = ids.length - 1;
    else return;
    e.preventDefault();
    chooseSpecimen(ids[i]);
  });
  on("#curve-toggles", "change", (e) => {
    if (e.target.checked) state.visible.add(e.target.dataset.model);
    else state.visible.delete(e.target.dataset.model);
    renderResults();
  });
  on("#opt-show13c", "change", renderResults);
  on("#btn-zoom-reset", "click", () => { state.zoom = null; renderResults(); });
  on("#btn-export-csv", "click", () => download("weanage_estimates.csv", new Blob([toCsv(state.estimates)], { type: "text/csv" })));
  on("#btn-export-json", "click", () => download("weanage_results.json", new Blob([JSON.stringify({ options: state.options, results: state.results }, null, 2)])));
  on("#btn-export-svg", "click", () => {
    // Redraw the chart in light colours on white, which suits papers and slides.
    const res = state.results.find((r) => r.specimen_id === state.current) || state.results[0];
    if (!res?.points.length) return;
    const options = { visible: state.visible, milestone: state.options.reported_milestone, xRange: state.zoom, showD13C: $("#opt-show13c").checked, palette: "light" };
    download(`${res.specimen_id}_weaning_curve.svg`, new Blob([offscreen((box) => curveChart(box, curveOptions(res, options)))], { type: "image/svg+xml" }));
  });
  for (const input of $$('input[name="group"], #cmp-milestone, #cmp-model')) input.addEventListener("change", refreshCompare);

  on("#btn-save", "click", () => download(`weanage_project_${new Date().toISOString().slice(0, 10)}.weanage.json`, new Blob([JSON.stringify(project(), null, 1)])));
  on("#project-input", "change", async (e) => {
    try {
      openProject(JSON.parse(await e.target.files[0].text()));
      toast(`Opened project ${e.target.files[0].name}`, "ok");
    } catch (err) {
      toast(err.message);
    }
  });
  on("#btn-report", "click", makeReport);
  on("#btn-help", "click", () => startTour(show));
  on("#btn-theme", "click", () => setLook("theme", document.documentElement.dataset.theme === "light" ? "dark" : "light"));
  on("#btn-text", "click", () => setLook("text", document.documentElement.dataset.text === "large" ? "normal" : "large"));
}

// ───────────── dark/light colours and text size ─────────────
// `key` is "theme" (dark/light) or "text" (normal/large). The choice is remembered.
function setLook(key, value) {
  document.documentElement.dataset[key] = value;
  try { localStorage.setItem(`weanage-${key}`, value); } catch {}
  showLook();
  if (state.results?.length) renderResults(); // charts pick their colours when drawn
  if (state.plan) renderPlan(state);
}

function showLook() {
  const light = document.documentElement.dataset.theme === "light";
  const large = document.documentElement.dataset.text === "large";
  $("#btn-theme").textContent = light ? "Dark mode" : "Light mode";
  $("#btn-theme").setAttribute("aria-pressed", String(light));
  $("#btn-text").textContent = large ? "Normal text" : "Larger text";
  $("#btn-text").setAttribute("aria-pressed", String(large));
}

// ───────────── start ─────────────
async function init() {
  try {
    state.config = await api.config();
  } catch (e) {
    return toast(`Could not reach the WeanAge backend: ${e.message}`);
  }
  initSettings();
  initPlanner(state);
  renderTbd();
  for (const slot of $$("[data-helpslot]")) slot.innerHTML = help(slot.dataset.helpslot);
  initGlossary();
  bind();
  showLook();
  renderData();
  offerRestore();
  if (!tourSeen()) startTour(show);
}

init();
