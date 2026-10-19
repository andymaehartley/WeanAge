// Project files (save / open) and automatic saving in the browser.

const FORMAT = "weanage-project";
const AUTOSAVE_KEY = "weanage-autosave";

export function serialiseProject(state, settings, appVersion) {
  return {
    format: FORMAT,
    format_version: 1,
    app_version: appVersion,
    saved_at: new Date().toISOString(),
    samples: state.samples,
    settings,
    results: state.results,
    estimates: state.estimates,
    analysis_options: state.options || null,
    current: state.current,
  };
}

export function parseProject(text) {
  const data = JSON.parse(text);
  if (data.format !== FORMAT) throw new Error("This file is not a WeanAge project.");
  if (!Array.isArray(data.samples)) throw new Error("The project file has no samples.");
  return data;
}

let timer = null;
/** Debounced save to localStorage; drops results if the browser quota is exceeded. */
export function autosave(project) {
  clearTimeout(timer);
  timer = setTimeout(() => {
    try {
      localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(project));
    } catch {
      try {
        localStorage.setItem(AUTOSAVE_KEY, JSON.stringify({ ...project, results: null, estimates: null }));
      } catch {
        /* storage unavailable (private window, blocked): nothing to do */
      }
    }
  }, 600);
}

export function loadAutosave() {
  try {
    const raw = localStorage.getItem(AUTOSAVE_KEY);
    return raw ? parseProject(raw) : null;
  } catch {
    return null;
  }
}

export function clearAutosave() {
  try {
    localStorage.removeItem(AUTOSAVE_KEY);
  } catch {}
}
