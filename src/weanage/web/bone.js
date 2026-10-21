// The bone calculation: many young animals that died at different ages (after WARN).
// Its data, settings and results live in state.bone, apart from the tooth calculation's.
import { api } from "./api.js";
import { curveChart } from "./chart.js";
import { offscreen } from "./report.js";
import { $, ci, color, download, esc, num, plural, progressBar, table, tbdBadge, toast, toCsv } from "./util.js";

// Bone settings and the form box that holds each (all numbers).
const FIELDS = ["max_weaning_age_months", "enrichment_prior_mean", "enrichment_prior_sd", "weaning_food_prior_sd",
  "female_mean", "female_sd", "chains", "warmup", "keep"];
const ESTIMATES = [
  ["onset", "Weaning starts", "months"], ["midpoint", "Weaning midpoint", "months"], ["completion", "Weaning ends", "months"],
  ["enrichment_permil", "Nursing enrichment", "‰"], ["weaning_food_d15N", "Weaning-food δ¹⁵N", "‰"],
  ["female_mean_d15N", "Mothers' mean δ¹⁵N", "‰"], ["sigma_permil", "Scatter between animals (SD)", "‰"],
];

let state;
let hooks; // { show, autosave, refreshNav }

export function initBone(appState, appHooks) {
  state = appState;
  hooks = appHooks;
  state.bone = { samples: [], report: null, results: null, options: null, current: null };
  applyBoneSettings(state.config.bone_defaults);
  $("#btn-bone-to-settings").addEventListener("click", () => hooks.show("settings"));
  $("#btn-bone-run").addEventListener("click", runBone);
  $("#bone-result-list").addEventListener("click", (e) => {
    const b = e.target.closest("[data-group]");
    if (b) choose(b.dataset.group);
  });
  $("#bone-result-list").addEventListener("keydown", (e) => {
    const names = state.bone.results.map((r) => r.group);
    const moves = { ArrowDown: 1, ArrowUp: -1 };
    if (!(e.key in moves)) return;
    e.preventDefault();
    const i = Math.min(Math.max(names.indexOf(state.bone.current) + moves[e.key], 0), names.length - 1);
    choose(names[i]);
  });
  $("#view-bone-settings").addEventListener("change", hooks.autosave);
  $("#btn-bone-csv").addEventListener("click", () => download("weanage_bone_estimates.csv", new Blob([toCsv(estimateRows())], { type: "text/csv" })));
  $("#btn-bone-json").addEventListener("click", () => download("weanage_bone_results.json",
    new Blob([JSON.stringify({ options: state.bone.options, results: state.bone.results }, null, 2)])));
  $("#btn-bone-svg").addEventListener("click", () => {
    const res = currentResult();
    if (res?.curve) download(`${res.group.replace(/\W+/g, "_")}_bone_weaning.svg`,
      new Blob([offscreen((box) => curveChart(box, chartOptions(res, "light")))], { type: "image/svg+xml" }));
  });
}

// ───────────── data ─────────────
export async function loadBoneFile(file) {
  try {
    setBoneReport(await api.boneUpload(file));
    toast(`Loaded ${plural(state.bone.samples.length, "animal")} from ${file.name}`, "ok");
  } catch (e) {
    toast(e.message);
  }
}

export async function loadBoneExample(name) {
  try {
    const report = await api.boneExample(name);
    setBoneReport(report);
    toast(report.message, "ok");
  } catch (e) {
    toast(e.message);
  }
}

export function setBoneReport(report, keepResults = false) {
  state.bone.report = report;
  state.bone.samples = report.samples;
  if (!keepResults) state.bone.results = null;
  renderBoneData();
  hooks.refreshNav();
  hooks.autosave();
}

export function renderBoneData() {
  if (state.mode !== "bone") return;
  const { report, samples } = state.bone;
  const issues = report ? report.issues : [];
  $("#issues-card").hidden = !issues.length;
  $("#issues").innerHTML = issues
    .map((i) => `<li class="${i.severity}">${i.row ? `<b>Row ${i.row}</b>${i.field ? ` (${esc(i.field)})` : ""}: ` : ""}${esc(i.message)}</li>`)
    .join("");
  $("#bone-groups-card").hidden = !samples.length;
  $("#bone-count").textContent = `· ${plural(samples.length, "animal")}`;
  $("#sb-data").textContent = samples.length ? `${plural(samples.length, "animal")} · ${plural(report.groups.length, "group")}` : "No data loaded";
  table($("#bone-group-table"), [
    { label: "Group", key: "group" },
    { label: "Young animals", key: "n_young", cls: "num" },
    { label: "Adult females", key: "n_adult_females", cls: "num" },
    { label: "All adults", key: "n_adults", cls: "num" },
    { label: "Bone turnover", render: (g) => turnoverLabel(g.species) },
  ], report ? report.groups : []);
  table($("#bone-sample-table"), [
    { label: "Specimen", key: "specimen_id" },
    { label: "Site", key: "site" },
    { label: "Species", key: "species" },
    { label: "Adult / young", render: (s) => (s.age_class === "adult" ? `adult${s.sex === "f" ? " ♀" : s.sex === "m" ? " ♂" : ""}` : "young") },
    { label: "Age (months)", cls: "num", render: (s) => (s.age_months == null ? "—" : s.age_min_months !== s.age_max_months ? `${num(s.age_min_months, 1)}–${num(s.age_max_months, 1)}` : num(s.age_months, 1)) },
    { label: "δ¹⁵N", cls: "num", render: (s) => num(s.d15N) },
    { label: "δ¹³C", cls: "num", render: (s) => num(s.d13C) },
    { label: "C:N", cls: "num", render: (s) => num(s.cn_ratio) },
    { label: "Notes", key: "notes" },
  ], samples);
}

function turnoverLabel(species) {
  const t = state.config.turnover_tables.find((x) => x.species === species);
  return t ? `${esc(t.label)} ${t.placeholder ? tbdBadge : ""}` : '<span class="warn-text">none for this species</span>';
}

// ───────────── settings ─────────────
export function applyBoneSettings(o) {
  for (const key of [...FIELDS, "weaning_form"]) if (key in o) $(`#bone-${key}`).value = o[key] ?? "";
}

export function boneSettings(qc) {
  const defaults = state.config.bone_defaults;
  const out = { qc, random_seed: 42, weaning_form: $("#bone-weaning_form").value };
  for (const key of FIELDS) {
    const value = $(`#bone-${key}`).value;
    out[key] = value === "" ? defaults[key] : Number(value);
  }
  return out;
}

export function renderTurnover() {
  const species = [...new Set(state.bone.samples.map((s) => s.species))];
  const tables = state.config.turnover_tables.filter((t) => !species.length || species.includes(t.species));
  $("#turnover-list").innerHTML = tables.length ? tables.map((t) => `<h3>${esc(t.label)} ${t.placeholder ? tbdBadge : ""}</h3>
    <table><thead><tr><th>Age (months)</th>${t.ages_months.map((a) => `<th class="num">${num(a, 0)}</th>`).join("")}</tr></thead>
    <tbody><tr><th>Renewed per month</th>${t.renewed_per_month.map((r) => `<td class="num">${Math.round(r * 100)}%</td>`).join("")}</tr></tbody></table>
    ${t.tbd_note ? `<p class="hint">${esc(t.tbd_note)}</p>` : ""}`).join("") : '<p class="muted">No turnover table for these species.</p>';
}

async function runBone() {
  if (!state.bone.samples.length) return toast("Load some bone data first.");
  const options = boneSettings(hooks.qc());
  const bar = $("#bone-progress");
  $("#btn-bone-run").disabled = true;
  progressBar(bar, 0, 0, "Fitting groups");
  try {
    const out = await api.boneAnalyze(state.bone.samples, options, (done, total) => progressBar(bar, done, total, "Fitting groups"));
    Object.assign(state.bone, { results: out.results, options, current: out.results[0]?.group });
    hooks.refreshNav();
    renderBoneResults();
    hooks.show("results");
    hooks.autosave();
  } catch (e) {
    toast(e.message);
  } finally {
    $("#btn-bone-run").disabled = false;
    bar.hidden = true;
  }
}

// ───────────── results ─────────────
const currentResult = () => state.bone.results?.find((r) => r.group === state.bone.current) || state.bone.results?.[0];
const isNote = (w) => /PLACEHOLDER|stand in|taken from Settings/.test(w);

function choose(group) {
  state.bone.current = group;
  renderBoneResults();
  $(`#bone-result-list [data-group="${CSS.escape(group)}"]`)?.focus();
}

export function renderBoneResults() {
  const results = state.bone.results || [];
  $("#bone-result-list").innerHTML = results.map((r) => {
    const chosen = r.group === state.bone.current;
    const end = r.estimates?.completion;
    const problems = r.warnings.filter((w) => !isNote(w)).length;
    return `<li><button role="option" aria-selected="${chosen}" tabindex="${chosen ? 0 : -1}" data-group="${esc(r.group)}" class="${chosen ? "active" : ""}">
      <span><strong>${esc(r.site)}</strong><small>${esc(r.species)}${r.period ? ` · ${esc(r.period)}` : ""} · ${plural(r.n_young, "young animal")}</small></span>
      <span><span class="age">${end ? `${num(end.estimate, 1)} mo` : "—"}</span>${problems ? `<span class="warn-dot" aria-label="${plural(problems, "warning")}">${problems}</span>` : ""}</span>
    </button></li>`;
  }).join("");
  const res = currentResult();
  if (!res) return;
  $("#bone-res-title").textContent = res.group;
  $("#bone-res-meta").innerHTML = `${plural(res.n_young, "young animal")} fitted · turnover: ${esc(res.turnover || "none")} ${res.turnover_placeholder ? tbdBadge : ""}`;
  $("#bone-res-summary").innerHTML = summary(res);
  if (res.curve) curveChart($("#bone-res-chart"), chartOptions(res));
  else $("#bone-res-chart").innerHTML = `<p class="muted">${esc(res.message)}</p>`;
  $("#bone-res-warnings").innerHTML = res.warnings
    .map((w) => `<li class="${/PLACEHOLDER/.test(w) ? "tbd-li" : isNote(w) ? "info" : "warning"}">${esc(w)}</li>`).join("");
  const rows = res.estimates ? ESTIMATES.map(([key, label, unit]) => ({ label, unit, ...res.estimates[key] })) : [];
  table($("#bone-fit-table"), [
    { label: "Estimate", render: (r) => esc(r.label) },
    { label: "Median", cls: "num", render: (r) => `${num(r.estimate, r.unit === "‰" ? 2 : 1)} ${r.unit === "‰" ? "‰" : "mo"}` },
    { label: "95% interval", cls: "num", render: (r) => (r.unit === "‰" ? `${num(r.ci_low)}–${num(r.ci_high)}` : ci(r)) },
  ], rows);
  if (res.rhat != null) {
    $("#bone-fit-table").insertAdjacentHTML("beforeend",
      `<tfoot><tr><td>R̂ (largest)</td><td class="num ${res.rhat > 1.1 ? "warn-text" : ""}">${num(res.rhat)}</td><td></td></tr></tfoot>`);
  }
}

function summary(res) {
  if (!res.estimates) return esc(res.message);
  const e = res.estimates;
  return `Weaning ran from about <strong>${num(e.onset.estimate, 1)}</strong> to <strong>${num(e.completion.estimate, 1)} months</strong>
    (end: 95% interval ${ci(e.completion)} months). Nursing young were about ${num(e.enrichment_permil.estimate, 1)}‰ above their mothers.
    ${res.turnover_placeholder ? '<span class="tbd-inline">Illustrative only: placeholder bone turnover.</span>' : ""}`;
}

function chartOptions(res, palette) {
  const c = res.curve;
  const e = res.estimates;
  const bone = color("average", palette);
  const accent = color("logistic", palette);
  const marker = (key, text) => ({ x: e[key].estimate, lo: e[key].ci_low, hi: e[key].ci_high, color: accent, label: `${text} ${num(e[key].estimate, 1)} mo` });
  const young = res.points.filter((p) => p.role === "non-adult");
  return {
    title: `Bone δ15N against age at death: ${res.group}`,
    desc: `${young.length} young animals; fitted bone curve with 95% band and the diet it implies. Weaning from ${num(e.onset.estimate, 1)} to ${num(e.completion.estimate, 1)} months.`,
    xLabel: "Age at death (months)",
    yLabel: "Bone collagen δ¹⁵N (‰ AIR)",
    markers: [marker("onset", "start"), marker("completion", "end")],
    bands: [{ xs: c.age, lo: c.bone_low, hi: c.bone_high, color: bone }],
    curves: [
      { xs: c.age, ys: c.bone, color: bone },
      { xs: c.age, ys: c.diet, color: bone, dash: "2 4", width: 2 },
      { xs: [c.age[0], c.age.at(-1)], ys: [e.female_mean_d15N.estimate, e.female_mean_d15N.estimate], color: bone, dash: "8 6", width: 1.5 },
    ],
    points: young.map((p) => ({
      x: p.age_months, y: p.d15N, xMin: p.age_min !== p.age_max ? p.age_min : null, xMax: p.age_max, used: p.used_in_fit,
      label: `${esc(p.specimen_id)}: ${p.age_min !== p.age_max ? `${num(p.age_min, 1)}–${num(p.age_max, 1)}` : num(p.age_months, 1)} months<br>δ¹⁵N ${num(p.d15N)}‰` +
        `${p.qc_flags.length ? `<br><em>${esc(p.qc_flags.join(", "))}</em>` : ""}`,
    })),
  };
}

function estimateRows() {
  return (state.bone.results || []).filter((r) => r.estimates).flatMap((r) => ESTIMATES.map(([key, label]) => ({
    group: r.group, site: r.site, species: r.species, period: r.period, estimate: label,
    median: r.estimates[key].estimate, ci_low: r.estimates[key].ci_low, ci_high: r.estimates[key].ci_high, rhat: r.rhat,
  })));
}
