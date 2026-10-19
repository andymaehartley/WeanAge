// Age-model (growth table) editor: edit knots, save, calibrate, or use a linear model.
import { api } from "./api.js";
import { $, esc, help, num, tbdBadge, toast } from "./util.js";

const keyOf = (t) => `${t.species}:${t.tooth}`;

function knotRows(t) {
  return t.knots
    .map((k, i) => `<tr>
      <td><input type="number" step="0.1" min="0" class="k-pos" data-i="${i}" value="${k.position_mm}" aria-label="Position ${i + 1} (mm)"></td>
      <td><input type="number" step="0.1" class="k-age" data-i="${i}" value="${k.age_months}" aria-label="Age ${i + 1} (months)"></td>
      <td><button type="button" class="ghost tiny" data-act="del-knot" data-i="${i}" aria-label="Remove point ${i + 1}" ${t.knots.length <= 2 ? "disabled" : ""}>✕</button></td>
    </tr>`)
    .join("");
}

export function renderGrowthList(state) {
  const known = Object.fromEntries(state.config.growth_tables.map((t) => [keyOf(t), t]));
  const combos = [...new Set(state.samples.map((s) => `${s.species}:${s.tooth}`))];
  const keys = combos.length ? combos : Object.keys(known);
  $("#growth-list").innerHTML = keys
    .map((key) => {
      const [species, tooth] = key.split(":");
      const edited = state.editedTables[key];
      const t = edited || known[key];
      const o = state.overrides[key];
      const placeholder = t && t.placeholder && !o;
      const body = o
        ? `<div class="form-grid">
            <label>Age at crown initiation (months)<input type="number" step="0.1" class="ovr-init" value="${o.initiation_age_months}"></label>
            <label>Extension rate (mm / month)<input type="number" step="0.1" min="0.01" class="ovr-rate" value="${o.extension_rate_mm_per_month}"></label>
          </div>`
        : t
          ? `<table class="knots-edit"><thead><tr><th scope="col">Position (mm)</th><th scope="col">Age (months)</th><th></th></tr></thead>
              <tbody>${knotRows(t)}</tbody></table>
             <button type="button" class="ghost tiny" data-act="add-knot">+ add point</button>
             <div class="form-grid">
               <label>Age uncertainty, 1 SD (months)<input type="number" step="0.1" min="0" class="t-sd" value="${t.age_uncertainty_months}"></label>
               <label>Source / citation<input class="t-source" value="${esc(t.source)}"></label>
             </div>
             <label class="check"><input type="checkbox" class="t-real" ${t.placeholder ? "" : "checked"}> These are real values (not a placeholder)</label>`
          : '<p class="warn-text">No table for this species/tooth yet: calibrate one, enter points, or use a linear model.</p>';
      return `<div class="growth-item ${placeholder ? "tbd" : ""}" data-key="${esc(key)}">
        <h3>${esc(key.replace(":", " · "))} ${placeholder ? tbdBadge : ""}
          ${t?.saved && !edited ? '<span class="pill">saved</span>' : ""}${edited ? '<span class="pill best">edited</span>' : ""}</h3>
        <p class="muted small">${esc(t ? t.label : "")}</p>
        <div class="seg" role="radiogroup" aria-label="Age model type">
          <label class="check"><input type="radio" name="mode-${esc(key)}" value="table" ${o ? "" : "checked"}> Growth table</label>
          <label class="check"><input type="radio" name="mode-${esc(key)}" value="linear" ${o ? "checked" : ""}> Simple linear</label>
        </div>
        ${body}
        ${o ? "" : `<div class="row gap growth-actions">
          ${t ? '<button type="button" class="secondary tiny" data-act="save">Save to my tables</button>' : '<button type="button" class="secondary tiny" data-act="new">Start a table</button>'}
          ${edited ? '<button type="button" class="ghost tiny" data-act="revert">Discard edits</button>' : ""}
          ${t?.saved && !edited ? '<button type="button" class="ghost tiny" data-act="delete">Delete saved version</button>' : ""}
          <button type="button" class="ghost tiny" data-act="calibrate" aria-expanded="false">Calibrate from reference data…</button> ${help("calibrate")}
        </div>
        <div class="calib" hidden>
          <label>Reference points: one <code>position_mm, age_months</code> pair per line
            <textarea class="c-points" rows="5" placeholder="0, 1.0&#10;10, 4.2&#10;20, 7.5"></textarea></label>
          <div class="form-grid">
            <label>Fit<select class="c-method"><option value="linear">Linear</option><option value="quadratic">Quadratic (growth slows / speeds up)</option><option value="isotonic">Isotonic (any increasing shape)</option></select></label>
            <label>Number of table points<input type="number" class="c-knots" min="2" max="50" value="6"></label>
          </div>
          <div class="row gap"><button type="button" class="tiny" data-act="fit">Fit</button><span class="c-out inline-msg" role="status"></span></div>
        </div>`}
      </div>`;
    })
    .join("");
}

function readTable(item, state, known) {
  const key = item.dataset.key;
  const base = state.editedTables[key] || known[key];
  if (!base) return null;
  const pos = [...item.querySelectorAll(".k-pos")].map((n) => Number(n.value));
  const age = [...item.querySelectorAll(".k-age")].map((n) => Number(n.value));
  return {
    ...base,
    knots: pos.map((p, i) => ({ position_mm: p, age_months: age[i] })),
    age_uncertainty_months: Number(item.querySelector(".t-sd")?.value) || 0,
    source: item.querySelector(".t-source")?.value ?? base.source,
    placeholder: !item.querySelector(".t-real")?.checked,
    tbd_note: item.querySelector(".t-real")?.checked ? null : base.tbd_note,
  };
}

function validKnots(t) {
  return t.knots.every((k, i) => i === 0 || (k.position_mm > t.knots[i - 1].position_mm && k.age_months >= t.knots[i - 1].age_months));
}

export function bindGrowthEditor(state, { refreshConfig, onChange }) {
  const list = $("#growth-list");
  const known = () => Object.fromEntries(state.config.growth_tables.map((t) => [keyOf(t), t]));
  const rerender = () => {
    renderGrowthList(state);
    onChange();
  };

  list.addEventListener("change", (e) => {
    const item = e.target.closest(".growth-item");
    if (!item) return;
    const key = item.dataset.key;
    if (e.target.type === "radio") {
      if (e.target.value === "linear") state.overrides[key] = { initiation_age_months: 0, extension_rate_mm_per_month: 3 };
      else delete state.overrides[key];
      rerender();
    } else if (e.target.matches(".k-pos, .k-age, .t-sd, .t-source, .t-real")) {
      const t = readTable(item, state, known());
      if (t) {
        state.editedTables[key] = t;
        if (!validKnots(t)) toast("Positions must increase and ages must not decrease down the table.");
        rerender();
      }
    }
  });
  list.addEventListener("input", (e) => {
    const item = e.target.closest(".growth-item");
    if (item && e.target.matches(".ovr-init, .ovr-rate")) {
      state.overrides[item.dataset.key] = {
        initiation_age_months: Number(item.querySelector(".ovr-init").value) || 0,
        extension_rate_mm_per_month: Number(item.querySelector(".ovr-rate").value) || 1,
      };
      onChange();
    }
  });
  list.addEventListener("click", async (e) => {
    const act = e.target.dataset.act;
    const item = e.target.closest(".growth-item");
    if (!act || !item) return;
    const key = item.dataset.key;
    const [species, tooth] = key.split(":");
    const current = readTable(item, state, known());
    try {
      if (act === "add-knot" && current) {
        const last = current.knots.at(-1);
        current.knots.push({ position_mm: +(last.position_mm + 5).toFixed(1), age_months: +(last.age_months + 1).toFixed(1) });
        state.editedTables[key] = current;
        rerender();
      } else if (act === "del-knot" && current) {
        current.knots.splice(Number(e.target.dataset.i), 1);
        state.editedTables[key] = current;
        rerender();
      } else if (act === "new") {
        state.editedTables[key] = {
          species, tooth, label: `${species} - ${tooth} (user)`, knots: [{ position_mm: 0, age_months: 0 }, { position_mm: 30, age_months: 10 }],
          age_uncertainty_months: 1, source: "", placeholder: true, tbd_note: "Entered in the app; replace with real data",
        };
        rerender();
      } else if (act === "revert") {
        delete state.editedTables[key];
        rerender();
      } else if (act === "save" && current) {
        if (!validKnots(current)) return toast("Positions must increase and ages must not decrease down the table.");
        const { saved, ...table } = current;
        await api.saveTable(table);
        delete state.editedTables[key];
        await refreshConfig();
        toast(`Saved ${key} to ${state.config.user_tables_path}`, "ok");
        rerender();
      } else if (act === "delete") {
        if (!confirm(`Delete your saved ${key} table and go back to the bundled one?`)) return;
        await api.deleteTable(species, tooth);
        await refreshConfig();
        rerender();
      } else if (act === "calibrate") {
        const panel = item.querySelector(".calib");
        panel.hidden = !panel.hidden;
        e.target.setAttribute("aria-expanded", String(!panel.hidden));
      } else if (act === "fit") {
        const points = item.querySelector(".c-points").value.split(/\n+/).map((l) => l.split(/[,;\t ]+/).map(Number))
          .filter((p) => p.length >= 2 && p.every(isFinite)).map(([position_mm, age_months]) => ({ position_mm, age_months }));
        const res = await api.calibrate({ species, tooth, points, method: item.querySelector(".c-method").value, n_knots: Number(item.querySelector(".c-knots").value) || 6 });
        state.editedTables[key] = res.table;
        rerender();
        const msg = $(`.growth-item[data-key="${CSS.escape(key)}"] .c-out`);
        const panel = $(`.growth-item[data-key="${CSS.escape(key)}"] .calib`);
        if (panel) panel.hidden = false;
        if (msg) {
          msg.className = "c-out inline-msg ok";
          msg.textContent = `Fitted ${res.n} points: residual SD ${num(res.residual_sd)} months${res.r2 != null ? `, R² ${num(res.r2, 3)}` : ""}. ${res.warnings.join(" ")} Review the table, then save it.`;
        }
      }
    } catch (err) {
      toast(err.message);
    }
  });
}
