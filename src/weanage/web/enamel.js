// The enamel calculation: season of birth (δ18O), rumen development and diet (δ13C) and mobility
// (87Sr/86Sr) along one cattle molar.
import { oneTableCalc } from "./calc.js";
import { forestChart, profileChart } from "./chart.js";
import { $, download, esc, help, num, plural, renderIssues, renderReady, renderWarnings, table, toCsv } from "./util.js";
import { figure } from "./figures.js";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const teeth = (n) => `${n} ${n === 1 ? "tooth" : "teeth"}`;

export const enamel = oneTableCalc({
  name: "enamel",
  plural: "enamel samples",
  working: "Fitting teeth",
  fields: ["period_min_mm", "period_max_mm", "min_amplitude_permil", "min_rumen_rise_permil", "max_rumen_rise_permil", "draws",
    "c3_plants_d13C", "c3_plants_sd", "c4_plants_d13C", "c4_plants_sd", "enamel_diet_spacing_permil", "enamel_diet_spacing_sd",
    "d18O_max_month", "reference_birth_index", "reference_birth_month", "sr_min_shift", "local_sr_min", "local_sr_max",
    "mineralisation_length_mm"],
  init: bindResults,
  renderData,
  renderResults,
  prepare: withToothWeaningAges,
  first: (output) => output.results[0]?.specimen_id,
});

function bindResults(calc) {
  const own = calc.own;
  const choose = (id) => {
    own().current = id;
    renderResults(own());
    $(`#enamel-result-list [data-tooth="${CSS.escape(id)}"]`)?.focus();
  };
  $("#enamel-result-list").addEventListener("click", (e) => {
    const b = e.target.closest("[data-tooth]");
    if (b) choose(b.dataset.tooth);
  });
  $("#enamel-result-list").addEventListener("keydown", (e) => {
    const ids = own().output.results.map((r) => r.specimen_id);
    const moves = { ArrowDown: 1, ArrowUp: -1 };
    if (!(e.key in moves)) return;
    e.preventDefault();
    choose(ids[Math.min(Math.max(ids.indexOf(own().current) + moves[e.key], 0), ids.length - 1)]);
  });
  $("#btn-enamel-csv").addEventListener("click", () => download("weanage_enamel_estimates.csv", new Blob([toCsv(estimateRows(own().output.results))], { type: "text/csv" })));
  $("#btn-enamel-json").addEventListener("click", () => download("weanage_enamel_results.json",
    new Blob([JSON.stringify({ options: own().options, ...own().output }, null, 2)])));
}

// Data
function renderData({ report, samples }) {
  const loaded = report?.teeth || [];
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
    { label: "⁸⁷Sr/⁸⁶Sr", key: "n_sr", cls: "num" },
    { label: "Crown sampled (mm)", cls: "num", render: (t) => num(t.span_mm, 1) },
  ], loaded);
  table($("#enamel-sample-table"), [
    { label: "Tooth", key: "specimen_id" },
    { label: "From ERJ (mm)", cls: "num", render: (s) => num(s.erj_distance_mm, 1) },
    { label: "δ¹⁸O", cls: "num", render: (s) => num(s.d18O) },
    { label: "δ¹³C", cls: "num", render: (s) => num(s.d13C) },
    { label: "⁸⁷Sr/⁸⁶Sr", cls: "num", render: (s) => num(s.sr87_86, 5) },
    { label: "Notes", key: "notes" },
  ], samples);
}

// The weaning age of each animal from the tooth (dentine) calculation, where the enamel table has none.
// Matched by specimen or individual ID; ages that are only bounds or withheld are not used.
function withToothWeaningAges(samples, appState) {
  const milestone = appState.options?.reported_milestone || "midpoint";
  const ages = new Map();
  for (const r of appState.results || []) {
    const age = r.model_average?.[milestone];
    if (age?.estimate != null && !age.beyond) {
      ages.set(r.specimen_id, { weaning_age_months: age.estimate, weaning_age_sd_months: age.ci_low != null ? (age.ci_high - age.ci_low) / 3.92 : null });
    }
  }
  if (!ages.size) return samples;
  return samples.map((s) => (s.weaning_age_months == null && ages.has(s.specimen_id) ? { ...s, ...ages.get(s.specimen_id) } : s));
}

// Results
const monthName = (m) => {
  if (m == null) return "—";
  const part = m % 1 < 1 / 3 ? "early" : m % 1 < 2 / 3 ? "mid" : "late";
  return `${part} ${MONTHS[Math.floor(m) - 1]}`;
};
const monthRange = (v) => (v?.ci_low != null ? ` (95% interval ${monthName(v.ci_low)} to ${monthName(v.ci_high)})` : "");
const range = (v, d = 2) => (v?.ci_low != null ? `${num(v.ci_low, d)}–${num(v.ci_high, d)}` : "");
const warningsOf = (r) => [r.season, r.rumen, r.diet, r.strontium].flatMap((part) => part?.warnings || []);
const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);

function renderResults({ output, current }) {
  const { results, groups } = output;
  $("#enamel-result-list").innerHTML = results.map((r) => {
    const chosen = r.specimen_id === current;
    const index = r.season?.birth_index;
    const n = warningsOf(r).length;
    return `<li role="none"><button role="option" aria-selected="${chosen}" tabindex="${chosen ? 0 : -1}" data-tooth="${esc(r.specimen_id)}" class="${chosen ? "active" : ""}">
      <span><strong>${esc(r.specimen_id)}</strong><small>${esc(r.site)} · ${esc(r.species)} ${esc(r.tooth)}</small></span>
      <span><span class="age">${index ? num(index.estimate, 2) : "—"}</span>${n ? `<span class="warn-dot" aria-label="${plural(n, "warning")}">${n}</span>` : ""}</span>
    </button></li>`;
  }).join("");
  const res = results.find((r) => r.specimen_id === current) || results[0];
  if (!res) return;
  $("#enamel-res-title").textContent = res.specimen_id;
  $("#enamel-res-meta").textContent = `${res.site} · ${res.species} ${res.tooth}${res.period ? ` · ${res.period}` : ""} · ${plural(res.points.length, "enamel sample")}`;
  $("#enamel-res-summary").innerHTML = summary(res);
  drawCharts(res);
  renderWarnings("#enamel-warnings-box", "#enamel-warnings-summary", "#enamel-res-warnings", warningsOf(res), () => "warning");
  renderGroups(groups);
}

function summary(res) {
  const s = res.season;
  const r = res.rumen;
  const season = !s ? "<p>No δ¹⁸O values.</p>" : s.birth_index
    ? `<p class="readout"><span class="figure">${num(s.birth_index.estimate, 2)}</span>
        <span class="what">birth index (x₀/X) ${help("birth_index")}${s.birth_index.ci_low != null ? ` · 95% interval ${range(s.birth_index)}` : ""}</span></p>
      <p>δ¹⁸O cycle of ${num(2 * s.amplitude_permil, 1)}‰ (maximum to minimum${s.amplitude_restored_permil != null
        ? `; about ${num(2 * s.amplitude_restored_permil, 1)}‰ before smoothing ${help("smoothing")}` : ""}); about ${num(s.period_mm, 0)} mm of crown formed in a year;
        δ¹⁸O maximum ${num(s.x0_mm, 1)} mm above the enamel-root junction.</p>`
    : `<p><strong>No birth index.</strong> ${esc(s.message)}.</p>`;
  const rumen = !r ? "<p>No δ¹³C values.</p>" : r.detected
    ? `<p><strong>Rumen development ${help("rumen")}:</strong> δ¹³C rises by ${num(r.rise_permil, 1)}‰ around
        ${num(r.transition_mm.estimate, 1)} mm above the enamel-root junction${r.transition_mm.ci_low != null ? ` (95% interval ${range(r.transition_mm, 1)} mm)` : ""}${
        r.months_after_first_sample != null ? `, about ${num(r.months_after_first_sample, 1)} months of crown growth after the first sample` : ""}.
        ${r.duration_months != null ? `The rise took about ${num(r.duration_months, 1)} months${r.duration_restored_months != null
          ? ` (about ${num(r.duration_restored_months, 1)} before smoothing)` : ""}.` : ""}</p>`
    : `<p><strong>No rumen development detected ${help("rumen")}.</strong> ${esc(r.message)}.</p>`;
  const d = res.diet;
  const diet = !d ? "" : d.share_c4
    ? `<p><strong>Diet ${help("c4")}:</strong> ${esc(d.category)}, about ${pct(d.share_c4.estimate)} C4 plants
        (95% interval ${pct(d.share_c4.ci_low)}–${pct(d.share_c4.ci_high)}; samples range ${pct(d.sample_range[0])}–${pct(d.sample_range[1])}),
        from ${plural(d.n, "sample")}${d.after_rumen ? " formed after the rumen transition" : ""}. Diet δ¹³C about ${num(d.diet_d13C, 1)}‰.</p>`
    : `<p><strong>No diet estimate ${help("c4")}.</strong> ${esc(d.message)}.</p>`;
  return season + rumen + diet + strontium(res.strontium) + calendar(res.calendar);
}

function strontium(sr) {
  if (!sr) return "";
  const shifts = sr.shifts.map((s) => `from ${num(s.from_value, 4)} to ${num(s.to_value, 4)} around ${num(s.position, 1)} mm${
    s.month ? ` (${monthName(s.month.estimate)})` : ""}${s.gradual ? ", gradually" : ""}`);
  return `<p><strong>Mobility ${help("strontium")}:</strong> ${shifts.length ? `⁸⁷Sr/⁸⁶Sr shifts ${shifts.join("; ")}.`
    : sr.message ? `${esc(sr.message)}.` : `no shift in ⁸⁷Sr/⁸⁶Sr (${num(sr.range[0], 4)}–${num(sr.range[1], 4)}).`}</p>`;
}

function calendar(c) {
  if (!c) return "";
  const parts = [
    c.rumen_month && `rumen transition in ${monthName(c.rumen_month.estimate)}${monthRange(c.rumen_month)}`,
    c.birth_month && `born in ${monthName(c.birth_month.estimate)}${monthRange(c.birth_month)}`,
    c.weaning_month && `weaned (at ${num(c.weaning_age_months, 1)} months) in ${monthName(c.weaning_month.estimate)}${monthRange(c.weaning_month)}`,
  ].filter(Boolean);
  if (!parts.length && !c.message) return "";
  return `<p><strong>Calendar ${help("calendar")}:</strong> ${parts.length ? `${parts.join("; ")}.` : ""} ${c.message ? `<span class="muted">${esc(c.message)}.</span>` : ""}</p>`;
}

function drawCharts(res) {
  const s = res.season;
  const r = res.rumen;
  const oxygen = res.points.filter((p) => p.d18O != null);
  const carbon = res.points.filter((p) => p.d13C != null);
  const sr = res.points.filter((p) => p.sr87_86 != null);
  const names = { d18O: ["δ¹⁸O", 2, "‰"], d13C: ["δ¹³C", 2, "‰"], sr87_86: ["⁸⁷Sr/⁸⁶Sr", 5, ""] };
  const point = (key) => (p) => ({ x: p.x, y: p[key], label: `${esc(res.specimen_id)}${p.sample_index != null ? ` #${p.sample_index}` : ""}: ${num(p.x, 1)} mm<br>${names[key][0]} ${num(p[key], names[key][1])}${names[key][2]}` });
  const curve = (fit) => (fit?.curve_x?.length ? { xs: fit.curve_x, ys: fit.curve_y } : null);
  $("#enamel-o-chart").hidden = !oxygen.length;
  $("#enamel-c-chart").hidden = !carbon.length;
  if (oxygen.length) figure($("#enamel-o-chart"), (box) => profileChart(box, {
    points: oxygen.map(point("d18O")), curve: curve(s), yLabel: "Enamel δ¹⁸O (‰ VPDB)", title: `Enamel δ18O along the crown: ${res.specimen_id}`,
    marks: s?.birth_index ? [{ x: s.x0_mm, label: `δ¹⁸O maximum ${num(s.x0_mm, 1)} mm` }] : [],
  }));
  if (carbon.length) figure($("#enamel-c-chart"), (box) => profileChart(box, {
    points: carbon.map(point("d13C")), curve: curve(r), yLabel: "Enamel δ¹³C (‰ VPDB)", title: `Enamel δ13C along the crown: ${res.specimen_id}`,
    marks: r?.detected ? [{ x: r.transition_mm.estimate, lo: r.transition_mm.ci_low, hi: r.transition_mm.ci_high, label: `rumen transition ${num(r.transition_mm.estimate, 1)} mm` }] : [],
  }));
  $("#enamel-sr-chart").hidden = !sr.length;
  if (sr.length) figure($("#enamel-sr-chart"), (box) => profileChart(box, {
    points: sr.map(point("sr87_86")), yLabel: "Enamel ⁸⁷Sr/⁸⁶Sr", title: `Enamel 87Sr/86Sr along the crown: ${res.specimen_id}`,
    marks: (res.strontium?.shifts || []).map((s) => ({ x: s.position, lo: s.between[1], hi: s.between[0], label: `shift ${num(s.position, 1)} mm` })),
  }));
}

function renderGroups(groups) {
  const dated = groups.filter((g) => g.n_index);
  $("#enamel-group-chart").innerHTML = dated.length ? "" : '<p class="muted">No tooth has a birth index.</p>';
  if (dated.length) figure($("#enamel-group-chart"), (box) => forestChart(box, dated.map((g) => ({
    label: g.group, mean: g.mean_index, lo: NaN, hi: NaN,
    values: g.teeth.map((t) => ({ v: t.birth_index, label: `${esc(t.specimen_id)}: ${num(t.birth_index, 2)}` })),
  })), "Birth index (x₀/X): squares = circular mean, dots = teeth"));
  table($("#enamel-group-table"), [
    { label: "Group", key: "group" },
    { label: "Teeth", key: "n", cls: "num" },
    { label: "Mean index", cls: "num", render: (g) => num(g.mean_index, 2) },
    { label: "Spread", cls: "num", render: (g) => num(g.spread_index, 2) },
    { label: "≈ months of births", cls: "num", render: (g) => num(g.spread_months, 1) },
    { label: "Mean C4 share", cls: "num", render: (g) => pct(g.mean_share_c4) },
    { label: "Mean rumen month", render: (g) => monthName(g.mean_rumen_month) },
    { label: "Sr shifts", cls: "num", render: (g) => `${g.n_movers} of ${g.n}` },
  ], groups);
}

function estimateRows(results) {
  return results.map((r) => ({
    specimen_id: r.specimen_id, site: r.site, species: r.species, tooth: r.tooth, period: r.period,
    birth_index: r.season?.birth_index?.estimate, birth_index_ci_low: r.season?.birth_index?.ci_low, birth_index_ci_high: r.season?.birth_index?.ci_high,
    period_mm: r.season?.period_mm, x0_mm: r.season?.x0_mm, d18O_amplitude_permil: r.season?.amplitude_permil,
    rumen_detected: r.rumen?.detected, rumen_transition_mm: r.rumen?.transition_mm?.estimate,
    rumen_transition_ci_low: r.rumen?.transition_mm?.ci_low, rumen_transition_ci_high: r.rumen?.transition_mm?.ci_high,
    rumen_rise_permil: r.rumen?.rise_permil, months_after_first_sample: r.rumen?.months_after_first_sample,
    diet: r.diet?.category, c4_share: r.diet?.share_c4?.estimate, c4_share_ci_low: r.diet?.share_c4?.ci_low,
    c4_share_ci_high: r.diet?.share_c4?.ci_high, diet_d13C: r.diet?.diet_d13C, diet_samples: r.diet?.n,
    d18O_amplitude_restored_permil: r.season?.amplitude_restored_permil, rumen_duration_months: r.rumen?.duration_months,
    rumen_duration_restored_months: r.rumen?.duration_restored_months,
    rumen_month: r.calendar?.rumen_month?.estimate, birth_month: r.calendar?.birth_month?.estimate,
    weaning_month: r.calendar?.weaning_month?.estimate, weaning_age_months: r.calendar?.weaning_age_months,
    sr_shifts: r.strontium?.shifts.map((s) => `${s.from_value.toFixed(5)}→${s.to_value.toFixed(5)} at ${s.position.toFixed(1)} mm`).join("; "),
    sr_outside_local: r.strontium?.outside_local,
  }));
}
