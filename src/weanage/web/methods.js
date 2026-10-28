// The methods paragraph: written by the server (methods.py) from the settings of every calculation that was run.
import { api } from "./api.js";
import { $, download, esc, toast } from "./util.js";

/** The calculations with results, with their settings and how many samples or individuals they used. */
export function methodRuns(state, calcs) {
  const runs = {};
  if (state.results) {
    runs.tooth = { options: state.options, n: state.results.length,
      details: { growth_tables: [...new Set(state.results.map((r) => r.growth_table).filter((t) => t && t !== "none"))] } };
  }
  if (state.bone?.results) {
    runs.bone = { options: state.bone.options, n: state.bone.samples.filter((s) => s.age_class !== "adult").length };
  }
  for (const calc of Object.values(calcs)) {
    const own = calc.own();
    if (!own?.output) continue;
    runs[calc.name] = { options: own.options, n: own.output.results?.length ?? own.samples.length };
    if (calc.name === "mobility") {
      const results = own.output.results;
      runs.mobility.details = { d18O: results.some((r) => r.d18O != null), sr: results.some((r) => r.sr87_86 != null),
        origins: results.some((r) => r.origins) };
    }
  }
  return runs;
}

let last = null;

export function initMethods(state, calcs) {
  $("#btn-methods").addEventListener("click", async () => {
    const runs = methodRuns(state, calcs);
    if (!Object.keys(runs).length) return toast("Run a calculation first.");
    try {
      last = await api.methods(runs);
    } catch (e) {
      return toast(e.message);
    }
    $("#methods-body").innerHTML = last.paragraphs.map((p) => `<p>${esc(p)}</p>`).join("")
      + `<h3>References</h3><ul class="refs-list">${last.references.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>`;
    $("#methods-placeholders").hidden = !last.placeholders.length;
    $("#methods-dialog").showModal();
  });
  $("#btn-methods-copy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(last.text);
      toast("Methods text copied.", "ok");
    } catch {
      toast("Copying is blocked here: use Download instead.");
    }
  });
  $("#btn-methods-download").addEventListener("click", () => download("weanage_methods.md", new Blob([last.text], { type: "text/markdown" })));
}
