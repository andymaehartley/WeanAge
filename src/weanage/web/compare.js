// The Compare page: weaning ages of groups (site, species, period or any kept column) compared, with
// random-effects and Bayesian tests, model disagreement and validation against known ages.
import { api } from "./api.js";
import { forestChart } from "./chart.js";
import { $, $$, ageNum, ageText, esc, help, labelScrollBoxes, num, percent, pIs, pval, table, toast, toUnit, unitWord } from "./util.js";
import { figure } from "./figures.js";

let state;
const capital = (s) => s[0].toUpperCase() + s.slice(1);

export function initCompare(appState) {
  state = appState;
}
/** Other columns of the tooth table (e.g. sex, burial type) can be grouped by too, if they vary. */
export function renderGroupChoices() {
  const values = {};
  for (const r of state.results || []) for (const [k, v] of Object.entries(r.labels || {})) (values[k] ??= new Set()).add(v);
  const ticked = new Set($$('#group-extra input:checked').map((box) => box.value));
  $("#group-extra").innerHTML = Object.entries(values).filter(([, v]) => v.size > 1 && v.size <= 20)
    .map(([k]) => `<label class="check"><input type="checkbox" name="group" value="${esc(k)}" ${ticked.has(k) ? "checked" : ""}> ${esc(k)}</label>`).join("");
}

export function compareRequest() {
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

export async function refreshCompare() {
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
    figure($("#cmp-chart"), (box) => forestChart(box, out.summary.map((s) => ({
      label: groupName(s),
      mean: toUnit(means[groupName(s)]?.mean),
      lo: toUnit(means[groupName(s)]?.ci_low),
      hi: toUnit(means[groupName(s)]?.ci_high),
      values: rows.filter((r) => groupName(r) === groupName(s) && r[milestone] != null)
        .map((r) => ({ v: toUnit(r[milestone]), label: `${esc(r.specimen_id)}: ${ageText(r[milestone])} (${r.model})` })),
    })), `Weaning ${milestone} (${unitWord()}): random-effects mean ± 95% interval, dots = specimens`));
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

