// Charts drawn as SVG (no chart library): weaning curves, group "forest" plots and line charts.
import { ageText, color, esc, MODEL_STYLE, num, theme, toUnit, unitWord } from "./util.js";

const SVG = "http://www.w3.org/2000/svg";
const SHAPES = ["circle", "square", "diamond", "triangle"];
let chartCount = 0;

// Make an SVG element with attributes, optionally adding it to a parent.
function el(tag, attrs = {}, parent) {
  const node = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

// Round numbers for the axis (e.g. 0, 2.5, 5, 7.5) covering min..max.
export function niceTicks(min, max, count = 6) {
  if (!isFinite(min) || !isFinite(max)) return [];
  if (min === max) [min, max] = [min - 1, max + 1];
  const rough = (max - min) / count;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= rough);
  const ticks = [];
  for (let v = Math.floor(min / step + 1e-9) * step; v <= Math.ceil(max / step - 1e-9) * step + step * 1e-9; v += step) {
    ticks.push(Math.round(v / step) * step);
  }
  return ticks;
}

// A function that turns a data value into a pixel position (and back with .invert).
function scale(d0, d1, p0, p1) {
  const k = (p1 - p0) / (d1 - d0 || 1);
  const f = (v) => p0 + (v - d0) * k;
  f.invert = (px) => d0 + (px - p0) / k;
  return f;
}

const label = (v) => (Math.abs(v) >= 100 ? v.toFixed(0) : String(+v.toFixed(2)));

function marker(shape, x, y, r, attrs, parent) {
  if (shape === "square") return el("rect", { x: x - r, y: y - r, width: 2 * r, height: 2 * r, ...attrs }, parent);
  const corners = {
    diamond: [[0, -1.3], [1.3, 0], [0, 1.3], [-1.3, 0]],
    triangle: [[0, -1.3], [1.2, 1], [-1.2, 1]],
  }[shape];
  if (corners) return el("polygon", { points: corners.map(([a, b]) => `${x + a * r},${y + b * r}`).join(" "), ...attrs }, parent);
  return el("circle", { cx: x, cy: y, r, ...attrs }, parent);
}

// Start a fresh chart inside `box`, with a title and description for screen readers.
function newChart(box, width, height, margin, title, description) {
  box.querySelectorAll("svg").forEach((s) => s.remove());
  const id = `chart-${++chartCount}`;
  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart", role: "img", "aria-labelledby": `${id}-t ${id}-d` });
  el("title", { id: `${id}-t` }, svg).textContent = title || "Chart";
  el("desc", { id: `${id}-d` }, svg).textContent = description || "";
  box.prepend(svg);
  const area = { left: margin.l, right: width - margin.r, bottom: height - margin.b, top: margin.t };
  return { svg, area, id, width };
}

function xAxis(g, area, xs, ticks, title) {
  for (const t of ticks) {
    el("line", { x1: xs(t), x2: xs(t), y1: area.bottom, y2: area.bottom + 5, class: "tick" }, g);
    el("text", { x: xs(t), y: area.bottom + 20, "text-anchor": "middle" }, g).textContent = label(t);
  }
  el("line", { x1: area.left, x2: area.right, y1: area.bottom, y2: area.bottom, class: "axis" }, g);
  el("text", { x: (area.left + area.right) / 2, y: area.bottom + 42, "text-anchor": "middle", class: "label" }, g).textContent = title;
}

function yAxis(g, area, ys, ticks, title) {
  for (const t of ticks) {
    el("line", { x1: area.left, x2: area.right, y1: ys(t), y2: ys(t), class: "grid" }, g);
    el("text", { x: area.left - 8, y: ys(t) + 4, "text-anchor": "end" }, g).textContent = label(t);
  }
  el("line", { x1: area.left, x2: area.left, y1: area.bottom, y2: area.top, class: "axis" }, g);
  const middle = (area.top + area.bottom) / 2;
  el("text", { x: 16, y: middle, transform: `rotate(-90 16 ${middle})`, "text-anchor": "middle", class: "label" }, g).textContent = title;
}

// Show `html` next to the mouse while it is over `node`.
function hover(box, node, html) {
  let tip = box.querySelector(".chart-tip");
  if (!tip) {
    tip = Object.assign(document.createElement("div"), { className: "chart-tip", hidden: true });
    box.appendChild(tip);
  }
  node.addEventListener("mouseenter", (e) => {
    const r = box.getBoundingClientRect();
    tip.innerHTML = html;
    tip.hidden = false;
    tip.style.left = `${e.clientX - r.left + 12}px`;
    tip.style.top = `${e.clientY - r.top - 12}px`;
  });
  node.addEventListener("mouseleave", () => (tip.hidden = true));
}

const path = (points, xs, ys) => points.map(([x, y], i) => `${i ? "L" : "M"}${xs(x).toFixed(1)},${ys(y).toFixed(1)}`).join("");

/**
 * Weaning curve chart.
 * points:  [{x, y, xMin?, xMax?, used, extrapolated, label, group?, position?, d13C?}]
 * curves:  [{color, dash, xs, ys}]     markers: [{x, lo, hi, color, label}] (weaning age ± 95 %)
 * xRange (zoom window), positionAxis (mm along the top), showD13C, onZoom(range | null)
 */
export function curveChart(box, o) {
  const { svg, area, id, width } = newChart(box, 760, 300, { l: 64, r: o.showD13C ? 58 : 20, t: o.positionAxis ? 44 : 16, b: 56 }, o.title, o.desc);
  // The axis range comes from the data and curves only, so one wild estimate cannot squash the chart.
  const allX = [...o.points.flatMap((p) => [p.x, p.xMin ?? p.x, p.xMax ?? p.x]), ...o.curves.flatMap((c) => c.xs)];
  let [xMin, xMax] = o.xRange || [Math.min(...allX), Math.max(...allX)];
  const inView = (x) => x >= xMin && x <= xMax;
  const allY = [...o.points.filter((p) => inView(p.x)).map((p) => p.y), ...o.curves.flatMap((c) => c.ys.filter((_, i) => inView(c.xs[i]))),
    ...(o.bands || []).flatMap((b) => [...b.lo, ...b.hi].filter((_, i) => inView(b.xs[i % b.xs.length])))];
  const pad = (Math.max(...allY) - Math.min(...allY)) * 0.08 || 0.5;
  const xTicks = niceTicks(xMin, xMax);
  const yTicks = niceTicks(Math.min(...allY) - pad, Math.max(...allY) + pad, 5);
  if (!o.xRange) [xMin, xMax] = [Math.min(xMin, xTicks[0]), Math.max(xMax, xTicks.at(-1))];
  const xs = scale(xMin, xMax, area.left, area.right);
  const ys = scale(yTicks[0], yTicks.at(-1), area.bottom, area.top);

  const axes = el("g", { class: "axes" }, svg);
  yAxis(axes, area, ys, yTicks, o.yLabel);
  xAxis(axes, area, xs, xTicks.filter(inView), o.xLabel);
  if (o.positionAxis) positionAxis(axes, area, xs, o.points, inView);

  el("clipPath", { id: `${id}-clip` }, svg).appendChild(el("rect", { x: area.left, y: area.top, width: area.right - area.left, height: area.bottom - area.top }));
  const plot = el("g", { "clip-path": `url(#${id}-clip)` }, svg);
  // Each weaning age: a dashed line, and its 95% interval as a thin bar stacked just above the age
  // axis, where ages are read. (Shaded full-height bands turned into a muddy overlap with five models.)
  o.markers.forEach((m, i) => {
    el("line", { x1: xs(m.x), x2: xs(m.x), y1: area.bottom, y2: area.top, stroke: m.color, "stroke-dasharray": "5 4", "stroke-width": 2 }, plot);
    if (m.lo == null) return;
    const y = area.bottom - 7 - i * 8;
    el("line", { x1: xs(m.lo), x2: xs(m.hi), y1: y, y2: y, stroke: m.color, "stroke-width": 3, "stroke-linecap": "butt", class: "interval" }, plot);
    for (const end of [m.lo, m.hi]) el("line", { x1: xs(end), x2: xs(end), y1: y - 3, y2: y + 3, stroke: m.color, "stroke-width": 2 }, plot);
  });

  // δ13C on its own axis on the right.
  const carbon = o.showD13C ? o.points.filter((p) => p.d13C != null).sort((a, b) => a.x - b.x) : [];
  if (carbon.length > 1) {
    const cTicks = niceTicks(Math.min(...carbon.map((p) => p.d13C)) - 0.2, Math.max(...carbon.map((p) => p.d13C)) + 0.2, 5);
    const cs = scale(cTicks[0], cTicks.at(-1), area.bottom, area.top);
    for (const t of cTicks) el("text", { x: area.right + 8, y: cs(t) + 4, class: "c13" }, axes).textContent = label(t);
    el("line", { x1: area.right, x2: area.right, y1: area.bottom, y2: area.top, class: "axis" }, axes);
    const middle = (area.top + area.bottom) / 2;
    el("text", { x: width - 10, y: middle, transform: `rotate(90 ${width - 10} ${middle})`, "text-anchor": "middle", class: "label c13" }, axes).textContent = "δ¹³C (‰ VPDB)";
    el("path", { d: path(carbon.map((p) => [p.x, p.d13C]), xs, cs), class: "c13-line" }, plot);
    for (const p of carbon) marker("diamond", xs(p.x), cs(p.d13C), 3, { class: "c13-pt" }, plot);
  }

  for (const b of o.bands || []) { // shaded intervals around a curve
    const outline = [...b.xs.map((x, i) => [x, b.hi[i]]), ...b.xs.map((x, i) => [x, b.lo[i]]).reverse()];
    el("path", { d: `${path(outline, xs, ys)}Z`, fill: b.color, opacity: 0.18 }, plot);
  }
  for (const c of o.curves) el("path", { d: path(c.xs.map((x, i) => [x, c.ys[i]]), xs, ys), fill: "none", stroke: c.color, "stroke-width": c.width || 3.5, "stroke-dasharray": c.dash }, plot);
  for (const p of o.points) if (p.xMin != null) el("line", { x1: xs(p.xMin), x2: xs(p.xMax), y1: ys(p.y), y2: ys(p.y), class: "win" }, plot);
  const groups = [...new Set(o.points.map((p) => p.group ?? ""))]; // one marker shape per tooth
  for (const p of o.points) {
    const cls = !p.used ? "pt pt-excluded" : p.extrapolated ? "pt pt-extra" : "pt";
    hover(box, marker(SHAPES[groups.indexOf(p.group ?? "") % 4], xs(p.x), ys(p.y), 4.5, { class: cls }, plot), p.label);
  }
  o.markers.forEach((m, i) => {
    const arrow = m.x > xMax ? " →" : m.x < xMin ? " ←" : ""; // estimate is off the chart
    const x = Math.min(Math.max(xs(m.x) + 4, area.left + 4), area.right - 70);
    el("text", { x, y: area.top + 14 + i * 16, fill: m.color, class: "marker-label" }, svg).textContent = m.label + arrow;
  });
  if (groups.length > 1) {
    groups.forEach((g, i) => {
      marker(SHAPES[i % 4], area.left + 12 + i * 70, area.bottom - 12, 4, { class: "pt" }, svg);
      el("text", { x: area.left + 21 + i * 70, y: area.bottom - 8, class: "legend-text" }, svg).textContent = g;
    });
  }
  if (o.onZoom) addZoom(svg, plot, area, xs, o.onZoom);
  return svg;
}

// Top axis: position along the tooth, found by interpolating between the samples.
function positionAxis(g, area, xs, points, inView) {
  const pts = points.filter((p) => p.position != null).sort((a, b) => a.position - b.position);
  if (pts.length < 2) return;
  el("line", { x1: area.left, x2: area.right, y1: area.top, y2: area.top, class: "axis" }, g);
  for (const mm of niceTicks(pts[0].position, pts.at(-1).position, 8)) {
    const after = pts.findIndex((p) => p.position >= mm);
    if (after < 1) continue;
    const [a, b] = [pts[after - 1], pts[after]];
    const age = a.x + ((mm - a.position) / (b.position - a.position || 1)) * (b.x - a.x);
    if (!inView(age)) continue;
    el("line", { x1: xs(age), x2: xs(age), y1: area.top, y2: area.top - 5, class: "tick" }, g);
    el("text", { x: xs(age), y: area.top - 9, "text-anchor": "middle" }, g).textContent = label(mm);
  }
  el("text", { x: (area.left + area.right) / 2, y: 13, "text-anchor": "middle", class: "label" }, g).textContent = "Position from cusp apex (mm)";
}

// Drag across the chart to zoom into an age range; double-click to reset.
function addZoom(svg, plot, area, xs, onZoom) {
  const band = el("rect", { y: area.top, height: area.bottom - area.top, class: "zoom-sel", visibility: "hidden" }, svg);
  const catcher = el("rect", { x: area.left, y: area.top, width: area.right - area.left, height: area.bottom - area.top, class: "zoom-hit" });
  svg.insertBefore(catcher, plot);
  const svgX = (e) => {
    const p = Object.assign(svg.createSVGPoint(), { x: e.clientX, y: e.clientY });
    return Math.min(Math.max(p.matrixTransform(svg.getScreenCTM().inverse()).x, area.left), area.right);
  };
  let start = null;
  catcher.addEventListener("pointerdown", (e) => { start = svgX(e); catcher.setPointerCapture(e.pointerId); });
  catcher.addEventListener("pointermove", (e) => {
    if (start == null) return;
    band.setAttribute("x", Math.min(start, svgX(e)));
    band.setAttribute("width", Math.abs(svgX(e) - start));
    band.setAttribute("visibility", "visible");
  });
  catcher.addEventListener("pointerup", (e) => {
    const end = svgX(e);
    band.setAttribute("visibility", "hidden");
    if (start != null && Math.abs(end - start) > 8) onZoom([xs.invert(Math.min(start, end)), xs.invert(Math.max(start, end))]);
    start = null;
  });
  svg.addEventListener("dblclick", () => onZoom(null));
}

/** Forest plot: one row per group with its interval, mean (square) and specimens (dots). */
export function forestChart(box, groups, xTitle) {
  const desc = groups.map((g) => `${g.label}: mean ${num(g.mean, 1)}`).join("; ");
  const { svg, area } = newChart(box, 760, 70 + 36 * Math.max(groups.length, 1), { l: 190, r: 24, t: 10, b: 50 }, xTitle, desc);
  const values = groups.flatMap((g) => [g.lo, g.hi, g.mean, ...g.values.map((v) => v.v)]).filter(isFinite);
  if (!values.length) return svg;
  const ticks = niceTicks(Math.min(...values), Math.max(...values));
  const xs = scale(ticks[0], ticks.at(-1), area.left, area.right);
  xAxis(el("g", { class: "axes" }, svg), area, xs, ticks, xTitle);
  groups.forEach((g, i) => {
    const y = area.top + 36 * (i + 0.5);
    el("text", { x: area.left - 10, y: y + 4, "text-anchor": "end", class: "row-label" }, svg).textContent = g.label;
    if (isFinite(g.lo) && isFinite(g.hi)) el("line", { x1: xs(g.lo), x2: xs(g.hi), y1: y, y2: y, class: "ci" }, svg);
    for (const v of g.values) hover(box, el("circle", { cx: xs(v.v), cy: y + 9, r: 4.5, class: "pt pt-small" }, svg), v.label);
    if (isFinite(g.mean)) el("rect", { x: xs(g.mean) - 5, y: y - 5, width: 10, height: 10, class: "mean" }, svg);
  });
  return svg;
}

/** Line chart for the planner. series: [{name, color, dash, points: [{x, y}]}] */
export function lineChart(box, series, { xLabel, yLabel, title, yMin } = {}) {
  const desc = series.map((s) => `${s.name}: ${s.points.map((p) => `${label(p.x)} → ${num(p.y)}`).join(", ")}`).join("; ");
  const legend = series.length > 1; // one line needs no legend: the axis title names it
  const { svg, area } = newChart(box, 760, 360, { l: 64, r: legend ? 130 : 24, t: 16, b: 56 }, title, desc);
  const hasValue = (p) => p.y != null && isFinite(p.y);
  const pts = series.flatMap((s) => s.points).filter(hasValue);
  if (!pts.length) return svg;
  const xt = niceTicks(Math.min(...pts.map((p) => p.x)), Math.max(...pts.map((p) => p.x)));
  const yt = niceTicks(yMin ?? Math.min(...pts.map((p) => p.y)), Math.max(...pts.map((p) => p.y)), 5);
  const xs = scale(xt[0], xt.at(-1), area.left, area.right);
  const ys = scale(yt[0], yt.at(-1), area.bottom, area.top);
  const axes = el("g", { class: "axes" }, svg);
  yAxis(axes, area, ys, yt, yLabel);
  xAxis(axes, area, xs, xt, xLabel);
  series.forEach((s, i) => {
    const ok = s.points.filter(hasValue);
    el("path", { d: path(ok.map((p) => [p.x, p.y]), xs, ys), fill: "none", stroke: s.color, "stroke-width": 3, "stroke-dasharray": s.dash }, svg);
    for (const p of ok) marker(SHAPES[i % 4], xs(p.x), ys(p.y), 5, { fill: s.color }, svg);
    if (!legend) return;
    const y = area.top + 12 + i * 18; // legend
    el("line", { x1: area.right + 12, x2: area.right + 34, y1: y, y2: y, stroke: s.color, "stroke-width": 3, "stroke-dasharray": s.dash }, svg);
    el("text", { x: area.right + 40, y: y + 4, class: "legend-text" }, svg).textContent = s.name;
  });
  return svg;
}

/** A weaning age (in months) as a chart marker in the chosen unit. */
export const ageMarker = (value, colour, prefix = "") => ({
  x: toUnit(value.estimate), lo: toUnit(value.ci_low), hi: toUnit(value.ci_high), color: colour, label: `${prefix}${ageText(value.estimate)}`,
});

/** Everything the weaning chart needs for one specimen's results. */
// `palette` is "dark" or "light"; the report always uses light so it prints well.
export function curveOptions(res, { visible, milestone, xRange = null, showD13C = false, onZoom = null, palette = theme() }) {
  const fits = res.fits.filter((f) => f.converged && visible.has(f.model));
  const multiTooth = new Set(res.points.map((p) => p.tooth)).size > 1;
  const markers = fits.filter((f) => f[milestone] && !f[milestone].beyond)
    .map((f) => ageMarker(f[milestone], color(f.model, palette), ""));
  const avg = res.model_average?.[milestone];
  if (visible.has("average") && avg && !avg.beyond) markers.push(ageMarker(avg, color("average", palette), "avg "));
  return {
    title: `Weaning curve for ${res.specimen_id}`,
    desc: `${res.points.length} samples of δ15N against age; ${fits.length} model ${fits.length === 1 ? "curve" : "curves"} shown.`,
    xLabel: `Age at dentine formation (${unitWord()})`,
    yLabel: "δ¹⁵N (‰ AIR)",
    xRange, showD13C, onZoom, positionAxis: !multiTooth, markers,
    curves: fits.map((f) => ({ color: color(f.model, palette), dash: MODEL_STYLE[f.model].dash, xs: f.curve_age.map(toUnit), ys: f.curve_d15N })),
    points: res.points.map((p) => ({
      x: toUnit(p.age_months), y: p.d15N, xMin: toUnit(p.age_min), xMax: toUnit(p.age_max), d13C: p.d13C, position: p.position_mm,
      group: multiTooth ? p.tooth : null, used: p.used_in_fit, extrapolated: p.extrapolated,
      label: `${multiTooth ? `${esc(p.tooth)} · ` : ""}${p.position_mm} mm → ${ageText(p.age_months)}${p.age_min != null ? ` (window ${ageText(p.age_min)}–${ageText(p.age_max)})` : ""}` +
        `<br>δ¹⁵N ${num(p.d15N)}‰${p.d13C != null ? ` · δ¹³C ${num(p.d13C)}‰` : ""}${p.qc_flags.length ? `<br><em>${esc(p.qc_flags.join(", "))}</em>` : ""}`,
    })),
  };
}

/** A standalone copy of a chart (with its styles built in) for downloads and the report. */
export function svgMarkup(svg) {
  const copy = svg.cloneNode(true);
  copy.setAttribute("xmlns", SVG);
  copy.querySelectorAll(".zoom-hit, .zoom-sel").forEach((n) => n.remove());
  const style = document.createElementNS(SVG, "style");
  // Exported charts always use the light colours, on a white background.
  style.textContent = `svg{background:#fff}text{font:13px sans-serif;fill:#24292f}.grid{stroke:#d0d7de}.axis,.tick{stroke:#30363d}.pt{fill:#0d1117}
    .pt-excluded{fill:none;stroke:#a40e26;stroke-width:2}.pt-extra{fill:#57606a}.pt-small{fill:#0060a8}.ci{stroke:#24292f;stroke-width:2}
    .mean{fill:#24292f}.label{font-weight:700}.win{stroke:#57606a;stroke-width:2}.c13,.c13-pt{fill:#6a4300}
    .c13-line{fill:none;stroke:#6a4300;stroke-width:1.5;stroke-dasharray:2 3}`;
  copy.prepend(style);
  return new XMLSerializer().serializeToString(copy);
}
