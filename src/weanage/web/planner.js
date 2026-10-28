// Sampling planner: simulate known-age teeth to choose a sampling protocol.
import { api } from "./api.js";
import { lineChart } from "./chart.js";
import { $, $$, ageNum, ageText, color, esc, MODEL_STYLE, num, percent, progressBar, table, toast, toUnit, unitWord } from "./util.js";
import { figure } from "./figures.js";

const SWEEPS = {
  "": "No sweep (single scenario)",
  sampling_interval_mm: "Sampling interval (mm, contiguous slices)",
  increment_width_mm: "Slice height (mm)",
  noise_sd: "Measurement noise (‰)",
  missing_fraction: "Missing / failed samples (fraction)",
  growth_layer_offset_mm: "Growth-layer offset (mm)",
  n_specimens: "Number of specimens",
};
// Error measures are ages, shown in the chosen unit; coverage and success are shares.
const METRICS = () => ({ mae: `Mean absolute error (${unitWord()})`, bias: `Bias (${unitWord()})`, rmse: `RMSE (${unitWord()})`, ci_coverage: "95% interval coverage", success_rate: "Share of specimens fitted" });
const AGE_METRICS = new Set(["mae", "bias", "rmse"]);

export function initPlanner(state) {
  const tables = state.config.growth_tables;
  $("#pl-target").innerHTML = tables.map((t) => `<option value="${esc(t.species)}:${esc(t.tooth)}">${esc(t.label)}${t.placeholder ? " (placeholder)" : ""}</option>`).join("");
  $("#pl-sweep").innerHTML = Object.entries(SWEEPS).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("#pl-metric").innerHTML = Object.entries(METRICS()).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("#pl-models").innerHTML = state.config.models
    .map((m) => `<label class="check"><input type="checkbox" name="pl-model" value="${m.name}" ${["logistic", "piecewise", "elbow"].includes(m.name) ? "checked" : ""}> ${esc(m.label)}</label>`)
    .join("");
  // Typical true weaning ages differ a lot between species; humans wean over years, not months.
  $("#pl-target").addEventListener("change", () => {
    const human = $("#pl-target").value.startsWith("human:");
    [$("#pl-mid-lo").value, $("#pl-mid-hi").value] = human ? [12, 36] : [4, 9];
    [$("#pl-scale-lo").value, $("#pl-scale-hi").value] = human ? [1.5, 4] : [0.4, 1];
  });
  $("#pl-sweep").value = "sampling_interval_mm";
  $("#pl-values").value = "0.5, 1, 2";

  $("#plan-form").addEventListener("submit", (e) => {
    e.preventDefault();
    runPlan(state);
  });
  $("#pl-metric").addEventListener("change", () => state.plan && renderPlan(state));
  $("#pl-sweep").addEventListener("change", () => {
    $("#pl-values").disabled = !$("#pl-sweep").value;
  });
}

function scenario() {
  const v = (id) => Number($(id).value);
  const [species, tooth] = $("#pl-target").value.split(":");
  return {
    species, tooth,
    n_specimens: v("#pl-n"),
    sampling_interval_mm: v("#pl-interval"),
    increment_width_mm: v("#pl-width"),
    noise_sd: v("#pl-noise"),
    missing_fraction: v("#pl-missing") / 100,
    growth_layer_offset_mm: v("#pl-offset"),
    age_model_error_sd: v("#pl-agesd"),
    midpoint_range_months: [v("#pl-mid-lo"), v("#pl-mid-hi")],
    scale_range_months: [v("#pl-scale-lo"), v("#pl-scale-hi")],
    drop_permil_range: [v("#pl-drop-lo"), v("#pl-drop-hi")],
    true_shape: $("#pl-shape").value,
    seed: v("#pl-seed") || 1,
  };
}

async function runPlan(state) {
  const models = $$('input[name="pl-model"]:checked').map((i) => i.value);
  if (!models.length) return toast("Choose at least one model to evaluate.");
  const sweepParam = $("#pl-sweep").value || null;
  const values = sweepParam ? $("#pl-values").value.split(/[,;\s]+/).map(Number).filter((x) => isFinite(x) && x >= 0) : [];
  if (sweepParam && !values.length) return toast("Enter the values to compare, e.g. 0.5, 1, 2");
  const btn = $("#pl-run");
  btn.disabled = true;
  try {
    const body = {
      scenario: scenario(),
      options: { models, monte_carlo_draws: Number($("#pl-draws").value) || 200, time_averaging: $("#pl-timeavg").checked },
      sweep_param: sweepParam,
      sweep_values: values,
    };
    state.plan = await api.simulate(body, (d, t) => progressBar($("#pl-progress"), d, t, "Simulating specimens"));
    state.plan.models = models;
    renderPlan(state);
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    $("#pl-progress").hidden = true;
  }
}

export function renderPlan(state) {
  const plan = state.plan;
  if (!plan) return;
  $("#pl-results").hidden = false;
  const param = plan.sweep_param;
  const xOf = (run) => (param ? run.scenario[param] : 0);
  const metric = $("#pl-metric").value || "mae";
  const rows = plan.runs.flatMap((run) => run.scores.map((s) => ({ ...s, x: xOf(run) })));
  table(
    $("#pl-table"),
    [
      ...(param ? [{ label: esc(SWEEPS[param]), render: (r) => num(r.x, 2), cls: "num" }] : []),
      { label: "Model", render: (r) => esc(r.model) },
      { label: "Fitted", render: (r) => percent(r.success_rate), cls: "num" },
      { label: "MAE", render: (r) => ageNum(r.mae, 2), cls: "num" },
      { label: "Bias", render: (r) => ageNum(r.bias, 2), cls: "num" },
      { label: "RMSE", render: (r) => ageNum(r.rmse, 2), cls: "num" },
      { label: "95% coverage", render: (r) => percent(r.ci_coverage), cls: "num" },
    ],
    rows
  );
  const box = $("#pl-chart");
  if (param && plan.runs.length > 1) {
    const models = [...new Set(rows.map((r) => r.model))];
    figure(box, (chartBox) => lineChart(
      chartBox,
      models.map((m) => ({
        name: m,
        color: color(m),
        dash: MODEL_STYLE[m]?.dash,
        points: rows.filter((r) => r.model === m).map((r) => ({ x: r.x, y: AGE_METRICS.has(metric) ? toUnit(r[metric]) : r[metric] })),
      })),
      { xLabel: SWEEPS[param], yLabel: METRICS()[metric], title: `${METRICS()[metric]} by ${SWEEPS[param]}`, yMin: metric === "bias" ? undefined : 0 }
    ));
  } else {
    box.innerHTML = '<p class="muted">Choose a setting to sweep to see a chart.</p>';
  }
  const best = [...rows].filter((r) => r.mae != null).sort((a, b) => a.mae - b.mae)[0];
  $("#pl-summary").innerHTML = best
    ? `Lowest error: <strong>${esc(best.model)}</strong>${param ? ` at ${esc(SWEEPS[param].toLowerCase())} = ${num(best.x, 2)}` : ""} (MAE ${ageText(best.mae, 2)}). Results use the selected growth table${$("#pl-target").selectedOptions[0]?.textContent.includes("placeholder") ? ", which is still a <span class=\"tbd-inline\">placeholder</span>" : ""}.`
    : "No estimates were produced.";
}
