import { api } from "./api.js";
import { curveChart, forestChart, svgToBlob } from "./chart.js";
import { curveOptions } from "./curves.js";
import { bindGrowthEditor, renderGrowthList } from "./growth.js";
import { initGlossary, startTour, tourSeen } from "./help.js";
import { initPlanner, renderPlan } from "./planner.js";
import { autosave, clearAutosave, loadAutosave, parseProject, serialiseProject } from "./project.js";
import { buildReport } from "./report.js";
import {
  $, $$, ci, download, esc, help, MILESTONES, num, progressBar, pval, swatch, table, tbdBadge, toast, toCsv,
} from "./util.js";

const state = {
  config: null,
  tbdIds: new Set(),
  samples: [],
  report: null,
  overrides: {}, // "species:tooth" -> {initiation_age_months, extension_rate_mm_per_month}
  baselines: {}, // "site:species" -> {mean, sd}
  editedTables: {}, // "species:tooth" -> GrowthTable (unsaved edits / calibrations)
  results: null,
  estimates: null,
  options: null,
  current: null,
  visible: new Set(),
  zoom: null,
  plan: null,
};

// ───────────────────────── navigation ─────────────────────────
function show(view) {
  $$(".step").forEach((b) => {
    const on = b.dataset.view === view;
    b.classList.toggle("active", on);
    if (on) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  if (view === "settings") {
    renderGrowthList(state);
    renderBaselines();
  }
  if (view === "compare") refreshCompare();
  window.scrollTo({ top: 0 });
}

function enableResultSteps(on) {
  $$('.step[data-view="results"], .step[data-view="compare"]').forEach((b) => (b.disabled = !on));
  $("#btn-report").disabled = !on;
}

function fillHelpSlots(root = document) {
  $$("[data-helpslot]", root).forEach((n) => {
    if (!n.firstChild) n.innerHTML = help(n.dataset.helpslot);
  });
}

// ───────────────────────── TBD banner ─────────────────────────
function renderTbd() {
  const items = state.config.tbd;
  state.tbdIds = new Set(items.map((i) => i.id));
  $("#tbd-banner").hidden = !items.length;
  $("#tbd-count").textContent = items.length;
  $("#tbd-list").innerHTML = items
    .map((i) => `<li><strong>${esc(i.area)}:</strong> ${esc(i.label)} — ${esc(i.note)} <code>${esc(i.file)}</code></li>`)
    .join("");
  $$("[data-tbd]").forEach((node) => {
    const on = state.tbdIds.has(node.dataset.tbd);
    node.classList.toggle("tbd", on);
    const target = node.matches("label") ? node : node.querySelector("h2");
    const badge = target?.querySelector(".tbd-badge");
    if (on && target && !badge) target.insertAdjacentHTML("beforeend", ` ${tbdBadge}`);
    if (!on && badge) badge.remove();
  });
}

async function refreshConfig() {
  state.config = await api.config();
  renderTbd();
}

// ───────────────────────── 1. data ─────────────────────────
function setReport(report, { keepResults = false } = {}) {
  state.report = report;
  state.samples = report.samples;
  if (!keepResults) {
    state.results = state.estimates = null;
    enableResultSteps(false);
  }
  renderData();
  persist();
}

async function revalidate() {
  setReport(await api.validateRecords(state.samples));
}

function ageModelLabel(species, tooth) {
  const key = `${species}:${tooth}`;
  if (state.overrides[key]) return "custom linear";
  const t = state.editedTables[key] || state.config.growth_tables.find((g) => `${g.species}:${g.tooth}` === key);
  if (!t) return '<span class="warn-text">none — add one in Settings</span>';
  return `${esc(t.label)} ${t.placeholder ? tbdBadge : ""}`;
}

function renderData() {
  const { report } = state;
  const issues = report ? report.issues : [];
  $("#issues-card").hidden = !issues.length;
  $("#issues").innerHTML = issues
    .map((i) => `<li class="${i.severity}">${i.row ? `<b>Row ${i.row}</b>${i.field ? ` (${esc(i.field)})` : ""}: ` : ""}${esc(i.message)}</li>`)
    .join("");

  $("#specimens-card").hidden = !state.samples.length;
  $("#sample-count").textContent = `· ${state.samples.length} samples`;
  table(
    $("#specimen-table"),
    [
      { label: "Specimen", key: "specimen_id" },
      { label: "Animal", render: (s) => esc(s.individual_id || "—") },
      { label: "Site", key: "site" },
      { label: "Species", key: "species" },
      { label: "Tooth", key: "tooth" },
      { label: "Samples", key: "n_samples", cls: "num" },
      { label: "Age model", render: (s) => ageModelLabel(s.species, s.tooth) },
    ],
    report ? report.specimens : []
  );

  const qc = settings().qc;
  const cnBad = (s) => s.cn_ratio != null && (s.cn_ratio < qc.cn_min || s.cn_ratio > qc.cn_max);
  table(
    $("#sample-table"),
    [
      { label: "Specimen", key: "specimen_id" },
      { label: "Position (mm)", render: (s) => `${num(s.position_mm, 2)}${s.position_measured_mm != null ? ` <small class="muted">(cervix ${num(s.position_measured_mm, 1)})</small>` : ""}`, cls: "num" },
      { label: "δ¹⁵N", render: (s) => num(s.d15N), cls: "num" },
      { label: "δ¹³C", render: (s) => num(s.d13C), cls: "num" },
      { label: "%C", render: (s) => num(s.pct_C, 1), cls: "num" },
      { label: "%N", render: (s) => num(s.pct_N, 1), cls: "num" },
      { label: "C:N", render: (s) => `<span class="${cnBad(s) ? "bad" : ""}">${num(s.cn_ratio)}</span>`, cls: "num" },
      { label: "Notes", key: "notes" },
      { label: "<span class='sr-only'>Remove</span>", render: (s) => `<button class="ghost tiny" data-remove="${state.samples.indexOf(s)}" aria-label="Remove sample at ${esc(s.position_mm)} mm from ${esc(s.specimen_id)}">✕</button>` },
    ],
    state.samples
  );
}

async function loadFile(file) {
  try {
    setReport(await api.uploadFile(file));
    toast(`Loaded ${state.samples.length} samples from ${file.name}`, "ok");
  } catch (e) {
    toast(e.message);
  }
}

async function addManualSample(ev) {
  ev.preventDefault();
  const form = ev.target;
  const data = Object.fromEntries(new FormData(form).entries());
  const step = parseFloat(data.step) || 1;
  delete data.step;
  const msg = $("#manual-msg");
  try {
    const check = await api.validateRecords([data]);
    const errors = check.issues.filter((i) => i.severity === "error");
    form.querySelectorAll(".invalid").forEach((n) => {
      n.classList.remove("invalid");
      n.removeAttribute("aria-invalid");
    });
    if (errors.length) {
      errors.forEach((e) => {
        const f = form.elements[e.field];
        if (f) {
          f.classList.add("invalid");
          f.setAttribute("aria-invalid", "true");
        }
      });
      msg.className = "inline-msg error";
      msg.textContent = errors.map((e) => `${e.field}: ${e.message}`).join("; ");
      return;
    }
    state.samples.push(check.samples[0]);
    await revalidate();
    msg.className = "inline-msg ok";
    msg.textContent = `Added ${check.samples[0].specimen_id} @ ${check.samples[0].position_mm} mm`;
    form.elements.position_mm.value = (parseFloat(data.position_mm) + step).toFixed(1);
    for (const f of ["d15N", "d13C", "pct_C", "pct_N", "cn_ratio", "collagen_yield_pct"]) form.elements[f].value = "";
    form.elements.d15N.focus();
  } catch (e) {
    msg.className = "inline-msg error";
    msg.textContent = e.message;
  }
}

// ───────────────────────── 2. settings ─────────────────────────
const FIELDS = {
  reported_milestone: ["#opt-milestone", "value"],
  analytical_sd_permil: ["#opt-sd", "number-or-null"],
  min_weaning_drop_permil: ["#opt-mindrop", "number"],
  monte_carlo_draws: ["#opt-draws", "number"],
  uncertainty: ["#opt-uncertainty", "value"],
  bootstrap_draws: ["#opt-boot", "number"],
  time_averaging: ["#opt-timeavg", "checked"],
  increment_width_mm: ["#opt-incwidth", "number"],
  growth_layer_offset_mm: ["#opt-layeroffset", "number"],
  inner_dentine_weight: ["#opt-innerweight", "number"],
  seasonal_term: ["#opt-seasonal", "checked"],
  season_period_months: ["#opt-period", "number"],
  elbow_normalise: ["#opt-elbownorm", "checked"],
  constrain_adult_plateau: ["#opt-constrain", "checked"],
};

function initSettings() {
  const d = state.config.defaults;
  $("#model-options").innerHTML = state.config.models
    .map(
      (m) => `<label class="check model-opt">
        <input type="checkbox" name="model" value="${m.name}" ${d.models.includes(m.name) ? "checked" : ""}>
        ${swatch(m.name)}
        <span><strong>${esc(m.label)}</strong> ${m.name === "two_phase" ? help("two_phase") : m.name === "elbow" ? help("elbow") : ""}<br><small>${esc(m.description)}</small></span>
      </label>`
    )
    .join("");
  const cmpModel = $("#cmp-model");
  for (const m of state.config.models) cmpModel.insertAdjacentHTML("beforeend", `<option value="${m.name}">${esc(m.label)}</option>`);
  applySettings(d);
}

/** Put an options object (defaults, or a loaded project's settings) into the form. */
function applySettings(o) {
  if (o.models) $$('input[name="model"]').forEach((i) => (i.checked = o.models.includes(i.value)));
  if (o.transition_threshold != null) $("#opt-threshold").value = Math.round(o.transition_threshold * 100);
  for (const [key, [sel, kind]] of Object.entries(FIELDS)) {
    if (!(key in o)) continue;
    const input = $(sel);
    if (kind === "checked") input.checked = !!o[key];
    else input.value = o[key] ?? "";
  }
  for (const [k, v] of Object.entries(o.qc || {})) {
    const input = $(`#qc-${k}`);
    if (!input) continue;
    if (input.type === "checkbox") input.checked = v;
    else input.value = v;
  }
  if (o.growth_overrides) state.overrides = { ...o.growth_overrides };
  if (o.adult_baselines) state.baselines = { ...o.adult_baselines };
  if (o.growth_tables) state.editedTables = Object.fromEntries(o.growth_tables.map((t) => [`${t.species}:${t.tooth}`, t]));
}

/** Current settings as an AnalysisOptions payload. */
function settings() {
  const qc = {};
  for (const k of Object.keys(state.config.defaults.qc)) {
    const input = $(`#qc-${k}`);
    qc[k] = input.type === "checkbox" ? input.checked : Number(input.value);
  }
  const out = {
    models: $$('input[name="model"]:checked').map((i) => i.value),
    transition_threshold: (Number($("#opt-threshold").value) || 5) / 100,
    random_seed: 42,
    qc,
    growth_overrides: state.overrides,
    adult_baselines: state.baselines,
    growth_tables: Object.values(state.editedTables).map(({ saved, ...t }) => t),
  };
  const d = state.config.defaults;
  for (const [key, [sel, kind]] of Object.entries(FIELDS)) {
    const input = $(sel);
    if (kind === "checked") out[key] = input.checked;
    else if (kind === "value") out[key] = input.value;
    else if (input.value === "") out[key] = kind === "number-or-null" ? null : d[key];
    else out[key] = Number(input.value);
  }
  if (!out.analytical_sd_permil) out.analytical_sd_permil = null;
  return out;
}

function renderBaselines() {
  const keys = [...new Set(state.samples.map((s) => `${s.site}:${s.species}`))];
  $("#baseline-list").innerHTML = keys.length
    ? keys
        .map((key) => {
          const b = state.baselines[key] || {};
          return `<div class="baseline-row" data-key="${esc(key)}">
            <span class="key">${esc(key.replace(":", " · "))}</span>
            <label>Mean δ¹⁵N (‰)<input type="number" step="0.01" class="bl-mean" value="${b.mean ?? ""}" placeholder="TBD-LAB"></label>
            <label>SD (‰)<input type="number" step="0.01" min="0.01" class="bl-sd" value="${b.sd ?? ""}" placeholder="0.5"></label>
          </div>`;
        })
        .join("")
    : '<p class="muted">Load data to enter baselines for each site and species.</p>';
}

function syncBaseline(row) {
  const mean = row.querySelector(".bl-mean").value;
  const sd = Number(row.querySelector(".bl-sd").value) || 0.5;
  if (mean === "") delete state.baselines[row.dataset.key];
  else state.baselines[row.dataset.key] = { mean: Number(mean), sd };
  persist();
}

async function runAnalysis() {
  const msg = $("#run-msg");
  const opts = settings();
  if (!state.samples.length) return toast("Load some data first.");
  if (!opts.models.length) return toast("Choose at least one curve model.");
  const btn = $("#btn-run");
  btn.disabled = true;
  msg.className = "inline-msg";
  msg.textContent = "";
  progressBar($("#run-progress"), 0, 0, "Fitting specimens");
  try {
    const out = await api.analyze(state.samples, opts, (d, t) => progressBar($("#run-progress"), d, t, "Fitting specimens"));
    state.results = out.results;
    state.estimates = out.estimates;
    state.options = opts;
    state.current = out.results[0]?.specimen_id;
    state.visible = new Set([...opts.models, "average"]);
    state.zoom = null;
    enableResultSteps(true);
    renderResults();
    show("results");
    persist();
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    $("#run-progress").hidden = true;
  }
}

// ───────────────────────── 3. results ─────────────────────────
const isInfo = (w) => /PLACEHOLDER|^Time averaging on|teeth .* combined/.test(w);

function renderResults() {
  const milestone = state.options.reported_milestone;
  $("#result-list").innerHTML = state.results
    .map((r) => {
      const best = r.fits.find((f) => f.model === r.best_model);
      const m = best?.[milestone];
      const warn = r.warnings.filter((w) => !isInfo(w)).length + r.fits.reduce((n, f) => n + f.warnings.length, 0);
      const sel = r.specimen_id === state.current;
      return `<li><button role="option" aria-selected="${sel}" tabindex="${sel ? 0 : -1}" data-specimen="${esc(r.specimen_id)}" class="${sel ? "active" : ""}">
        <span><strong>${esc(r.specimen_id)}</strong><small>${esc(r.site)} · ${esc(r.species)} ${esc(r.tooth)}</small></span>
        <span class="pill">${m ? `${num(m.estimate, 1)} mo` : "—"}${warn ? ` <span class="warn-dot" aria-label="${warn} warning(s)">!</span>` : ""}</span>
      </button></li>`;
    })
    .join("");
  const res = state.results.find((r) => r.specimen_id === state.current) || state.results[0];
  if (!res) return;

  $("#res-title").textContent = res.specimen_id;
  $("#res-meta").innerHTML = `${esc(res.site)} · ${esc(res.species)} ${esc(res.tooth)}${res.period ? ` · ${esc(res.period)}` : ""} · age model: ${esc(res.growth_table)} ${res.growth_placeholder ? tbdBadge : ""}`;

  const toggles = [...res.fits.map((f) => [f.model, f.label.split(" (")[0]]), ...(Object.keys(res.model_average || {}).length ? [["average", "Model average"]] : [])];
  $("#curve-toggles").innerHTML = toggles
    .map(([m, label]) => `<label class="check toggle"><input type="checkbox" data-model="${m}" ${state.visible.has(m) ? "checked" : ""}>${swatch(m)}${esc(label)}</label>`)
    .join("");

  const best = res.fits.find((f) => f.model === res.best_model);
  const bm = best?.[milestone];
  const avg = res.model_average?.[milestone];
  const extra = best?.model === "two_phase"
    ? ` Staged weaning: an intermediate plateau at ${num(best.extra.intermediate_d15N, 1)}‰ lasting about ${num(best.extra.supplementation_months, 1)} months (supplementary feeding while suckling).`
    : "";
  $("#res-summary").innerHTML = best && bm
    ? `Best-supported model: <strong>${esc(best.label)}</strong>. Estimated weaning ${milestone}: <strong>${num(bm.estimate, 1)} months</strong>${bm.ci_low != null ? ` (95% interval ${ci(bm)})` : ""}.
       ${avg ? `Averaged over all models: <strong>${num(avg.estimate, 1)} months</strong>${avg.ci_low != null ? ` (${ci(avg)})` : ""}.` : ""}
       Nursing δ¹⁵N ≈ ${num(best.nursing_d15N, 1)}‰, adult ≈ ${num(best.adult_d15N, 1)}‰ (drop ${num(best.drop_permil, 1)}‰)${best.enrichment_permil != null ? `; ${num(best.enrichment_permil, 1)}‰ above adult females` : ""}.${extra}
       ${res.growth_placeholder ? '<span class="tbd-inline">Illustrative only: placeholder age model.</span>' : ""}`
    : best
      ? `Best-supported model: <strong>${esc(best.label)}</strong>, which does not report a ${milestone}${avg ? `; the model average is <strong>${num(avg.estimate, 1)} months</strong>` : ""}.`
      : "No model could be fitted to this specimen.";

  if (res.points.length) {
    curveChart($("#res-chart"), curveOptions(res, {
      visible: state.visible,
      milestone,
      xRange: state.zoom,
      showD13C: $("#opt-show13c").checked,
      onZoom: (range) => {
        state.zoom = range;
        renderResults();
      },
    }));
  } else {
    $("#res-chart").innerHTML = '<p class="muted">No data points to plot.</p>';
  }
  $("#btn-zoom-reset").hidden = !state.zoom;

  const warnings = [...res.warnings, ...res.fits.flatMap((f) => f.warnings.map((w) => `${f.label}: ${w}`))];
  $("#res-warnings").innerHTML = warnings
    .map((w) => `<li class="${/PLACEHOLDER/.test(w) ? "tbd-li" : isInfo(w) ? "info" : "warning"}">${esc(w)}</li>`)
    .join("");
  const dg = res.diagnostics || {};
  const diag = [
    dg.residual_seasonal_p != null && `annual cycle in residuals: ${num(dg.residual_seasonal_amplitude)}‰ (p ${pval(dg.residual_seasonal_p)})`,
    dg.d13C_seasonal_p != null && `annual cycle in δ¹³C: ${num(dg.d13C_seasonal_amplitude)}‰ (p ${pval(dg.d13C_seasonal_p)})`,
    dg.d13C_d15N_spearman != null && `δ¹³C–δ¹⁵N correlation ρ = ${num(dg.d13C_d15N_spearman)}`,
  ].filter(Boolean);
  $("#res-diagnostics").innerHTML = diag.length ? `<p class="muted small">Seasonality checks ${help("seasonal")}: ${diag.join(" · ")}</p>` : "";

  const avgRow = Object.keys(res.model_average || {}).length
    ? [{ model: "average", label: "Model average", converged: true, ...res.model_average, isAverage: true }]
    : [];
  table(
    $("#fit-table"),
    [
      { label: "Model", render: (f) => `${swatch(f.model)}${esc(f.label)}${f.model === res.best_model ? ' <span class="pill best">best</span>' : ""}` },
      ...MILESTONES.map((k) => ({
        label: k[0].toUpperCase() + k.slice(1),
        cls: "num",
        render: (f) => (f[k] ? `${num(f[k].estimate, 1)}<br><small>${ci(f[k])}</small>` : "—"),
      })),
      { label: "Nursing δ¹⁵N", render: (f) => num(f.nursing_d15N), cls: "num" },
      { label: "Adult δ¹⁵N", render: (f) => num(f.adult_d15N), cls: "num" },
      { label: "Drop (‰)", render: (f) => num(f.drop_permil), cls: "num" },
      { label: "Enrichment vs ♀ (‰)", title: "Nursing δ15N minus adult-female baseline", render: (f) => num(f.enrichment_permil), cls: "num" },
      { label: "RMSE", render: (f) => num(f.rmse, 3), cls: "num" },
      { label: "ΔAICc", render: (f) => num(f.delta_aicc, 2), cls: "num" },
      { label: "Weight", render: (f) => num(f.akaike_weight, 2), cls: "num" },
      {
        label: "Notes",
        render: (f) => {
          if (f.isAverage) return '<small class="muted">weighted by Akaike weight</small>';
          if (!f.converged) return `<span class="warn-text">${esc(f.message)}</span>`;
          const e = f.extra || {};
          const bits = [];
          if (e.intermediate_d15N != null) bits.push(`intermediate ${num(e.intermediate_d15N, 1)}‰ for ${num(e.supplementation_months, 1)} mo`);
          if (e.seasonal_amplitude_permil != null) bits.push(`seasonal ±${num(e.seasonal_amplitude_permil)}‰`);
          return `<small>${bits.join("; ") || "fitted"}</small>`;
        },
      },
    ],
    [...res.fits, ...avgRow],
    (f) => (f.model === res.best_model ? "best-row" : f.isAverage ? "avg-row" : "")
  );
}

// ───────────────────────── 4. compare ─────────────────────────
function compareRequest() {
  return {
    estimates: state.estimates,
    group_by: $$('input[name="group"]:checked').map((i) => i.value),
    milestone: $("#cmp-milestone").value,
    model: $("#cmp-model").value || null,
  };
}

async function refreshCompare() {
  if (!state.estimates) return;
  const body = compareRequest();
  if (!body.group_by.length) return toast("Choose at least one grouping.");
  const { group_by, milestone, model } = body;
  try {
    const out = await api.aggregate(body);
    state.lastCompare = out;
    const label = (row) => group_by.map((g) => row[g] ?? "—").join(" · ");
    const rows = state.estimates.filter((e) => (model ? e.model === model : e.is_best));
    const re = Object.fromEntries(out.tests.groups.map((g) => [g.group, g]));
    forestChart(
      $("#cmp-chart"),
      out.summary.map((s) => {
        const g = re[label(s)];
        return {
          label: label(s),
          mean: g ? g.mean : s.mean,
          lo: g ? g.ci_low : s.ci95_low,
          hi: g ? g.ci_high : s.ci95_high,
          values: rows
            .filter((r) => group_by.every((k) => (r[k] ?? "—") === s[k]))
            .filter((r) => r[milestone] != null)
            .map((r) => ({ v: r[milestone], label: `${esc(r.specimen_id)}: ${num(r[milestone], 1)} mo (${r.model})` })),
        };
      }),
      `Weaning ${milestone} (months): random-effects mean ± 95% CI, dots = specimens`
    );
    table(
      $("#cmp-table"),
      [
        ...group_by.map((g) => ({ label: g[0].toUpperCase() + g.slice(1), key: g })),
        { label: "Estimates", key: "model" },
        { label: "n", key: "n", cls: "num" },
        { label: "Mean", render: (r) => num(r.mean, 1), cls: "num" },
        { label: "SD", render: (r) => num(r.sd, 1), cls: "num" },
        { label: "Median", render: (r) => num(r.median, 1), cls: "num" },
        { label: "Range", render: (r) => `${num(r.min, 1)}–${num(r.max, 1)}`, cls: "num" },
        { label: "95% CI (t)", render: (r) => (r.ci95_low != null ? `${num(r.ci95_low, 1)}–${num(r.ci95_high, 1)}` : "—"), cls: "num" },
      ],
      out.summary
    );
    renderTests(out.tests);
    const models = state.options.models;
    table(
      $("#dis-table"),
      [
        { label: "Specimen", key: "specimen_id" },
        { label: "Site", key: "site" },
        { label: "Species", key: "species" },
        ...models.map((m) => ({ label: esc(m), render: (r) => num(r[m], 1), cls: "num" })),
        { label: "Range (months)", render: (r) => `<strong>${num(r.range, 1)}</strong>`, cls: "num" },
      ],
      out.disagreement
    );
    $("#val-body").innerHTML = out.validation.length
      ? '<div class="table-wrap"><table id="val-table"></table></div>'
      : `<div class="tbd tbd-block">${tbdBadge} No known-age reference animals or published estimates in this dataset. Add a
         <code>known_weaning_age_months</code> column for modern reference animals, or a
         <code>published_weaning_age_months</code> column to compare with published estimates (e.g. WEAN or
         visual readings), to see bias, MAE, RMSE and interval coverage for each model here.</div>`;
    if (out.validation.length) {
      table(
        $("#val-table"),
        [
          { label: "Reference", key: "reference" },
          { label: "Model", key: "model" },
          { label: "n", key: "n", cls: "num" },
          { label: "Bias", render: (r) => num(r.bias), cls: "num" },
          { label: "MAE", render: (r) => num(r.mae), cls: "num" },
          { label: "RMSE", render: (r) => num(r.rmse), cls: "num" },
          { label: "Pearson r", render: (r) => num(r.pearson_r), cls: "num" },
          { label: "95% interval coverage", render: (r) => (r.ci_coverage != null ? `${Math.round(r.ci_coverage * 100)}%` : "—"), cls: "num" },
        ],
        out.validation
      );
    }
  } catch (e) {
    toast(e.message);
  }
}

function renderTests(t) {
  const groups = t.groups
    .map((g) => `<tr><td>${esc(g.group)}</td><td class="num">${g.n}</td><td class="num">${num(g.mean, 1)}</td><td class="num">${num(g.ci_low, 1)}–${num(g.ci_high, 1)}</td><td class="num">${num(g.tau, 2)}</td></tr>`)
    .join("");
  const sig = (p) => (p != null && p < 0.05 ? ' class="sig"' : "");
  const pairs = t.pairwise
    .map((p) => `<tr><td>${esc(p.group_a)} − ${esc(p.group_b)}</td><td class="num">${num(p.difference, 1)}</td><td class="num">${num(p.se, 2)}</td><td class="num">${pval(p.p)}</td><td class="num"${sig(p.p_holm)}>${pval(p.p_holm)}</td></tr>`)
    .join("");
  const overall = t.q_p != null
    ? `<p class="summary">Do groups differ at all? Between-group Q = ${num(t.q_between, 2)} on ${t.q_df} df,
       <strong>p = ${pval(t.q_p)}</strong>; permutation test p = ${pval(t.permutation_p)}.
       ${t.q_p < 0.05 ? "There is evidence that weaning ages differ between groups." : "No clear evidence that weaning ages differ between groups."}</p>`
    : '<p class="muted">At least two groups are needed for a comparison.</p>';
  $("#tests-body").innerHTML = `${overall}
    <div class="grid-2">
      <div class="table-wrap"><table><thead><tr><th scope="col">Group</th><th scope="col">n</th><th scope="col">Mean</th><th scope="col">95% CI</th><th scope="col">τ</th></tr></thead><tbody>${groups}</tbody></table></div>
      ${pairs ? `<div class="table-wrap"><table><thead><tr><th scope="col">Pair</th><th scope="col">Difference</th><th scope="col">SE</th><th scope="col">p</th><th scope="col">p (Holm)</th></tr></thead><tbody>${pairs}</tbody></table></div>` : ""}
    </div>
    ${t.notes.map((n) => `<p class="muted small">${esc(n)}</p>`).join("")}`;

  const b = t.bayes;
  if (!b) {
    $("#bayes-body").innerHTML = '<p class="muted">Needs at least three specimens.</p>';
    return;
  }
  $("#bayes-body").innerHTML = `
    <p class="muted small">Shared between-animal SD τ = ${num(b.tau_mean, 2)} months (95% CrI ${num(b.tau_ci_low, 2)}–${num(b.tau_ci_high, 2)}) ·
      max R̂ ${num(b.rhat_max, 3)} ${help("rhat")} · ${b.draws} posterior draws${b.rhat_max > 1.05 ? ' · <span class="warn-text">not fully converged</span>' : ""}</p>
    <div class="grid-2">
      <div class="table-wrap"><table><thead><tr><th scope="col">Group</th><th scope="col">Posterior mean</th><th scope="col">95% CrI</th></tr></thead>
        <tbody>${b.groups.map((g) => `<tr><td>${esc(g.group)}</td><td class="num">${num(g.mean, 1)}</td><td class="num">${num(g.ci_low, 1)}–${num(g.ci_high, 1)}</td></tr>`).join("")}</tbody></table></div>
      <div class="table-wrap"><table><thead><tr><th scope="col">Comparison</th><th scope="col">Probability the first weaned earlier</th><th scope="col">Difference (95% CrI)</th></tr></thead>
        <tbody>${b.pairs.map((p) => `<tr><td>${esc(p.group_a)} vs ${esc(p.group_b)}</td><td class="num">${Math.round(p.prob_a_earlier * 100)}%</td><td class="num">${num(p.difference_mean, 1)} (${num(p.difference_ci_low, 1)}–${num(p.difference_ci_high, 1)})</td></tr>`).join("")}</tbody></table></div>
    </div>
    <details><summary>Specimen estimates after partial pooling</summary>
      <div class="table-wrap"><table><thead><tr><th scope="col">Specimen</th><th scope="col">Group</th><th scope="col">Own estimate</th><th scope="col">Pooled estimate</th><th scope="col">95% CrI</th></tr></thead>
      <tbody>${b.specimens.map((s) => `<tr><td>${esc(s.specimen_id)}</td><td>${esc(s.group)}</td><td class="num">${num(s.observed, 1)}</td><td class="num">${num(s.shrunk, 1)}</td><td class="num">${num(s.ci_low, 1)}–${num(s.ci_high, 1)}</td></tr>`).join("")}</tbody></table></div>
    </details>`;
}

// ───────────────────────── projects, report ─────────────────────────
function projectData() {
  return serialiseProject(state, settings(), state.config.version);
}

function persist() {
  if (state.config) autosave({ ...projectData(), plan: state.plan });
}

function restoreProject(p) {
  applySettings(p.settings || {});
  state.samples = p.samples;
  state.results = p.results || null;
  state.estimates = p.estimates || null;
  state.options = p.analysis_options || null;
  state.current = p.current || p.results?.[0]?.specimen_id;
  state.plan = p.plan || null;
  state.visible = new Set([...(state.options?.models || []), "average"]);
  enableResultSteps(!!(state.results && state.options));
  revalidate().then(() => {
    if (p.results) {
      state.results = p.results;
      state.estimates = p.estimates;
      enableResultSteps(true);
      renderResults();
    }
    if (state.plan) renderPlan(state);
  });
}

async function openProject(file) {
  try {
    restoreProject(parseProject(await file.text()));
    toast(`Opened project ${file.name}`, "ok");
  } catch (e) {
    toast(e.message);
  }
}

async function makeReport() {
  if (!state.results) return;
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

// ───────────────────────── events ─────────────────────────
function bind() {
  $$(".step").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  $("#btn-to-settings").addEventListener("click", () => show("settings"));

  const input = $("#csv-input");
  const zone = $("#dropzone");
  input.addEventListener("change", () => input.files[0] && loadFile(input.files[0]));
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    if (e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
  });
  zone.setAttribute("tabindex", "0");
  zone.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), input.click()));

  $("#btn-template").href = api.templateUrl;
  $("#btn-example").addEventListener("click", async () => {
    try {
      setReport(await api.example());
      toast("Loaded SYNTHETIC example data (simulated, not real measurements).", "ok");
    } catch (e) {
      toast(e.message);
    }
  });
  $("#btn-clear").addEventListener("click", () => {
    if (state.samples.length && !confirm("Remove all loaded samples?")) return;
    setReport({ samples: [], issues: [], specimens: [] });
  });
  $("#manual-form").addEventListener("submit", addManualSample);
  $("#sample-table").addEventListener("click", async (e) => {
    const idx = e.target.closest("[data-remove]")?.dataset.remove;
    if (idx == null) return;
    state.samples.splice(Number(idx), 1);
    await revalidate();
  });

  bindGrowthEditor(state, { refreshConfig, onChange: persist });
  $("#baseline-list").addEventListener("input", (e) => {
    const row = e.target.closest(".baseline-row");
    if (row) syncBaseline(row);
  });
  $("#view-settings").addEventListener("change", persist);
  $("#btn-run").addEventListener("click", runAnalysis);

  const list = $("#result-list");
  list.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-specimen]");
    if (!btn) return;
    state.current = btn.dataset.specimen;
    state.zoom = null;
    renderResults();
    $(`[data-specimen="${CSS.escape(state.current)}"]`)?.focus();
  });
  list.addEventListener("keydown", (e) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const ids = state.results.map((r) => r.specimen_id);
    let i = ids.indexOf(state.current);
    i = e.key === "Home" ? 0 : e.key === "End" ? ids.length - 1 : Math.min(Math.max(i + (e.key === "ArrowDown" ? 1 : -1), 0), ids.length - 1);
    state.current = ids[i];
    state.zoom = null;
    renderResults();
    $(`[data-specimen="${CSS.escape(state.current)}"]`)?.focus();
  });
  $("#curve-toggles").addEventListener("change", (e) => {
    const m = e.target.dataset.model;
    if (e.target.checked) state.visible.add(m);
    else state.visible.delete(m);
    renderResults();
  });
  $("#opt-show13c").addEventListener("change", renderResults);
  $("#btn-zoom-reset").addEventListener("click", () => {
    state.zoom = null;
    renderResults();
  });
  $("#btn-export-csv").addEventListener("click", () =>
    download("weanage_estimates.csv", new Blob([toCsv(state.estimates)], { type: "text/csv" }))
  );
  $("#btn-export-json").addEventListener("click", () =>
    download("weanage_results.json", new Blob([JSON.stringify({ options: state.options, results: state.results }, null, 2)], { type: "application/json" }))
  );
  $("#btn-export-svg").addEventListener("click", () => {
    const svg = $("#res-chart svg");
    if (svg) download(`${state.current}_weaning_curve.svg`, svgToBlob(svg));
  });

  $$('input[name="group"], #cmp-milestone, #cmp-model').forEach((n) => n.addEventListener("change", refreshCompare));

  $("#btn-save").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify({ ...projectData(), plan: state.plan }, null, 1)], { type: "application/json" });
    download(`weanage_project_${new Date().toISOString().slice(0, 10)}.weanage.json`, blob);
  });
  $("#project-input").addEventListener("change", (e) => e.target.files[0] && openProject(e.target.files[0]));
  $("#btn-report").addEventListener("click", makeReport);
  $("#btn-help").addEventListener("click", () => startTour(show));
}

function offerRestore() {
  const saved = loadAutosave();
  if (!saved || !saved.samples?.length) return;
  $("#restore-when").textContent = `${saved.samples.length} samples, ${new Date(saved.saved_at).toLocaleString()}`;
  $("#restore-banner").hidden = false;
  $("#btn-restore").addEventListener("click", () => {
    restoreProject(saved);
    $("#restore-banner").hidden = true;
  });
  $("#btn-discard").addEventListener("click", () => {
    clearAutosave();
    $("#restore-banner").hidden = true;
  });
}

async function init() {
  try {
    state.config = await api.config();
  } catch (e) {
    toast(`Could not reach the WeanAge backend: ${e.message}`);
    return;
  }
  initSettings();
  initPlanner(state);
  renderTbd();
  fillHelpSlots();
  initGlossary();
  bind();
  renderData();
  offerRestore();
  if (!tourSeen()) startTour(show);
}

init();
