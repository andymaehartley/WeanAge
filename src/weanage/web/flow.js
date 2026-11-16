// The bar at the bottom of every page: Back on the left, and on the right a Next button named after the
// tab it leads to. Next stays dark and cannot be pressed until the page has what the next step needs.
// nextStep() is pure (page facts in, what the bar shows out), so it is unit-tested in tests/js.
import { $, $$ } from "./util.js";

const TAB = { data: "Data", settings: "Settings", results: "Results", compare: "Compare", individuals: "Individuals", plan: "Plan sampling" };

/** The pages in working order for a calculation (Compare is for the tooth calculation only). */
export const sequence = (mode) => ["data", "settings", "results", ...(mode === "tooth" ? ["compare"] : []), "individuals"];

/**
 * What the bar shows on one page.
 * page: { view, mode, chosen (a calculation is ticked), dataReady, readyText, running, invalid (label of the first
 *         setting that is not valid, or null), compareOpen, individualsOpen, methodsOpen }
 * Returns { back, label, action: {go: view} | {run: true} | {methods: true}, enabled, hint }.
 */
export function nextStep(page) {
  const steps = sequence(page.mode);
  const at = steps.indexOf(page.view);
  const back = at > 0 ? steps[at - 1] : null;
  if (page.view === "plan") {
    return { back: null, label: "Next: Data", action: { go: "data" }, enabled: true, hint: "Planning is separate from the analysis: go to Data when you have measurements." };
  }
  if (page.view === "data") {
    const hint = !page.chosen ? "Load a file, then tick a calculation, to continue."
      : page.dataReady ? page.readyText : "Load data for the ticked calculation to continue.";
    return { back, label: "Next: Settings", action: { go: "settings" }, enabled: Boolean(page.chosen && page.dataReady), hint };
  }
  if (page.view === "settings") {
    const enabled = page.dataReady && !page.running && !page.invalid;
    const hint = !page.dataReady ? "Load data on the Data page first."
      : page.running ? "Running…"
        : page.invalid ? `Fill in or correct “${page.invalid}” to continue.`
          : "Next runs the calculation with these settings and shows the results.";
    return { back, label: "Next: Results", action: { run: true }, enabled, hint };
  }
  if (page.view === "individuals") {
    return { back, label: "Next: Methods text", action: { methods: true }, enabled: page.methodsOpen,
      hint: page.methodsOpen ? "Write a methods paragraph, with references, for everything you ran." : "Run a calculation first." };
  }
  // Results and Compare lead on to the next page that is open.
  const next = steps.slice(at + 1).find((view) => ({ compare: page.compareOpen, individuals: page.individualsOpen })[view]);
  const fallback = steps[at + 1];
  return { back, label: `Next: ${TAB[next || fallback]}`, action: { go: next || fallback }, enabled: Boolean(next),
    hint: next ? "" : "Nothing to show on the next page yet." };
}

let hooks; // { show(view), mode() }
let scheduled = false;

const runButton = (mode) => $({ tooth: "#btn-run", bone: "#btn-bone-run" }[mode] || `#btn-${mode}-run`);
const tabOpen = (view) => !$(`.step[data-view="${view}"]`)?.disabled;

// A setting blocks Next if it is missing, out of range or not a number. Step mismatches do not: several
// defaults are finer than their input's step, and the calculation accepts them.
const blocks = ({ validity: v }) => v.valueMissing || v.rangeUnderflow || v.rangeOverflow || v.badInput || v.typeMismatch || v.patternMismatch;

/** Mark the settings on the open page that block Next, and return the first one's label text. */
function firstInvalid() {
  const fields = $$(".view.active input, .view.active select, .view.active textarea")
    .filter((el) => !el.disabled && el.type !== "hidden" && el.type !== "file" && !el.closest("[hidden]"));
  let first = null;
  for (const el of fields) {
    const bad = blocks(el);
    if (bad !== (el.getAttribute("aria-invalid") === "true")) el.setAttribute("aria-invalid", String(bad));
    if (bad && !first) first = el;
  }
  if (!first) return null;
  return first.closest("label")?.childNodes[0]?.textContent?.trim() || first.getAttribute("aria-label") || first.name || "a setting";
}

function pageFacts() {
  const mode = hooks.mode();
  return {
    view: $(".step.active")?.dataset.view || "data",
    mode,
    chosen: hooks.chosen(),
    dataReady: !$("#data-ready").hidden,
    readyText: $("#data-ready-text").textContent,
    running: Boolean(runButton(mode)?.disabled),
    invalid: firstInvalid(),
    compareOpen: tabOpen("compare"),
    individualsOpen: tabOpen("individuals"),
    methodsOpen: !$("#btn-methods").disabled,
  };
}

let current = null;

function update() {
  scheduled = false;
  current = nextStep(pageFacts());
  const next = $("#btn-next");
  const set = (el, key, value) => { if (el[key] !== value) el[key] = value; };
  set(next, "textContent", current.label);
  set(next, "disabled", !current.enabled);
  set($("#btn-back"), "hidden", !current.back);
  if (current.back) set($("#btn-back"), "textContent", `Back: ${TAB[current.back]}`);
  set($("#flow-hint"), "textContent", current.hint);
  // The Data page's "What a table needs" shows until the calculation shown has its data.
  set($("#data-guide"), "hidden", !$("#data-ready").hidden);
}

/** Update the bar soon (once, however many changes come in together). */
export function refreshFlow() {
  if (scheduled || !hooks) return;
  scheduled = true;
  queueMicrotask(update);
}

export function initFlow(appHooks) {
  hooks = appHooks;
  $("#btn-next").addEventListener("click", () => {
    if (!current?.enabled) return;
    if (current.action.go) hooks.show(current.action.go);
    if (current.action.run) runButton(hooks.mode()).click();
    if (current.action.methods) $("#btn-methods").click();
  });
  $("#btn-back").addEventListener("click", () => current?.back && hooks.show(current.back));
  // Whatever changes a page (data loaded, a run finishing, a tab opening, a setting typed) updates the bar.
  new MutationObserver((records) => {
    const inBar = (node) => (node.nodeType === 1 ? node : node.parentElement)?.closest("#flow-bar");
    if (records.some((r) => !inBar(r.target))) refreshFlow();
  }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["hidden", "disabled", "class"], childList: true, characterData: true });
  document.addEventListener("input", refreshFlow);
  document.addEventListener("change", refreshFlow);
  refreshFlow();
}
