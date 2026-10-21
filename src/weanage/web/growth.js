// The age-model editor in Settings: edit a growth table's points, save it,
// calibrate it from reference data, or switch to a simple linear model.
import { api } from "./api.js";
import { $, esc, help, num, tbdBadge, toast } from "./util.js";

const keyOf = (t) => `${t.species}:${t.tooth}`;

function tableFor(state, key) {
  return state.editedTables[key] || state.config.growth_tables.find((t) => keyOf(t) === key);
}

function pointRows(t) {
  return t.knots.map((k, i) => `<tr>
    <td><input type="number" step="0.1" min="0" class="k-pos" value="${k.position_mm}" aria-label="Position ${i + 1} (mm)"></td>
    <td><input type="number" step="0.1" class="k-age" value="${k.age_months}" aria-label="Age ${i + 1} (months)"></td>
    <td><button type="button" class="ghost tiny" data-act="remove-point" data-i="${i}" aria-label="Remove point ${i + 1}" ${t.knots.length <= 2 ? "disabled" : ""}>✕</button></td>
  </tr>`).join("");
}

function card(state, key, open = false) {
  const t = tableFor(state, key);
  const linear = state.overrides[key];
  const edited = !!state.editedTables[key];
  const placeholder = t?.placeholder && !linear;
  let body;
  if (linear) {
    body = `<div class="form-grid">
      <label>Age at crown initiation (months)<input type="number" step="0.1" class="ovr-init" value="${linear.initiation_age_months}"></label>
      <label>Extension rate (mm / month)<input type="number" step="0.1" min="0.01" class="ovr-rate" value="${linear.extension_rate_mm_per_month}"></label></div>`;
  } else if (t) {
    body = `<table class="knots-edit"><thead><tr><th scope="col">Position (mm)</th><th scope="col">Age (months)</th><th></th></tr></thead>
        <tbody>${pointRows(t)}</tbody></table>
      <button type="button" class="ghost tiny" data-act="add-point">+ add point</button>
      <div class="form-grid">
        <label>Age uncertainty, 1 SD (months)<input type="number" step="0.1" min="0" class="t-sd" value="${t.age_uncertainty_months}"></label>
        <label>Source / citation<input class="t-source" value="${esc(t.source)}"></label></div>
      <label class="check"><input type="checkbox" class="t-real" ${t.placeholder ? "" : "checked"}> These are real values (not a placeholder)</label>`;
  } else {
    body = '<p class="warn-text">No table for this species/tooth yet: calibrate one, enter points, or use a linear model.</p>';
  }
  const actions = linear ? "" : `<div class="row gap growth-actions">
      <button type="button" class="secondary tiny" data-act="${t ? "save" : "new"}">${t ? "Save to my tables" : "Start a table"}</button>
      ${edited ? '<button type="button" class="ghost tiny" data-act="discard">Discard edits</button>' : ""}
      ${t?.saved && !edited ? '<button type="button" class="ghost tiny" data-act="delete">Delete saved version</button>' : ""}
      <button type="button" class="ghost tiny" data-act="calibrate">Calibrate from reference data…</button> ${help("calibrate")}
    </div>
    <div class="calib" hidden>
      <label>Reference points: one <code>position_mm, age_months</code> pair per line
        <textarea class="c-points" rows="5" placeholder="0, 1.0&#10;10, 4.2&#10;20, 7.5"></textarea></label>
      <div class="form-grid">
        <label>Fit<select class="c-method"><option value="linear">Linear</option><option value="quadratic">Quadratic (growth slows / speeds up)</option>
          <option value="isotonic">Isotonic (any increasing shape)</option></select></label>
        <label>Number of table points<input type="number" class="c-knots" min="2" max="50" value="6"></label></div>
      <div class="row gap"><button type="button" class="tiny" data-act="fit">Fit</button><span class="c-out inline-msg" role="status"></span></div>
    </div>`;
  // Each table is folded to one line; open it to edit.
  return `<details class="growth-item ${placeholder ? "tbd" : ""}" data-key="${esc(key)}" ${open ? "open" : ""}>
    <summary><strong>${esc(key.replace(":", " · "))}</strong> <span class="muted small">${esc(t?.label || "no table yet")}</span>
      ${placeholder ? tbdBadge : ""}${t?.saved && !edited ? '<span class="pill">saved</span>' : ""}${edited ? '<span class="pill best">edited</span>' : ""}${linear ? '<span class="pill">linear</span>' : ""}</summary>
    <div class="seg" role="radiogroup" aria-label="Age model type">
      <label class="check"><input type="radio" name="mode-${esc(key)}" value="table" ${linear ? "" : "checked"}> Growth table</label>
      <label class="check"><input type="radio" name="mode-${esc(key)}" value="linear" ${linear ? "checked" : ""}> Simple linear</label>
    </div>${body}${actions}</details>`;
}

export function renderGrowthList(state) {
  const inData = [...new Set(state.samples.map((s) => `${s.species}:${s.tooth}`))];
  const keys = inData.length ? inData : state.config.growth_tables.map(keyOf);
  const opened = new Set([...document.querySelectorAll("#growth-list details[open]")].map((d) => d.dataset.key));
  $("#growth-list").innerHTML = keys.map((key) => card(state, key, opened.has(key))).join("");
}

// Read the table currently shown in a card (including unsaved typing).
function readCard(item, state) {
  const base = tableFor(state, item.dataset.key);
  if (!base || !item.querySelector(".t-real")) return base || null; // nothing editable shown
  const positions = [...item.querySelectorAll(".k-pos")].map((n) => Number(n.value));
  const ages = [...item.querySelectorAll(".k-age")].map((n) => Number(n.value));
  const real = item.querySelector(".t-real").checked;
  return {
    ...base,
    knots: positions.map((p, i) => ({ position_mm: p, age_months: ages[i] })),
    age_uncertainty_months: Number(item.querySelector(".t-sd").value) || 0,
    source: item.querySelector(".t-source").value,
    placeholder: !real,
    tbd_note: real ? null : base.tbd_note,
  };
}

const inOrder = (t) => t.knots.every((k, i) => i === 0 || (k.position_mm > t.knots[i - 1].position_mm && k.age_months >= t.knots[i - 1].age_months));
const ORDER_MESSAGE = "Positions must increase and ages must not decrease down the table.";

export function bindGrowthEditor(state, { refreshConfig, onChange }) {
  const list = $("#growth-list");
  const redraw = () => { renderGrowthList(state); onChange(); };

  list.addEventListener("change", (e) => {
    const item = e.target.closest(".growth-item");
    const key = item?.dataset.key;
    if (!key) return;
    if (e.target.type === "radio") {
      if (e.target.value === "linear") state.overrides[key] = { initiation_age_months: 0, extension_rate_mm_per_month: 3 };
      else delete state.overrides[key];
      redraw();
    } else if (e.target.matches(".k-pos, .k-age, .t-sd, .t-source, .t-real")) {
      state.editedTables[key] = readCard(item, state);
      if (!inOrder(state.editedTables[key])) toast(ORDER_MESSAGE);
      redraw();
    }
  });

  list.addEventListener("input", (e) => {
    const item = e.target.closest(".growth-item");
    if (!e.target.matches(".ovr-init, .ovr-rate")) return;
    state.overrides[item.dataset.key] = {
      initiation_age_months: Number(item.querySelector(".ovr-init").value) || 0,
      extension_rate_mm_per_month: Number(item.querySelector(".ovr-rate").value) || 1,
    };
    onChange();
  });

  const actions = {
    "add-point": (item, key, t) => {
      const last = t.knots.at(-1);
      t.knots.push({ position_mm: +(last.position_mm + 5).toFixed(1), age_months: +(last.age_months + 1).toFixed(1) });
      state.editedTables[key] = t;
      redraw();
    },
    "remove-point": (item, key, t, button) => {
      t.knots.splice(Number(button.dataset.i), 1);
      state.editedTables[key] = t;
      redraw();
    },
    new: (item, key) => {
      const [species, tooth] = key.split(":");
      state.editedTables[key] = {
        species, tooth, label: `${species} - ${tooth} (user)`, age_uncertainty_months: 1, source: "", placeholder: true,
        knots: [{ position_mm: 0, age_months: 0 }, { position_mm: 30, age_months: 10 }], tbd_note: "Entered in the app; replace with real data",
      };
      redraw();
    },
    discard: (item, key) => { delete state.editedTables[key]; redraw(); },
    save: async (item, key, t) => {
      if (!inOrder(t)) return toast(ORDER_MESSAGE);
      const { saved, ...table } = t;
      await api.saveTable(table);
      delete state.editedTables[key];
      await refreshConfig();
      toast(`Saved ${key} to ${state.config.user_tables_path}`, "ok");
      redraw();
    },
    delete: async (item, key) => {
      if (!confirm(`Delete your saved ${key} table and go back to the bundled one?`)) return;
      await api.deleteTable(...key.split(":"));
      await refreshConfig();
      redraw();
    },
    calibrate: (item) => { item.querySelector(".calib").hidden = !item.querySelector(".calib").hidden; },
    fit: async (item, key) => {
      const [species, tooth] = key.split(":");
      const points = item.querySelector(".c-points").value.split("\n")
        .map((line) => line.split(/[,;\t ]+/).map(Number))
        .filter((p) => p.length >= 2 && p.every(isFinite))
        .map(([position_mm, age_months]) => ({ position_mm, age_months }));
      const fit = await api.calibrate({ species, tooth, points, method: item.querySelector(".c-method").value, n_knots: Number(item.querySelector(".c-knots").value) || 6 });
      state.editedTables[key] = fit.table;
      redraw();
      const fresh = $(`.growth-item[data-key="${CSS.escape(key)}"]`);
      fresh.querySelector(".calib").hidden = false;
      const message = fresh.querySelector(".c-out");
      message.className = "c-out inline-msg ok";
      message.textContent = `Fitted ${fit.n} points: residual SD ${num(fit.residual_sd)} months${fit.r2 != null ? `, R² ${num(fit.r2, 3)}` : ""}. ${fit.warnings.join(" ")} Review the table, then save it.`;
    },
  };

  list.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-act]");
    const item = e.target.closest(".growth-item");
    if (!button || !item) return;
    const key = item.dataset.key;
    try {
      await actions[button.dataset.act](item, key, readCard(item, state), button);
    } catch (err) {
      toast(err.message);
    }
  });
}
