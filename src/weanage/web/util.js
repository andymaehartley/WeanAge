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

// Ages in months or years
// The analysis always works in months; results can be shown in years instead (humans and other
// long-lived species). Inputs such as growth tables stay in months and say so.
let ageUnit = "months";
try {
  if (localStorage.getItem("weanage-units") === "years") ageUnit = "years";
} catch {}
export const getAgeUnit = () => ageUnit;
export function setAgeUnit(unit) {
  ageUnit = unit === "years" ? "years" : "months";
  try { localStorage.setItem("weanage-units", ageUnit); } catch {}
}
/** A value in months, in the chosen unit. */
export const toUnit = (months) => (months == null || !isFinite(months) ? months : ageUnit === "years" ? months / 12 : months);
/** A value typed in the chosen unit, back in months. */
export const fromUnit = (value) => (value == null || value === "" ? null : ageUnit === "years" ? Number(value) * 12 : Number(value));
/** An age in months, shown as a number in the chosen unit (years get one more decimal place). */
export const ageNum = (months, d = 1) => num(toUnit(months), ageUnit === "years" ? d + 1 : d);
export const unitWord = () => ageUnit; // "months" or "years"
export const unitShort = () => (ageUnit === "years" ? "yr" : "mo");
/** "9.3 mo" or "0.78 yr" */
export const ageText = (months, d = 1) => `${ageNum(months, d)} ${unitShort()}`;
/** The 95% interval of an age, in the chosen unit: "7.3–11.5". */
export const ci = (x) => (x && x.ci_low != null && !x.beyond ? `${ageNum(x.ci_low)}–${ageNum(x.ci_high)}` : "");
/** A weaning age as a number in the chosen unit, or "after 12.1" when it lies beyond the samples. */
export const ageValue = (x) => (x?.beyond ? `${x.beyond} ${ageNum(x.bound)}` : ageNum(x?.estimate));
export const pval = (p) => (p == null ? "—" : p < 0.001 ? "< 0.001" : p.toFixed(3));
/** "p < 0.001" or "p = 0.042" */
export const pIs = (p) => (p != null && p < 0.001 ? "p < 0.001" : `p = ${pval(p)}`);
/** A share as a whole percentage: 0.83 → "83%". */
export const percent = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);

/** A message in the corner. Errors stay until closed; other messages close after 10 s. */
export function toast(message, kind = "error") {
  const t = $("#toast");
  $("#toast-text").textContent = message;
  $("#toast-live").textContent = ""; // re-announce a repeated message
  setTimeout(() => ($("#toast-live").textContent = kind === "error" ? `Error: ${message}` : message), 50);
  t.className = `toast ${kind}`;
  t.hidden = false;
  clearTimeout(toast.timer);
  if (kind !== "error") toast.timer = setTimeout(() => (t.hidden = true), 10000);
}

/** Scrollable table boxes can be scrolled from the keyboard, and screen readers announce what they hold. */
export function labelScrollBoxes() {
  const used = new Map();
  for (const box of $$(".table-wrap")) {
    const heading = box.previousElementSibling?.matches("h2, h3") ? box.previousElementSibling
      : box.closest("details")?.querySelector("summary") || box.closest(".card")?.querySelector("h2, h3");
    const name = (heading?.textContent || "Table").trim();
    used.set(name, (used.get(name) || 0) + 1);
    box.tabIndex = 0;
    box.setAttribute("role", "region");
    box.setAttribute("aria-label", `${name}${used.get(name) > 1 ? ` ${used.get(name)}` : ""} (scrollable table)`);
  }
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

/** Placeholder-table warnings that the result summary already states ("Illustrative only: …"). */
export const SAID_IN_SUMMARY = /PLACEHOLDER (growth )?table/;
export const tbdBadge = '<span class="tbd-badge">placeholder<span class="sr-only"> value, waiting on lab data</span></span>';

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

/** The Checks list on the Data page: open by itself only when something must be fixed. */
export function renderIssues(issues) {
  const errors = issues.filter((i) => i.severity === "error").length;
  const others = issues.length - errors;
  $("#issues-card").hidden = !issues.length;
  $("#issues-box").open = errors > 0;
  $("#issues-summary").textContent = `Checks: ${[errors && plural(errors, "problem"), others && plural(others, "note")].filter(Boolean).join(", ")}`;
  $("#issues-summary").classList.toggle("warn-text", errors > 0);
  $("#issues").innerHTML = issues
    .map((i) => `<li class="${i.severity}">${i.row ? `<b>Row ${i.row}</b>${i.field ? ` (${esc(i.field)})` : ""}: ` : ""}${esc(i.message)}</li>`)
    .join("");
}

/** "3 samples loaded · Next" line under the file box, so the next step is always in view. */
export function renderReady(text) {
  $("#data-ready").hidden = !text;
  $("#data-ready-text").textContent = text || "";
}

/** Fill a collapsed Warnings box and show how many there are on its summary line. */
export function renderWarnings(box, summary, list, items, classOf) {
  const problems = items.filter((w) => classOf(w) === "warning").length;
  $(box).hidden = !items.length;
  $(summary).textContent = problems ? `Warnings (${problems})` : `Notes (${items.length})`;
  $(summary).classList.toggle("warn-text", problems > 0);
  $(list).innerHTML = items.map((w) => `<li class="${classOf(w)}">${esc(w)}</li>`).join("");
}

/** The headline figure of a result: "9.3 months · weaning midpoint · 95% interval 7.3–11.5". */
export const readout = (value, what) => (value?.estimate == null ? "" :
  `<p class="readout"><span class="figure">${ageValue(value)}</span><span class="unit">${unitWord()}</span>
    <span class="what">${what}${value.beyond ? ` · ${value.beyond === "after" ? "later than the last" : "earlier than the first"} sample, so no exact age`
      : value.ci_low != null ? ` · 95% interval ${ci(value)}` : ""}</span></p>`);

// Editable tables: one row of inputs per item (food groups, candidate origins).
// columns: {key: label}; keys in textKeys are text, the rest numbers (blank = null).
export function writeEditTable(tbody, columns, rows, noun, textKeys = ["name"]) {
  const cell = (i, key, value) => `<td><input data-row="${i}" data-key="${key}" aria-label="${esc(columns[key])} of ${noun} ${i + 1}"
    ${textKeys.includes(key) ? 'type="text"' : 'type="number" step="any"'} value="${esc(value ?? "")}"></td>`;
  tbody.innerHTML = rows.map((r, i) => `<tr>${Object.keys(columns).map((key) => cell(i, key, r[key])).join("")}
    <td><button class="ghost tiny" type="button" data-remove-row="${i}" aria-label="Remove ${noun} ${i + 1}">Remove</button></td></tr>`).join("");
}

export function readEditTable(tbody, textKeys = ["name"]) {
  const rows = {};
  for (const input of $$("input", tbody)) {
    const value = input.value.trim();
    (rows[input.dataset.row] ??= {})[input.dataset.key] = textKeys.includes(input.dataset.key) ? value : value === "" ? null : Number(value);
  }
  return Object.values(rows);
}
