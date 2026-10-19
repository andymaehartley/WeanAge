// How the app asks for work to be done. There are two versions:
// * local app (`weanage`): requests go to the Python server on this computer.
// * browser version: Python runs inside the page (pyworker.js), with no server at all.
// The browser build marks its page with <meta name="weanage-mode" content="browser">.
const IN_BROWSER = document.querySelector('meta[name="weanage-mode"]')?.content === "browser";

async function request(path, options = {}) {
  const res = await fetch(path, options);
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = body && body.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => `${(d.loc || []).join(".")}: ${d.msg}`).join("; ")
      : detail || res.statusText;
    throw new Error(message);
  }
  return body;
}

const json = (body, method = "POST") => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

/** Poll a background job until it finishes, reporting (done, total) as it goes. */
async function waitForJob(job, onProgress) {
  for (;;) {
    const state = await request(`/api/jobs/${job.id}`);
    if (onProgress) onProgress(state.done, state.total);
    if (state.status === "done") return state.result;
    if (state.status === "error") throw new Error(state.error || "Job failed");
    await new Promise((r) => setTimeout(r, 300));
  }
}

const server = {
  config: () => request("/api/config"),
  example: () => request("/api/example"),
  uploadFile(file) {
    const form = new FormData();
    form.append("file", file);
    return request("/api/ingest/file", { method: "POST", body: form });
  },
  validateRecords: (records) => request("/api/ingest/records", json({ records })),
  async analyze(samples, options, onProgress) {
    const job = await request("/api/jobs/analyze", json({ samples, options }));
    return waitForJob(job, onProgress);
  },
  async simulate(body, onProgress) {
    const job = await request("/api/jobs/simulate", json(body));
    return waitForJob(job, onProgress);
  },
  aggregate: (body) => request("/api/aggregate", json(body)),
  saveTable: (table) => request("/api/growth-tables", json(table)),
  deleteTable: (species, tooth) =>
    request(`/api/growth-tables/${encodeURIComponent(species)}/${encodeURIComponent(tooth)}`, { method: "DELETE" }),
  calibrate: (body) => request("/api/growth-tables/calibrate", json(body)),
  templateUrl: "/api/template.csv",
};

// ───────────── browser version ─────────────
let worker = null;
let nextId = 0;
const waiting = new Map(); // request id -> { resolve, reject, onProgress }
let showStatus = () => {};

function python(name, request = {}, onProgress = null, content = undefined) {
  if (!worker) {
    worker = new Worker("pyworker.js");
    worker.onmessage = ({ data }) => {
      if ("status" in data) return showStatus(data.status);
      const job = waiting.get(data.id);
      if (!job) return;
      if (data.progress) return job.onProgress?.(...data.progress);
      waiting.delete(data.id);
      data.ok ? job.resolve(data.result) : job.reject(new Error(data.error));
    };
    worker.onerror = (event) => { // the engine crashed: fail every waiting request instead of hanging
      showStatus(null);
      for (const job of waiting.values()) job.reject(new Error(event.message || "the analysis engine stopped"));
      waiting.clear();
    };
  }
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    waiting.set(id, { resolve, reject, onProgress });
    worker.postMessage({ id, name, request, content });
  });
}

const browser = {
  config: () => python("config"),
  example: () => python("example"),
  uploadFile: async (file) => python("upload", { filename: file.name }, null, new Uint8Array(await file.arrayBuffer())),
  validateRecords: (records) => python("records", { records }),
  analyze: (samples, options, onProgress) => python("analyze", { samples, options }, onProgress),
  simulate: (body, onProgress) => python("simulate", body, onProgress),
  aggregate: (body) => python("aggregate", body),
  saveTable: (table) => python("save_table", table),
  deleteTable: (species, tooth) => python("delete_table", { species, tooth }),
  calibrate: (body) => python("calibrate", body),
  templateUrl: "weanage_template.csv",
};

export const api = IN_BROWSER ? browser : server;
export const inBrowser = IN_BROWSER;
/** Show loading messages from the browser version's engine (text, or null when ready). */
export const onEngineStatus = (callback) => { showStatus = callback; };
