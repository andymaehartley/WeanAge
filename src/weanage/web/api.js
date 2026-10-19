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
// Python runs in background "engines" (web workers, see pyworker.js). Engine 0 does
// everything; big analyses are shared out to extra engines, one per spare processor core.
const engines = []; // promises of { worker, waiting }
let nextId = 0;
let showStatus = () => {};

// sw.js keeps copies of the app and of Python so the page also works offline. It must be
// in charge before the first engine starts, or Python's files would not be kept.
async function offlineCopies() {
  if (!("serviceWorker" in navigator)) return;
  try {
    await navigator.serviceWorker.register("sw.js");
    if (!navigator.serviceWorker.controller) { // first visit: give it up to 3 s to take over
      await Promise.race([
        new Promise((resolve) => navigator.serviceWorker.addEventListener("controllerchange", resolve, { once: true })),
        new Promise((resolve) => setTimeout(resolve, 3000)),
      ]);
    }
  } catch {
    // Offline copies are a convenience; the app works without them.
  }
}

async function startEngine(index) {
  if (index === 0) await offlineCopies();
  const worker = new Worker("pyworker.js");
  const waiting = new Map(); // request id -> { resolve, reject, onProgress }
  worker.onmessage = ({ data }) => {
    if ("status" in data) return index === 0 && showStatus(data.status);
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
  return { worker, waiting };
}

async function python(name, request = {}, onProgress = null, content = undefined, index = 0) {
  if (index > 0) await (engines[0] ??= startEngine(0)); // extra engines start after the first is in charge
  const { worker, waiting } = await (engines[index] ??= startEngine(index));
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    waiting.set(id, { resolve, reject, onProgress });
    worker.postMessage({ id, name, request, content });
  });
}

/** Split the specimens between several engines when there are enough of them. */
async function analyzeInParallel(samples, options, onProgress) {
  const specimenOf = (s) => s.individual_id || s.specimen_id; // as analysis.group_by_specimen
  const specimens = [...new Set(samples.map(specimenOf))];
  const spareCores = (navigator.hardwareConcurrency || 2) - 1;
  const memoryLimit = navigator.deviceMemory ? Math.floor(navigator.deviceMemory / 2) : 3; // each engine needs ~0.3 GB
  const count = Math.min(3, spareCores, memoryLimit, Math.floor(specimens.length / 3));
  if (count < 2) return python("analyze", { samples, options }, onProgress);
  // Consecutive blocks of specimens, so the joined results keep the original order.
  const size = Math.ceil(specimens.length / count);
  const blocks = Array.from({ length: count }, (_, i) => new Set(specimens.slice(i * size, (i + 1) * size)))
    .filter((block) => block.size);
  const done = blocks.map(() => 0);
  const parts = await Promise.all(blocks.map((block, i) => python(
    "analyze", { samples: samples.filter((s) => block.has(specimenOf(s))), options },
    (finished) => { done[i] = finished; onProgress?.(done.reduce((a, b) => a + b, 0), specimens.length); },
    undefined, i)));
  return { results: parts.flatMap((p) => p.results), estimates: parts.flatMap((p) => p.estimates) };
}

const browser = {
  config: () => python("config"),
  example: () => python("example"),
  uploadFile: async (file) => python("upload", { filename: file.name }, null, new Uint8Array(await file.arrayBuffer())),
  validateRecords: (records) => python("records", { records }),
  analyze: analyzeInParallel,
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
