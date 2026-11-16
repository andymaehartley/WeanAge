// The bottom bar's Next button: its label, when it can be pressed and what it does.
import assert from "node:assert/strict";
import { test } from "node:test";

import { nextStep, sequence } from "../../src/weanage/web/flow.js";

const page = (facts) => ({ mode: "tooth", chosen: true, dataReady: true, readyText: "3 samples loaded.", running: false, invalid: null,
  compareOpen: false, individualsOpen: false, methodsOpen: false, ...facts });

test("labels match the tab names, in working order", () => {
  assert.deepEqual(sequence("tooth"), ["data", "settings", "results", "compare", "individuals"]);
  assert.deepEqual(sequence("killoff"), ["data", "settings", "results", "individuals"]);
  assert.equal(nextStep(page({ view: "data" })).label, "Next: Settings");
  assert.equal(nextStep(page({ view: "settings" })).label, "Next: Results");
  assert.equal(nextStep(page({ view: "results", compareOpen: true })).label, "Next: Compare");
  assert.equal(nextStep(page({ view: "results", mode: "killoff", individualsOpen: true })).label, "Next: Individuals");
  assert.equal(nextStep(page({ view: "individuals", methodsOpen: true })).label, "Next: Methods text");
});

test("Data: dark until a calculation is ticked and its data are loaded", () => {
  assert.equal(nextStep(page({ view: "data", chosen: false, dataReady: false })).enabled, false);
  assert.match(nextStep(page({ view: "data", chosen: false, dataReady: false })).hint, /tick a calculation/);
  assert.equal(nextStep(page({ view: "data", dataReady: false })).enabled, false);
  const ready = nextStep(page({ view: "data" }));
  assert.equal(ready.enabled, true);
  assert.deepEqual(ready.action, { go: "settings" });
  assert.equal(ready.back, null);
});

test("Settings: dark while a setting is wrong or a run is going, otherwise runs the calculation", () => {
  const wrong = nextStep(page({ view: "settings", invalid: "Bootstrap refits" }));
  assert.equal(wrong.enabled, false);
  assert.match(wrong.hint, /Bootstrap refits/);
  assert.equal(nextStep(page({ view: "settings", running: true })).enabled, false);
  const ok = nextStep(page({ view: "settings" }));
  assert.equal(ok.enabled, true);
  assert.deepEqual(ok.action, { run: true });
  assert.equal(ok.back, "data");
});

test("Results and Compare lead to the next page that is open", () => {
  assert.equal(nextStep(page({ view: "results" })).enabled, false);
  assert.deepEqual(nextStep(page({ view: "results", individualsOpen: true })).action, { go: "individuals" });
  assert.deepEqual(nextStep(page({ view: "compare", individualsOpen: true })).action, { go: "individuals" });
  assert.equal(nextStep(page({ view: "individuals" })).enabled, false);
  assert.deepEqual(nextStep(page({ view: "individuals", methodsOpen: true })).action, { methods: true });
});
