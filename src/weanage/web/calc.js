// The one-table calculations (enamel, kill-off, diet mixing) load data, read settings, run and are
// saved the same way; each supplies its own pages. Their data, settings and results live in
// state[name], apart from the tooth and bone calculations'.
import { api } from "./api.js";
import { $, progressBar, toast } from "./util.js";

/**
 * spec: name ("enamel", "killoff" or "mixing"), plural ("enamel samples"), working ("Fitting teeth"),
 * fields (number settings, in inputs #<name>-<field>), renderData(own), renderResults(own),
 * and optionally init(calc), readSettings(out), writeSettings(options), prepare(samples, state), first(output).
 */
export function oneTableCalc(spec) {
  const { name } = spec;
  let state;
  let hooks; // { show, autosave, refreshNav }
  const own = () => state[name];

  async function run() {
    if (!own().samples.length) return toast(`Load some ${spec.plural} first.`);
    const options = calc.settings();
    const bar = $(`#${name}-progress`);
    const button = $(`#btn-${name}-run`);
    button.disabled = true;
    progressBar(bar, 0, 0, spec.working);
    try {
      const samples = spec.prepare ? spec.prepare(own().samples, state) : own().samples;
      const output = await api.calcAnalyze(name, samples, options, (done, total) => progressBar(bar, done, total, spec.working));
      Object.assign(own(), { output, options, current: spec.first?.(output) ?? null });
      hooks.refreshNav();
      calc.renderResults();
      hooks.show("results");
      hooks.autosave();
    } catch (e) {
      toast(e.message);
    } finally {
      button.disabled = false;
      bar.hidden = true;
    }
  }

  const calc = {
    name,
    plural: spec.plural,
    own,
    init(appState, appHooks) {
      state = appState;
      hooks = appHooks;
      state[name] = { samples: [], report: null, output: null, options: null, current: null };
      calc.applySettings(state.config.calculations[name].defaults);
      $(`#btn-${name}-run`).addEventListener("click", run);
      $(`#view-${name}-settings`).addEventListener("change", hooks.autosave);
      spec.init?.(calc);
    },
    async loadFile(file) {
      try {
        calc.setReport(await api.calcUpload(name, file));
      } catch (e) {
        toast(e.message);
      }
    },
    async loadExample(example) {
      try {
        const report = await api.calcExample(name, example);
        calc.setReport(report);
        toast(report.message, "ok");
      } catch (e) {
        toast(e.message);
      }
    },
    setReport(report, keepResults = false) {
      Object.assign(own(), { report, samples: report.samples });
      if (!keepResults) own().output = null;
      calc.renderData();
      hooks.refreshNav();
      hooks.autosave();
    },
    renderData() {
      if (state.mode === name) spec.renderData(own());
    },
    renderResults() {
      if (own().output) spec.renderResults(own());
    },
    hasResults: () => Boolean(own()?.output),
    clear() {
      if (!own().samples.length || confirm(`Remove all loaded ${spec.plural}?`)) calc.setReport({ samples: [], issues: [] });
    },
    applySettings(options) {
      for (const key of spec.fields) if (key in options) $(`#${name}-${key}`).value = options[key] ?? "";
      spec.writeSettings?.(options);
    },
    settings() {
      const defaults = state.config.calculations[name].defaults;
      const out = { random_seed: 42 };
      for (const key of spec.fields) {
        const value = $(`#${name}-${key}`).value;
        out[key] = value === "" ? defaults[key] : Number(value);
      }
      return spec.readSettings ? spec.readSettings(out) : out;
    },
    saved: (withResults = true) => ({ samples: own().samples, settings: calc.settings(), output: withResults ? own().output : null,
      options: own().options, current: own().current }),
    restore(p) {
      calc.applySettings(p.settings || {});
      const output = p.output ?? (p.results ? { results: p.results, groups: p.groups } : null); // older projects
      Object.assign(own(), { output, options: p.options, current: p.current });
      api.calcRecords(name, p.samples || []).then((report) => {
        calc.setReport(report, true);
        calc.renderResults();
      }).catch((e) => toast(e.message));
    },
  };
  return calc;
}
