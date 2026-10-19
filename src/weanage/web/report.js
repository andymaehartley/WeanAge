// Builds a standalone HTML report (settings, charts, tables, references) that prints cleanly to PDF.
import { curveChart, curveOptions, forestChart, svgMarkup } from "./chart.js";
import { esc, MILESTONES, num, pval } from "./util.js";

const REFERENCES = [
  "DeNiro, M. J. (1985). Postmortem preservation and alteration of in vivo bone collagen isotope ratios in relation to palaeodietary reconstruction. Nature 317, 806–809.",
  "van Klinken, G. J. (1999). Bone collagen quality indicators for palaeodietary and radiocarbon measurements. Journal of Archaeological Science 26, 687–695.",
  "Tsutaya, T., & Yoneda, M. (2013). Quantitative reconstruction of weaning ages in archaeological human populations using bone collagen nitrogen isotope ratios and approximate Bayesian computation. PLoS ONE 8, e72327.",
  "Tsutaya, T. (2020). Blurred time resolution of tooth dentin serial sections. American Journal of Physical Anthropology 173, 748–759.",
  "Ganiatsou, E., Souleles, A., & Papageorgopoulou, C. (2023). WEaning Age FiNder (WEAN): a tool for estimating weaning age from stable isotope ratios of dentinal collagen. Archaeological and Anthropological Sciences 15, 50.",
  "Brown, W. A. B., Christofferson, P. V., Massler, M., & Weiss, M. B. (1960). Postnatal tooth development in cattle. American Journal of Veterinary Research 21, 7–34.",
  "Balasse, M., Bocherens, H., Mariotti, A., & Ambrose, S. H. (2001). Detection of dietary changes by intra-tooth carbon and nitrogen isotopic analysis: an experimental study of dentine collagen of cattle (Bos taurus). Journal of Archaeological Science 28, 235–245.",
  "Guiry, E. J., & Szpak, P. (2020). Quality control for modern bone collagen stable carbon and nitrogen isotope measurements. Methods in Ecology and Evolution 11, 1049–1060.",
  "Beaumont, J., & Montgomery, J. (2016). The Great Irish Famine: identifying starvation in the tissues of victims using stable isotope analysis of bone and incremental dentine collagen. PLoS ONE 11, e0160065.",
  "Balasse, M., et al. (2021). Seasonal calving in European prehistoric cattle and its impacts on milk availability and cheesemaking. Scientific Reports 11, 8185.",
  "Burnham, K. P., & Anderson, D. R. (2002). Model Selection and Multimodel Inference (2nd ed.). Springer.",
  "DerSimonian, R., & Laird, N. (1986). Meta-analysis in clinical trials. Controlled Clinical Trials 7, 177–188.",
];

const CSS = `body{font:14px/1.5 system-ui,sans-serif;color:#1f2328;max-width:960px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.6rem}h2{font-size:1.2rem;border-bottom:1px solid #ddd;padding-bottom:.2rem;margin-top:2rem}h3{font-size:1rem;margin-top:1.4rem}
table{border-collapse:collapse;width:100%;font-size:12px;margin:.4rem 0}th,td{border-bottom:1px solid #e3e1da;padding:.25rem .4rem;text-align:left;vertical-align:top}
.warn{background:#fff4b8;border-left:4px solid #e6b800;padding:.4rem .7rem;margin:.6rem 0}.muted{color:#667085}
section{break-inside:avoid}svg{width:100%;height:auto}@media print{body{margin:0}h2{break-after:avoid}}`;

// headers: list of column titles; rows: list of lists of cell HTML.
const htmlTable = (headers, rows) =>
  `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c ?? "—"}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
const withCI = (v) => (v ? `${num(v.estimate, 1)}${v.ci_low != null ? ` <span class="muted">(${num(v.ci_low, 1)}–${num(v.ci_high, 1)})</span>` : ""}` : "—");

// Draw a chart off-screen and return its SVG text.
export function offscreen(draw) {
  const box = Object.assign(document.createElement("div"), { style: "position:absolute;left:-9999px;width:760px" });
  document.body.appendChild(box);
  const markup = svgMarkup(draw(box));
  box.remove();
  return markup;
}

function specimenSection(r, milestone) {
  const visible = new Set([...r.fits.map((f) => f.model), "average"]);
  const chart = r.points.length ? offscreen((box) => curveChart(box, curveOptions(r, { visible, milestone, showD13C: r.points.some((p) => p.d13C != null), palette: "light" }))) : "";
  const rows = r.fits.map((f) => [`${esc(f.label)}${f.model === r.best_model ? " <b>(best)</b>" : ""}`, ...MILESTONES.map((k) => withCI(f[k])),
    num(f.drop_permil), num(f.rmse, 3), num(f.delta_aicc), num(f.akaike_weight)]);
  if (Object.keys(r.model_average).length) rows.push(["<i>Model average</i>", ...MILESTONES.map((k) => withCI(r.model_average[k])), "", "", "", ""]);
  const warnings = [...r.warnings, ...r.fits.flatMap((f) => f.warnings.map((w) => `${f.label}: ${w}`))];
  return `<section><h3>${esc(r.specimen_id)} <span class="muted">— ${esc(r.site)}, ${esc(r.species)} ${esc(r.tooth)}</span></h3>
    <p class="muted">Age model: ${esc(r.growth_table)}</p>${chart}
    ${htmlTable(["Model", ...MILESTONES, "Drop ‰", "RMSE", "ΔAICc", "Weight"], rows)}
    ${warnings.map((w) => `<div class="warn">${esc(w)}</div>`).join("")}</section>`;
}

function compareSection(t) {
  const forest = offscreen((box) => forestChart(box, t.groups.map((g) => ({ label: g.group, mean: g.mean, lo: g.ci_low, hi: g.ci_high, values: [] })),
    `Weaning ${t.milestone} (months), random-effects mean ± 95% CI`));
  const b = t.bayes;
  return `<h2>Group comparison</h2>
    <p>Grouping: ${esc(t.group_by.join(" × "))}; milestone: ${esc(t.milestone)}; estimates: ${esc(t.model)}.</p>${forest}
    ${htmlTable(["Group", "n", "Mean", "95% CI", "τ"], t.groups.map((g) => [esc(g.group), g.n, num(g.mean, 1), `${num(g.ci_low, 1)}–${num(g.ci_high, 1)}`, num(g.tau)]))}
    <p>Between-group Q = ${num(t.q_between)} (df ${t.q_df}), p = ${pval(t.q_p)}; permutation p = ${pval(t.permutation_p)}.</p>
    ${t.pairwise.length ? htmlTable(["Pair", "Difference", "p", "p (Holm)"], t.pairwise.map((p) => [`${esc(p.group_a)} − ${esc(p.group_b)}`, num(p.difference, 1), pval(p.p), pval(p.p_holm)])) : ""}
    ${b ? `<h3>Hierarchical Bayesian model</h3><p class="muted">τ = ${num(b.tau_mean)} months (${num(b.tau_ci_low)}–${num(b.tau_ci_high)}); max R̂ = ${num(b.rhat_max, 3)}; ${b.draws} draws.</p>
      ${htmlTable(["Comparison", "P(first earlier)", "Difference (95% CrI)"], b.pairs.map((p) => [`${esc(p.group_a)} vs ${esc(p.group_b)}`, num(p.prob_a_earlier, 3),
        `${num(p.difference_mean, 1)} (${num(p.difference_ci_low, 1)}–${num(p.difference_ci_high, 1)})`]))}` : ""}
    ${t.notes.map((n) => `<p class="muted">${esc(n)}</p>`).join("")}`;
}

function ageModelLine(key, opts, tables) {
  const linear = opts.growth_overrides?.[key];
  if (linear) return `<li><b>${esc(key)}</b>: custom linear, ${linear.initiation_age_months} mo + position / ${linear.extension_rate_mm_per_month} mm·mo⁻¹</li>`;
  const t = (opts.growth_tables || []).concat(tables).find((g) => `${g.species}:${g.tooth}` === key);
  if (!t) return `<li><b>${esc(key)}</b>: none</li>`;
  return `<li><b>${esc(key)}</b>: ${esc(t.label)}${t.placeholder ? " <b>[PLACEHOLDER]</b>" : ""} — points ${t.knots.map((k) => `${k.position_mm} mm→${k.age_months} mo`).join(", ")}; ±${t.age_uncertainty_months} mo; ${esc(t.source)}</li>`;
}

export function buildReport({ config, state, settings, compare }) {
  const o = state.options;
  const milestone = o.reported_milestone;
  const keys = [...new Set(state.samples.map((s) => `${s.species}:${s.tooth}`))];
  const baselines = Object.entries(o.adult_baselines || {}).map(([k, b]) => `${k}: ${b.mean} ± ${b.sd}‰`).join("; ");
  const methods = [
    ["Curve models", esc(o.models.join(", "))],
    ["Reported milestone", esc(milestone)],
    ["Transition threshold", `${num(o.transition_threshold * 100, 0)}% of the δ¹⁵N drop`],
    ["Uncertainty", o.uncertainty === "bootstrap" ? `residual bootstrap (${o.bootstrap_draws} refits)` : `parameter covariance (${o.monte_carlo_draws} draws)`],
    ["Age-model error", "growth-table SD applied as one shared shift per draw"],
    ["Analytical SD (δ¹⁵N)", o.analytical_sd_permil ? `${o.analytical_sd_permil}‰` : "not set"],
    ["Time averaging", o.time_averaging ? `on — slice ${o.increment_width_mm} mm, growth-layer offset ${o.growth_layer_offset_mm} mm, inner dentine weight ${o.inner_dentine_weight}` : "off"],
    ["Seasonal term", o.seasonal_term ? `on (period ${o.season_period_months} months)` : "off"],
    ["Collagen QC", `C:N ${o.qc.cn_min}–${o.qc.cn_max}; %C ≥ ${o.qc.pct_C_min}; %N ≥ ${o.qc.pct_N_min}; yield ≥ ${o.qc.collagen_yield_min}%; failed samples ${o.qc.exclude_failed ? "excluded" : "kept"}`],
    ["Adult-female baselines", baselines ? esc(baselines) + (o.constrain_adult_plateau ? " (adult plateau constrained)" : "") : "none"],
    ["Random seed", esc(o.random_seed)],
  ];
  const summary = state.results.map((r) => {
    const best = r.fits.find((f) => f.model === r.best_model);
    const warnings = r.warnings.length + r.fits.reduce((n, f) => n + f.warnings.length, 0);
    return [esc(r.specimen_id), esc(r.site), `${esc(r.species)} ${esc(r.tooth)}`, esc(best?.label || "—"), withCI(best?.[milestone]), withCI(r.model_average[milestone]), warnings];
  });
  const synthetic = state.samples.some((s) => /SYNTHETIC/.test(s.notes || ""));
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>WeanAge report</title><style>${CSS}</style></head><body>
    <h1>WeanAge report</h1>
    <p class="muted">Generated ${esc(new Date().toLocaleString())} with WeanAge ${esc(config.version)}. ${state.samples.length} samples, ${state.results.length} specimens.</p>
    ${synthetic ? '<div class="warn"><b>Synthetic data:</b> this dataset includes simulated values, not real measurements.</div>' : ""}
    ${config.tbd.length ? `<div class="warn"><b>Placeholder values in use (TBD-LAB):</b> ${config.tbd.map((i) => esc(i.label)).join("; ")}. Estimates are illustrative until these are replaced.</div>` : ""}
    <h2>Methods and settings</h2>${htmlTable(["Setting", "Value"], methods)}
    <h3>Age models</h3><ul>${keys.map((k) => ageModelLine(k, o, state.config.growth_tables)).join("")}</ul>
    <p class="muted">Models are compared by AICc and Akaike weights; the model average combines all fitted models by weight, with intervals from a weighted mix of their draws. Full settings are stored at the end of this file.</p>
    <h2>Summary</h2>${htmlTable(["Specimen", "Site", "Taxon / tooth", "Best model", `${milestone} (best)`, `${milestone} (average)`, "Warnings"], summary)}
    ${compare ? compareSection(compare.tests) : ""}
    <h2>Specimens</h2>${state.results.map((r) => specimenSection(r, milestone)).join("")}
    <h2>References</h2><ol>${REFERENCES.map((r) => `<li>${esc(r)}</li>`).join("")}</ol>
    <script type="application/json" id="weanage-settings">${JSON.stringify({ app_version: config.version, settings, options: o }).replace(/</g, "\\u003c")}</script>
    </body></html>`;
}
