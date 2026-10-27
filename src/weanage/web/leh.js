// Enamel hypoplasia timing: when each defect formed, set against the same individual's weaning
// interval and stress episodes from the tooth calculation.
import { oneTableCalc } from "./calc.js";
import { forestChart } from "./chart.js";
import { $, ageNum, ageText, download, esc, num, plural, renderIssues, renderReady, renderWarnings, table, toCsv, toUnit, unitWord } from "./util.js";

export const leh = oneTableCalc({
  name: "leh",
  plural: "hypoplasia defects",
  working: "Dating defects",
  fields: ["measurement_sd_mm", "draws"],
  prepareOptions: (options, state) => ({ ...options, dentine: dentineContext(state) }),
  init: (calc) => {
    $("#btn-leh-csv").addEventListener("click", () => download("weanage_hypoplasia_ages.csv", new Blob([toCsv(defectRows(calc.own().output))], { type: "text/csv" })));
  },
  renderData,
  renderResults,
});

/** What the tooth calculation found for each individual: its weaning interval and stress episodes. */
function dentineContext(state) {
  const milestone = (r, key) => {
    const v = r.model_average?.[key];
    return v?.estimate != null && !v.beyond ? v.estimate : null;
  };
  return Object.fromEntries((state.results || []).map((r) => [r.specimen_id, {
    onset: milestone(r, "onset"), midpoint: milestone(r, "midpoint"), completion: milestone(r, "completion"),
    stress: (r.diagnostics?.stress_episodes || []).map((e) => [e.from_age, e.to_age]),
  }]));
}

function renderData({ report, samples }) {
  const people = report?.individuals || [];
  renderIssues(report ? report.issues : []);
  renderReady(samples.length && `${plural(samples.length, "defect")} on ${plural(people.length, "individual")} loaded.`);
  $("#leh-card").hidden = !samples.length;
  $("#leh-count").textContent = `· ${plural(people.length, "individual")}`;
  $("#sb-data").textContent = samples.length ? plural(samples.length, "defect") : "No data loaded";
  table($("#leh-table"), [
    { label: "Individual", key: "specimen_id" },
    { label: "Tooth", key: "tooth" },
    { label: "Defect above CEJ (mm)", cls: "num", render: (s) => num(s.defect_mm, 1) },
    { label: "Crown height (mm)", cls: "num", render: (s) => num(s.crown_height_mm, 1) },
    { label: "Notes", key: "notes" },
  ], samples);
}

const WEANING = { during: "during weaning", before: "before weaning", after: "after weaning" };

function renderResults({ output }) {
  const { results, individuals, share_during_weaning: share, placeholder, warnings } = output;
  $("#leh-placeholder").hidden = !placeholder;
  $("#leh-summary").innerHTML = share == null
    ? "<p>No defect could be set against a weaning interval: run the tooth calculation for the same individuals first.</p>"
    : `<p><strong>${Math.round(share * 100)}%</strong> of the defects that can be compared formed during weaning (between the onset and completion of the δ¹⁵N fall).</p>`;
  forestChart($("#leh-chart"), individuals.map((p) => ({
    label: p.specimen_id,
    mean: toUnit(p.weaning?.midpoint), lo: toUnit(p.weaning?.onset), hi: toUnit(p.weaning?.completion),
    values: results.filter((r) => r.specimen_id === p.specimen_id)
      .map((r) => ({ v: toUnit(r.age.estimate), label: `${esc(r.tooth)} defect at ${num(r.defect_mm, 1)} mm: ${ageText(r.age.estimate)}` })),
  })), `Age (${unitWord()}): dots = defects; bar = weaning in the dentine, square = its midpoint`);
  table($("#leh-results"), [
    { label: "Individual", key: "specimen_id" },
    { label: "Tooth", key: "tooth" },
    { label: "Height (mm)", cls: "num", render: (r) => `${num(r.defect_mm, 1)} / ${num(r.crown_height_mm, 1)}` },
    { label: `Age (${unitWord()})`, cls: "num", render: (r) => `${ageNum(r.age.estimate)} <small class="muted">(${ageNum(r.age.ci_low)}–${ageNum(r.age.ci_high)})</small>` },
    { label: "Against weaning", render: (r) => (r.dentine?.weaning ? WEANING[r.dentine.weaning] : "—") },
    { label: "Stress episode", render: (r) => (r.dentine?.stress_episodes.length ? "yes" : r.dentine ? "no" : "—") },
  ], results);
  renderWarnings("#leh-warnings-box", "#leh-warnings-summary", "#leh-warnings", warnings, () => "warning");
}

function defectRows({ results }) {
  return results.map((r) => ({ specimen_id: r.specimen_id, site: r.site, tooth: r.tooth, defect_id: r.defect_id,
    defect_mm: r.defect_mm, crown_height_mm: r.crown_height_mm, age_months: r.age.estimate, age_ci_low: r.age.ci_low,
    age_ci_high: r.age.ci_high, against_weaning: r.dentine?.weaning, with_stress_episode: r.dentine ? r.dentine.stress_episodes.length > 0 : null }));
}
