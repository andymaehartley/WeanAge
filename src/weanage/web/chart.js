// Dependency-free, accessible SVG charts: weaning curves, group forest plots and
// line charts for the sampling planner.

const SVG_NS = "http://www.w3.org/2000/svg";
let uid = 0;

function el(tag, attrs = {}, parent) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

export function niceTicks(min, max, count = 6) {
  if (!isFinite(min) || !isFinite(max)) return [];
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const ticks = [];
  const end = Math.ceil(max / step - 1e-9) * step;
  for (let v = Math.floor(min / step + 1e-9) * step; v <= end + step * 1e-9; v += step) {
    ticks.push(Math.round(v / step) * step);
  }
  return ticks;
}

function scale(d0, d1, r0, r1) {
  const k = (r1 - r0) / (d1 - d0 || 1);
  const f = (v) => r0 + (v - d0) * k;
  f.invert = (px) => d0 + (px - r0) / k;
  return f;
}

function fmt(v) {
  return Math.abs(v) >= 100 ? v.toFixed(0) : +v.toFixed(2) + "";
}

function tooltip(container) {
  let tip = container.querySelector(".chart-tip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.setAttribute("role", "status");
    tip.hidden = true;
    container.appendChild(tip);
  }
  return {
    show(html, x, y) {
      tip.innerHTML = html;
      tip.hidden = false;
      tip.style.left = `${x + 12}px`;
      tip.style.top = `${y - 12}px`;
    },
    hide() {
      tip.hidden = true;
    },
  };
}

function frame(container, width, height, margin, title, desc) {
  container.querySelectorAll("svg").forEach((s) => s.remove());
  const id = `chart-${++uid}`;
  const svg = el("svg", {
    viewBox: `0 0 ${width} ${height}`,
    class: "chart",
    role: "img",
    "aria-labelledby": `${id}-t ${id}-d`,
    preserveAspectRatio: "xMidYMid meet",
  });
  el("title", { id: `${id}-t` }, svg).textContent = title || "Chart";
  el("desc", { id: `${id}-d` }, svg).textContent = desc || "";
  container.prepend(svg);
  const plot = { x0: margin.l, x1: width - margin.r, y0: height - margin.b, y1: margin.t };
  return { svg, plot, id };
}

function bottomAxis(g, plot, xs, ticks, label) {
  for (const t of ticks) {
    el("line", { x1: xs(t), x2: xs(t), y1: plot.y0, y2: plot.y0 + 5, class: "tick" }, g);
    el("text", { x: xs(t), y: plot.y0 + 20, "text-anchor": "middle" }, g).textContent = fmt(t);
  }
  el("line", { x1: plot.x0, x2: plot.x1, y1: plot.y0, y2: plot.y0, class: "axis" }, g);
  el("text", { x: (plot.x0 + plot.x1) / 2, y: plot.y0 + 42, "text-anchor": "middle", class: "label" }, g)
    .textContent = label;
}

function leftAxis(g, plot, ys, ticks, label, grid = true) {
  for (const t of ticks) {
    if (grid) el("line", { x1: plot.x0, x2: plot.x1, y1: ys(t), y2: ys(t), class: "grid" }, g);
    el("text", { x: plot.x0 - 8, y: ys(t) + 4, "text-anchor": "end" }, g).textContent = fmt(t);
  }
  el("line", { x1: plot.x0, x2: plot.x0, y1: plot.y0, y2: plot.y1, class: "axis" }, g);
  if (label) {
    const cy = (plot.y0 + plot.y1) / 2;
    el("text", { x: 16, y: cy, transform: `rotate(-90 16 ${cy})`, "text-anchor": "middle", class: "label" }, g)
      .textContent = label;
  }
}

const SHAPES = ["circle", "square", "diamond", "triangle"];

function marker(shape, cx, cy, r, attrs, parent) {
  if (shape === "square") return el("rect", { x: cx - r, y: cy - r, width: 2 * r, height: 2 * r, ...attrs }, parent);
  if (shape === "diamond") return el("polygon", { points: `${cx},${cy - r * 1.3} ${cx + r * 1.3},${cy} ${cx},${cy + r * 1.3} ${cx - r * 1.3},${cy}`, ...attrs }, parent);
  if (shape === "triangle") return el("polygon", { points: `${cx},${cy - r * 1.3} ${cx + r * 1.2},${cy + r} ${cx - r * 1.2},${cy + r}`, ...attrs }, parent);
  return el("circle", { cx, cy, r, ...attrs }, parent);
}

/**
 * Weaning curve plot.
 * opts.points:  [{x, y, xMin?, xMax?, used, extrapolated, label, group?, position?, d13C?}]
 * opts.curves:  [{name, label, color, dash, xs:[], ys:[]}]
 * opts.markers: [{x, lo, hi, color, label}]  vertical milestone lines with CI bands
 * opts.xRange:  [min, max] zoom window (optional)
 * opts.positionAxis: true to label the top axis in mm along the tooth
 * opts.showD13C: true to overlay δ13C on a right-hand axis
 * opts.onZoom(range|null): called after a drag-zoom or reset
 */
export function curveChart(container, opts) {
  const W = 760, H = 440;
  const right = opts.showD13C ? 58 : 20;
  const top = opts.positionAxis ? 44 : 16;
  const { svg, plot, id } = frame(container, W, H, { l: 64, r: right, t: top, b: 56 }, opts.title, opts.desc);
  const tip = tooltip(container);

  let allX = [...opts.points.flatMap((p) => [p.x, p.xMin ?? p.x, p.xMax ?? p.x]), ...opts.curves.flatMap((c) => c.xs)];
  // Markers are not used for the axis range, so one wild estimate cannot squash the data.
  allX = allX.filter(isFinite);
  let [xMin, xMax] = opts.xRange || [Math.min(...allX), Math.max(...allX)];
  const inX = (x) => x >= xMin && x <= xMax;
  const visY = [...opts.points.filter((p) => inX(p.x)).map((p) => p.y), ...opts.curves.flatMap((c) => c.ys.filter((_, i) => inX(c.xs[i])))];
  let [yMin, yMax] = [Math.min(...visY), Math.max(...visY)];
  const padY = (yMax - yMin) * 0.08 || 0.5;
  yMin -= padY;
  yMax += padY;
  const xTicks = niceTicks(xMin, xMax);
  const yTicks = niceTicks(yMin, yMax, 5);
  if (!opts.xRange) {
    xMin = Math.min(xMin, xTicks[0] ?? xMin);
    xMax = Math.max(xMax, xTicks.at(-1) ?? xMax);
  }
  yMin = Math.min(yMin, yTicks[0] ?? yMin);
  yMax = Math.max(yMax, yTicks.at(-1) ?? yMax);
  const xs = scale(xMin, xMax, plot.x0, plot.x1);
  const ys = scale(yMin, yMax, plot.y0, plot.y1);

  el("clipPath", { id: `${id}-clip` }, svg).appendChild(
    el("rect", { x: plot.x0, y: plot.y1, width: plot.x1 - plot.x0, height: plot.y0 - plot.y1 })
  );
  const axesG = el("g", { class: "axes" }, svg);
  leftAxis(axesG, plot, ys, yTicks, opts.yLabel);
  bottomAxis(axesG, plot, xs, xTicks.filter((t) => t >= xMin - 1e-9 && t <= xMax + 1e-9), opts.xLabel);

  // Top axis: position along the tooth (interpolated from the samples' own ages).
  if (opts.positionAxis) {
    const pts = opts.points.filter((p) => p.position != null).sort((a, b) => a.x - b.x);
    if (pts.length > 1) {
      const posTicks = niceTicks(Math.min(...pts.map((p) => p.position)), Math.max(...pts.map((p) => p.position)), 8);
      const ageAt = (pos) => {
        for (let i = 1; i < pts.length; i++) {
          const a = pts[i - 1], b = pts[i];
          if (pos >= Math.min(a.position, b.position) && pos <= Math.max(a.position, b.position) && b.position !== a.position) {
            return a.x + ((pos - a.position) / (b.position - a.position)) * (b.x - a.x);
          }
        }
        return null;
      };
      el("line", { x1: plot.x0, x2: plot.x1, y1: plot.y1, y2: plot.y1, class: "axis" }, axesG);
      for (const t of posTicks) {
        const age = ageAt(t);
        if (age == null || !inX(age)) continue;
        el("line", { x1: xs(age), x2: xs(age), y1: plot.y1, y2: plot.y1 - 5, class: "tick" }, axesG);
        el("text", { x: xs(age), y: plot.y1 - 9, "text-anchor": "middle" }, axesG).textContent = fmt(t);
      }
      el("text", { x: (plot.x0 + plot.x1) / 2, y: 13, "text-anchor": "middle", class: "label" }, axesG)
        .textContent = "Position from cusp apex (mm)";
    }
  }

  const layer = el("g", { "clip-path": `url(#${id}-clip)` }, svg);
  for (const m of opts.markers) {
    if (m.lo != null && m.hi != null) {
      el("rect", {
        x: xs(m.lo), y: plot.y1, width: Math.max(xs(m.hi) - xs(m.lo), 1), height: plot.y0 - plot.y1,
        fill: m.color, opacity: 0.1,
      }, layer);
    }
    el("line", { x1: xs(m.x), x2: xs(m.x), y1: plot.y0, y2: plot.y1, stroke: m.color, "stroke-dasharray": "5 4", "stroke-width": 1.5 }, layer);
  }

  // δ13C overlay on its own right-hand axis.
  const c13 = opts.showD13C ? opts.points.filter((p) => p.d13C != null) : [];
  if (c13.length > 1) {
    const cv = c13.map((p) => p.d13C);
    const cTicks = niceTicks(Math.min(...cv) - 0.2, Math.max(...cv) + 0.2, 5);
    const cs = scale(cTicks[0], cTicks.at(-1), plot.y0, plot.y1);
    for (const t of cTicks) {
      el("text", { x: plot.x1 + 8, y: cs(t) + 4, class: "c13" }, axesG).textContent = fmt(t);
    }
    el("line", { x1: plot.x1, x2: plot.x1, y1: plot.y0, y2: plot.y1, class: "axis" }, axesG);
    const cy = (plot.y0 + plot.y1) / 2;
    el("text", { x: W - 10, y: cy, transform: `rotate(90 ${W - 10} ${cy})`, "text-anchor": "middle", class: "label c13" }, axesG)
      .textContent = "δ¹³C (‰ VPDB)";
    const sorted = [...c13].sort((a, b) => a.x - b.x);
    el("path", { d: sorted.map((p, i) => `${i ? "L" : "M"}${xs(p.x).toFixed(1)},${cs(p.d13C).toFixed(1)}`).join(""), class: "c13-line" }, layer);
    for (const p of sorted) marker("diamond", xs(p.x), cs(p.d13C), 3, { class: "c13-pt" }, layer);
  }

  for (const c of opts.curves) {
    const d = c.xs.map((x, i) => `${i ? "L" : "M"}${xs(x).toFixed(1)},${ys(c.ys[i]).toFixed(1)}`).join("");
    el("path", { d, fill: "none", stroke: c.color, "stroke-width": 2.5, "stroke-dasharray": c.dash || null, class: "curve" }, layer);
  }
  for (const p of opts.points) {
    if (p.xMin != null && p.xMax != null) {
      el("line", { x1: xs(p.xMin), x2: xs(p.xMax), y1: ys(p.y), y2: ys(p.y), class: "win" }, layer);
    }
  }
  const groups = [...new Set(opts.points.map((p) => p.group ?? ""))];
  for (const p of opts.points) {
    const shape = SHAPES[groups.indexOf(p.group ?? "") % SHAPES.length];
    const dot = marker(shape, xs(p.x), ys(p.y), 4.5, {
      class: p.used ? (p.extrapolated ? "pt pt-extra" : "pt") : "pt pt-excluded",
      tabindex: "-1",
    }, layer);
    dot.addEventListener("mouseenter", (ev) => {
      const rect = container.getBoundingClientRect();
      tip.show(p.label, ev.clientX - rect.left, ev.clientY - rect.top);
    });
    dot.addEventListener("mouseleave", () => tip.hide());
  }
  opts.markers.forEach((m, i) => {
    const off = m.x > xMax ? " →" : m.x < xMin ? " ←" : "";
    const x = Math.min(Math.max(xs(m.x) + 4, plot.x0 + 4), plot.x1 - 70);
    el("text", { x, y: plot.y1 + 14 + i * 16, fill: m.color, class: "marker-label" }, svg).textContent = m.label + off;
  });
  if (groups.length > 1) {
    groups.forEach((g, i) => {
      const x = plot.x0 + 12 + i * 70, y = plot.y0 - 12;
      marker(SHAPES[i % SHAPES.length], x, y, 4, { class: "pt" }, svg);
      el("text", { x: x + 9, y: y + 4, class: "legend-text" }, svg).textContent = g;
    });
  }

  // Drag across the plot to zoom into an age range; double-click to reset.
  if (opts.onZoom) {
    const sel = el("rect", { y: plot.y1, height: plot.y0 - plot.y1, class: "zoom-sel", visibility: "hidden" }, svg);
    const hit = el("rect", { x: plot.x0, y: plot.y1, width: plot.x1 - plot.x0, height: plot.y0 - plot.y1, class: "zoom-hit" });
    svg.insertBefore(hit, layer);
    const toX = (ev) => {
      const pt = svg.createSVGPoint();
      pt.x = ev.clientX;
      pt.y = ev.clientY;
      return Math.min(Math.max(pt.matrixTransform(svg.getScreenCTM().inverse()).x, plot.x0), plot.x1);
    };
    let start = null;
    hit.addEventListener("pointerdown", (ev) => {
      start = toX(ev);
      hit.setPointerCapture(ev.pointerId);
    });
    hit.addEventListener("pointermove", (ev) => {
      if (start == null) return;
      const x = toX(ev);
      sel.setAttribute("x", Math.min(start, x));
      sel.setAttribute("width", Math.abs(x - start));
      sel.setAttribute("visibility", "visible");
    });
    hit.addEventListener("pointerup", (ev) => {
      if (start == null) return;
      const x = toX(ev);
      const [a, b] = [xs.invert(Math.min(start, x)), xs.invert(Math.max(start, x))];
      start = null;
      sel.setAttribute("visibility", "hidden");
      if (Math.abs(xs(b) - xs(a)) > 8) opts.onZoom([a, b]);
    });
    svg.addEventListener("dblclick", () => opts.onZoom(null));
  }
  return svg;
}

/**
 * Forest plot: one row per group with an interval and individual specimen dots.
 * groups: [{label, mean, lo, hi, values:[{v, label}]}]
 */
export function forestChart(container, groups, xLabel, title) {
  const rowH = 36;
  const W = 760, H = 70 + rowH * Math.max(groups.length, 1);
  const desc = groups.map((g) => `${g.label}: mean ${isFinite(g.mean) ? g.mean.toFixed(1) : "n/a"}`).join("; ");
  const { svg, plot } = frame(container, W, H, { l: 190, r: 24, t: 10, b: 50 }, title || xLabel, desc);
  const tip = tooltip(container);
  const vals = groups.flatMap((g) => [g.lo, g.hi, g.mean, ...g.values.map((v) => v.v)]).filter(isFinite);
  if (!vals.length) return svg;
  const ticks = niceTicks(Math.min(...vals), Math.max(...vals));
  const xs = scale(Math.min(ticks[0], ...vals), Math.max(ticks.at(-1), ...vals), plot.x0, plot.x1);
  const yAt = (i) => plot.y1 + rowH * (i + 0.5);
  const g0 = el("g", { class: "axes" }, svg);
  bottomAxis(g0, plot, xs, ticks, xLabel);
  groups.forEach((g, i) => {
    const y = yAt(i);
    el("text", { x: plot.x0 - 10, y: y + 4, "text-anchor": "end", class: "row-label" }, svg).textContent = g.label;
    if (isFinite(g.lo) && isFinite(g.hi)) el("line", { x1: xs(g.lo), x2: xs(g.hi), y1: y, y2: y, class: "ci" }, svg);
    for (const v of g.values) {
      const dot = el("circle", { cx: xs(v.v), cy: y + 9, r: 3.5, class: "pt pt-small" }, svg);
      dot.addEventListener("mouseenter", (ev) => {
        const rect = container.getBoundingClientRect();
        tip.show(v.label, ev.clientX - rect.left, ev.clientY - rect.top);
      });
      dot.addEventListener("mouseleave", () => tip.hide());
    }
    if (isFinite(g.mean)) el("rect", { x: xs(g.mean) - 5, y: y - 5, width: 10, height: 10, class: "mean" }, svg);
  });
  return svg;
}

/**
 * Simple line chart with markers. series: [{name, color, dash, points:[{x, y}]}]
 */
export function lineChart(container, series, { xLabel, yLabel, title, yMin } = {}) {
  const W = 760, H = 360;
  const desc = series.map((s) => `${s.name}: ${s.points.map((p) => `${fmt(p.x)} → ${p.y == null ? "n/a" : fmt(p.y)}`).join(", ")}`).join("; ");
  const { svg, plot } = frame(container, W, H, { l: 64, r: 130, t: 16, b: 56 }, title, desc);
  const pts = series.flatMap((s) => s.points).filter((p) => p.y != null && isFinite(p.y));
  if (!pts.length) return svg;
  const xt = niceTicks(Math.min(...pts.map((p) => p.x)), Math.max(...pts.map((p) => p.x)), 6);
  const yt = niceTicks(yMin ?? Math.min(...pts.map((p) => p.y)), Math.max(...pts.map((p) => p.y)), 5);
  const xs = scale(xt[0], xt.at(-1), plot.x0, plot.x1);
  const ys = scale(yt[0], yt.at(-1), plot.y0, plot.y1);
  const g = el("g", { class: "axes" }, svg);
  leftAxis(g, plot, ys, yt, yLabel);
  bottomAxis(g, plot, xs, xt, xLabel);
  series.forEach((s, i) => {
    const ok = s.points.filter((p) => p.y != null && isFinite(p.y));
    el("path", { d: ok.map((p, j) => `${j ? "L" : "M"}${xs(p.x)},${ys(p.y)}`).join(""), fill: "none", stroke: s.color, "stroke-width": 2.2, "stroke-dasharray": s.dash || null }, svg);
    for (const p of ok) marker(SHAPES[i % SHAPES.length], xs(p.x), ys(p.y), 4, { fill: s.color }, svg);
    const ly = plot.y1 + 12 + i * 18;
    el("line", { x1: plot.x1 + 12, x2: plot.x1 + 34, y1: ly, y2: ly, stroke: s.color, "stroke-width": 2.2, "stroke-dasharray": s.dash || null }, svg);
    el("text", { x: plot.x1 + 40, y: ly + 4, class: "legend-text" }, svg).textContent = s.name;
  });
  return svg;
}

export function svgToBlob(svg) {
  return new Blob([svgMarkup(svg)], { type: "image/svg+xml" });
}

/** Standalone SVG markup with embedded styles (for downloads and reports). */
export function svgMarkup(svg) {
  const clone = svg.cloneNode(true);
  clone.setAttribute("xmlns", SVG_NS);
  clone.querySelectorAll(".zoom-hit, .zoom-sel").forEach((n) => n.remove());
  const style = document.createElementNS(SVG_NS, "style");
  style.textContent = `text{font:12px sans-serif;fill:#333}.grid{stroke:#e5e5e5}.axis,.tick{stroke:#555}
  .pt{fill:#222}.pt-excluded{fill:none;stroke:#c0392b;stroke-width:1.5}.pt-extra{fill:#888}.pt-small{fill:#0072B2;opacity:.65}
  .ci{stroke:#333;stroke-width:2}.mean{fill:#333}.label{font-weight:600}.win{stroke:#888;stroke-width:1.5;opacity:.55}
  .c13,.c13-pt{fill:#7a5c00}.c13-line{fill:none;stroke:#7a5c00;stroke-width:1.2;stroke-dasharray:2 3}`;
  clone.prepend(style);
  return new XMLSerializer().serializeToString(clone);
}
