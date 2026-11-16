// Marks every setting that is not WeanAge's default with "changed", and gives each Settings page a
// "Reset to defaults" link. The defaults are read from the form once, after start-up fills it in.
// Tables people type into (food groups, places, growth tables, baselines) are data, not defaults, so are left out.
import { $$, plural } from "./util.js";

const PAGES = '[id^="view-"][id$="settings"]';
const SKIP = ".edit-table, #growth-list, .baseline-block, #qc-preset";
const fields = (page) => [...page.querySelectorAll("input, select, textarea")]
  .filter((el) => el.type !== "file" && el.type !== "hidden" && !el.closest(SKIP) && "def" in el.dataset);
const valueOf = (el) => (el.type === "checkbox" || el.type === "radio" ? String(el.checked) : el.value.trim());

/** Two values are the same setting if they are equal as text, or as lists of numbers ("0, 2,6" = "0,2,6"). */
export function sameValue(a, b) {
  if (a === b) return true;
  const numbers = (text) => text.split(/[,;\s]+/).filter(Boolean).map(Number);
  const x = numbers(a);
  const y = numbers(b);
  return x.length > 0 && x.length === y.length && x.every((v, i) => Number.isFinite(v) && Math.abs(v - y[i]) < 1e-9);
}

/** Remember the form's current values as the defaults (call once, after the defaults are filled in). */
export function rememberDefaults() {
  for (const page of $$(PAGES)) {
    for (const el of page.querySelectorAll("input, select, textarea")) {
      if (el.type !== "file" && el.type !== "hidden" && !el.closest(SKIP)) el.dataset.def = valueOf(el);
    }
    if (!page.querySelector(".reset-row")) {
      page.insertAdjacentHTML("afterbegin", `<p class="reset-row"><span class="muted small" data-changed-count></span>
        <button type="button" class="link small" data-reset>Reset to defaults</button></p>`);
    }
  }
  markChanged();
}

/** Ages typed in months become years (or back): convert the remembered defaults the same way. */
export function convertDefault(input, convert) {
  if (input.dataset.def) input.dataset.def = convert(input.dataset.def);
}

/** Show which settings differ from the defaults, and how many on each page. */
export function markChanged() {
  for (const page of $$(PAGES)) {
    let count = 0;
    for (const el of fields(page)) {
      const changed = !sameValue(valueOf(el), el.dataset.def);
      count += changed;
      const label = el.closest("label") || el.parentElement;
      label.classList.toggle("changed", changed);
      let mark = label.querySelector(":scope > .changed-mark");
      if (changed && !mark) {
        label.insertAdjacentHTML("beforeend", '<span class="changed-mark">changed</span>');
        mark = label.querySelector(":scope > .changed-mark");
      }
      if (mark) mark.hidden = !changed;
    }
    const counter = page.querySelector("[data-changed-count]");
    if (counter) counter.textContent = count ? `${plural(count, "setting")} changed from the defaults` : "All settings are the defaults";
    const reset = page.querySelector("[data-reset]");
    if (reset) reset.hidden = !count;
  }
}

/** Put every setting on a page back to its default, as if typed, so the page's own listeners run. */
function reset(page) {
  for (const el of fields(page)) {
    if (sameValue(valueOf(el), el.dataset.def)) continue;
    if (el.type === "checkbox" || el.type === "radio") el.checked = el.dataset.def === "true";
    else el.value = el.dataset.def;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }
  markChanged();
}

export function initDefaults() {
  document.addEventListener("input", markChanged);
  document.addEventListener("change", markChanged);
  document.addEventListener("click", (e) => {
    const button = e.target.closest("[data-reset]");
    if (button) reset(button.closest(PAGES));
  });
}
