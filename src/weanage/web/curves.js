// Builds chart options for a specimen result (shared by the results view and the report).
import { color, esc, MODEL_STYLE, num } from "./util.js";

export function curveOptions(res, { visible, milestone, xRange = null, showD13C = false, onZoom = null }) {
  const fits = res.fits.filter((f) => f.converged && visible.has(f.model));
  const multiTooth = new Set(res.points.map((p) => p.tooth)).size > 1;
  const markers = fits
    .map((f) => ({ f, m: f[milestone] }))
    .filter(({ m }) => m && m.estimate != null)
    .map(({ f, m }) => ({ x: m.estimate, lo: m.ci_low, hi: m.ci_high, color: color(f.model), label: `${num(m.estimate, 1)} mo` }));
  const avg = res.model_average?.[milestone];
  if (visible.has("average") && avg && avg.estimate != null) {
    markers.push({ x: avg.estimate, lo: avg.ci_low, hi: avg.ci_high, color: MODEL_STYLE.average.color, label: `avg ${num(avg.estimate, 1)} mo` });
  }
  const best = res.fits.find((f) => f.model === res.best_model);
  const bm = best?.[milestone];
  return {
    title: `Weaning curve for ${res.specimen_id}`,
    desc: `${res.points.length} samples of δ15N against age. ${fits.length} model curve(s) shown.` +
      (bm ? ` Best model ${best.label}: weaning ${milestone} ${num(bm.estimate, 1)} months.` : ""),
    xLabel: "Age at dentine formation (months)",
    yLabel: "δ¹⁵N (‰ AIR)",
    xRange,
    showD13C,
    positionAxis: !multiTooth,
    onZoom,
    points: res.points.map((p) => ({
      x: p.age_months,
      y: p.d15N,
      xMin: p.age_min,
      xMax: p.age_max,
      d13C: p.d13C,
      position: p.position_mm,
      group: multiTooth ? p.tooth : null,
      used: p.used_in_fit,
      extrapolated: p.extrapolated,
      label: `${multiTooth ? `${esc(p.tooth)} · ` : ""}${p.position_mm} mm → ${num(p.age_months, 1)} mo${p.age_min != null ? ` (window ${num(p.age_min, 1)}–${num(p.age_max, 1)})` : ""}<br>δ¹⁵N ${num(p.d15N)}‰${p.d13C != null ? ` · δ¹³C ${num(p.d13C)}‰` : ""}${p.qc_flags.length ? `<br><em>${esc(p.qc_flags.join(", "))}</em>` : ""}`,
    })),
    curves: fits.map((f) => ({ name: f.model, color: color(f.model), dash: MODEL_STYLE[f.model]?.dash, xs: f.curve_age, ys: f.curve_d15N })),
    markers,
  };
}
