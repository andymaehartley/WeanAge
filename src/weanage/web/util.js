// Shared helpers for the WeanAge frontend.

// Okabe-Ito colour-blind-safe palette, plus a distinct dash pattern per model so
// curves stay distinguishable in greyscale and for colour-vision deficiency.
export const MODEL_STYLE = {
  logistic: { color: "#0072B2", dash: null },
  piecewise: { color: "#009E73", dash: "9 4" },
  exponential: { color: "#CC79A7", dash: "2 3" },
  two_phase: { color: "#D55E00", dash: "10 3 2 3" },
  elbow: { color: "#B07C00", dash: "5 2" },
  average: { color: "#444444", dash: null },
};
export const color = (m) => (MODEL_STYLE[m] || MODEL_STYLE.average).color;
export const MILESTONES = ["onset", "midpoint", "completion"];

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

export const num = (v, d = 2) => (v == null || !isFinite(v) ? "—" : Number(v).toFixed(d));
export const ci = (x) => (x && x.ci_low != null ? `${num(x.ci_low, 1)}–${num(x.ci_high, 1)}` : "");
export const pval = (p) => (p == null ? "—" : p < 0.001 ? "< 0.001" : p.toFixed(3));

export function toast(message, kind = "error") {
  const t = $("#toast");
  t.textContent = message;
  t.className = `toast ${kind}`;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 6000);
}

export function download(name, blob) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export function toCsv(rows) {
  if (!rows.length) return "";
  const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  const cell = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.join(","), ...rows.map((r) => cols.map((c) => cell(r[c])).join(","))].join("\n");
}

/** Render a table; columns: [{label, key?, render?, cls?, title?}] */
export function table(el, columns, rows, rowClass = () => "") {
  const head = columns.map((c) => `<th scope="col" title="${esc(c.title || "")}">${c.label}</th>`).join("");
  const body = rows
    .map((r, i) => `<tr class="${rowClass(r)}">${columns.map((c) => `<td class="${c.cls || ""}">${c.render ? c.render(r, i) : esc(r[c.key])}</td>`).join("")}</tr>`)
    .join("");
  el.innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="${columns.length}" class="muted">Nothing to show</td></tr>`}</tbody>`;
}

export const tbdBadge = '<span class="tbd-badge" title="Placeholder awaiting lab work">TBD-LAB</span>';

export function swatch(model) {
  const s = MODEL_STYLE[model] || MODEL_STYLE.average;
  return `<svg class="swatch-line" width="22" height="10" aria-hidden="true"><line x1="1" y1="5" x2="21" y2="5" stroke="${s.color}" stroke-width="3" ${s.dash ? `stroke-dasharray="${s.dash}"` : ""}/></svg>`;
}

/** A small "?" button that opens the glossary entry for ``term``. */
export const help = (term, label = term) =>
  `<button type="button" class="help-btn" data-help="${esc(term)}" aria-label="Explain ${esc(label)}">?</button>`;

export function progressBar(el, done, total, label = "") {
  el.hidden = false;
  const pct = total ? Math.round((100 * done) / total) : 0;
  el.innerHTML = `<div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-label="${esc(label)}">
    <div class="progress-fill" style="width:${pct}%"></div></div>
    <span class="progress-text">${esc(label)} ${total ? `${done} / ${total}` : "starting…"}</span>`;
}
