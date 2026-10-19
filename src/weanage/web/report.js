// Standalone, reproducible HTML report (prints cleanly to PDF).
import { curveChart, forestChart, svgMarkup } from "./chart.js";
import { curveOptions } from "./curves.js";
import { esc, MILESTONES, num, pval } from "./util.js";

const REFERENCES = [
  "DeNiro, M. J. (1985). Postmortem preservation and alteration of in vivo bone collagen isotope ratios in relation to palaeodietary reconstruction. Nature 317, 806–809.",
  "van Klinken, G. J. (1999). Bone collagen quality indicators for palaeodietary and radiocarbon measurements. Journal of Archaeological Science 26, 687–695.",
  "Tsutaya, T., & Yoneda, M. (2013). Quantitative reconstruction of weaning ages in archaeological human populations using bone collagen nitrogen isotope ratios and approximate Bayesian computation. PLoS ONE 8, e72327.",
  "Tsutaya, T. (2020). Blurred time resolution of tooth dentin serial sections. American Journal of Physical Anthropology 173, 748–759.",
  "Ganiatsou, E., Souleles, A., & Papageorgopoulou, C. (2023). WEaning Age FiNder (WEAN): a tool for estimating weaning age from stable isotope ratios of dentinal collagen. Archaeological and Anthropological Sciences 15, 50.",
  "Burnham, K. P., & Anderson, D. R. (2002). Model Selection and Multimodel Inference (2nd ed.). Springer.",
  "DerSimonian, R., & Laird, N. (1986). Meta-analysis in clinical trials. Controlled Clinical Trials 7, 177–188.",
];

const CSS = `body{font:14px/1.5 system-ui,sans-serif;color:#1f2328;max-width:960px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.6rem}h2{font-size:1.2rem;border-bottom:1px solid #ddd;padding-bottom:.2rem;margin-top:2rem}
h3{font-size:1rem;margin-top:1.4rem}table{border-collapse:collapse;width:100%;font-size:12px;margin:.4rem 0}
th,td{border-bottom:1px solid #e3e1da;padding:.25rem .4rem;text-align:left;vertical-align:top}td.num{text-align:right}
.warn{background:#fff4b8;border-left:4px solid #e6b800;padding:.4rem .7rem;margin:.6rem 0}
.muted{color:#667085}.specimen{break-inside:avoid;page-break-inside:avoid}svg{width:100%;height:auto}
code{background:#f1f0eb;padding:0 3px;border-radius:3px}@media print{body{margin:0}h2{break-after:avoid}}`;

function kv(rows) {
  return `<table>${rows.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${v}</td></tr>`).join("")}</table>`;
}

function fitTable(res) {
  const head = ["Model", ...MILESTONES, "Drop ‰", "RMSE", "ΔAICc", "Weight"];
  const rows = res.fits.map((f) => [
    `${esc(f.label)}${f.model === res.best_model ? " <b>(best)</b>" : ""}`,
    ...MILESTONES.map((k) => (f[k] ? `${num(f[k].estimate, 1)}${f[k].ci_low != null ? ` <span class="muted">(${num(f[k].ci_low, 1)}–${num(f[k].ci_high, 1)})</span>` : ""}` : "—")),
    num(f.drop_permil), num(f.rmse, 3), num(f.delta_aicc), num(f.akaike_weight),
  ]);
  const avg = res.model_average || {};
  if (Object.keys(avg).length) {
    rows.push(["<i>Model average</i>", ...MILESTONES.map((k) => (avg[k] ? `${num(avg[k].estimate, 1)} <span class="muted">(${num(avg[k].ci_low, 1)}–${num(avg[k].ci_high, 1)})</span>` : "—")), "", "", "", ""]);
  }
  return `<table><thead><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c, i) => `<td class="${i ? "num" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function chartSvg(res, milestone) {
  const holder = document.createElement("div");
  holder.style.cssText = "position:absolute;left:-9999px;width:760px";
  document.body.appendChild(holder);
  const visible = new Set([...res.fits.map((f) => f.model), "average"]);
  const svg = curveChart(holder, curveOptions(res, { visible, milestone, showD13C: res.points.some((p) => p.d13C != null) }));
  const markup = svgMarkup(svg);
  holder.remove();
  return markup;
}

function compareSection(cmp) {
  if (!cmp) return "";
  const t = cmp.tests;
  const holder = document.createElement("div");
  holder.style.cssText = "position:absolute;left:-9999px;width:760px";
  document.body.appendChild(holder);
  const svg = forestChart(holder, t.groups.map((g) => ({ label: g.group, mean: g.mean, lo: g.ci_low, hi: g.ci_high, values: [] })),
    `Weaning ${t.milestone} (months), random-effects mean ± 95% CI`);
  const forest = svgMarkup(svg);
  holder.remove();
  const groups = t.groups.map((g) => `<tr><td>${esc(g.group)}</td><td class="num">${g.n}</td><td class="num">${num(g.mean, 1)}</td><td class="num">${num(g.ci_low, 1)}–${num(g.ci_high, 1)}</td><td class="num">${num(g.tau, 2)}</td></tr>`).join("");
  const pairs = t.pairwise.map((p) => `<tr><td>${esc(p.group_a)} − ${esc(p.group_b)}</td><td class="num">${num(p.difference, 1)}</td><td class="num">${pval(p.p)}</td><td class="num">${pval(p.p_holm)}</td></tr>`).join("");
  const bayes = t.bayes
    ? `<h3>Hierarchical Bayesian model</h3><p class="muted">Shared between-animal SD τ = ${num(t.bayes.tau_mean, 2)} months (${num(t.bayes.tau_ci_low, 2)}–${num(t.bayes.tau_ci_high, 2)}); max R̂ = ${num(t.bayes.rhat_max, 3)}; ${t.bayes.draws} draws.</p>
      <table><thead><tr><th>Comparison</th><th>P(first earlier)</th><th>Difference (95% CrI)</th></tr></thead><tbody>${t.bayes.pairs.map((p) => `<tr><td>${esc(p.group_a)} vs ${esc(p.group_b)}</td><td class="num">${num(p.prob_a_earlier, 3)}</td><td class="num">${num(p.difference_mean, 1)} (${num(p.difference_ci_low, 1)}–${num(p.difference_ci_high, 1)})</td></tr>`).join("")}</tbody></table>`
    : "";
  return `<h2>Group comparison</h2>
    <p>Grouping: ${esc(t.group_by.join(" × "))}; milestone: ${esc(t.milestone)}; estimates: ${esc(t.model)}.</p>
    ${forest}
    <table><thead><tr><th>Group</th><th>n</th><th>Mean</th><th>95% CI</th><th>τ</th></tr></thead><tbody>${groups}</tbody></table>
    <p>Between-group Q = ${num(t.q_between, 2)} (df ${t.q_df}), p = ${pval(t.q_p)}; permutation p = ${pval(t.permutation_p)}.</p>
    ${pairs ? `<table><thead><tr><th>Pair</th><th>Difference</th><th>p</th><th>p (Holm)</th></tr></thead><tbody>${pairs}</tbody></table>` : ""}
    ${bayes}${t.notes.map((n) => `<p class="muted">${esc(n)}</p>`).join("")}`;
}

export function buildReport({ config, state, settings, compare }) {
  const opts = state.options;
  const milestone = opts.reported_milestone;
  const tables = state.config.growth_tables;
  const used = [...new Set(state.samples.map((s) => `${s.species}:${s.tooth}`))];
  const ageModels = used.map((key) => {
    const o = opts.growth_overrides?.[key];
    if (o) return `<li><b>${esc(key)}</b>: custom linear, ${o.initiation_age_months} mo + position / ${o.extension_rate_mm_per_month} mm·mo⁻¹</li>`;
    const t = (opts.growth_tables || []).find((g) => `${g.species}:${g.tooth}` === key) || tables.find((g) => `${g.species}:${g.tooth}` === key);
    if (!t) return `<li><b>${esc(key)}</b>: none</li>`;
    return `<li><b>${esc(key)}</b>: ${esc(t.label)}${t.placeholder ? " <b>[PLACEHOLDER]</b>" : ""} — knots ${t.knots.map((k) => `${k.position_mm} mm→${k.age_months} mo`).join(", ")}; ±${t.age_uncertainty_months} mo; ${esc(t.source)}</li>`;
  }).join("");
  const synthetic = state.samples.some((s) => /SYNTHETIC/.test(s.notes || ""));
  const placeholders = state.results.some((r) => r.growth_placeholder) || config.tbd.length;

  const summaryRows = state.results.map((r) => {
    const best = r.fits.find((f) => f.model === r.best_model);
    const bm = best?.[milestone];
    const avg = r.model_average?.[milestone];
    const nWarn = r.warnings.length + r.fits.reduce((n, f) => n + f.warnings.length, 0);
    return `<tr><td>${esc(r.specimen_id)}</td><td>${esc(r.site)}</td><td>${esc(r.species)} ${esc(r.tooth)}</td><td>${esc(best?.label || "—")}</td>
      <td class="num">${bm ? `${num(bm.estimate, 1)} (${num(bm.ci_low, 1)}–${num(bm.ci_high, 1)})` : "—"}</td>
      <td class="num">${avg ? `${num(avg.estimate, 1)} (${num(avg.ci_low, 1)}–${num(avg.ci_high, 1)})` : "—"}</td><td class="num">${nWarn}</td></tr>`;
  }).join("");

  const specimens = state.results.map((r) => `<section class="specimen">
      <h3>${esc(r.specimen_id)} <span class="muted">— ${esc(r.site)}, ${esc(r.species)} ${esc(r.tooth)}</span></h3>
      <p class="muted">Age model: ${esc(r.growth_table)}</p>
      ${r.points.length ? chartSvg(r, milestone) : ""}
      ${fitTable(r)}
      ${[...r.warnings, ...r.fits.flatMap((f) => f.warnings.map((w) => `${f.label}: ${w}`))].map((w) => `<div class="warn">${esc(w)}</div>`).join("")}
    </section>`).join("");

  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>WeanAge report</title><style>${CSS}</style></head><body>
    <h1>WeanAge report</h1>
    <p class="muted">Generated ${esc(new Date().toLocaleString())} with WeanAge ${esc(config.version)}.
      ${state.samples.length} samples, ${state.results.length} specimens.</p>
    ${synthetic ? '<div class="warn"><b>Synthetic data:</b> this dataset includes simulated values, not real measurements.</div>' : ""}
    ${placeholders ? `<div class="warn"><b>Placeholder values in use (TBD-LAB):</b> ${config.tbd.map((i) => esc(i.label)).join("; ")}. Estimates are illustrative until these are replaced.</div>` : ""}
    <h2>Methods and settings</h2>
    ${kv([
      ["Curve models", esc(opts.models.join(", "))],
      ["Reported milestone", esc(milestone)],
      ["Transition threshold", `${num(opts.transition_threshold * 100, 0)}% of the δ¹⁵N drop`],
      ["Uncertainty", opts.uncertainty === "bootstrap" ? `residual bootstrap (${opts.bootstrap_draws} refits)` : `parameter covariance (${opts.monte_carlo_draws} draws)`],
      ["Age-model error", "growth-table SD applied as one shared shift per draw"],
      ["Analytical SD (δ¹⁵N)", opts.analytical_sd_permil ? `${opts.analytical_sd_permil}‰` : "not set"],
      ["Time averaging", opts.time_averaging ? `on — increment ${opts.increment_width_mm} mm, growth-layer offset ${opts.growth_layer_offset_mm} mm, inner dentine weight ${opts.inner_dentine_weight}` : "off"],
      ["Seasonal term", opts.seasonal_term ? `on (period ${opts.season_period_months} months)` : "off"],
      ["Collagen QC", `C:N ${opts.qc.cn_min}–${opts.qc.cn_max}; %C ≥ ${opts.qc.pct_C_min}; %N ≥ ${opts.qc.pct_N_min}; yield ≥ ${opts.qc.collagen_yield_min}%; failed samples ${opts.qc.exclude_failed ? "excluded" : "kept"}`],
      ["Adult-female baselines", Object.keys(opts.adult_baselines || {}).length ? esc(Object.entries(opts.adult_baselines).map(([k, b]) => `${k}: ${b.mean} ± ${b.sd}‰`).join("; ")) + (opts.constrain_adult_plateau ? " (adult plateau constrained)" : "") : "none"],
      ["Random seed", esc(opts.random_seed)],
    ])}
    <h3>Age models</h3><ul>${ageModels}</ul>
    <p class="muted">Model comparison uses AICc and Akaike weights; the model average combines all fitted models by weight with intervals from a weighted mixture of their draws. Full settings are embedded at the end of this file.</p>
    <h2>Summary</h2>
    <table><thead><tr><th>Specimen</th><th>Site</th><th>Taxon / tooth</th><th>Best model</th><th>${esc(milestone)} (best)</th><th>${esc(milestone)} (average)</th><th>Warnings</th></tr></thead><tbody>${summaryRows}</tbody></table>
    ${compareSection(compare)}
    <h2>Specimens</h2>${specimens}
    <h2>References</h2><ol>${REFERENCES.map((r) => `<li>${esc(r)}</li>`).join("")}</ol>
    <script type="application/json" id="weanage-settings">${JSON.stringify({ app_version: config.version, settings, options: opts }).replace(/</g, "\\u003c")}</script>
    </body></html>`;
}
