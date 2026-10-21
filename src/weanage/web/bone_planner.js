// Planning a bone study: simulate sites with a known weaning age and see how well a design recovers it.
import { api } from "./api.js";
import { lineChart } from "./chart.js";
import { $, ageNum, ageText, color, esc, fromUnit, num, plural, progressBar, table, toast, toUnit, unitWord } from "./util.js";

// Settings that can be compared; `age` ones are typed in the chosen unit.
const SWEEPS = {
  "": { label: "No comparison (one design)" },
  n_young: { label: "Young animals per site" },
  age_error_months: { label: "Age precision (±)", age: true },
  oldest_young_months: { label: "Oldest young animal", age: true },
  n_adult_females: { label: "Adult females" },
  scatter_permil: { label: "Scatter between animals (‰)" },
};
// What a run is scored on: ages are shown in the chosen unit, the rest are shares.
const METRICS = () => ({
  ci_width: `Width of the 95% interval (${unitWord()})`,
  mae: `Mean absolute error (${unitWord()})`,
  bias: `Bias (${unitWord()})`,
  ci_coverage: "95% interval contains the truth",
  signal_found: "Nursing signal found",
});
const AGE_METRICS = new Set(["ci_width", "mae", "bias", "rmse"]);
// Typical settings by species (in months), so a human study starts from human ages.
const TYPICAL = {
  human: { oldest: 120, ageerr: 6, lo: 18, hi: 36 },
  pig: { oldest: 12, ageerr: 1, lo: 2, hi: 5 },
  default: { oldest: 36, ageerr: 3, lo: 6, hi: 12 },
};

export function initBonePlanner(state) {
  $("#bp-species").innerHTML = state.config.turnover_tables
    .map((t) => `<option value="${esc(t.species)}">${esc(t.species)}${t.placeholder ? " (placeholder turnover)" : ""}</option>`).join("");
  $("#bp-sweep").innerHTML = Object.entries(SWEEPS).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join("");
  $("#bp-sweep").value = "n_young";
  $("#bp-values").value = "20, 40, 80";
  fillMetrics();
  $("#bp-species").addEventListener("change", () => {
    const t = TYPICAL[$("#bp-species").value] || TYPICAL.default;
    $("#bp-oldest").value = +toUnit(t.oldest).toFixed(2);
    $("#bp-ageerr").value = +toUnit(t.ageerr).toFixed(2);
    $("#bp-end-lo").value = +toUnit(t.lo).toFixed(2);
    $("#bp-end-hi").value = +toUnit(t.hi).toFixed(2);
  });
  $("#bp-sweep").addEventListener("change", () => { $("#bp-values").disabled = !$("#bp-sweep").value; });
  $("#bp-metric").addEventListener("change", () => state.bonePlan && renderBonePlan(state));
  $("#bone-plan-form").addEventListener("submit", (e) => {
    e.preventDefault();
    runBonePlan(state);
  });
}

function fillMetrics() {
  const chosen = $("#bp-metric").value || "ci_width";
  $("#bp-metric").innerHTML = Object.entries(METRICS()).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("#bp-metric").value = chosen;
}

function scenario() {
  const v = (id) => Number($(id).value);
  return {
    species: $("#bp-species").value,
    n_young: v("#bp-n"),
    oldest_young_months: fromUnit($("#bp-oldest").value),
    age_spread: $("#bp-spread").value,
    age_error_months: fromUnit($("#bp-ageerr").value),
    n_adult_females: v("#bp-females"),
    completion_range_months: [fromUnit($("#bp-end-lo").value), fromUnit($("#bp-end-hi").value)],
    scatter_permil: v("#bp-scatter"),
    enrichment_permil: v("#bp-enrich"),
    newborn_offset_permil: v("#bp-newborn"),
    weaning_form: $("#bp-form").value,
    replicates: v("#bp-reps"),
    seed: v("#bp-seed") || 1,
  };
}

async function runBonePlan(state) {
  const param = $("#bp-sweep").value;
  let values = [];
  if (param) {
    values = $("#bp-values").value.split(/[,;\s]+/).filter(Boolean).map(Number).filter((x) => isFinite(x));
    if (!values.length) return toast("Enter the values to try, e.g. 20, 40, 80.");
    if (SWEEPS[param].age) values = values.map(fromUnit);
  }
  const body = { scenario: scenario(), sweep_param: param || null, sweep_values: values };
  const bar = $("#bp-progress");
  $("#bp-run").disabled = true;
  progressBar(bar, 0, 0, "Simulating sites");
  try {
    state.bonePlan = await api.boneSimulate(body, (done, total) => progressBar(bar, done, total, "Simulating sites"));
    renderBonePlan(state);
  } catch (e) {
    toast(e.message);
  } finally {
    $("#bp-run").disabled = false;
    bar.hidden = true;
  }
}

const shown = (metric, value) => (value == null ? null : AGE_METRICS.has(metric) ? toUnit(value) : value);
const value = (x) => (Number.isInteger(x) ? String(x) : num(x, 2)); // counts stay whole numbers
const share = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export function renderBonePlan(state) {
  const plan = state.bonePlan;
  if (!plan) return;
  fillMetrics();
  $("#bp-results").hidden = false;
  const param = plan.sweep_param;
  const sweep = SWEEPS[param || ""];
  const xOf = (r) => (sweep?.age ? toUnit(r.x) : r.x);
  const rows = plan.runs.map((r) => ({ x: r.x, ...r.metrics, n: r.cases.length }));
  table($("#bp-table"), [
    ...(param ? [{ label: esc(sweep.label + (sweep.age ? ` (${unitWord()})` : "")), cls: "num", render: (r) => value(xOf(r)) }] : []),
    { label: "Sites", key: "n", cls: "num" },
    { label: "Fitted", cls: "num", render: (r) => share(r.success_rate) },
    { label: "Signal found", cls: "num", render: (r) => share(r.signal_found) },
    { label: "MAE", cls: "num", render: (r) => ageNum(r.mae, 2) },
    { label: "Bias", cls: "num", render: (r) => ageNum(r.bias, 2) },
    { label: "95% interval width", cls: "num", render: (r) => ageNum(r.ci_width, 2) },
    { label: "95% coverage", cls: "num", render: (r) => share(r.ci_coverage) },
  ], rows);
  const metric = $("#bp-metric").value;
  if (param && rows.length > 1) {
    lineChart($("#bp-chart"), [{ name: METRICS()[metric], color: color("logistic"), points: rows.map((r) => ({ x: xOf(r), y: shown(metric, r[metric]) })) }],
      { xLabel: sweep.label + (sweep.age ? ` (${unitWord()})` : ""), yLabel: METRICS()[metric], title: `${METRICS()[metric]} by ${sweep.label}`, yMin: metric === "bias" ? undefined : 0 });
  } else {
    $("#bp-chart").innerHTML = '<p class="muted">Choose a setting to compare to see a chart.</p>';
  }
  $("#bp-summary").innerHTML = summary(plan, rows, sweep, xOf);
}

/** One plain sentence: the smallest design that finds the signal and dates weaning within a set precision. */
function summary(plan, rows, sweep, xOf) {
  const tbd = plan.turnover_placeholder ? ' <span class="tbd-inline">Uses placeholder bone turnover for this species.</span>' : "";
  const describe = (r) => `the 95% interval is ${ageText(r.ci_width)} wide on average, the error ${ageText(r.mae)}, and the nursing signal was found at ${share(r.signal_found)} of the sites`;
  if (rows.length === 1) return `<p>With this design ${describe(rows[0])}.${tbd}</p>`;
  const good = rows.filter((r) => r.signal_found >= 0.8 && r.ci_coverage >= 0.8);
  const first = good.length ? good.reduce((a, b) => (xOf(a) <= xOf(b) ? a : b)) : null;
  const label = sweep.label.toLowerCase();
  return `<p>${first
    ? `From ${label} = <strong>${value(xOf(first))}${sweep.age ? ` ${unitWord()}` : ""}</strong>, ${describe(first)}.`
    : `None of the values tried reliably found the nursing signal and dated weaning (signal found and interval covering the truth at 80% of sites or more).`}
    Each value was tried on ${plural(rows[0].n, "simulated site")}.${tbd}</p>`;
}
