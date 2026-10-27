// Collagen diet mixing: the share of each food group in the diet, from δ13C, δ15N and δ34S.
import { oneTableCalc } from "./calc.js";
import { biplotChart } from "./chart.js";
import { $, $$, download, esc, num, plural, renderIssues, renderReady, renderWarnings, table, toast, toCsv } from "./util.js";

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const SOURCE_KEYS = { name: "Name", d13C: "δ13C", d13C_sd: "δ13C SD", d15N: "δ15N", d15N_sd: "δ15N SD", d34S: "δ34S", d34S_sd: "δ34S SD" };
const MAX_SOURCES = 6;

export const mixing = oneTableCalc({
  name: "mixing",
  plural: "collagen samples",
  working: "Weighing diets",
  fields: ["offset_d13C", "offset_d13C_sd", "offset_d15N", "offset_d15N_sd", "offset_d34S", "offset_d34S_sd", "measurement_sd_permil", "draws"],
  readSettings: (out) => ({ ...out, sources: readSources() }),
  writeSettings: (o) => { if (o.sources) writeSources(o.sources); },
  init: (calc) => {
    $("#btn-mixing-add-source").addEventListener("click", () => {
      const sources = readSources();
      if (sources.length >= MAX_SOURCES) return toast(`At most ${MAX_SOURCES} food groups.`);
      writeSources([...sources, { name: `Food ${sources.length + 1}` }]);
    });
    $("#mixing-sources").addEventListener("click", (e) => {
      const row = e.target.closest("[data-remove-source]");
      if (!row) return;
      const sources = readSources();
      if (sources.length <= 2) return toast("At least two food groups are needed.");
      sources.splice(Number(row.dataset.removeSource), 1);
      writeSources(sources);
    });
    $("#btn-mixing-csv").addEventListener("click", () => download("weanage_diet_shares.csv", new Blob([toCsv(shareRows(calc.own().output))], { type: "text/csv" })));
    $("#btn-mixing-json").addEventListener("click", () => download("weanage_diet_results.json",
      new Blob([JSON.stringify({ options: calc.own().options, ...calc.own().output }, null, 2)])));
  },
  renderData,
  renderResults,
});

// Food groups, edited as a table of inputs
function writeSources(sources) {
  const cell = (i, key, value) => `<td><input data-source="${i}" data-key="${key}" aria-label="${SOURCE_KEYS[key]} of food group ${i + 1}"
    ${key === "name" ? 'type="text"' : 'type="number" step="0.1"'} value="${esc(value ?? "")}"></td>`;
  $("#mixing-sources tbody").innerHTML = sources.map((s, i) => `<tr>${Object.keys(SOURCE_KEYS).map((key) => cell(i, key, s[key])).join("")}
    <td><button class="ghost tiny" type="button" data-remove-source="${i}" aria-label="Remove food group ${i + 1}">Remove</button></td></tr>`).join("");
}

function readSources() {
  const rows = {};
  for (const input of $$("#mixing-sources input")) {
    const value = input.value.trim();
    (rows[input.dataset.source] ??= {})[input.dataset.key] = input.dataset.key === "name" ? value : value === "" ? null : Number(value);
  }
  return Object.values(rows);
}

// Data
function renderData({ report, samples }) {
  renderIssues(report ? report.issues : []);
  const sites = new Set(samples.map((s) => s.site)).size;
  renderReady(samples.length && `${plural(samples.length, "sample")} from ${plural(sites, "site")} loaded.`);
  $("#mixing-samples-card").hidden = !samples.length;
  $("#mixing-count").textContent = `· ${plural(samples.length, "sample")}`;
  $("#sb-data").textContent = samples.length ? plural(samples.length, "collagen sample") : "No data loaded";
  table($("#mixing-sample-table"), [
    { label: "Sample", key: "specimen_id" },
    { label: "Site", key: "site" },
    { label: "Species", key: "species" },
    { label: "δ¹³C", cls: "num", render: (s) => num(s.d13C) },
    { label: "δ¹⁵N", cls: "num", render: (s) => num(s.d15N) },
    { label: "δ³⁴S", cls: "num", render: (s) => num(s.d34S) },
    { label: "Notes", key: "notes" },
  ], samples);
}

// Results
function renderResults({ output }) {
  const { results, groups, sources, offsets, placeholder } = output;
  const names = sources.map((s) => s.name);
  $("#mixing-placeholder").hidden = !placeholder;
  biplotChart($("#mixing-biplot"), {
    title: "Collagen δ13C and δ15N with the food groups plus offsets",
    points: results.map((r) => ({ x: r.d13C, y: r.d15N, group: [r.site, r.species].filter(Boolean).join(" · "),
      label: `${esc(r.specimen_id)}: δ¹³C ${num(r.d13C)}‰, δ¹⁵N ${num(r.d15N)}‰` })),
    sources: sources.map((s) => ({ name: s.name, x: s.d13C + offsets.d13C.mean, y: s.d15N + offsets.d15N.mean,
      sdx: Math.hypot(s.d13C_sd, offsets.d13C.sd || 0), sdy: Math.hypot(s.d15N_sd, offsets.d15N.sd || 0) })),
  });
  table($("#mixing-group-table"), [
    { label: "Group", key: "group" },
    { label: "Samples", key: "n", cls: "num" },
    ...names.map((name) => ({ label: esc(name), cls: "num", render: (g) => pct(g.shares[name]) })),
  ], groups);
  table($("#mixing-result-table"), [
    { label: "Sample", render: (r) => `${esc(r.specimen_id)} <small class="muted">${esc(r.site)}</small>` },
    { label: "Isotopes", render: (r) => r.isotopes.map((i) => i.replace("d", "δ")).join(", ") },
    ...names.map((name) => ({ label: esc(name), cls: "num",
      render: (r) => `${pct(r.shares[name].estimate)} <small class="muted">(${pct(r.shares[name].ci_low)}–${pct(r.shares[name].ci_high)})</small>` })),
    { label: "Warnings", cls: "num", render: (r) => (r.warnings.length ? `<span class="warn-text">${r.warnings.length}</span>` : "") },
  ], results);
  const warnings = [...new Set(results.flatMap((r) => r.warnings))].map((w) => {
    const which = results.filter((r) => r.warnings.includes(w)).map((r) => r.specimen_id);
    return `${w} (${which.length > 5 ? plural(which.length, "sample") : which.join(", ")})`;
  });
  renderWarnings("#mixing-warnings-box", "#mixing-warnings-summary", "#mixing-warnings", warnings, () => "warning");
}

function shareRows({ results, sources }) {
  return results.map((r) => ({
    specimen_id: r.specimen_id, site: r.site, species: r.species, period: r.period, d13C: r.d13C, d15N: r.d15N, d34S: r.d34S,
    isotopes: r.isotopes.join(" "), effective_draws: r.effective_draws,
    ...Object.fromEntries(sources.flatMap((s) => [[s.name, r.shares[s.name].estimate], [`${s.name} 2.5%`, r.shares[s.name].ci_low],
      [`${s.name} 97.5%`, r.shares[s.name].ci_high]])),
    warnings: r.warnings.join(" | "),
  }));
}
