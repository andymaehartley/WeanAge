// Life tables: deaths, survivorship and life expectancy from skeletal ages at death (in years).
import { oneTableCalc } from "./calc.js";
import { lineChart } from "./chart.js";
import { $, color, download, esc, help, num, plural, renderIssues, renderReady, renderWarnings, table, toCsv } from "./util.js";

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const withRange = (v, show = (x) => num(x, 1)) => (v == null ? "—"
  : `${show(v.estimate)}${v.ci_low != null ? ` <small class="muted">(${show(v.ci_low)}–${show(v.ci_high)})</small>` : ""}`);

export const lifetable = oneTableCalc({
  name: "lifetable",
  plural: "skeletons",
  working: "Building life tables",
  fields: ["bootstrap_draws", "permutations", "expected_infant_share"],
  readSettings: (out) => ({ ...out, siler: $("#lifetable-siler").checked,
    group_by: ["site", $("#lifetable-group").value].filter(Boolean),
    class_bounds_years: $("#lifetable-class_bounds_years").value.split(/[,;\s]+/).filter(Boolean).map(Number) }),
  writeSettings: (o) => {
    if (o.class_bounds_years) $("#lifetable-class_bounds_years").value = o.class_bounds_years.join(", ");
    if ("siler" in o) $("#lifetable-siler").checked = o.siler;
    if (o.group_by) groupChoice(o.group_by[1] ?? "");
  },
  init: (calc) => {
    $("#btn-lifetable-csv").addEventListener("click", () => download("weanage_life_tables.csv", new Blob([toCsv(tableRows(calc.own().output))], { type: "text/csv" })));
  },
  renderData,
  renderResults,
});

/** Group by site and: period, sex, or a column kept from the table (e.g. grave goods). */
function groupChoice(value, columns = []) {
  const select = $("#lifetable-group");
  const keep = value ?? select.value;
  const options = [["period", "period"], ["sex", "sex"], ...columns.map((c) => [c, c]), ["", "nothing else"]];
  select.innerHTML = options.map(([v, label]) => `<option value="${esc(v)}">${esc(label)}</option>`).join("");
  select.value = options.some(([v]) => v === keep) ? keep : "period";
}

function renderData({ report, samples }) {
  const groups = report?.groups || [];
  groupChoice(null, report?.columns || []);
  renderIssues(report ? report.issues : []);
  renderReady(samples.length && `${plural(samples.length, "skeleton")} in ${plural(groups.length, "group")} loaded.`);
  $("#lifetable-card").hidden = !samples.length;
  $("#lifetable-count").textContent = `· ${plural(groups.length, "group")}`;
  $("#sb-data").textContent = samples.length ? plural(samples.length, "skeleton") : "No data loaded";
  table($("#lifetable-group-table"), [{ label: "Group", key: "group" }, { label: "Skeletons", key: "n", cls: "num" }], groups);
}

const PALETTE = ["logistic", "piecewise", "exponential", "two_phase"];

function renderResults({ output }) {
  const { results, comparisons, warnings } = output;
  const series = results.flatMap((g, i) => [
    { name: g.group, color: color(PALETTE[i % 4]), dash: null,
      points: [{ x: g.rows[0].from_years, y: 100 }, ...g.rows.map((r) => ({ x: r.to_years, y: 100 * (r.l - r.d) }))] },
    ...(g.siler ? [{ name: `${g.group} (Siler)`, color: color(PALETTE[i % 4]), dash: "5 4", markers: false,
      points: g.siler.curve_age.filter((_, k) => k % 8 === 0).map((x, k) => ({ x, y: 100 * g.siler.curve_survival[k * 8] })) }] : []),
  ]);
  lineChart($("#lifetable-chart"), series, { xLabel: "Age (years)", yLabel: "Still alive (%)", title: "Survivorship by group", yMin: 0 });
  table($("#lifetable-summary"), [
    { label: "Group", key: "group" },
    { label: "Skeletons", key: "n", cls: "num" },
    { label: `e₀ (years) ${help("e0")}`, cls: "num", render: (g) => withRange(g.summary.e0) },
    { label: "e₀, Siler", cls: "num", render: (g) => (g.siler ? num(g.siler.e0, 1) : "—") },
    ...(results.some((g) => g.corrected) ? [{ label: "e₀ with missing infants added", cls: "num",
      render: (g) => `${num(g.corrected.summary.e0, 1)} <small class="muted">(+${num(g.corrected.added_infants, 1)} infants)</small>` }] : []),
    { label: "Infants (<1 y)", cls: "num", render: (g) => withRange(g.summary.infant_share, pct) },
    { label: "Under 5", cls: "num", render: (g) => withRange(g.summary.under5_share, pct) },
    { label: `Juvenility index ${help("juvenility")}`, cls: "num", render: (g) => withRange(g.summary.juvenility_index, (x) => num(x, 2)) },
  ], results);
  $("#lifetable-tables").innerHTML = results.map((g, i) => `<details class="samples-details"${i ? "" : " open"}>
    <summary>Life table: ${esc(g.group)}</summary><div class="table-wrap"><table id="lifetable-t${i}"></table></div></details>`).join("");
  results.forEach((g, i) => table($(`#lifetable-t${i}`), [
    { label: "Age (years)", render: (r) => `${num(r.from_years, 0)}–${num(r.to_years, 0)}` },
    { label: "Dx", cls: "num", render: (r) => num(r.D, 1) },
    { label: "dx", cls: "num", render: (r) => num(r.d, 3) },
    { label: "lx", cls: "num", render: (r) => num(r.l, 3) },
    { label: "qx", cls: "num", render: (r) => num(r.q, 3) },
    { label: "Lx", cls: "num", render: (r) => num(r.L, 2) },
    { label: "Tx", cls: "num", render: (r) => num(r.T, 2) },
    { label: "ex", cls: "num", render: (r) => num(r.e, 1) },
  ], g.rows));
  $("#lifetable-compare-card").hidden = !comparisons.length;
  table($("#lifetable-compare"), [
    { label: "Groups", render: (c) => c.groups.map(esc).join(" vs ") },
    { label: "Difference in deaths by age", cls: "num", render: (c) => pct(c.difference) },
    { label: "p (permutation)", cls: "num", render: (c) => (c.p_value == null ? "—" : c.p_value < 0.001 ? "< 0.001" : num(c.p_value, 3)) },
  ], comparisons);
  renderWarnings("#lifetable-warnings-box", "#lifetable-warnings-summary", "#lifetable-warnings",
    [...warnings, ...results.flatMap((g) => g.warnings.map((w) => `${g.group}: ${w}`))], () => "warning");
}

function tableRows({ results }) {
  return results.flatMap((g) => g.rows.map((r) => ({ group: g.group, site: g.site, period: g.period, from_years: r.from_years,
    to_years: r.to_years, Dx: r.D, dx: r.d, lx: r.l, qx: r.q, Lx: r.L, Tx: r.T, ex: r.e })));
}
