// The enamel calculation: season of birth (δ18O) and rumen development (δ13C) along one cattle molar.
// Its data, settings and results live in state.enamel, apart from the other calculations'.
import { api } from "./api.js";
import { forestChart, profileChart } from "./chart.js";
import { $, download, esc, help, num, plural, progressBar, renderIssues, renderReady, renderWarnings, table, toast, toCsv } from "./util.js";

const FIELDS = ["period_min_mm", "period_max_mm", "min_amplitude_permil", "min_rumen_rise_permil", "max_rumen_rise_permil", "draws",
  "c3_plants_d13C", "c3_plants_sd", "c4_plants_d13C", "c4_plants_sd", "enamel_diet_spacing_permil", "enamel_diet_spacing_sd"];

const teeth = (n) => `${n} ${n === 1 ? "tooth" : "teeth"}`;

let state;
let hooks; // { show, autosave, refreshNav }

export function initEnamel(appState, appHooks) {
  state = appState;
  hooks = appHooks;
  state.enamel = { samples: [], report: null, results: null, groups: null, options: null, current: null };
  applyEnamelSettings(state.config.enamel_defaults);
  $("#btn-enamel-run").addEventListener("click", runEnamel);
  $("#enamel-result-list").addEventListener("click", (e) => {
    const b = e.target.closest("[data-tooth]");
    if (b) choose(b.dataset.tooth);
  });
  $("#enamel-result-list").addEventListener("keydown", (e) => {
    const ids = state.enamel.results.map((r) => r.specimen_id);
    const moves = { ArrowDown: 1, ArrowUp: -1 };
    if (!(e.key in moves)) return;
    e.preventDefault();
    choose(ids[Math.min(Math.max(ids.indexOf(state.enamel.current) + moves[e.key], 0), ids.length - 1)]);
  });
  $("#view-enamel-settings").addEventListener("change", hooks.autosave);
  $("#btn-enamel-csv").addEventListener("click", () => download("weanage_enamel_estimates.csv", new Blob([toCsv(estimateRows())], { type: "text/csv" })));
  $("#btn-enamel-json").addEventListener("click", () => download("weanage_enamel_results.json",
    new Blob([JSON.stringify({ options: state.enamel.options, results: state.enamel.results, groups: state.enamel.groups }, null, 2)])));
}

// Data
export async function loadEnamelFile(file) {
  try {
    setEnamelReport(await api.enamelUpload(file));
  } catch (e) {
    toast(e.message);
  }
}

export async function loadEnamelExample(name) {
  try {
    const report = await api.enamelExample(name);
    setEnamelReport(report);
    toast(report.message, "ok");
  } catch (e) {
    toast(e.message);
  }
}

export function setEnamelReport(report, keepResults = false) {
  state.enamel.report = report;
  state.enamel.samples = report.samples;
  if (!keepResults) state.enamel.results = null;
  renderEnamelData();
  hooks.refreshNav();
  hooks.autosave();
}

export function renderEnamelData() {
  if (state.mode !== "enamel") return;
  const { report, samples } = state.enamel;
  const loaded = report?.teeth || [];
  $("#specimens-card").hidden = true; // the tooth calculation's table
  renderIssues(report ? report.issues : []);
  renderReady(samples.length && `${plural(samples.length, "sample")} from ${teeth(loaded.length)} loaded.`);
  $("#enamel-teeth-card").hidden = !samples.length;
  $("#enamel-count").textContent = `· ${teeth(loaded.length)}`;
  $("#sb-data").textContent = samples.length ? `${plural(samples.length, "enamel sample")}` : "No data loaded";
  table($("#enamel-teeth-table"), [
    { label: "Tooth", render: (t) => `${esc(t.specimen_id)} <small class="muted">${esc(t.tooth)}</small>` },
    { label: "Site", key: "site" },
    { label: "Samples", key: "n_samples", cls: "num" },
    { label: "δ¹⁸O", key: "n_d18O", cls: "num" },
    { label: "δ¹³C", key: "n_d13C", cls: "num" },
    { label: "Crown sampled (mm)", cls: "num", render: (t) => num(t.span_mm, 1) },
  ], loaded);
  table($("#enamel-sample-table"), [
    { label: "Tooth", key: "specimen_id" },
    { label: "From ERJ (mm)", cls: "num", render: (s) => num(s.erj_distance_mm, 1) },
    { label: "δ¹⁸O", cls: "num", render: (s) => num(s.d18O) },
    { label: "δ¹³C", cls: "num", render: (s) => num(s.d13C) },
    { label: "Notes", key: "notes" },
  ], samples);
}

// Settings
export function applyEnamelSettings(o) {
  for (const key of FIELDS) if (key in o) $(`#enamel-${key}`).value = o[key] ?? "";
}

export function enamelSettings() {
  const defaults = state.config.enamel_defaults;
  const out = { random_seed: 42 };
  for (const key of FIELDS) {
    const value = $(`#enamel-${key}`).value;
    out[key] = value === "" ? defaults[key] : Number(value);
  }
  return out;
}

async function runEnamel() {
  if (!state.enamel.samples.length) return toast("Load some enamel data first.");
  const options = enamelSettings();
  const bar = $("#enamel-progress");
  $("#btn-enamel-run").disabled = true;
  progressBar(bar, 0, 0, "Fitting teeth");
  try {
    const out = await api.enamelAnalyze(state.enamel.samples, options, (done, total) => progressBar(bar, done, total, "Fitting teeth"));
    Object.assign(state.enamel, { results: out.results, groups: out.groups, options, current: out.results[0]?.specimen_id });
    hooks.refreshNav();
    renderEnamelResults();
    hooks.show("results");
    hooks.autosave();
  } catch (e) {
    toast(e.message);
  } finally {
    $("#btn-enamel-run").disabled = false;
    bar.hidden = true;
  }
}

// Results
const currentResult = () => state.enamel.results?.find((r) => r.specimen_id === state.enamel.current) || state.enamel.results?.[0];
const range = (v, d = 2) => (v?.ci_low != null ? `${num(v.ci_low, d)}–${num(v.ci_high, d)}` : "");
const warningsOf = (r) => [...(r.season?.warnings || []), ...(r.rumen?.warnings || []), ...(r.diet?.warnings || [])];
const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);

function choose(id) {
  state.enamel.current = id;
  renderEnamelResults();
  $(`#enamel-result-list [data-tooth="${CSS.escape(id)}"]`)?.focus();
}

export function renderEnamelResults() {
  const results = state.enamel.results || [];
  $("#enamel-result-list").innerHTML = results.map((r) => {
    const chosen = r.specimen_id === state.enamel.current;
    const index = r.season?.birth_index;
    const n = warningsOf(r).length;
    return `<li role="none"><button role="option" aria-selected="${chosen}" tabindex="${chosen ? 0 : -1}" data-tooth="${esc(r.specimen_id)}" class="${chosen ? "active" : ""}">
      <span><strong>${esc(r.specimen_id)}</strong><small>${esc(r.site)} · ${esc(r.species)} ${esc(r.tooth)}</small></span>
      <span><span class="age">${index ? num(index.estimate, 2) : "—"}</span>${n ? `<span class="warn-dot" aria-label="${plural(n, "warning")}">${n}</span>` : ""}</span>
    </button></li>`;
  }).join("");
  const res = currentResult();
  if (!res) return;
  $("#enamel-res-title").textContent = res.specimen_id;
  $("#enamel-res-meta").textContent = `${res.site} · ${res.species} ${res.tooth}${res.period ? ` · ${res.period}` : ""} · ${plural(res.points.length, "enamel sample")}`;
  $("#enamel-res-summary").innerHTML = summary(res);
  drawCharts(res);
  renderWarnings("#enamel-warnings-box", "#enamel-warnings-summary", "#enamel-res-warnings", warningsOf(res), () => "warning");
  renderGroups();
}

function summary(res) {
  const s = res.season;
  const r = res.rumen;
  const season = !s ? "<p>No δ¹⁸O values.</p>" : s.birth_index
    ? `<p class="readout"><span class="figure">${num(s.birth_index.estimate, 2)}</span>
        <span class="what">birth index (x₀/X) ${help("birth_index")}${s.birth_index.ci_low != null ? ` · 95% interval ${range(s.birth_index)}` : ""}</span></p>
      <p>δ¹⁸O cycle of ${num(2 * s.amplitude_permil, 1)}‰ (maximum to minimum); about ${num(s.period_mm, 0)} mm of crown formed in a year;
        δ¹⁸O maximum ${num(s.x0_mm, 1)} mm above the enamel-root junction.</p>`
    : `<p><strong>No birth index.</strong> ${esc(s.message)}.</p>`;
  const rumen = !r ? "<p>No δ¹³C values.</p>" : r.detected
    ? `<p><strong>Rumen development ${help("rumen")}:</strong> δ¹³C rises by ${num(r.rise_permil, 1)}‰ around
        ${num(r.transition_mm.estimate, 1)} mm above the enamel-root junction${r.transition_mm.ci_low != null ? ` (95% interval ${range(r.transition_mm, 1)} mm)` : ""}${
        r.months_after_first_sample != null ? `, about ${num(r.months_after_first_sample, 1)} months of crown growth after the first sample` : ""}.</p>`
    : `<p><strong>No rumen development detected ${help("rumen")}.</strong> ${esc(r.message)}.</p>`;
  const d = res.diet;
  const diet = !d ? "" : d.share_c4
    ? `<p><strong>Diet ${help("c4")}:</strong> ${esc(d.category)}, about ${pct(d.share_c4.estimate)} C4 plants
        (95% interval ${pct(d.share_c4.ci_low)}–${pct(d.share_c4.ci_high)}; samples range ${pct(d.sample_range[0])}–${pct(d.sample_range[1])}),
        from ${plural(d.n, "sample")}${d.after_rumen ? " formed after the rumen transition" : ""}. Diet δ¹³C about ${num(d.diet_d13C, 1)}‰.</p>`
    : `<p><strong>No diet estimate ${help("c4")}.</strong> ${esc(d.message)}.</p>`;
  return season + rumen + diet;
}

function drawCharts(res) {
  const s = res.season;
  const r = res.rumen;
  const oxygen = res.points.filter((p) => p.d18O != null);
  const carbon = res.points.filter((p) => p.d13C != null);
  const point = (key) => (p) => ({ x: p.x, y: p[key], label: `${esc(res.specimen_id)}${p.sample_index != null ? ` #${p.sample_index}` : ""}: ${num(p.x, 1)} mm<br>${key === "d18O" ? "δ¹⁸O" : "δ¹³C"} ${num(p[key])}‰` });
  const curve = (fit) => (fit?.curve_x?.length ? { xs: fit.curve_x, ys: fit.curve_y } : null);
  $("#enamel-o-chart").hidden = !oxygen.length;
  $("#enamel-c-chart").hidden = !carbon.length;
  if (oxygen.length) profileChart($("#enamel-o-chart"), {
    points: oxygen.map(point("d18O")), curve: curve(s), yLabel: "Enamel δ¹⁸O (‰ VPDB)", title: `Enamel δ18O along the crown: ${res.specimen_id}`,
    marks: s?.birth_index ? [{ x: s.x0_mm, label: `δ¹⁸O maximum ${num(s.x0_mm, 1)} mm` }] : [],
  });
  if (carbon.length) profileChart($("#enamel-c-chart"), {
    points: carbon.map(point("d13C")), curve: curve(r), yLabel: "Enamel δ¹³C (‰ VPDB)", title: `Enamel δ13C along the crown: ${res.specimen_id}`,
    marks: r?.detected ? [{ x: r.transition_mm.estimate, lo: r.transition_mm.ci_low, hi: r.transition_mm.ci_high, label: `rumen transition ${num(r.transition_mm.estimate, 1)} mm` }] : [],
  });
}

function renderGroups() {
  const groups = state.enamel.groups || [];
  const dated = groups.filter((g) => g.n_index);
  $("#enamel-group-chart").innerHTML = dated.length ? "" : '<p class="muted">No tooth has a birth index.</p>';
  if (dated.length) forestChart($("#enamel-group-chart"), dated.map((g) => ({
    label: g.group, mean: g.mean_index, lo: NaN, hi: NaN,
    values: g.teeth.map((t) => ({ v: t.birth_index, label: `${esc(t.specimen_id)}: ${num(t.birth_index, 2)}` })),
  })), "Birth index (x₀/X): squares = circular mean, dots = teeth");
  table($("#enamel-group-table"), [
    { label: "Group", key: "group" },
    { label: "Teeth", key: "n", cls: "num" },
    { label: "Mean index", cls: "num", render: (g) => num(g.mean_index, 2) },
    { label: "Spread", cls: "num", render: (g) => num(g.spread_index, 2) },
    { label: "≈ months of births", cls: "num", render: (g) => num(g.spread_months, 1) },
    { label: "Mean C4 share", cls: "num", render: (g) => pct(g.mean_share_c4) },
  ], groups);
}

function estimateRows() {
  return (state.enamel.results || []).map((r) => ({
    specimen_id: r.specimen_id, site: r.site, species: r.species, tooth: r.tooth, period: r.period,
    birth_index: r.season?.birth_index?.estimate, birth_index_ci_low: r.season?.birth_index?.ci_low, birth_index_ci_high: r.season?.birth_index?.ci_high,
    period_mm: r.season?.period_mm, x0_mm: r.season?.x0_mm, d18O_amplitude_permil: r.season?.amplitude_permil,
    rumen_detected: r.rumen?.detected, rumen_transition_mm: r.rumen?.transition_mm?.estimate,
    rumen_transition_ci_low: r.rumen?.transition_mm?.ci_low, rumen_transition_ci_high: r.rumen?.transition_mm?.ci_high,
    rumen_rise_permil: r.rumen?.rise_permil, months_after_first_sample: r.rumen?.months_after_first_sample,
    diet: r.diet?.category, c4_share: r.diet?.share_c4?.estimate, c4_share_ci_low: r.diet?.share_c4?.ci_low,
    c4_share_ci_high: r.diet?.share_c4?.ci_high, diet_d13C: r.diet?.diet_d13C, diet_samples: r.diet?.n,
  }));
}
