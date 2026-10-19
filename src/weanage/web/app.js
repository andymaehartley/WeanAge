import { api } from "./api.js";
import { curveChart, forestChart, svgToBlob } from "./chart.js";

const MODEL_COLORS = { logistic: "#2f6fdf", piecewise: "#0f9d8a", exponential: "#b5459b" };
const MILESTONES = ["onset", "midpoint", "completion"];

const state = {
  config: null,
  tbdIds: new Set(),
  samples: [],
  report: null,
  overrides: {}, // "species:tooth" -> {initiation_age_months, extension_rate_mm_per_month}
  results: null,
  estimates: null,
  current: null,
  visible: new Set(Object.keys(MODEL_COLORS)),
};

// ───────────────────────── helpers ─────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

const num = (v, d = 2) => (v == null || !isFinite(v) ? "—" : Number(v).toFixed(d));
const ci = (x) => (x && x.ci_low != null ? `${num(x.ci_low, 1)}–${num(x.ci_high, 1)}` : "");

function toast(message, kind = "error") {
  const t = $("#toast");
  t.textContent = message;
  t.className = `toast ${kind}`;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 6000);
}

function download(name, blob) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function toCsv(rows) {
  if (!rows.length) return "";
  const cols = Object.keys(rows[0]);
  const cell = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.join(","), ...rows.map((r) => cols.map((c) => cell(r[c])).join(","))].join("\n");
}

function table(el, columns, rows, rowClass = () => "") {
  const head = columns.map((c) => `<th title="${esc(c.title || "")}">${c.label}</th>`).join("");
  const body = rows
    .map((r) => `<tr class="${rowClass(r)}">${columns.map((c) => `<td class="${c.cls || ""}">${c.render ? c.render(r) : esc(r[c.key])}</td>`).join("")}</tr>`)
    .join("");
  el.innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="${columns.length}" class="muted">Nothing to show</td></tr>`}</tbody>`;
}

const tbdBadge = '<span class="tbd-badge" title="Placeholder awaiting lab work">TBD-LAB</span>';

// ───────────────────────── navigation ─────────────────────────
function show(view) {
  $$(".step").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  if (view === "settings") renderGrowthList();
  if (view === "compare") refreshCompare();
  window.scrollTo({ top: 0 });
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
    if (!state.tbdIds.has(node.dataset.tbd)) return;
    node.classList.add("tbd");
    const target = node.matches("label") ? node : node.querySelector("h2");
    if (target && !target.querySelector(".tbd-badge")) target.insertAdjacentHTML("beforeend", ` ${tbdBadge}`);
  });
}

// ───────────────────────── 1. data ─────────────────────────
function setReport(report) {
  state.report = report;
  state.samples = report.samples;
  state.results = null;
  $$('.step[data-view="results"], .step[data-view="compare"]').forEach((b) => (b.disabled = true));
  renderData();
}

async function revalidate() {
  setReport(await api.validateRecords(state.samples));
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
  const tables = Object.fromEntries(state.config.growth_tables.map((t) => [`${t.species}:${t.tooth}`, t]));
  table(
    $("#specimen-table"),
    [
      { label: "Specimen", key: "specimen_id" },
      { label: "Site", key: "site" },
      { label: "Species", key: "species" },
      { label: "Tooth", key: "tooth" },
      { label: "Samples", key: "n_samples", cls: "num" },
      {
        label: "Age model",
        render: (s) => {
          const t = tables[`${s.species}:${s.tooth}`];
          if (!t) return '<span class="warn-text">none — add a custom model in Settings</span>';
          return `${esc(t.label)} ${t.placeholder ? tbdBadge : ""}`;
        },
      },
    ],
    report ? report.specimens : []
  );

  const qc = currentOptions().qc;
  const cnBad = (s) => s.cn_ratio != null && (s.cn_ratio < qc.cn_min || s.cn_ratio > qc.cn_max);
  table(
    $("#sample-table"),
    [
      { label: "Specimen", key: "specimen_id" },
      { label: "Position (mm)", key: "position_mm", cls: "num" },
      { label: "δ¹⁵N", render: (s) => num(s.d15N), cls: "num" },
      { label: "δ¹³C", render: (s) => num(s.d13C), cls: "num" },
      { label: "%C", render: (s) => num(s.pct_C, 1), cls: "num" },
      { label: "%N", render: (s) => num(s.pct_N, 1), cls: "num" },
      { label: "C:N", render: (s) => `<span class="${cnBad(s) ? "bad" : ""}">${num(s.cn_ratio)}</span>`, cls: "num" },
      { label: "Notes", key: "notes" },
      { label: "", render: (s) => `<button class="ghost tiny" data-remove="${state.samples.indexOf(s)}" title="Remove sample">✕</button>` },
    ],
    state.samples
  );
}

async function loadCsv(file) {
  try {
    setReport(await api.uploadCsv(file));
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
    form.querySelectorAll(".invalid").forEach((n) => n.classList.remove("invalid"));
    if (errors.length) {
      errors.forEach((e) => form.elements[e.field]?.classList.add("invalid"));
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
function initSettings() {
  const d = state.config.defaults;
  $("#model-options").innerHTML = state.config.models
    .map(
      (m) => `<label class="check model-opt">
        <input type="checkbox" name="model" value="${m.name}" ${d.models.includes(m.name) ? "checked" : ""}>
        <span class="swatch" style="background:${MODEL_COLORS[m.name]}"></span>
        <span><strong>${esc(m.label)}</strong><br><small>${esc(m.description)}</small></span>
      </label>`
    )
    .join("");
  $("#opt-milestone").value = d.reported_milestone;
  $("#opt-threshold").value = Math.round(d.transition_threshold * 100);
  $("#opt-sd").value = d.analytical_sd_permil ?? "";
  $("#opt-mindrop").value = d.min_weaning_drop_permil;
  $("#opt-draws").value = d.monte_carlo_draws;
  for (const [k, v] of Object.entries(d.qc)) {
    const input = $(`#qc-${k}`);
    if (!input) continue;
    if (input.type === "checkbox") input.checked = v;
    else input.value = v;
  }
  const cmpModel = $("#cmp-model");
  for (const m of state.config.models) cmpModel.insertAdjacentHTML("beforeend", `<option value="${m.name}">${esc(m.label)}</option>`);
}

function currentOptions() {
  const val = (id) => {
    const v = $(id).value;
    return v === "" ? null : Number(v);
  };
  const qc = {};
  for (const k of Object.keys(state.config.defaults.qc)) {
    const input = $(`#qc-${k}`);
    qc[k] = input.type === "checkbox" ? input.checked : Number(input.value);
  }
  return {
    models: $$('input[name="model"]:checked').map((i) => i.value),
    reported_milestone: $("#opt-milestone").value,
    transition_threshold: (val("#opt-threshold") ?? 5) / 100,
    analytical_sd_permil: val("#opt-sd") || null,
    min_weaning_drop_permil: val("#opt-mindrop") ?? 0,
    monte_carlo_draws: val("#opt-draws") ?? 1000,
    random_seed: 42,
    qc,
    growth_overrides: state.overrides,
  };
}

function renderGrowthList() {
  const combos = [...new Map(state.samples.map((s) => [`${s.species}:${s.tooth}`, s])).keys()];
  const tables = Object.fromEntries(state.config.growth_tables.map((t) => [`${t.species}:${t.tooth}`, t]));
  const keys = combos.length ? combos : Object.keys(tables);
  $("#growth-list").innerHTML = keys
    .map((key) => {
      const t = tables[key];
      const o = state.overrides[key];
      const knots = t
        ? `<table class="knots"><tr><th>mm</th>${t.knots.map((k) => `<td>${k.position_mm}</td>`).join("")}</tr>
           <tr><th>months</th>${t.knots.map((k) => `<td>${k.age_months}</td>`).join("")}</tr></table>
           <p class="muted small">± ${t.age_uncertainty_months} months · ${esc(t.source)}</p>`
        : '<p class="warn-text">No bundled table for this species/tooth — a custom model is required.</p>';
      return `<div class="growth-item ${t && t.placeholder && !o ? "tbd" : ""}" data-key="${esc(key)}">
        <h3>${esc(key.replace(":", " · "))} ${t && t.placeholder && !o ? tbdBadge : ""}</h3>
        ${knots}
        <label class="check"><input type="checkbox" class="ovr-toggle" ${o ? "checked" : ""}> Use custom linear model</label>
        <div class="form-grid ovr-fields" ${o ? "" : "hidden"}>
          <label>Age at crown initiation (months)<input type="number" step="0.1" class="ovr-init" value="${o ? o.initiation_age_months : 0}"></label>
          <label>Extension rate (mm / month)<input type="number" step="0.1" min="0.01" class="ovr-rate" value="${o ? o.extension_rate_mm_per_month : 3}"></label>
        </div>
      </div>`;
    })
    .join("");
}

function syncOverride(item) {
  const key = item.dataset.key;
  const on = item.querySelector(".ovr-toggle").checked;
  item.querySelector(".ovr-fields").hidden = !on;
  if (!on) delete state.overrides[key];
  else {
    state.overrides[key] = {
      initiation_age_months: Number(item.querySelector(".ovr-init").value) || 0,
      extension_rate_mm_per_month: Number(item.querySelector(".ovr-rate").value) || 1,
    };
  }
}

async function runAnalysis() {
  const msg = $("#run-msg");
  const opts = currentOptions();
  if (!state.samples.length) return toast("Load some data first.");
  if (!opts.models.length) return toast("Choose at least one curve model.");
  const btn = $("#btn-run");
  btn.disabled = true;
  msg.className = "inline-msg";
  msg.textContent = "Fitting curves…";
  try {
    const out = await api.analyze(state.samples, opts);
    state.results = out.results;
    state.estimates = out.estimates;
    state.options = opts;
    state.current = out.results[0]?.specimen_id;
    state.visible = new Set(opts.models);
    $$('.step[data-view="results"], .step[data-view="compare"]').forEach((b) => (b.disabled = false));
    msg.textContent = "";
    renderResults();
    show("results");
  } catch (e) {
    msg.textContent = "";
    toast(e.message);
  } finally {
    btn.disabled = false;
  }
}

// ───────────────────────── 3. results ─────────────────────────
function reported(fit) {
  return fit ? fit[state.options.reported_milestone] : null;
}

function renderResults() {
  const milestone = state.options.reported_milestone;
  $("#result-list").innerHTML = state.results
    .map((r) => {
      const best = r.fits.find((f) => f.model === r.best_model);
      const m = reported(best);
      const warn = r.warnings.filter((w) => !/PLACEHOLDER/.test(w)).length + r.fits.reduce((n, f) => n + f.warnings.length, 0);
      return `<li><button data-specimen="${esc(r.specimen_id)}" class="${r.specimen_id === state.current ? "active" : ""}">
        <span><strong>${esc(r.specimen_id)}</strong><small>${esc(r.site)} · ${esc(r.species)}</small></span>
        <span class="pill">${m ? `${num(m.estimate, 1)} mo` : "—"}${warn ? ' <span class="warn-dot" title="Has warnings">!</span>' : ""}</span>
      </button></li>`;
    })
    .join("");
  const res = state.results.find((r) => r.specimen_id === state.current) || state.results[0];
  if (!res) return;

  $("#res-title").textContent = res.specimen_id;
  $("#res-meta").innerHTML = `${esc(res.site)} · ${esc(res.species)} ${esc(res.tooth)}${res.period ? ` · ${esc(res.period)}` : ""} · age model: ${esc(res.growth_table)} ${res.growth_placeholder ? tbdBadge : ""}`;

  $("#curve-toggles").innerHTML = res.fits
    .map((f) => `<label class="check toggle"><input type="checkbox" data-model="${f.model}" ${state.visible.has(f.model) ? "checked" : ""}>
      <span class="swatch" style="background:${MODEL_COLORS[f.model]}"></span>${esc(f.label.split(" (")[0])}</label>`)
    .join("");

  const best = res.fits.find((f) => f.model === res.best_model);
  const bm = reported(best);
  $("#res-summary").innerHTML = best && bm
    ? `Best-supported model: <strong>${esc(best.label)}</strong>. Estimated weaning ${milestone}: <strong>${num(bm.estimate, 1)} months</strong>${bm.ci_low != null ? ` (95% interval ${ci(bm)} months)` : ""}. Nursing δ¹⁵N ≈ ${num(best.nursing_d15N, 1)}‰, adult ≈ ${num(best.adult_d15N, 1)}‰ (drop ${num(best.drop_permil, 1)}‰).${res.growth_placeholder ? ' <span class="tbd-inline">Illustrative only: placeholder age model.</span>' : ""}`
    : "No model could be fitted to this specimen.";

  const fits = res.fits.filter((f) => f.converged && state.visible.has(f.model));
  if (res.points.length) {
    curveChart($("#res-chart"), {
      xLabel: "Age at dentine formation (months)",
      yLabel: "δ¹⁵N (‰ AIR)",
      points: res.points.map((p) => ({
        x: p.age_months,
        y: p.d15N,
        used: p.used_in_fit,
        extrapolated: p.extrapolated,
        label: `${p.position_mm} mm → ${num(p.age_months, 1)} mo<br>δ¹⁵N ${num(p.d15N)}‰${p.qc_flags.length ? `<br><em>${esc(p.qc_flags.join(", "))}</em>` : ""}`,
      })),
      curves: fits.map((f) => ({ name: f.model, color: MODEL_COLORS[f.model], xs: f.curve_age, ys: f.curve_d15N })),
      markers: fits
        .map((f) => ({ f, m: reported(f) }))
        .filter(({ m }) => m && m.estimate != null)
        .map(({ f, m }) => ({ x: m.estimate, lo: m.ci_low, hi: m.ci_high, color: MODEL_COLORS[f.model], label: `${num(m.estimate, 1)} mo` })),
    });
  } else {
    $("#res-chart").innerHTML = '<p class="muted">No data points to plot.</p>';
  }

  const warnings = [...res.warnings, ...res.fits.flatMap((f) => f.warnings.map((w) => `${f.label}: ${w}`))];
  $("#res-warnings").innerHTML = warnings.map((w) => `<li class="${/PLACEHOLDER/.test(w) ? "tbd-li" : "warning"}">${esc(w)}</li>`).join("");

  table(
    $("#fit-table"),
    [
      { label: "Model", render: (f) => `<span class="swatch" style="background:${MODEL_COLORS[f.model]}"></span>${esc(f.label)}${f.model === res.best_model ? ' <span class="pill best">best</span>' : ""}` },
      ...MILESTONES.map((k) => ({
        label: k[0].toUpperCase() + k.slice(1),
        cls: "num",
        render: (f) => (f[k] ? `${num(f[k].estimate, 1)}<br><small>${ci(f[k])}</small>` : "—"),
      })),
      { label: "Nursing δ¹⁵N", render: (f) => num(f.nursing_d15N), cls: "num" },
      { label: "Adult δ¹⁵N", render: (f) => num(f.adult_d15N), cls: "num" },
      { label: "Drop (‰)", render: (f) => num(f.drop_permil), cls: "num" },
      { label: "RMSE", render: (f) => num(f.rmse, 3), cls: "num" },
      { label: "R²", render: (f) => num(f.r2, 3), cls: "num" },
      { label: "ΔAICc", render: (f) => num(f.delta_aicc, 2), cls: "num" },
      { label: "Weight", render: (f) => num(f.akaike_weight, 2), cls: "num" },
      { label: "Status", render: (f) => (f.converged ? "fitted" : `<span class="warn-text">${esc(f.message)}</span>`) },
    ],
    res.fits,
    (f) => (f.model === res.best_model ? "best-row" : "")
  );
}

// ───────────────────────── 4. compare ─────────────────────────
async function refreshCompare() {
  if (!state.estimates) return;
  const group_by = $$('input[name="group"]:checked').map((i) => i.value);
  if (!group_by.length) return toast("Choose at least one grouping.");
  const milestone = $("#cmp-milestone").value;
  const model = $("#cmp-model").value || null;
  try {
    const out = await api.aggregate({ estimates: state.estimates, group_by, milestone, model });
    const label = (row) => group_by.map((g) => row[g]).join(" · ");
    const rows = state.estimates.filter((e) => (model ? e.model === model : e.is_best));
    forestChart(
      $("#cmp-chart"),
      out.summary.map((s) => ({
        label: label(s),
        mean: s.mean,
        lo: s.ci95_low,
        hi: s.ci95_high,
        values: rows
          .filter((r) => group_by.every((g) => (r[g] ?? "—") === s[g]))
          .filter((r) => r[milestone] != null)
          .map((r) => ({ v: r[milestone], label: `${esc(r.specimen_id)}: ${num(r[milestone], 1)} mo (${r.model})` })),
      })),
      `Weaning ${milestone} (months)`
    );
    table(
      $("#cmp-table"),
      [
        ...group_by.map((g) => ({ label: g[0].toUpperCase() + g.slice(1), key: g })),
        { label: "Model", key: "model" },
        { label: "n", key: "n", cls: "num" },
        { label: "Mean", render: (r) => num(r.mean, 1), cls: "num" },
        { label: "SD", render: (r) => num(r.sd, 1), cls: "num" },
        { label: "Median", render: (r) => num(r.median, 1), cls: "num" },
        { label: "Range", render: (r) => `${num(r.min, 1)}–${num(r.max, 1)}`, cls: "num" },
        { label: "95% CI of mean", render: (r) => (r.ci95_low != null ? `${num(r.ci95_low, 1)}–${num(r.ci95_high, 1)}` : "—"), cls: "num" },
      ],
      out.summary
    );
    const models = state.options.models;
    table(
      $("#dis-table"),
      [
        { label: "Specimen", key: "specimen_id" },
        { label: "Site", key: "site" },
        { label: "Species", key: "species" },
        ...models.map((m) => ({ label: m, render: (r) => num(r[m], 1), cls: "num" })),
        { label: "Range (months)", render: (r) => `<strong>${num(r.range, 1)}</strong>`, cls: "num" },
      ],
      out.disagreement
    );
    $("#val-body").innerHTML = out.validation.length
      ? '<table id="val-table"></table>'
      : `<div class="tbd tbd-block">${tbdBadge} No known-age reference animals in this dataset. Add a
         <code>known_weaning_age_months</code> column for modern reference animals (or published series) to see
         bias, MAE, RMSE and interval coverage for each model here.</div>`;
    if (out.validation.length) {
      table(
        $("#val-table"),
        [
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

// ───────────────────────── events ─────────────────────────
function bind() {
  $$(".step").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  $("#btn-to-settings").addEventListener("click", () => show("settings"));

  const input = $("#csv-input");
  const zone = $("#dropzone");
  input.addEventListener("change", () => input.files[0] && loadCsv(input.files[0]));
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    if (e.dataTransfer.files[0]) loadCsv(e.dataTransfer.files[0]);
  });

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
    const idx = e.target.dataset.remove;
    if (idx == null) return;
    state.samples.splice(Number(idx), 1);
    await revalidate();
  });

  $("#growth-list").addEventListener("input", (e) => {
    const item = e.target.closest(".growth-item");
    if (item) syncOverride(item);
  });
  $("#growth-list").addEventListener("change", (e) => {
    if (e.target.classList.contains("ovr-toggle")) {
      syncOverride(e.target.closest(".growth-item"));
      renderGrowthList();
    }
  });
  $("#btn-run").addEventListener("click", runAnalysis);

  $("#result-list").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-specimen]");
    if (!btn) return;
    state.current = btn.dataset.specimen;
    renderResults();
  });
  $("#curve-toggles").addEventListener("change", (e) => {
    const m = e.target.dataset.model;
    if (e.target.checked) state.visible.add(m);
    else state.visible.delete(m);
    renderResults();
  });
  $("#btn-export-csv").addEventListener("click", () =>
    download("weanage_estimates.csv", new Blob([toCsv(state.estimates)], { type: "text/csv" }))
  );
  $("#btn-export-json").addEventListener("click", () =>
    download(
      "weanage_results.json",
      new Blob([JSON.stringify({ options: state.options, results: state.results }, null, 2)], { type: "application/json" })
    )
  );
  $("#btn-export-svg").addEventListener("click", () => {
    const svg = $("#res-chart svg");
    if (svg) download(`${state.current}_weaning_curve.svg`, svgToBlob(svg));
  });

  $$('input[name="group"], #cmp-milestone, #cmp-model').forEach((n) => n.addEventListener("change", refreshCompare));
}

async function init() {
  try {
    state.config = await api.config();
  } catch (e) {
    toast(`Could not reach the WeanAge backend: ${e.message}`);
    return;
  }
  initSettings();
  renderTbd();
  bind();
  renderData();
}

init();
