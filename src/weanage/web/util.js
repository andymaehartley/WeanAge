// Shared helpers for the WeanAge frontend.

// Colour-blind-safe colours (based on Okabe-Ito), one set per theme so every curve has at
// least 4.5:1 contrast with the background. Each model also has its own dash pattern, so
// curves can be told apart without colour at all.
export const PALETTE = {
  dark: { logistic: "#56b4e9", piecewise: "#3fd8a8", exponential: "#f0a6d8", two_phase: "#ff9e5e", elbow: "#f0e442", average: "#f0f3f6" },
  light: { logistic: "#0060a8", piecewise: "#00765a", exponential: "#a3407a", two_phase: "#b04500", elbow: "#6e5a00", average: "#24292f" },
};
export const MODEL_STYLE = {
  logistic: { dash: null }, piecewise: { dash: "9 4" }, exponential: { dash: "2 3" },
  two_phase: { dash: "10 3 2 3" }, elbow: { dash: "5 2" }, average: { dash: null },
};
export const theme = () => (document.documentElement.dataset.theme === "light" ? "light" : "dark");
export const color = (m, which = theme()) => PALETTE[which][m] || PALETTE[which].average;
export const MILESTONES = ["onset", "midpoint", "completion"];

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/** "1 warning", "3 warnings" */
export const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
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
  const head = columns.map((c) => `<th scope="col" class="${c.cls || ""}" title="${esc(c.title || "")}">${c.label}</th>`).join("");
  const body = rows
    .map((r, i) => `<tr class="${rowClass(r)}">${columns.map((c) => `<td class="${c.cls || ""}">${c.render ? c.render(r, i) : esc(r[c.key])}</td>`).join("")}</tr>`)
    .join("");
  el.innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="${columns.length}" class="muted">Nothing to show</td></tr>`}</tbody>`;
}

export const tbdBadge = '<span class="tbd-badge" title="Placeholder awaiting lab work">TBD-LAB</span>';

export function swatch(model) {
  const s = MODEL_STYLE[model] || MODEL_STYLE.average;
  return `<svg class="swatch-line" width="22" height="10" aria-hidden="true"><line x1="1" y1="5" x2="21" y2="5" stroke="${color(model)}" stroke-width="3" ${s.dash ? `stroke-dasharray="${s.dash}"` : ""}/></svg>`;
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
