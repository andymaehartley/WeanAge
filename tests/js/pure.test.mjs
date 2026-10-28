// Unit tests for the web app's pure functions: run with `node --test "tests/js/*.test.mjs"`.
import assert from "node:assert/strict";
import { test } from "node:test";

import { boneAges, lifeTableAges, matchAges } from "../../src/weanage/web/dental.js";
import { belongs, evidence, individuals } from "../../src/weanage/web/individuals.js";
import { readStageTable } from "../../src/weanage/web/killoff.js";
import { methodRuns } from "../../src/weanage/web/methods.js";

const dentalOutput = { results: [
  { specimen_id: "B1", age_min_months: 6, age_max_months: 18, estimate_months: 12 },
  { specimen_id: "B2", age_min_months: 30, age_max_months: null, estimate_months: null },
  { specimen_id: "B3", age_min_months: null, age_max_months: null, estimate_months: null },
] };

test("belongs matches the ID itself or a tooth of it, not a longer ID", () => {
  assert.ok(belongs("04/293", "04/293"));
  assert.ok(belongs("04/293 C", "04/293"));
  assert.ok(!belongs("04/2930", "04/293"));
});

test("dental ages go to young animals in the bone calculation, in months", () => {
  const samples = [
    { specimen_id: "B1", age_class: "infant", age_months: 3 },
    { specimen_id: "B2", age_class: "infant" },
    { specimen_id: "B3", age_class: "infant" },
    { specimen_id: "A1", age_class: "adult" },
    { specimen_id: "B1x", age_class: "adult" },
  ];
  const { changed, matched } = matchAges(dentalOutput, samples, boneAges);
  assert.equal(matched, 2);
  assert.deepEqual(changed[0], { specimen_id: "B1", age_class: "infant", age_months: null, age_min_months: 6, age_max_months: 18 });
  assert.equal(changed[1].age_max_months, 31, "an open-ended age gets a one-month range");
  assert.equal(changed[2], samples[2], "no age, unchanged");
  assert.equal(changed[3], samples[3]);
});

test("adults in the bone calculation are not given a child's age", () => {
  const { matched } = matchAges(dentalOutput, [{ specimen_id: "B1", age_class: "adult" }], boneAges);
  assert.equal(matched, 0);
});

test("dental ages go to life tables in years, open-ended stays open", () => {
  const samples = [{ specimen_id: "B1", age_min_years: 20 }, { specimen_id: "B2" }, { specimen_id: "Z" }];
  const { changed, matched } = matchAges(dentalOutput, samples, lifeTableAges);
  assert.equal(matched, 2);
  assert.equal(changed[0].age_min_years, 0.5);
  assert.equal(changed[0].age_max_years, 1.5);
  assert.equal(changed[1].age_min_years, 2.5);
  assert.equal(changed[1].age_max_years, null);
  assert.equal(changed[2], samples[2]);
});

test("readStageTable reads 'stage: from-to' lines and skips the rest", () => {
  assert.deepEqual(readStageTable("A: 0-2\nB, 2, 6\n C : 6.5 – 12 \nnonsense\n"), { A: [0, 2], B: [2, 6], C: [6.5, 12] });
});

const appState = {
  results: [{ specimen_id: "G1", site: "Mikulčice", growth_table: "none",
    model_average: { onset: { estimate: 6 }, completion: { estimate: 30 }, midpoint: { estimate: 18 } },
    diagnostics: { stress_episodes: [{ from_age: 10, to_age: 14 }] }, milk_share: { below_half_age: 20 } }],
  mobility: { output: { results: [{ specimen_id: "G1 M1", site: "Mikulčice", tooth: "M1", non_local: true, sr87_86: 0.7123,
    origins: { none_fit: false, candidates: [{ region: "Bohemia", probability: 0.7, fits: true }] } }, { specimen_id: "G2", site: "Mikulčice", non_local: false }] } },
  lifetable: { samples: [{ specimen_id: "G1", site: "Mikulčice", age_min_years: 3, age_max_years: 5 }] },
};

test("individuals are gathered across calculations, those in most first", () => {
  const people = individuals(appState);
  assert.deepEqual(people.map((p) => p.id), ["G1", "G2"]);
  assert.deepEqual(people[0].calcs.sort(), ["lifetable", "mobility", "tooth"]);
});

test("evidence puts everything on one timeline in months", () => {
  const { rows, findings } = evidence(appState, "G1");
  const labels = rows.map((r) => r.label);
  assert.deepEqual(labels, ["Weaning (dentine)", "Stress episodes", "Milk below half", "Age at death (skeleton)"]);
  assert.deepEqual(rows[3].items[0], { from: 36, to: 60, text: rows[3].items[0].text });
  const mobility = findings.find((f) => f.calc === "mobility").text;
  assert.match(mobility, /non-local/);
  assert.match(mobility, /Bohemia/);
});

test("methodRuns counts individuals for dental, rows elsewhere, and says what mobility used", () => {
  const calc = (name, own) => ({ name, own: () => own });
  const runs = methodRuns({ results: appState.results, options: { x: 1 } }, {
    dental: calc("dental", { options: {}, samples: [1, 2, 3], output: { results: [1] } }),
    leh: calc("leh", { options: {}, samples: [1, 2, 3], output: { results: [1] } }),
    mobility: calc("mobility", { options: {}, samples: [1], output: { results: [{ sr87_86: 0.71 }] } }),
    mixing: calc("mixing", { options: {}, samples: [1] }),
  });
  assert.deepEqual(Object.keys(runs).sort(), ["dental", "leh", "mobility", "tooth"]);
  assert.equal(runs.dental.n, 1);
  assert.equal(runs.leh.n, 3);
  assert.deepEqual(runs.tooth.details.growth_tables, []);
  assert.deepEqual(runs.mobility.details, { d18O: false, sr: true, origins: false });
});
