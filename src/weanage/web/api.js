// Thin wrapper over the WeanAge FastAPI backend.

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

export const api = {
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
