// Kill-off profiles: deaths and survivorship by age class from aged mandibles, after Payne (1973).
import { oneTableCalc } from "./calc.js";
import { lineChart } from "./chart.js";
import { $, color, download, esc, help, num, plural, renderIssues, renderReady, renderWarnings, table, toCsv } from "./util.js";
import { figure } from "./figures.js";

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const withRange = (v) => (v == null ? "—" : `${pct(v.estimate)}${v.ci_low != null ? ` <small class="muted">(${pct(v.ci_low)}–${pct(v.ci_high)})</small>` : ""}`);

export const killoff = oneTableCalc({
  name: "killoff",
  plural: "mandibles",
  working: "Building profiles",
  fields: ["bootstrap_draws", "permutations"],
  readSettings: (out) => ({ ...out, class_bounds_months: $("#killoff-class_bounds_months").value.split(/[,;\s]+/).filter(Boolean).map(Number),
    stage_ages: readStageTable($("#killoff-stage-table").value), stage_source: $("#killoff-stage_source").value.trim() }),
  writeSettings: (o) => {
    if (o.class_bounds_months) $("#killoff-class_bounds_months").value = o.class_bounds_months.join(", ");
    if (o.stage_ages) $("#killoff-stage-table").value = Object.entries(o.stage_ages).map(([k, [a, b]]) => `${k}: ${a}-${b}`).join("\n");
    if ("stage_source" in o) $("#killoff-stage_source").value = o.stage_source;
  },
  init: (calc) => {
    $("#btn-killoff-csv").addEventListener("click", () => download("weanage_killoff_profiles.csv", new Blob([toCsv(profileRows(calc.own().output))], { type: "text/csv" })));
    $("#btn-killoff-json").addEventListener("click", () => download("weanage_killoff_results.json",
      new Blob([JSON.stringify({ options: calc.own().options, ...calc.own().output }, null, 2)])));
  },
  renderData,
  renderResults,
});

/** "B: 1-8" lines -> {B: [1, 8]}; lines that do not parse are skipped. */
export function readStageTable(text) {
  const table = {};
  for (const line of text.split("\n")) {
    const m = line.match(/^\s*([^:,]+?)\s*[:,]\s*(\d+(?:\.\d+)?)\s*[-–,]\s*(\d+(?:\.\d+)?)\s*$/);
    if (m) table[m[1]] = [Number(m[2]), Number(m[3])];
  }
  return table;
}

function renderData({ report, samples }) {
  const groups = report?.groups || [];
  renderIssues(report ? report.issues : []);
  renderReady(samples.length && `${plural(samples.length, "mandible")} in ${plural(groups.length, "group")} loaded.`);
  $("#killoff-groups-card").hidden = !samples.length;
  $("#killoff-count").textContent = `· ${plural(groups.length, "group")}`;
  $("#sb-data").textContent = samples.length ? plural(samples.length, "mandible") : "No data loaded";
  table($("#killoff-group-table"), [{ label: "Group", key: "group" }, { label: "Mandibles", key: "n", cls: "num" }], groups);
  table($("#killoff-sample-table"), [
    { label: "Mandible", key: "specimen_id" },
    { label: "Site", key: "site" },
    { label: "Stage", key: "payne_stage" },
    { label: "Age (months)", cls: "num", render: (s) => `${num(s.age_min_months, 0)}–${num(s.age_max_months, 0)}` },
    { label: "Notes", key: "notes" },
  ], samples);
}

function renderResults({ output }) {
  const { results, comparisons, class_labels: labels } = output;
  const palette = ["logistic", "piecewise", "exponential", "two_phase"];
  const dashes = [null, "9 4", "2 3", "10 3 2 3"];
  const oneSpecies = new Set(results.map((g) => g.species)).size === 1; // then the legend can leave it out
  figure($("#killoff-survival-chart"), (box) => lineChart(box, results.map((g, i) => ({
    name: oneSpecies ? [g.site, g.period].filter(Boolean).join(" · ") : g.group, color: color(palette[i % 4]), dash: dashes[i % 4],
    points: [{ x: g.classes[0].from_months, y: 100 }, ...g.classes.map((c) => ({ x: c.to_months, y: 100 * c.survival.estimate }))],
  })), { xLabel: "Age (months)", yLabel: "Still alive (%)", title: "Survivorship by group", yMin: 0 }),
    { caption: `Share of each group's animals still alive at each age, from mandibles aged by tooth wear (${results.map((g) => `${g.group}: n = ${num(g.n, 0)}`).join("; ")}). Ages of each stage are spread over its age range.` });
  table($("#killoff-summary-table"), [
    { label: "Group", key: "group" },
    { label: "Mandibles", cls: "num", render: (g) => num(g.n, 0) },
    { label: "Most deaths in", render: (g) => esc(g.peak_class ?? "—") },
    { label: "Killed before 6 months", cls: "num", render: (g) => withRange(g.indicators.killed_before_6) },
    { label: "Killed 6–36 months", cls: "num", render: (g) => withRange(g.indicators.killed_6_to_36) },
    { label: "Alive at 4 years", cls: "num", render: (g) => withRange(g.indicators.surviving_past_48) },
  ], results);
  table($("#killoff-class-table"), [
    { label: "Group", key: "group" },
    ...labels.map((label, k) => ({ label: esc(label), cls: "num", render: (g) => withRange(g.classes[k].deaths) })),
  ], results);
  $("#killoff-compare-card").hidden = !comparisons.length;
  table($("#killoff-compare-table"), [
    { label: "Groups", render: (c) => c.groups.map(esc).join(" vs ") },
    { label: `Difference ${help("killoff_difference")}`, cls: "num", render: (c) => pct(c.difference) },
    { label: "p (permutation)", cls: "num", render: (c) => (c.p_value == null ? "—" : c.p_value < 0.001 ? "< 0.001" : num(c.p_value, 3)) },
  ], comparisons);
  renderWarnings("#killoff-warnings-box", "#killoff-warnings-summary", "#killoff-warnings",
    results.flatMap((g) => g.warnings.map((w) => `${g.group}: ${w}`)), () => "warning");
}

function profileRows({ results }) {
  return results.flatMap((g) => g.classes.map((c) => ({
    group: g.group, site: g.site, species: g.species, period: g.period, n: g.n, class: c.label, from_months: c.from_months,
    to_months: c.to_months, count: c.count, deaths: c.deaths.estimate, deaths_ci_low: c.deaths.ci_low, deaths_ci_high: c.deaths.ci_high,
    survival: c.survival.estimate, survival_ci_low: c.survival.ci_low, survival_ci_high: c.survival.ci_high,
  })));
}
