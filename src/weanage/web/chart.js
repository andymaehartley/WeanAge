// Dependency-free SVG charts: a weaning-curve plot and a group "forest" plot.

const SVG_NS = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}, parent) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

function niceTicks(min, max, count = 6) {
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
  return (v) => r0 + (v - d0) * k;
}

function fmt(v) {
  return Math.abs(v) >= 100 ? v.toFixed(0) : +v.toFixed(2) + "";
}

function tooltip(container) {
  let tip = container.querySelector(".chart-tip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "chart-tip";
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

function frame(container, width, height, margin) {
  container.querySelectorAll("svg").forEach((s) => s.remove());
  const svg = el("svg", {
    viewBox: `0 0 ${width} ${height}`,
    class: "chart",
    role: "img",
    preserveAspectRatio: "xMidYMid meet",
  });
  container.prepend(svg);
  const plot = { x0: margin.l, x1: width - margin.r, y0: height - margin.b, y1: margin.t };
  return { svg, plot };
}

function axes(svg, plot, xs, ys, xTicks, yTicks, xLabel, yLabel) {
  const g = el("g", { class: "axes" }, svg);
  for (const t of yTicks) {
    el("line", { x1: plot.x0, x2: plot.x1, y1: ys(t), y2: ys(t), class: "grid" }, g);
    el("text", { x: plot.x0 - 8, y: ys(t) + 4, "text-anchor": "end" }, g).textContent = fmt(t);
  }
  for (const t of xTicks) {
    el("line", { x1: xs(t), x2: xs(t), y1: plot.y0, y2: plot.y0 + 5, class: "tick" }, g);
    el("text", { x: xs(t), y: plot.y0 + 20, "text-anchor": "middle" }, g).textContent = fmt(t);
  }
  el("line", { x1: plot.x0, x2: plot.x1, y1: plot.y0, y2: plot.y0, class: "axis" }, g);
  el("line", { x1: plot.x0, x2: plot.x0, y1: plot.y0, y2: plot.y1, class: "axis" }, g);
  el("text", { x: (plot.x0 + plot.x1) / 2, y: plot.y0 + 42, "text-anchor": "middle", class: "label" }, g)
    .textContent = xLabel;
  if (yLabel) {
    const cy = (plot.y0 + plot.y1) / 2;
    el("text", { x: 18, y: cy, transform: `rotate(-90 18 ${cy})`, "text-anchor": "middle", class: "label" }, g)
      .textContent = yLabel;
  }
}

/**
 * Weaning curve plot.
 * opts.points:  [{x, y, xMin?, xMax?, used, extrapolated, label}]
 * opts.curves:  [{name, color, xs:[], ys:[]}]
 * opts.markers: [{x, lo, hi, color, label}]  vertical milestone lines with CI bands
 */
export function curveChart(container, opts) {
  const W = 760, H = 420;
  const { svg, plot } = frame(container, W, H, { l: 64, r: 20, t: 16, b: 56 });
  const tip = tooltip(container);

  const allX = [...opts.points.flatMap((p) => [p.x, p.xMin ?? p.x, p.xMax ?? p.x]), ...opts.curves.flatMap((c) => c.xs)];
  const allY = [...opts.points.map((p) => p.y), ...opts.curves.flatMap((c) => c.ys)];
  for (const m of opts.markers) allX.push(m.x);
  let [xMin, xMax] = [Math.min(...allX), Math.max(...allX)];
  let [yMin, yMax] = [Math.min(...allY), Math.max(...allY)];
  const padY = (yMax - yMin) * 0.08 || 0.5;
  yMin -= padY;
  yMax += padY;
  const xTicks = niceTicks(xMin, xMax);
  const yTicks = niceTicks(yMin, yMax, 5);
  xMin = Math.min(xMin, xTicks[0] ?? xMin);
  xMax = Math.max(xMax, xTicks.at(-1) ?? xMax);
  yMin = Math.min(yMin, yTicks[0] ?? yMin);
  yMax = Math.max(yMax, yTicks.at(-1) ?? yMax);
  const xs = scale(xMin, xMax, plot.x0, plot.x1);
  const ys = scale(yMin, yMax, plot.y0, plot.y1);

  el("clipPath", { id: "plot-clip" }, svg).appendChild(
    el("rect", { x: plot.x0, y: plot.y1, width: plot.x1 - plot.x0, height: plot.y0 - plot.y1 })
  );
  axes(svg, plot, xs, ys, xTicks, yTicks, opts.xLabel, opts.yLabel);
  const layer = el("g", { "clip-path": "url(#plot-clip)" }, svg);

  for (const m of opts.markers) {
    if (m.lo != null && m.hi != null) {
      el("rect", {
        x: xs(m.lo), y: plot.y1, width: Math.max(xs(m.hi) - xs(m.lo), 1), height: plot.y0 - plot.y1,
        fill: m.color, opacity: 0.1,
      }, layer);
    }
    el("line", {
      x1: xs(m.x), x2: xs(m.x), y1: plot.y0, y2: plot.y1, stroke: m.color,
      "stroke-dasharray": "5 4", "stroke-width": 1.5,
    }, layer);
  }

  for (const c of opts.curves) {
    const d = c.xs.map((x, i) => `${i ? "L" : "M"}${xs(x).toFixed(1)},${ys(c.ys[i]).toFixed(1)}`).join("");
    el("path", { d, fill: "none", stroke: c.color, "stroke-width": 2.5, class: "curve" }, layer);
  }

  for (const p of opts.points) {
    if (p.xMin != null && p.xMax != null) {
      el("line", { x1: xs(p.xMin), x2: xs(p.xMax), y1: ys(p.y), y2: ys(p.y), class: "win" }, layer);
    }
  }
  for (const p of opts.points) {
    const dot = el("circle", {
      cx: xs(p.x), cy: ys(p.y), r: 4.5,
      class: p.used ? (p.extrapolated ? "pt pt-extra" : "pt") : "pt pt-excluded",
    }, layer);
    dot.addEventListener("mouseenter", (ev) => {
      const rect = container.getBoundingClientRect();
      tip.show(p.label, ev.clientX - rect.left, ev.clientY - rect.top);
    });
    dot.addEventListener("mouseleave", () => tip.hide());
  }

  // Marker labels drawn last so they sit above the data.
  opts.markers.forEach((m, i) => {
    el("text", {
      x: xs(m.x) + 4, y: plot.y1 + 14 + i * 16, fill: m.color, class: "marker-label",
    }, svg).textContent = m.label;
  });
  return svg;
}

/**
 * Forest plot: one row per group with mean ± 95 % CI and individual specimen dots.
 * groups: [{label, mean, lo, hi, values:[{v, label}]}]
 */
export function forestChart(container, groups, xLabel) {
  const rowH = 36;
  const W = 760, H = 70 + rowH * Math.max(groups.length, 1);
  const { svg, plot } = frame(container, W, H, { l: 190, r: 24, t: 10, b: 50 });
  const tip = tooltip(container);
  const vals = groups.flatMap((g) => [g.lo, g.hi, g.mean, ...g.values.map((v) => v.v)]).filter(isFinite);
  if (!vals.length) return svg;
  const ticks = niceTicks(Math.min(...vals), Math.max(...vals));
  const xs = scale(Math.min(ticks[0], ...vals), Math.max(ticks.at(-1), ...vals), plot.x0, plot.x1);
  const yAt = (i) => plot.y1 + rowH * (i + 0.5);
  axes(svg, plot, xs, () => 0, ticks, [], xLabel, "");
  svg.querySelectorAll(".axes .grid").forEach((n) => n.remove());

  groups.forEach((g, i) => {
    const y = yAt(i);
    el("text", { x: plot.x0 - 10, y: y + 4, "text-anchor": "end", class: "row-label" }, svg).textContent = g.label;
    if (isFinite(g.lo) && isFinite(g.hi)) {
      el("line", { x1: xs(g.lo), x2: xs(g.hi), y1: y, y2: y, class: "ci" }, svg);
    }
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

export function svgToBlob(svg) {
  const clone = svg.cloneNode(true);
  clone.setAttribute("xmlns", SVG_NS);
  const style = document.createElementNS(SVG_NS, "style");
  style.textContent = `text{font:12px sans-serif;fill:#333}.grid{stroke:#e5e5e5}.axis,.tick{stroke:#555}
  .pt{fill:#222}.pt-excluded{fill:none;stroke:#c0392b;stroke-width:1.5}.pt-extra{fill:#888}
  .ci{stroke:#333;stroke-width:2}.mean{fill:#333}.label{font-weight:600}`;
  clone.prepend(style);
  return new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml" });
}
