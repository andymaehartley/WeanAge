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

const json = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  config: () => request("/api/config"),
  example: () => request("/api/example"),
  uploadCsv(file) {
    const form = new FormData();
    form.append("file", file);
    return request("/api/ingest/csv", { method: "POST", body: form });
  },
  validateRecords: (records) => request("/api/ingest/records", json({ records })),
  analyze: (samples, options) => request("/api/analyze", json({ samples, options })),
  aggregate: (body) => request("/api/aggregate", json(body)),
  templateUrl: "/api/template.csv",
};
