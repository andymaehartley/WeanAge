// Dental age: children's age at death from tooth formation stages, which can be passed on as ages
// at death to the bone calculation and to life tables.
import { api } from "./api.js";
import { setBoneReport } from "./bone.js";
import { oneTableCalc } from "./calc.js";
import { forestChart } from "./chart.js";
import { lifetable } from "./lifetable.js";
import { $, ageNum, ageText, download, esc, plural, renderIssues, renderReady, renderWarnings, table, toast, toCsv, toUnit, unitWord } from "./util.js";

export const dental = oneTableCalc({
  name: "dental",
  plural: "scored teeth",
  working: "Estimating ages",
  fields: ["interval_z", "discordance_z"],
  init: (calc) => {
    $("#btn-dental-csv").addEventListener("click", () => download("weanage_dental_ages.csv", new Blob([toCsv(ageRows(calc.own().output))], { type: "text/csv" })));
    $("#btn-dental-to-bone").addEventListener("click", () => useInBone(calc.own().output, calc.app()));
    $("#btn-dental-to-life").addEventListener("click", () => useInLifeTables(calc.own().output, calc.app()));
  },
  renderData,
  renderResults,
});

function renderData({ report, samples }) {
  const people = report?.individuals || [];
  renderIssues(report ? report.issues : []);
  renderReady(samples.length && `${samples.length} ${samples.length === 1 ? "tooth" : "teeth"} from ${plural(people.length, "individual")} loaded.`);
  $("#dental-card").hidden = !samples.length;
  $("#dental-count").textContent = `· ${plural(people.length, "individual")}`;
  $("#sb-data").textContent = samples.length ? plural(people.length, "individual") : "No data loaded";
  table($("#dental-table"), [
    { label: "Individual", key: "specimen_id" },
    { label: "Site", key: "site" },
    { label: "Tooth", key: "tooth" },
    { label: "Stage", key: "stage" },
    { label: "Notes", key: "notes" },
  ], samples);
}

const range = (r) => (r.age_max_months == null ? `at least ${ageText(r.age_min_months)}` : `${ageNum(r.age_min_months)}–${ageNum(r.age_max_months)}`);

function renderResults({ output }) {
  const { results, placeholder } = output;
  $("#dental-placeholder").hidden = !placeholder;
  const dated = results.filter((r) => r.estimate_months != null).sort((a, b) => a.estimate_months - b.estimate_months);
  $("#dental-chart").innerHTML = dated.length ? "" : '<p class="muted">No individual could be aged.</p>';
  if (dated.length) forestChart($("#dental-chart"), dated.map((r) => ({
    label: r.specimen_id, mean: toUnit(r.estimate_months), lo: toUnit(r.age_min_months), hi: toUnit(r.age_max_months),
    values: r.teeth.filter((t) => t.estimate != null).map((t) => ({ v: toUnit(t.estimate), label: `${esc(t.tooth)} ${esc(t.stage)}: ${ageText(t.estimate)}` })),
  })), `Age at death (${unitWord()}): squares = estimate, bars = range passed on, dots = single teeth`);
  table($("#dental-results"), [
    { label: "Individual", key: "specimen_id" },
    { label: "Site", key: "site" },
    { label: "Teeth", cls: "num", render: (r) => r.teeth.length },
    { label: `Age (${unitWord()})`, cls: "num", render: (r) => (r.estimate_months == null ? "—" : ageNum(r.estimate_months)) },
    { label: "Range passed on", cls: "num", render: range },
    { label: "Stages", render: (r) => r.teeth.map((t) => `${esc(t.tooth)} ${esc(t.stage)}`).join(", ") },
  ], results);
  renderWarnings("#dental-warnings-box", "#dental-warnings-summary", "#dental-warnings",
    results.flatMap((r) => r.warnings.map((w) => `${r.specimen_id}: ${w}`)), () => "warning");
}

function ageRows({ results }) {
  return results.map((r) => ({ specimen_id: r.specimen_id, site: r.site, species: r.species, period: r.period,
    age_months: r.estimate_months, sd_months: r.sd_months, age_min_months: r.age_min_months, age_max_months: r.age_max_months,
    teeth: r.teeth.map((t) => `${t.tooth} ${t.stage}`).join("; "), warnings: r.warnings.join(" | ") }));
}

/** Give individuals with the same specimen ID in another calculation these ages at death. */
async function passOn(output, samples, update, check, apply, where) {
  const ages = new Map(output.results.filter((r) => r.age_min_months != null).map((r) => [r.specimen_id, r]));
  let matched = 0;
  const changed = samples.map((s) => {
    const r = ages.get(s.specimen_id);
    const values = r && update(s, r);
    if (!values) return s;
    matched += 1;
    return { ...s, ...values };
  });
  if (!matched) return toast(`No samples in ${where} have the same specimen IDs as these individuals.`);
  try {
    apply(await check(changed), true);
    toast(`Ages at death set for ${plural(matched, "individual")} in ${where}.`, "ok");
  } catch (e) {
    toast(e.message);
  }
}

function useInBone(output, appState) {
  passOn(output, appState.bone.samples, (s, r) => s.age_class !== "adult" && {
    age_months: null, age_min_months: r.age_min_months, age_max_months: r.age_max_months ?? r.age_min_months + 1,
  }, api.boneRecords, setBoneReport, "the bone calculation");
}

function useInLifeTables(output, appState) {
  passOn(output, appState.lifetable.samples, (s, r) => ({
    age_min_years: r.age_min_months / 12, age_max_years: r.age_max_months == null ? null : r.age_max_months / 12,
    age_min_months: null, age_max_months: null,
  }), (rows) => api.calcRecords("lifetable", rows), lifetable.setReport, "the life tables");
}
