// One page per individual: everything the calculations found for one specimen ID, on one timeline.
// The gathering functions are pure (state in, plain objects out), so they are unit-tested in tests/js.
import { timelineChart } from "./chart.js";
import { $, ageText, esc, num, plural, toUnit, unitWord } from "./util.js";

const LABELS = { tooth: "Tooth (dentine δ¹⁵N)", bone: "Bone calculation", enamel: "Enamel (cattle)", dental: "Dental age",
  leh: "Enamel hypoplasia", lifetable: "Life tables", mobility: "Mobility", mixing: "Diet mixing", killoff: "Kill-off" };
const pct = (v) => `${Math.round(v * 100)}%`;
const range = (a, b) => (b == null ? `at least ${ageText(a)}` : `${ageText(a)}–${ageText(b)}`);

/** A record belongs to an individual if its ID is the individual's, or starts with it ("04/293 C" for a tooth of 04/293). */
export const belongs = (recordId, id) => recordId === id || String(recordId).startsWith(`${id} `);

/** Every calculation's records, as [calc, id, record] (results where there are per-individual results, else samples). */
export function records(state) {
  const out = [];
  const push = (calc, list, key = "specimen_id") => list?.forEach((r) => out.push([calc, String(r[key]), r]));
  push("tooth", state.results);
  push("bone", state.bone?.samples);
  push("enamel", state.enamel?.output?.results);
  push("dental", state.dental?.output?.results);
  push("leh", state.leh?.output?.results);
  push("mobility", state.mobility?.output?.results);
  push("mixing", state.mixing?.output?.results);
  push("lifetable", state.lifetable?.samples);
  push("killoff", state.killoff?.samples);
  return out;
}

/** The individuals found, with the calculations each appears in; those in more calculations first. */
export function individuals(state) {
  const seen = new Map();
  for (const [calc, id, r] of records(state)) {
    const key = calc === "mobility" || calc === "leh" ? id.split(" ")[0] : id; // a tooth of an individual
    const entry = seen.get(key) ?? { id: key, site: r.site, calcs: new Set() };
    entry.calcs.add(calc);
    seen.set(key, entry);
  }
  return [...seen.values()].map((e) => ({ ...e, calcs: [...e.calcs] }))
    .sort((a, b) => b.calcs.length - a.calcs.length || a.id.localeCompare(b.id, undefined, { numeric: true }));
}

/** What each calculation found for one individual: timeline rows (ages in months) and short findings. */
export function evidence(state, id) {
  const rows = [];
  const findings = [];
  const mine = records(state).filter(([, rid]) => belongs(rid, id));
  const of = (calc) => mine.filter(([c]) => c === calc).map(([, , r]) => r);
  const add = (calc, text) => findings.push({ calc, label: LABELS[calc], text });

  for (const r of of("tooth")) {
    const m = r.model_average || {};
    const items = [];
    if (m.onset?.estimate != null && m.completion?.estimate != null && !m.onset.beyond && !m.completion.beyond) {
      items.push({ from: m.onset.estimate, to: m.completion.estimate, text: `weaning ${range(m.onset.estimate, m.completion.estimate)}` });
    }
    if (m.midpoint?.estimate != null && !m.midpoint.beyond) items.push({ at: m.midpoint.estimate, text: `midpoint ${ageText(m.midpoint.estimate)}` });
    if (items.length) rows.push({ label: "Weaning (dentine)", items });
    const stress = r.diagnostics?.stress_episodes || [];
    if (stress.length) rows.push({ label: "Stress episodes", items: stress.map((e) => ({ from: e.from_age, to: e.to_age, text: `stress ${range(e.from_age, e.to_age)}` })) });
    const half = r.milk_share?.below_half_age;
    if (half != null) rows.push({ label: "Milk below half", items: [{ at: half, text: `milk below half the diet at ${ageText(half)}` }] });
    add("tooth", [m.midpoint?.estimate != null && !m.midpoint.beyond ? `weaning midpoint ${ageText(m.midpoint.estimate)}` : "no weaning age reported",
      half != null && `milk below half at ${ageText(half)}`, stress.length && plural(stress.length, "stress episode")].filter(Boolean).join("; "));
  }
  for (const r of of("bone")) {
    if (r.age_class !== "adult" && r.age_min_months != null) {
      rows.push({ label: "Age at death (bone data)", items: [{ from: r.age_min_months, to: r.age_max_months ?? r.age_min_months, text: `died ${range(r.age_min_months, r.age_max_months)}` }] });
    }
    add("bone", `${r.age_class === "adult" ? "adult" : "young"}${r.sex ? ` (${r.sex === "f" ? "female" : "male"})` : ""}; bone δ¹⁵N ${num(r.d15N, 1)}‰`);
  }
  for (const r of of("dental")) {
    if (r.age_min_months != null) {
      rows.push({ label: "Age at death (teeth)", items: [{ from: r.age_min_months, to: r.age_max_months, at: r.estimate_months,
        text: `dental age ${r.estimate_months != null ? ageText(r.estimate_months) : ""} (${range(r.age_min_months, r.age_max_months)})` }] });
    }
    add("dental", r.estimate_months != null ? `age at death about ${ageText(r.estimate_months)} (${range(r.age_min_months, r.age_max_months)})` : `at least ${ageText(r.age_min_months)}`);
  }
  for (const r of of("lifetable")) {
    const lo = r.age_min_years * 12;
    const hi = r.age_max_years == null ? null : r.age_max_years * 12;
    rows.push({ label: "Age at death (skeleton)", items: [{ from: lo, to: hi ?? lo, text: `died ${range(lo, hi)}` }] });
    add("lifetable", `age at death ${range(lo, hi)}`);
  }
  const defects = of("leh");
  if (defects.length) {
    rows.push({ label: "Enamel hypoplasia", items: defects.map((d) => ({ from: d.age.ci_low, to: d.age.ci_high, at: d.age.estimate,
      text: `${d.tooth} defect at ${ageText(d.age.estimate)}${d.dentine?.weaning ? `, ${d.dentine.weaning} weaning` : ""}` })) });
    const during = defects.filter((d) => d.dentine?.weaning === "during").length;
    add("leh", `${plural(defects.length, "defect")} at ${defects.map((d) => ageText(d.age.estimate)).join(", ")}${during ? `; ${during} during weaning` : ""}`);
  }
  for (const r of of("enamel")) {
    const parts = [r.season?.birth_index && `birth index ${num(r.season.birth_index.estimate, 2)}`,
      r.rumen?.detected && `rumen transition at ${num(r.rumen.transition_mm.estimate, 1)} mm`,
      r.diet?.share_c4 && `${pct(r.diet.share_c4.estimate)} C4 plants`,
      r.strontium?.shifts?.length && plural(r.strontium.shifts.length, "strontium shift")];
    add("enamel", parts.filter(Boolean).join("; ") || "no clear signals");
  }
  for (const r of of("mobility")) {
    const origin = r.origins && !r.origins.none_fit ? `; perhaps from ${r.origins.candidates[0].region}` : "";
    add("mobility", `${r.tooth ? `${r.tooth}: ` : ""}${r.non_local ? "non-local" : "local"}${r.d18O_dw ? `; drinking water δ¹⁸O ${num(r.d18O_dw.estimate, 1)}‰` : ""}${r.sr87_86 != null ? `; ⁸⁷Sr/⁸⁶Sr ${num(r.sr87_86, 5)}` : ""}${origin}`);
  }
  for (const r of of("mixing")) {
    const top = Object.entries(r.shares).sort((a, b) => b[1].estimate - a[1].estimate).slice(0, 2);
    add("mixing", `mostly ${top.map(([name, v]) => `${name} (${pct(v.estimate)})`).join(" and ")}`);
  }
  for (const r of of("killoff")) add("killoff", r.payne_stage ? `wear stage ${r.payne_stage}` : r.wear_stage ? `wear stage ${r.wear_stage}` : `age ${range(r.age_min_months, r.age_max_months)}`);
  return { rows, findings };
}

let state;
let hooks; // { open(calc, id) }

export function initIndividuals(appState, appHooks) {
  state = appState;
  hooks = appHooks;
  state.individual = null;
  const choose = (id) => {
    state.individual = id;
    renderIndividuals();
    $(`#individual-list [data-individual="${CSS.escape(id)}"]`)?.focus();
  };
  $("#individual-list").addEventListener("click", (e) => {
    const b = e.target.closest("[data-individual]");
    if (b) choose(b.dataset.individual);
  });
  $("#individual-list").addEventListener("keydown", (e) => {
    const ids = [...document.querySelectorAll("#individual-list [data-individual]")].map((b) => b.dataset.individual);
    const moves = { ArrowDown: 1, ArrowUp: -1 };
    if (!(e.key in moves)) return;
    e.preventDefault();
    choose(ids[Math.min(Math.max(ids.indexOf(state.individual) + moves[e.key], 0), ids.length - 1)]);
  });
  $("#individual-filter").addEventListener("input", renderIndividuals);
  $("#individual-findings").addEventListener("click", (e) => {
    const b = e.target.closest("[data-open]");
    if (b) hooks.open(b.dataset.open, state.individual);
  });
}

export const hasIndividuals = (appState) => records(appState).length > 0;

export function renderIndividuals() {
  const filter = $("#individual-filter").value.trim().toLowerCase();
  const people = individuals(state);
  const shown = people.filter((p) => !filter || p.id.toLowerCase().includes(filter));
  if (!people.some((p) => p.id === state.individual)) state.individual = people[0]?.id ?? null;
  $("#individual-count").textContent = `· ${plural(people.length, "individual")}`;
  $("#individual-list").innerHTML = shown.map((p) => {
    const chosen = p.id === state.individual;
    return `<li role="none"><button role="option" aria-selected="${chosen}" tabindex="${chosen ? 0 : -1}" data-individual="${esc(p.id)}" class="${chosen ? "active" : ""}">
      <span><strong>${esc(p.id)}</strong><small>${esc(p.site ?? "")}</small></span><span class="age">${p.calcs.length}</span></button></li>`;
  }).join("") || '<li class="muted small">No match.</li>';
  const person = people.find((p) => p.id === state.individual);
  $("#individual-main").hidden = !person;
  if (!person) return;
  const { rows, findings } = evidence(state, person.id);
  $("#individual-title").textContent = person.id;
  $("#individual-meta").textContent = `${person.site ?? ""} · in ${plural(person.calcs.length, "calculation")}: ${person.calcs.map((c) => LABELS[c]).join(", ")}`;
  $("#individual-chart").hidden = !rows.length;
  if (rows.length) {
    timelineChart($("#individual-chart"), rows.map((r) => ({ ...r, items: r.items.map((i) => ({ ...i, from: toUnit(i.from), to: toUnit(i.to), at: toUnit(i.at) })) })),
      { title: `What happened at what age: ${person.id}`, xLabel: `Age (${unitWord()})` });
  }
  $("#individual-findings").innerHTML = findings.map((f) => `<dt>${esc(f.label)}</dt><dd>${esc(f.text)}
    <button class="link small" type="button" data-open="${f.calc}">open</button></dd>`).join("");
}
