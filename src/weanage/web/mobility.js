// Mobility from bulk enamel: δ18O as drinking water and 87Sr/86Sr against the local range.
import { oneTableCalc } from "./calc.js";
import { biplotChart } from "./chart.js";
import { $, download, esc, num, plural, readEditTable, renderIssues, renderReady, renderWarnings, table, toCsv, writeEditTable } from "./util.js";

const REGION_KEYS = { name: "Place", sr87_86: "87Sr/86Sr", sr_sd: "87Sr/86Sr SD", d18O_dw: "drinking water δ18O", d18O_dw_sd: "δ18O SD" };
const writeRegions = (rows) => writeEditTable($("#mobility-regions tbody"), REGION_KEYS, rows, "place");
const readRegions = () => readEditTable($("#mobility-regions tbody")).filter((r) => r.name)
  .map((r) => ({ ...r, sr_sd: r.sr_sd ?? 0.0005, d18O_dw_sd: r.d18O_dw_sd ?? 1 }));

export const mobility = oneTableCalc({
  name: "mobility",
  plural: "enamel samples",
  working: "Checking samples",
  fields: ["drinking_water_sd", "local_d18O_dw_min", "local_d18O_dw_max", "local_sr_min", "local_sr_max", "baseline_sd_multiplier"],
  readSettings: (out) => ({ ...out, regions: readRegions(), origins_from_sites: $("#mobility-origins_from_sites").checked }),
  writeSettings: (o) => {
    if (o.regions) writeRegions(o.regions);
    if ("origins_from_sites" in o) $("#mobility-origins_from_sites").checked = o.origins_from_sites;
  },
  init: (calc) => {
    $("#btn-mobility-add-region").addEventListener("click", () => writeRegions([...readRegions(), { name: "", sr_sd: 0.0005, d18O_dw_sd: 1 }]));
    $("#mobility-regions").addEventListener("click", (e) => {
      const b = e.target.closest("[data-remove-row]");
      if (!b) return;
      const rows = readEditTable($("#mobility-regions tbody"));
      rows.splice(Number(b.dataset.removeRow), 1);
      writeRegions(rows);
    });
    $("#btn-mobility-csv").addEventListener("click", () => download("weanage_mobility.csv", new Blob([toCsv(rows(calc.own().output))], { type: "text/csv" })));
  },
  renderData,
  renderResults,
});

function renderData({ report, samples }) {
  const sites = report?.sites || [];
  renderIssues(report ? report.issues : []);
  renderReady(samples.length && `${plural(samples.length, "sample")} from ${plural(sites.length, "site")} loaded.`);
  $("#mobility-card").hidden = !samples.length;
  $("#mobility-count").textContent = `· ${plural(samples.length, "sample")}`;
  $("#sb-data").textContent = samples.length ? plural(samples.length, "enamel sample") : "No data loaded";
  table($("#mobility-site-table"), [
    { label: "Site", key: "site" },
    { label: "People", key: "n_samples", cls: "num" },
    { label: "Baseline samples", key: "n_baseline", cls: "num" },
  ], sites);
}

const STATUS = { local: "local", "non-local": '<strong class="warn-text">non-local</strong>' };
const rangeText = (r, d) => (r ? `${num(r[0], d)} to ${num(r[1], d)}` : "—");

function renderResults({ output }) {
  const { results, sites, warnings } = output;
  const both = results.filter((r) => r.d18O_dw && r.sr87_86 != null);
  const site = sites.find((s) => s.sr_range && s.d18O_dw_range);
  $("#mobility-chart").innerHTML = both.length ? "" : '<p class="muted">The plot needs samples with both δ¹⁸O and ⁸⁷Sr/⁸⁶Sr.</p>';
  if (both.length) biplotChart($("#mobility-chart"), {
    title: "Drinking-water δ18O and 87Sr/86Sr of each person, with the local range",
    xLabel: "Drinking water δ¹⁸O (‰ VSMOW)", yLabel: "Enamel ⁸⁷Sr/⁸⁶Sr",
    points: both.map((r) => ({ x: r.d18O_dw.estimate, y: r.sr87_86, group: r.non_local ? "non-local" : "local",
      label: `${esc(r.specimen_id)}: δ¹⁸O(dw) ${num(r.d18O_dw.estimate, 1)}‰, ⁸⁷Sr/⁸⁶Sr ${num(r.sr87_86, 5)}` })),
    sources: site ? [{ name: `local range (${site.site})`, x: (site.d18O_dw_range[0] + site.d18O_dw_range[1]) / 2,
      y: (site.sr_range[0] + site.sr_range[1]) / 2, sdx: (site.d18O_dw_range[1] - site.d18O_dw_range[0]) / 2,
      sdy: (site.sr_range[1] - site.sr_range[0]) / 2 }] : [],
  });
  table($("#mobility-sites"), [
    { label: "Site", key: "site" },
    { label: "People", key: "n", cls: "num" },
    { label: "Non-local", cls: "num", render: (s) => s.n_non_local },
    { label: "Local ⁸⁷Sr/⁸⁶Sr", render: (s) => `${rangeText(s.sr_range, 5)} <small class="muted">${esc(s.sr_range_from || "")}</small>` },
    { label: "Local drinking water δ¹⁸O", render: (s) => `${rangeText(s.d18O_dw_range, 1)} <small class="muted">${esc(s.d18O_dw_range_from || "")}</small>` },
  ], sites);
  table($("#mobility-results"), [
    { label: "Sample", render: (r) => `${esc(r.specimen_id)} <small class="muted">${esc(r.site)}${r.tooth ? ` · ${esc(r.tooth)}` : ""}</small>` },
    { label: "δ¹⁸O", cls: "num", render: (r) => (r.d18O == null ? "—" : `${num(r.d18O, 2)} <small class="muted">${r.d18O_material === "phosphate" ? "PO₄, VSMOW" : "CO₃, VPDB"}</small>`) },
    { label: "Drinking water δ¹⁸O", cls: "num", render: (r) => (r.d18O_dw ? `${num(r.d18O_dw.estimate, 1)} <small class="muted">(${num(r.d18O_dw.ci_low, 1)} to ${num(r.d18O_dw.ci_high, 1)})</small>` : "—") },
    { label: "⁸⁷Sr/⁸⁶Sr", cls: "num", render: (r) => num(r.sr87_86, 5) },
    { label: "Sr", render: (r) => STATUS[r.sr_status] || "—" },
    { label: "δ¹⁸O", render: (r) => STATUS[r.d18O_status] || "—" },
    { label: "Possible origin", render: originText },
    { label: "Notes", render: (r) => esc(r.notes.join("; ")) },
  ], results);
  renderWarnings("#mobility-warnings-box", "#mobility-warnings-summary", "#mobility-warnings", warnings, () => "warning");
}

function originText(r) {
  if (!r.origins) return r.non_local ? '<span class="muted">no places to compare</span>' : "";
  if (r.origins.none_fit) return '<span class="muted">none of the places fits</span>';
  return r.origins.candidates.filter((c) => c.fits).slice(0, 2)
    .map((c) => `${esc(c.region)} <small class="muted">${Math.round(c.probability * 100)}%</small>`).join(", ");
}

function rows({ results }) {
  return results.map((r) => ({ specimen_id: r.specimen_id, site: r.site, tooth: r.tooth, d18O: r.d18O, d18O_material: r.d18O_material,
    d18O_drinking_water: r.d18O_dw?.estimate, d18O_dw_ci_low: r.d18O_dw?.ci_low, d18O_dw_ci_high: r.d18O_dw?.ci_high,
    sr87_86: r.sr87_86, sr_status: r.sr_status, d18O_status: r.d18O_status, non_local: r.non_local,
    best_origin: r.origins && !r.origins.none_fit ? r.origins.candidates[0].region : null,
    best_origin_probability: r.origins && !r.origins.none_fit ? r.origins.candidates[0].probability : null, notes: r.notes.join("; ") }));
}
