// The main page: holds the app's state and draws each of the five views.
import { initAbout } from "./about.js";
import { initBonePlanner, renderBonePlan } from "./bone_planner.js";
import { applyBoneSettings, boneSettings, initBone, loadBoneExample, loadBoneFile, renderBoneData, renderBoneResults, renderTurnover, setBoneReport } from "./bone.js";
import { dental } from "./dental.js";
import { enamel } from "./enamel.js";
import { killoff } from "./killoff.js";
import { leh } from "./leh.js";
import { lifetable } from "./lifetable.js";
import { mixing } from "./mixing.js";
import { mobility } from "./mobility.js";
import { api, inBrowser, onEngineStatus } from "./api.js";
import { curveChart, curveOptions, forestChart, lineChart } from "./chart.js";
import { bindGrowthEditor, renderGrowthList } from "./growth.js";
import { initGlossary, initHelpMenu, startTour, tourSeen } from "./help.js";
import { initPlanner, renderPlan } from "./planner.js";
import { buildReport, offscreen } from "./report.js";
import { $, $$, ageNum, ageText, ageValue, ci, color, download, esc, getAgeUnit, help, labelScrollBoxes, MILESTONES, num, plural, progressBar, pIs, percent, pval, readout, renderIssues, renderReady, renderWarnings, SAID_IN_SUMMARY, setAgeUnit, swatch, table, tbdBadge, toast, toCsv, toUnit, unitShort, unitWord } from "./util.js";

const state = {
  config: null, // settings and lists sent by the server
  mode: "tooth", // the calculation shown: "tooth", "bone", or one of CALCS (their data and results are in state.bone, state.enamel...)
  chosen: [], // the calculations ticked on the Data page
  file: null, // the last file dropped, and which calculations can use it
  detected: null,
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

// The one-table calculations (see calc.js)
const CALCS = { enamel, killoff, mixing, dental, leh, lifetable, mobility };
const oneTable = () => CALCS[state.mode];

// Every calculation offered on the Data page, in the order shown.
const CALC_INFO = [
  { name: "tooth", group: "Weaning", label: "Tooth calculation", blurb: "δ¹⁵N in slices along a tooth: one individual's own weaning curve." },
  { name: "bone", group: "Weaning", label: "Bone calculation", blurb: "Bone δ¹⁵N of many young individuals who died at different ages, after WARN." },
  { name: "dental", group: "People", label: "Dental age", blurb: "Children's age at death from tooth formation stages (Moorrees et al. 1963)." },
  { name: "leh", group: "People", label: "Enamel hypoplasia timing", blurb: "When enamel defects formed, set against weaning and stress in the dentine." },
  { name: "lifetable", group: "People", label: "Life tables", blurb: "Deaths, survivorship and life expectancy from skeletal ages at death." },
  { name: "mobility", group: "People", label: "Mobility (bulk enamel)", blurb: "Enamel δ¹⁸O as drinking water, and ⁸⁷Sr/⁸⁶Sr against the local range." },
  { name: "mixing", group: "Diet", label: "Diet mixing", blurb: "Bone collagen δ¹³C, δ¹⁵N (and δ³⁴S): the share of each food group in the diet." },
  { name: "enamel", group: "Animals", label: "Enamel: season and rumen", blurb: "δ¹⁸O, δ¹³C and ⁸⁷Sr/⁸⁶Sr along a cattle molar: season of birth, rumen, diet and moves." },
  { name: "killoff", group: "Animals", label: "Kill-off profiles", blurb: "Aged mandibles: at what ages a herd's animals were killed, after Payne (1973)." },
];
const calcLabel = (name) => CALC_INFO.find((c) => c.name === name).label;

// Switching views
// The bone calculation and CALCS have their own pages for these views.
const OWN_VIEWS = { bone: ["settings", "results", "plan"], ...Object.fromEntries(Object.keys(CALCS).map((name) => [name, ["settings", "results"]])) };

function show(view) {
  for (const b of $$(".step")) {
    const isThis = b.dataset.view === view;
    b.classList.toggle("active", isThis);
    if (isThis) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  const own = OWN_VIEWS[state.mode]?.includes(view) ? state.mode : null;
  const bone = own === "bone";
  for (const v of $$(".view")) v.classList.toggle("active", v.id === `view-${own ? `${own}-${view}` : view}`);
  if (view === "settings" && !oneTable()) {
    // The collagen QC limits are shared, so their card moves to whichever settings page is open.
    $(bone ? "#qc-bone-home" : "#qc-home").append($("#qc-card"));
    if (bone) renderTurnover();
    renderGrowthList(state);
    renderBaselines();
  }
  if (view === "compare") {
    renderGroupChoices();
    refreshCompare();
  }
  window.scrollTo({ top: 0 });
}

function enableResults() {
  const tooth = state.mode === "tooth";
  $('.step[data-view="settings"]').disabled = !state.chosen.length;
  $('.step[data-view="results"]').disabled = !(oneTable() ? oneTable().hasResults() : { tooth: state.results, bone: state.bone.results }[state.mode]);
  for (const b of $$('.step[data-view="compare"], #btn-report')) {
    b.disabled = !tooth || !state.results;
    b.title = tooth ? "" : "Tooth calculation only";
  }
  const plan = $('.step[data-view="plan"]');
  plan.disabled = Boolean(oneTable());
  plan.title = oneTable() ? "Tooth and bone calculations only" : "";
}

/** Show one calculation; each keeps its own data and results. */
function setMode(mode, save = true) {
  state.mode = mode;
  const shown = state.chosen.includes(mode);
  for (const node of $$("[data-mode]")) node.hidden = !shown || node.dataset.mode !== mode;
  $("#btn-template").href = oneTable() ? api.calcTemplateUrl(mode) : { tooth: api.templateUrl, bone: api.boneTemplateUrl }[mode];
  $("#btn-template").textContent = `Download blank template: ${calcLabel(mode)}`;
  $("#btn-template").hidden = !shown;
  if (shown) renderData();
  else renderReady("");
  enableResults();
  renderCalcList();
  renderCalcTabs();
  if (save) autosave(); // not on start-up, which would overwrite the session waiting to be restored
}

// Choosing calculations
/** The Data page's list of calculations: what each needs, and whether the loaded file can feed it. */
function renderCalcList() {
  const found = state.detected?.calculations;
  let group = null;
  $("#calc-list").innerHTML = CALC_INFO.map((c) => {
    const d = found?.[c.name];
    const chosen = state.chosen.includes(c.name);
    const usable = !found || d.rows > 0;
    const status = !found ? "" : d.rows
      ? `<small class="calc-status ok">${plural(d.rows, "row")} can be used${d.row_errors ? ` · ${plural(d.row_errors, "problem")}` : ""}</small>`
      : `<small class="calc-status">Not with this file: ${esc(d.problem)}</small>`;
    const heading = c.group !== group ? `<p class="calc-group">${esc((group = c.group))}</p>` : "";
    return `${heading}<label class="calc-option${usable ? "" : " unusable"}">
      <input type="checkbox" name="calc" value="${c.name}" ${chosen ? "checked" : ""} ${usable || chosen ? "" : "disabled"}>
      <span><strong>${esc(c.label)}</strong><small>${c.blurb}</small>${status}</span></label>`;
  }).join("");
  const usableCount = found ? Object.values(found).filter((d) => d.rows).length : 0;
  $("#calc-hint").textContent = !found
    ? "Load a file to see which calculations it can be used for, or tick one to type data in or load its example."
    : usableCount ? "Tick the calculations to run with this file. Each keeps its own settings and results."
      : "No calculation can use this file: check the column names under Columns, template and more.";
}

/** Above every page when more than one calculation is ticked: which one is shown. */
function renderCalcTabs() {
  const nav = $("#calc-tabs");
  nav.hidden = state.chosen.length < 2;
  nav.innerHTML = `<span class="muted small">Showing:</span>${state.chosen.map((name) =>
    `<button type="button" class="secondary calc-tab" data-calc="${name}" aria-pressed="${name === state.mode}">${esc(calcLabel(name))}</button>`).join("")}`;
}

function switchCalc(name) {
  const view = $(".step.active")?.dataset.view || "data";
  setMode(name);
  const open = { results: !$('.step[data-view="results"]').disabled, compare: name === "tooth" && state.results,
    plan: !oneTable(), settings: true, data: true }[view];
  show(open ? view : "data");
}

async function loadInto(name, file) {
  if (name === "tooth") {
    try {
      setReport(await api.uploadFile(file));
    } catch (e) {
      toast(e.message);
    }
  } else if (name === "bone") await loadBoneFile(file);
  else await CALCS[name].loadFile(file);
}

async function toggleCalc(name, on) {
  state.chosen = on ? [...new Set([...state.chosen, name])] : state.chosen.filter((c) => c !== name);
  const next = on ? name : state.mode === name ? state.chosen.at(-1) || name : state.mode;
  setMode(next);
  if (on && state.detected?.calculations[name]?.rows) await loadInto(name, state.file);
}

async function loadExample(value) {
  const [name, example] = value.split(":");
  Object.assign(state, { file: null, detected: null });
  $("#file-status").hidden = true;
  if (!state.chosen.includes(name)) state.chosen.push(name);
  setMode(name);
  if (name === "bone") return loadBoneExample(example);
  if (CALCS[name]) return CALCS[name].loadExample(example);
  try {
    const report = await api.example(example);
    setReport(report);
    toast(report.message, "ok");
  } catch (e) {
    toast(e.message);
  }
}

function fillExampleChoice() {
  const lists = { tooth: state.config.examples, bone: state.config.bone_examples,
    ...Object.fromEntries(Object.keys(CALCS).map((name) => [name, state.config.calculations[name].examples])) };
  $("#example-choice").innerHTML = CALC_INFO.map((c) => `<optgroup label="${esc(c.label)}">${lists[c.name]
    .map((e) => `<option value="${c.name}:${esc(e.name)}">${esc(e.label)}</option>`).join("")}</optgroup>`).join("");
}

// Highlight every setting that is still a placeholder (TBD-LAB).
function renderTbd() {
  const items = state.config.tbd;
  const ids = new Set(items.map((i) => i.id));
  $("#tbd-banner").hidden = !items.length;
  $("#tbd-count").textContent = `${plural(items.length, "placeholder value")} ${items.length === 1 ? "is" : "are"}`;
  $("#tbd-list").innerHTML = items.map((i) => `<li><strong>${esc(i.area)}:</strong> ${esc(i.label)} — ${esc(i.note)} <code>${esc(i.file)}</code></li>`).join("");
  for (const node of $$("[data-tbd]")) {
    const on = ids.has(node.dataset.tbd);
    const title = node.matches("label") ? node : node.querySelector("h2, h3");
    node.classList.toggle("tbd", on);
    title.querySelector(".tbd-badge")?.remove();
    if (on) title.insertAdjacentHTML("beforeend", ` ${tbdBadge}`);
  }
}

async function refreshConfig() {
  state.config = await api.config();
  renderTbd();
}

// 1. data
function setReport(report, keepResults = false) {
  state.report = report;
  state.samples = report.samples;
  if (!keepResults) {
    state.results = state.estimates = null;
    enableResults();
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
  if (state.mode === "bone") return renderBoneData(); // the Data page is showing another calculation
  if (oneTable()) {
    $("#specimens-card").hidden = true; // the tooth calculation's table
    return oneTable().renderData();
  }
  renderIssues(state.report ? state.report.issues : []);
  $("#specimens-card").hidden = !state.samples.length || state.mode === "bone";
  $("#sample-count").textContent = `· ${state.samples.length} samples`;
  const specimens = new Set(state.samples.map((s) => s.individual_id || s.specimen_id)).size;
  $("#sb-data").textContent = state.samples.length ? `${state.samples.length} samples · ${specimens} specimens` : "No data loaded";
  renderReady(state.samples.length && `${plural(state.samples.length, "sample")} from ${plural(specimens, "specimen")} loaded.`);
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
    { label: "<span class='sr-only'>Remove</span>", render: (s, i) => `<button class="ghost tiny" data-remove="${i}" aria-label="Remove sample at ${esc(s.position_mm)} mm from ${esc(s.specimen_id)}">Remove</button>` },
  ], state.samples);
}

/** A dropped file: find which calculations can use it, and load it into the ticked ones that can. */
async function loadFile(file) {
  let detected;
  try {
    detected = await api.detect(file);
  } catch (e) {
    return toast(e.message);
  }
  Object.assign(state, { file, detected });
  const found = detected.calculations;
  const usable = CALC_INFO.filter((c) => found[c.name].rows).map((c) => c.name);
  // With nothing ticked yet and only one calculation that fits, tick that one.
  if (!state.chosen.some((n) => found[n].rows) && usable.length === 1) state.chosen.push(usable[0]);
  $("#file-status").hidden = false;
  $("#file-status").textContent = `${detected.filename}: ${plural(detected.n_rows, "row")}, ${plural(detected.columns.length, "column")}. `
    + (usable.length ? `It can be used by ${plural(usable.length, "calculation")} (below).` : "No calculation can use it.");
  const targets = state.chosen.filter((n) => found[n].rows);
  setMode(targets.includes(state.mode) ? state.mode : targets[0] || state.mode);
  for (const name of targets) {
    state.mode = name; // each loader draws its own Data page
    await loadInto(name, file);
  }
  setMode(targets.includes(state.mode) ? state.mode : targets[0] || state.mode);
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

// 2. settings
// Which form control holds each setting, and what kind of value it holds.
const FIELDS = {
  reported_milestone: ["#opt-milestone", "text"],
  analytical_sd_permil: ["#opt-sd", "number"],
  min_weaning_drop_permil: ["#opt-mindrop", "number"],
  max_plausible_drop_permil: ["#opt-maxdrop", "number"],
  monte_carlo_draws: ["#opt-draws", "number"],
  uncertainty: ["#opt-uncertainty", "text"],
  bootstrap_draws: ["#opt-boot", "number"],
  time_averaging: ["#opt-timeavg", "tick"],
  increment_width_mm: ["#opt-incwidth", "number"],
  growth_layer_offset_mm: ["#opt-layeroffset", "number"],
  inner_dentine_weight: ["#opt-innerweight", "number"],
  seasonal_term: ["#opt-seasonal", "tick"],
  season_period_months: ["#opt-period", "number"],
  stress_d15N_permil: ["#opt-stressn", "number"],
  stress_d13C_permil: ["#opt-stressc", "number"],
  d34S_min_shift_permil: ["#opt-sshift", "number"],
  nursing_enrichment_d15N: ["#opt-enrich-n", "number"],
  nursing_enrichment_d15N_sd: ["#opt-enrich-n-sd", "number"],
  nursing_enrichment_d13C: ["#opt-enrich-c", "number"],
  nursing_enrichment_d13C_sd: ["#opt-enrich-c-sd", "number"],
  elbow_normalise: ["#opt-elbownorm", "tick"],
  constrain_adult_plateau: ["#opt-constrain", "tick"],
};

function initSettings() {
  $("#model-options").innerHTML = state.config.models
    .map((m) => `<label class="check model-opt">
        <input type="checkbox" name="model" value="${m.name}">${swatch(m.name)}<span>${esc(m.label)}</span>
      </label>`)
    .join("");
  $("#model-notes").innerHTML = `<h3>About the models</h3><dl class="terms small">${state.config.models
    .map((m) => `<dt>${esc(m.label)}</dt><dd>${esc(m.description)}</dd>`).join("")}</dl>`;
  for (const m of state.config.models) $("#cmp-model").insertAdjacentHTML("beforeend", `<option value="${m.name}">${esc(m.label)}</option>`);
  // Published QC limits: choosing one fills in the boxes, which can still be edited.
  const presets = state.config.qc_presets || {};
  for (const [key, p] of Object.entries(presets)) $("#qc-preset").insertAdjacentHTML("beforeend", `<option value="${key}">${esc(p.label)}</option>`);
  $("#qc-preset").addEventListener("change", (e) => {
    const { label, ...limits } = presets[e.target.value] || {};
    if (label) applySettings({ qc: limits });
  });
  for (const input of $$("#qc-card input")) input.addEventListener("input", matchQcPreset);
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
  if ("weaning_food" in o) {
    const f = o.weaning_food || {};
    [["#food-name", f.name], ["#food-d15N", f.d15N], ["#food-d15N-sd", f.d15N_sd], ["#food-d13C", f.d13C], ["#food-d13C-sd", f.d13C_sd]]
      .forEach(([id, v]) => { $(id).value = v ?? ""; });
  }
  matchQcPreset();
}

/** Show the published set of limits the boxes match, or "Custom". */
function matchQcPreset() {
  const presets = state.config.qc_presets || {};
  const match = Object.entries(presets).find(([, { label, ...limits }]) =>
    Object.entries(limits).every(([key, value]) => Number($(`#qc-${key}`)?.value) === value));
  $("#qc-preset").value = match ? match[0] : "";
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
  const food = (id) => ($(id).value === "" ? null : Number($(id).value));
  out.weaning_food = $("#food-name").value.trim() && food("#food-d15N") != null ? {
    name: $("#food-name").value.trim(), d15N: food("#food-d15N"), d15N_sd: food("#food-d15N-sd") ?? 0.5,
    d13C: food("#food-d13C"), d13C_sd: food("#food-d13C-sd") ?? 0.5 } : null;
  return out;
}

/** The share of breast milk at each increment, when an adult-female baseline was given. */
function renderMilkShare(res) {
  const m = res.milk_share;
  $("#milk-chart").hidden = !m?.points.length;
  if (!m) {
    $("#milk-summary").innerHTML = `<p class="muted">Enter the adult-female δ¹⁵N for ${esc(res.site)} (${esc(res.species)}) under
      Settings → Advanced to see how much of the diet was breast milk at each increment.</p>`;
    return;
  }
  $("#milk-summary").innerHTML = `<p>${m.below_half_age != null ? `Breast milk fell below half the diet at about <strong>${ageText(m.below_half_age)}</strong>.`
    : "Breast milk did not clearly fall below half the diet within the sampled ages."} Nursing enrichment δ¹⁵N ${num(m.enrichment_d15N, 1)} ± ${num(m.enrichment_d15N_sd, 1)}‰.</p>`;
  const line = (key, pick, name, colour, dash) => ({ name, color: colour, dash, markers: key === "estimate",
    points: m.points.map((p) => ({ x: toUnit(p.age_months), y: 100 * pick(p)[key] })) });
  const series = [line("estimate", (p) => p.milk, "Breast milk", color("logistic"), null),
    line("ci_low", (p) => p.milk, "95% lower", color("logistic"), "3 3"), line("ci_high", (p) => p.milk, "95% upper", color("logistic"), "3 3")];
  if (m.other_food) series.push(line("estimate", (p) => p.other, m.other_food, color("piecewise"), "9 4"));
  lineChart($("#milk-chart"), series,
    { xLabel: `Age (${unitWord()})`, yLabel: "Share of the diet (%)", title: `Breast-milk share at each increment: ${res.specimen_id}`, yMin: 0 });
}

function renderBaselines() {
  const keys = [...new Set(state.samples.map((s) => `${s.site}:${s.species}`))];
  $("#baseline-list").innerHTML = keys.length
    ? keys.map((key) => `<div class="baseline-row" data-key="${esc(key)}">
          <span class="key">${esc(key.replace(":", " · "))}</span>
          <label>Mean δ¹⁵N (‰)<input type="number" step="0.01" class="bl-mean" value="${state.baselines[key]?.mean ?? ""}" ></label>
          <label>SD (‰)<input type="number" step="0.01" min="0.01" class="bl-sd" value="${state.baselines[key]?.sd ?? ""}" placeholder="0.5"></label>
          <label>Mean δ¹³C (‰)<input type="number" step="0.01" class="bl-c" value="${state.baselines[key]?.d13C_mean ?? ""}"></label>
          <label>SD (‰)<input type="number" step="0.01" min="0.01" class="bl-c-sd" value="${state.baselines[key]?.d13C_sd ?? ""}" placeholder="0.5"></label>
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
    enableResults();
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

// 3. results
const isNote = (w) => /PLACEHOLDER|^Time averaging on|teeth .* combined/.test(w); // information, not a problem
const warningCount = (r) => r.warnings.filter((w) => !isNote(w)).length + r.fits.reduce((n, f) => n + f.warnings.length, 0);

function renderResults() {
  const milestone = state.options.reported_milestone;
  $("#result-list").innerHTML = state.results
    .map((r) => {
      const age = headline(r, milestone);
      const chosen = r.specimen_id === state.current;
      return `<li role="none"><button role="option" aria-selected="${chosen}" tabindex="${chosen ? 0 : -1}" data-specimen="${esc(r.specimen_id)}" class="${chosen ? "active" : ""}">
        <span><strong>${esc(r.specimen_id)}</strong><small>${esc(r.site)} · ${esc(r.species)} ${esc(r.tooth)}</small></span>
        <span><span class="age">${age ? `${ageValue(age)} ${unitShort()}` : "—"}</span>${warningCount(r) ? `<span class="warn-dot" title="${plural(warningCount(r), "warning")}" aria-label="${plural(warningCount(r), "warning")}">${warningCount(r)}</span>` : ""}</span>
      </button></li>`;
    })
    .join("");
  const res = state.results.find((r) => r.specimen_id === state.current) || state.results[0];
  if (!res) return;
  $("#res-title").textContent = res.specimen_id;
  $("#res-meta").innerHTML = `${esc(res.site)} · ${esc(res.species)} ${esc(res.tooth)}${res.period ? ` · ${esc(res.period)}` : ""} · age model: ${esc(res.growth_table)}`;

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
  [$("#zoom-from").value, $("#zoom-to").value] = state.zoom ? state.zoom.map((v) => +v.toFixed(2)) : ["", ""];

  const warnings = [...res.warnings.filter((w) => !SAID_IN_SUMMARY.test(w)), ...res.fits.flatMap((f) => f.warnings.map((w) => `${f.label}: ${w}`))];
  renderWarnings("#res-warnings-box", "#res-warnings-summary", "#res-warnings", warnings, (w) => (isNote(w) ? "info" : "warning"));
  const d = res.diagnostics;
  const checks = [
    d.residual_seasonal_p != null && `annual cycle in residuals: ${num(d.residual_seasonal_amplitude)}‰ (${pIs(d.residual_seasonal_p)})`,
    d.d13C_seasonal_p != null && `annual cycle in δ¹³C: ${num(d.d13C_seasonal_amplitude)}‰ (${pIs(d.d13C_seasonal_p)})`,
    d.d13C_d15N_spearman != null && `δ¹³C–δ¹⁵N correlation ρ = ${num(d.d13C_d15N_spearman)}`,
  ].filter(Boolean);
  const carbon = d.d13C_weaning_shift == null ? "" :
    `<p class="muted small">δ¹³C after weaning minus before ${help("carbon")}: ${d.d13C_weaning_shift > 0 ? "+" : ""}${num(d.d13C_weaning_shift)}‰</p>`;
  const stress = d.stress_episodes == null ? "" :
    `<p class="muted small">Stress episodes ${help("stress")}: ${d.stress_episodes.length
      ? d.stress_episodes.map((e) => `${num(e.from_age)}–${num(e.to_age)} months`).join(", ") : "none found"}${
      d.d15N_d13C_residual_spearman == null ? "" : ` (residual δ¹⁵N–δ¹³C ρ = ${num(d.d15N_d13C_residual_spearman)})`}</p>`;
  const sulphur = d.d34S_shifts == null ? "" :
    `<p class="muted small">δ³⁴S shifts ${help("sulphur")}: ${d.d34S_shifts.length
      ? d.d34S_shifts.map((s) => `${s.size > 0 ? "+" : ""}${num(s.size)}‰ at about ${num(s.position)} months`).join(", ") : "none found"}</p>`;
  $("#res-diagnostics").innerHTML = (checks.length ? `<p class="muted small">Seasonality checks ${help("seasonal")}: ${checks.join(" · ")}</p>` : "") + carbon + stress + sulphur;
  renderMilkShare(res);

  const averageRow = hasAverage ? [{ model: "average", label: "Model average", converged: true, isAverage: true, ...res.model_average }] : [];
  table($("#fit-table"), [
    { label: "Model", render: (f) => `${swatch(f.model)}${esc(f.label)}${f.model === res.best_model ? ' <span class="pill best">best</span>' : ""}` },
    ...MILESTONES.map((k) => ({ label: capital(k), cls: "num", render: (f) => (f[k] ? `${ageValue(f[k])}<br><small>${ci(f[k])}</small>` : "—") })),
    { label: "Nursing δ¹⁵N", cls: "num", render: (f) => num(f.nursing_d15N) },
    { label: "Adult δ¹⁵N", cls: "num", render: (f) => num(f.adult_d15N) },
    { label: "Drop (‰)", cls: "num", render: (f) => num(f.drop_permil) },
    { label: "Above adult females (‰)", title: "Nursing δ15N minus the adult-female baseline", cls: "num", render: (f) => num(f.enrichment_permil) },
    { label: "RMSE", cls: "num", render: (f) => num(f.rmse, 3) },
    { label: "ΔAICc", cls: "num", render: (f) => num(f.delta_aicc) },
    { label: "Weight", cls: "num", render: (f) => num(f.akaike_weight) },
    { label: "Notes", render: fitNotes },
  ], [...res.fits, ...averageRow], (f) => (f.model === res.best_model ? "best-row" : f.isAverage ? "avg-row" : ""));
}

const MILESTONE_NAME = { onset: "weaning onset", midpoint: "weaning midpoint", completion: "weaning completion" };

/** The age shown for a specimen: the best model's, or the model average when the best model gives none. */
const headline = (res, milestone) => res.fits.find((f) => f.model === res.best_model)?.[milestone] || res.model_average[milestone];

function summaryText(res, milestone) {
  const best = res.fits.find((f) => f.model === res.best_model);
  if (!best) return "<p>No model could be fitted to this specimen.</p>";
  const age = headline(res, milestone);
  if (!age) return `<p><strong>No ${MILESTONE_NAME[milestone]} reported.</strong> ${esc(best.withheld ? `${best.label}: ${best.withheld}.` : `${best.label} does not give one.`)}</p>`;
  const avg = res.model_average[milestone];
  const others = MILESTONES.filter((k) => k !== milestone && headline(res, k))
    .map((k) => `${capital(MILESTONE_NAME[k])} ${ageValue(headline(res, k))} ${unitShort()}`);
  const staged = best.model === "two_phase"
    ? ` Staged weaning: an intermediate plateau at ${num(best.extra.intermediate_d15N, 1)}‰ lasting about ${ageText(best.extra.supplementation_months)}.` : "";
  return `${readout(age, MILESTONE_NAME[milestone])}
    <p>${others.join(" · ")}${others.length ? ". " : ""}Best-supported model: <strong>${esc(best.label)}</strong>${!best[milestone] ? `, which gives no ${milestone}, so the age shown is the model average`
      : avg ? `; model average ${ageValue(avg)} ${unitShort()}` : ""}.
    Nursing δ¹⁵N ${num(best.nursing_d15N, 1)}‰, adult ${num(best.adult_d15N, 1)}‰ (drop ${num(best.drop_permil, 1)}‰)${best.enrichment_permil != null ? `, ${num(best.enrichment_permil, 1)}‰ above adult females` : ""}.${staged}
    ${res.growth_placeholder ? '<span class="tbd-inline">Illustrative only: placeholder age model.</span>' : ""}</p>`;
}

function fitNotes(f) {
  if (f.isAverage) return '<small class="muted">weighted by Akaike weight</small>';
  if (!f.converged || f.message) return `<span class="warn-text">${esc(f.message)}</span>`;
  const notes = [];
  if (f.extra.intermediate_d15N != null) notes.push(`intermediate ${num(f.extra.intermediate_d15N, 1)}‰ for ${ageText(f.extra.supplementation_months)}`);
  if (f.extra.seasonal_amplitude_permil != null) notes.push(`seasonal ±${num(f.extra.seasonal_amplitude_permil)}‰`);
  return `<small>${notes.join("; ") || "fitted"}</small>`;
}

function chooseSpecimen(id) {
  state.current = id;
  state.zoom = null;
  renderResults();
  $(`[data-specimen="${CSS.escape(id)}"]`)?.focus();
}

// 4. compare
/** Other columns of the tooth table (e.g. sex, burial type) can be grouped by too, if they vary. */
function renderGroupChoices() {
  const values = {};
  for (const r of state.results || []) for (const [k, v] of Object.entries(r.labels || {})) (values[k] ??= new Set()).add(v);
  const ticked = new Set($$('#group-extra input:checked').map((box) => box.value));
  $("#group-extra").innerHTML = Object.entries(values).filter(([, v]) => v.size > 1 && v.size <= 20)
    .map(([k]) => `<label class="check"><input type="checkbox" name="group" value="${esc(k)}" ${ticked.has(k) ? "checked" : ""}> ${esc(k)}</label>`).join("");
}

function compareRequest() {
  const group_by = $$('input[name="group"]:checked').map((box) => box.value);
  const body = { estimates: state.estimates, group_by, milestone: $("#cmp-milestone").value, model: $("#cmp-model").value || null,
    bayes: $("#cmp-bayes").value, transition_threshold: state.options.transition_threshold };
  if (body.bayes === "one_stage") {
    // The one-stage model needs each specimen's samples and logistic fit (but not the drawn curves).
    body.results = state.results.map((r) => ({ ...r, fits: r.fits.filter((f) => f.model === "logistic")
      .map(({ curve_age, curve_d15N, ...fit }) => fit) }));
  }
  return body;
}

async function refreshCompare() {
  if (!state.estimates) return;
  const body = compareRequest();
  if (!body.group_by.length) return toast("Choose at least one grouping.");
  const { group_by, milestone, model } = body;
  if (body.bayes === "one_stage") $("#bayes-body").innerHTML = '<p class="muted">Fitting the one-stage model (this can take a minute)…</p>';
  try {
    const out = await api.aggregate(body);
    const groupName = (row) => group_by.map((g) => row[g] ?? "—").join(" · ");
    const rows = state.estimates.filter((e) => (model ? e.model === model : e.is_best));
    const means = Object.fromEntries(out.tests.groups.map((g) => [g.group, g]));
    forestChart($("#cmp-chart"), out.summary.map((s) => ({
      label: groupName(s),
      mean: toUnit(means[groupName(s)]?.mean),
      lo: toUnit(means[groupName(s)]?.ci_low),
      hi: toUnit(means[groupName(s)]?.ci_high),
      values: rows.filter((r) => groupName(r) === groupName(s) && r[milestone] != null)
        .map((r) => ({ v: toUnit(r[milestone]), label: `${esc(r.specimen_id)}: ${ageText(r[milestone])} (${r.model})` })),
    })), `Weaning ${milestone} (${unitWord()}): random-effects mean ± 95% interval, dots = specimens`);
    table($("#cmp-table"), [
      ...group_by.map((g) => ({ label: capital(g), key: g })),
      { label: "Estimates", key: "model" },
      { label: "n", key: "n", cls: "num" },
      { label: "Mean", cls: "num", render: (r) => ageNum(r.mean) },
      { label: "SD", cls: "num", render: (r) => ageNum(r.sd) },
      { label: "Median", cls: "num", render: (r) => ageNum(r.median) },
      { label: "Range", cls: "num", render: (r) => range(r.min, r.max) },
      { label: "95% interval (t)", cls: "num", render: (r) => (r.ci95_low != null ? range(r.ci95_low, r.ci95_high) : "—") },
    ], out.summary);
    renderTests(out.tests);
    table($("#dis-table"), [
      { label: "Specimen", key: "specimen_id" },
      { label: "Site", key: "site" },
      { label: "Species", key: "species" },
      ...state.options.models.map((m) => ({ label: esc(m), cls: "num", render: (r) => ageNum(r[m]) })),
      { label: `Range (${unitWord()})`, cls: "num", render: (r) => `<strong>${ageNum(r.range)}</strong>` },
    ], out.disagreement);
    renderValidation(out.validation);
    labelScrollBoxes(); // the tables above are new
  } catch (e) {
    toast(e.message);
  }
}

const range = (lo, hi) => `${ageNum(lo)}–${ageNum(hi)}`; // ages, in the chosen unit


function renderTests(t) {
  $("#tests-body").innerHTML = `${t.q_p != null
    ? `<p class="summary">Do groups differ at all? Between-group Q = ${num(t.q_between)} on ${t.q_df} df, <strong>${pIs(t.q_p)}</strong>;
       permutation test ${pIs(t.permutation_p)}. ${t.q_p < 0.05 ? "There is evidence that weaning ages differ between groups." : "No clear evidence that weaning ages differ between groups."}</p>`
    : '<p class="muted">At least two groups are needed for a comparison.</p>'}
    <div class="table-wrap"><table id="t-groups"></table></div>
    <details class="advanced"><summary>Pairwise comparisons (${t.pairwise.filter((p) => p.p_holm < 0.05).length} of ${t.pairwise.length} differ)</summary>
      <div class="advanced-body"><div class="table-wrap"><table id="t-pairs"></table></div></div></details>
    ${t.notes.map((n) => `<p class="muted small">${esc(n)}</p>`).join("")}`;
  table($("#t-groups"), [
    { label: "Group", key: "group" }, { label: "n", key: "n", cls: "num" },
    { label: "Mean", cls: "num", render: (g) => ageNum(g.mean) },
    { label: "95% interval", cls: "num", render: (g) => range(g.ci_low, g.ci_high) },
    { label: "τ", cls: "num", render: (g) => ageNum(g.tau, 2) },
  ], t.groups);
  table($("#t-pairs"), [
    { label: "Pair", render: (p) => `${esc(p.group_a)} − ${esc(p.group_b)}` },
    { label: "Difference", cls: "num", render: (p) => ageNum(p.difference) },
    { label: "SE", cls: "num", render: (p) => ageNum(p.se, 2) },
    { label: "p", cls: "num", render: (p) => pval(p.p) },
    { label: "p (Holm)", cls: "num", render: (p) => `<span class="${p.p_holm < 0.05 ? "sig" : ""}">${pval(p.p_holm)}</span>` },
  ], t.pairwise);

  const b = t.bayes;
  if (!b) return ($("#bayes-body").innerHTML = '<p class="muted">Needs at least three specimens.</p>');
  $("#bayes-body").innerHTML = `<p class="muted small">${b.method === "one-stage" ? "One-stage model on the raw δ¹⁵N values · " : ""}Shared between-animal SD τ = ${ageNum(b.tau_mean, 2)} ${unitWord()} (95% interval ${ageNum(b.tau_ci_low, 2)}–${ageNum(b.tau_ci_high, 2)}) ·
      max R̂ ${num(b.rhat_max, 3)} ${help("rhat")} · ${b.draws} posterior draws${b.rhat_max > 1.05 ? ' · <span class="warn-text">not fully converged</span>' : ""}</p>
    <div class="grid-2"><div class="table-wrap"><table id="b-groups"></table></div><div class="table-wrap"><table id="b-pairs"></table></div></div>
    <details><summary>Specimen estimates after partial pooling</summary><div class="table-wrap"><table id="b-specimens"></table></div></details>`;
  table($("#b-groups"), [
    { label: "Group", key: "group" },
    { label: "Posterior mean", cls: "num", render: (g) => ageNum(g.mean) },
    { label: "95% interval", cls: "num", render: (g) => range(g.ci_low, g.ci_high) },
  ], b.groups);
  table($("#b-pairs"), [
    { label: "Comparison", render: (p) => `${esc(p.group_a)} vs ${esc(p.group_b)}` },
    { label: "Probability the first weaned earlier", cls: "num", render: (p) => percent(p.prob_a_earlier) },
    { label: "Difference (95% interval)", cls: "num", render: (p) => `${ageNum(p.difference_mean)} (${range(p.difference_ci_low, p.difference_ci_high)})` },
  ], b.pairs);
  table($("#b-specimens"), [
    { label: "Specimen", key: "specimen_id" }, { label: "Group", key: "group" },
    { label: "Own estimate", cls: "num", render: (s) => ageNum(s.observed) },
    { label: "Pooled estimate", cls: "num", render: (s) => ageNum(s.shrunk) },
    { label: "95% interval", cls: "num", render: (s) => range(s.ci_low, s.ci_high) },
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
    { label: "Bias", cls: "num", render: (r) => ageNum(r.bias, 2) },
    { label: "MAE", cls: "num", render: (r) => ageNum(r.mae, 2) },
    { label: "RMSE", cls: "num", render: (r) => ageNum(r.rmse, 2) },
    { label: "Pearson r", cls: "num", render: (r) => num(r.pearson_r) },
    { label: "95% interval coverage", cls: "num", render: (r) => percent(r.ci_coverage) },
  ], rows);
}

// Saving, opening and the report
function project() {
  return {
    format: "weanage-project", format_version: 1, app_version: state.config.version, saved_at: new Date().toISOString(),
    samples: state.samples, settings: settings(), results: state.results, estimates: state.estimates,
    analysis_options: state.options, current: state.current, plan: state.plan, mode: state.mode, chosen: state.chosen,
    bone: { samples: state.bone.samples, settings: boneSettings(settings().qc), results: state.bone.results,
      options: state.bone.options, current: state.bone.current },
    ...Object.fromEntries(Object.values(CALCS).map((calc) => [calc.name, calc.saved()])),
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
      try {
        const small = project();
        small.bone.results = null;
        for (const name in CALCS) small[name].output = null;
        localStorage.setItem("weanage-autosave", JSON.stringify({ ...small, results: null, estimates: null }));
      } catch {}
    }
  }, 600);
}

function openProject(p) {
  if (p.format !== "weanage-project" || !Array.isArray(p.samples)) throw new Error("This file is not a WeanAge project.");
  applySettings(p.settings || {});
  if (p.bone) {
    applyBoneSettings(p.bone.settings || {});
    Object.assign(state.bone, { results: p.bone.results, options: p.bone.options, current: p.bone.current });
    api.boneRecords(p.bone.samples || []).then((report) => {
      setBoneReport(report, true);
      if (state.bone.results) renderBoneResults();
    }).catch((e) => toast(e.message));
  }
  for (const calc of Object.values(CALCS)) if (p[calc.name]) calc.restore(p[calc.name]);
  state.chosen = p.chosen || [p.mode || "tooth"]; // older projects had one calculation
  setMode(p.mode || "tooth");
  Object.assign(state, { samples: p.samples, options: p.analysis_options, plan: p.plan || null });
  state.visible = new Set([...(state.options?.models || []), "average"]);
  recheck(true).then(() => {
    if (p.results && p.analysis_options) {
      Object.assign(state, { results: p.results, estimates: p.estimates, current: p.current || p.results[0]?.specimen_id });
      enableResults();
      renderResults();
    }
    if (state.plan) renderPlan(state);
  });
}

function offerRestore() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("weanage-autosave")); } catch {}
  const animals = saved?.bone?.samples?.length || 0;
  const others = Object.values(CALCS).map((calc) => [saved?.[calc.name]?.samples?.length || 0, calc.plural]);
  if (!saved?.samples?.length && !animals && !others.some(([n]) => n)) return;
  const what = [saved.samples.length && `${saved.samples.length} tooth samples`, animals && `${animals} animals (bone)`,
    ...others.map(([n, noun]) => n && `${n} ${noun}`)].filter(Boolean).join(", ");
  $("#restore-when").textContent = `${what}, ${new Date(saved.saved_at).toLocaleString()}`;
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
    toast("Report downloaded.", "ok");
  } catch (e) {
    toast(e.message);
  }
}

// Buttons and inputs
function bind() {
  const on = (selector, event, handler) => $(selector).addEventListener(event, handler);
  for (const b of $$(".step")) b.addEventListener("click", () => show(b.dataset.view));
  on("#btn-next-settings", "click", () => show("settings"));

  const zone = $("#dropzone");
  on("#csv-input", "change", (e) => e.target.files[0] && loadFile(e.target.files[0]));
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("over"); e.dataTransfer.files[0] && loadFile(e.dataTransfer.files[0]); });
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#csv-input").click(); } });
  on("#calc-list", "change", (e) => e.target.name === "calc" && toggleCalc(e.target.value, e.target.checked));
  on("#calc-tabs", "click", (e) => { const b = e.target.closest("[data-calc]"); if (b) switchCalc(b.dataset.calc); });
  on("#btn-example", "click", () => loadExample($("#example-choice").value));
  on("#btn-clear", "click", () => {
    if (state.mode === "bone") {
      if (!state.bone.samples.length || confirm("Remove all loaded animals?")) setBoneReport({ samples: [], issues: [], groups: [] });
    } else if (oneTable()) {
      oneTable().clear();
    } else if (!state.samples.length || confirm("Remove all loaded samples?")) setReport({ samples: [], issues: [], specimens: [] });
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
    else {
      const carbon = row.querySelector(".bl-c").value;
      state.baselines[row.dataset.key] = { mean: Number(mean), sd: Number(row.querySelector(".bl-sd").value) || 0.5,
        d13C_mean: carbon === "" ? null : Number(carbon), d13C_sd: Number(row.querySelector(".bl-c-sd").value) || 0.5 };
    }
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
  // Typing the age range does the same as dragging across the chart, without needing a pointer.
  on("#zoom-form", "submit", (e) => {
    e.preventDefault();
    const [from, to] = [$("#zoom-from").value, $("#zoom-to").value].map(Number);
    if ($("#zoom-from").value === "" || $("#zoom-to").value === "" || !(from < to)) return toast("Enter two ages, the first smaller than the second.");
    state.zoom = [from, to];
    renderResults();
  });
  on("#toast-close", "click", () => ($("#toast").hidden = true));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#toast").hidden && !document.querySelector("dialog[open]")) $("#toast").hidden = true; });
  on("#btn-export-csv", "click", () => download("weanage_estimates.csv", new Blob([toCsv(state.estimates)], { type: "text/csv" })));
  on("#btn-export-json", "click", () => download("weanage_results.json", new Blob([JSON.stringify({ options: state.options, results: state.results }, null, 2)])));
  on("#btn-export-svg", "click", () => {
    // Redraw the chart in light colours on white, which suits papers and slides.
    const res = state.results.find((r) => r.specimen_id === state.current) || state.results[0];
    if (!res?.points.length) return;
    const options = { visible: state.visible, milestone: state.options.reported_milestone, xRange: state.zoom, showD13C: $("#opt-show13c").checked, palette: "light" };
    download(`${res.specimen_id}_weaning_curve.svg`, new Blob([offscreen((box) => curveChart(box, curveOptions(res, options)))], { type: "image/svg+xml" }));
  });
  for (const input of $$('input[name="group"], #cmp-milestone, #cmp-model, #cmp-bayes, #group-extra')) input.addEventListener("change", refreshCompare);

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
  initHelpMenu(show, () => state.mode);
  on("#btn-theme", "click", () => setLook("theme", document.documentElement.dataset.theme === "light" ? "dark" : "light"));
  on("#btn-text", "click", () => setLook("text", document.documentElement.dataset.text === "large" ? "normal" : "large"));
  on("#btn-units", "click", () => setUnits(getAgeUnit() === "years" ? "months" : "years"));
}

// Dark/light colours and text size
// `key` is "theme" (dark/light) or "text" (normal/large). The choice is remembered.
function setLook(key, value) {
  document.documentElement.dataset[key] = value;
  try { localStorage.setItem(`weanage-${key}`, value); } catch {}
  showLook();
  if (state.results?.length) renderResults(); // charts pick their colours when drawn
  if (state.bone?.results) renderBoneResults();
  for (const calc of Object.values(CALCS)) calc.renderResults();
  if (state.plan) renderPlan(state);
  if (state.bonePlan) renderBonePlan(state);
}

/** Show results in months or years. The analysis itself always works in months. */
function setUnits(unit) {
  const before = getAgeUnit();
  setAgeUnit(unit);
  // Boxes that hold an age keep the same age in the new unit.
  const factor = before === unit ? 1 : unit === "years" ? 1 / 12 : 12;
  convertAgeInputs(factor);
  state.zoom = null; // a zoom window is in the old unit
  showUnits();
  if (state.mode === "bone") renderBoneData();
  if (state.results?.length) renderResults();
  if (state.bone?.results) renderBoneResults();
  for (const calc of Object.values(CALCS)) calc.renderResults();
  if (state.plan) renderPlan(state);
  if (state.bonePlan) renderBonePlan(state);
  if ($("#view-compare").classList.contains("active")) refreshCompare();
}

/** Boxes that hold an age (data-age) or a list of ages (data-age-list) keep the same age in a new unit. */
function convertAgeInputs(factor) {
  const convert = (text) => text.split(/[,;\s]+/).filter(Boolean).map((v) => +(Number(v) * factor).toFixed(3)).join(", ");
  for (const input of $$("input[data-age]")) if (input.value !== "") input.value = convert(input.value);
  for (const input of $$("input[data-age-list]")) input.value = convert(input.value);
}

function showUnits() {
  const years = getAgeUnit() === "years";
  $("#btn-units").textContent = years ? "Ages in months" : "Ages in years";
  $("#btn-units").setAttribute("aria-pressed", String(years));
  for (const node of $$(".unit-word")) node.textContent = unitWord();
}

function showLook() {
  const light = document.documentElement.dataset.theme === "light";
  const large = document.documentElement.dataset.text === "large";
  $("#btn-theme").textContent = light ? "Dark mode" : "Light mode";
  $("#btn-theme").setAttribute("aria-pressed", String(light));
  $("#btn-text").textContent = large ? "Normal text" : "Larger text";
  $("#btn-text").setAttribute("aria-pressed", String(large));
}

// Start
async function init() {
  try {
    // The browser version downloads its Python engine first; show what is happening.
    onEngineStatus((text) => {
      $("#engine-status").hidden = !text;
      $("#engine-status").textContent = text || "";
    });
    state.config = await api.config();
  } catch (e) {
    return toast(`Could not start WeanAge: ${e.message}`);
  }
  $("#sb-mode").textContent = inBrowser ? "Running in this browser" : "Local app";
  initSettings();
  initBone(state, { show, autosave, refreshNav: enableResults, qc: () => settings().qc });
  for (const calc of Object.values(CALCS)) calc.init(state, { show, autosave, refreshNav: enableResults });
  fillExampleChoice();
  setMode("tooth", false);
  initAbout(state.config);
  initPlanner(state);
  initBonePlanner(state);
  renderTbd();
  for (const slot of $$("[data-helpslot]")) slot.innerHTML = help(slot.dataset.helpslot);
  labelScrollBoxes();
  initGlossary();
  bind();
  showLook();
  showUnits();
  if (getAgeUnit() === "years") convertAgeInputs(1 / 12); // the page's starting values are in months
  renderData();
  offerRestore();
  if (!tourSeen()) startTour(show, state.mode);
}

init();
