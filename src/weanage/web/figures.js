// Publication figures: every chart can be downloaded as SVG or PNG, redrawn in the light colours on
// white with a caption underneath, and its caption copied for the figure legend.
import { download, toast } from "./util.js";

const STYLES = ["fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-opacity", "fill-opacity", "opacity",
  "font-family", "font-size", "font-weight", "font-style", "paint-order", "text-anchor", "dominant-baseline"];
const TOOLS = `<div class="figure-tools"><span class="muted small">Figure:</span>
  <button type="button" class="link small" data-figure="svg">SVG</button>
  <button type="button" class="link small" data-figure="png">PNG</button>
  <button type="button" class="link small" data-figure="caption">copy caption</button></div>`;
const PNG_SCALE = 4; // 760 px wide charts become ~3000 px: 300 dpi at a two-column width of about 25 cm

/**
 * Draw a chart into `box` and keep the drawing, so that it can be redrawn for export.
 * draw(box) must work out its colours when called (e.g. from color() or the default palette), so
 * that the export comes out in the light colours. caption: a sentence added after the chart title.
 */
export function figure(box, draw, { name, caption = "" } = {}) {
  const svg = draw(box);
  box.figure = { draw, name: name || box.id.replace(/-chart$/, ""), caption };
  if (!box.querySelector(":scope > .figure-tools")) box.insertAdjacentHTML("beforeend", TOOLS);
  return svg;
}

/** The figure's caption: the chart's title, then any extra sentence. */
function captionOf(svg, extra) {
  const title = svg.querySelector("title")?.textContent.trim() || "";
  return [title && `${title.replace(/[.:]\s*$/, "")}.`, extra].filter(Boolean).join(" ");
}

/** Redraw the chart offscreen in the light theme and return standalone SVG markup with its caption. */
export function figureMarkup(box) {
  const root = document.documentElement;
  const was = root.dataset.theme;
  root.dataset.theme = "light";
  const off = Object.assign(document.createElement("div"), { style: "position:absolute;left:-9999px;top:0;width:760px" });
  document.body.appendChild(off);
  try {
    box.figure.draw(off);
    const svg = off.querySelector("svg.chart");
    if (!svg) return null;
    const caption = captionOf(svg, box.figure.caption);
    return { ...standalone(svg, caption), caption };
  } finally {
    off.remove();
    if (was == null) delete root.dataset.theme;
    else root.dataset.theme = was;
  }
}

function standalone(svg, caption) {
  const copy = svg.cloneNode(true);
  // Copy the computed (light-theme) styles onto the copy, so it looks the same outside the app.
  const from = [svg, ...svg.querySelectorAll("*")];
  const to = [copy, ...copy.querySelectorAll("*")];
  from.forEach((node, i) => {
    const style = getComputedStyle(node);
    to[i].setAttribute("style", STYLES.map((p) => `${p}:${style.getPropertyValue(p)}`).join(";"));
  });
  copy.querySelectorAll(".zoom-hit, .zoom-sel").forEach((n) => n.remove());
  const [, , width, height] = copy.getAttribute("viewBox").split(" ").map(Number);
  const lines = wrap(caption, 112);
  const total = height + 16 + lines.length * 18;
  const ns = copy.namespaceURI;
  const add = (tag, attrs, parent = copy) => {
    const n = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    parent.appendChild(n);
    return n;
  };
  copy.setAttribute("xmlns", ns);
  copy.setAttribute("viewBox", `0 0 ${width} ${total}`);
  copy.setAttribute("width", width);
  copy.setAttribute("height", total);
  copy.removeAttribute("class");
  const background = add("rect", { x: 0, y: 0, width, height: total, fill: "#ffffff" });
  copy.prepend(background);
  lines.forEach((line, i) => {
    add("text", { x: 12, y: height + 22 + i * 18, style: "font-family:sans-serif;font-size:13px;fill:#1a1815" }).textContent = line;
  });
  return { markup: new XMLSerializer().serializeToString(copy), width, height: total };
}

function wrap(text, size) {
  const lines = [];
  let line = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    if (line && (line + " " + word).length > size) {
      lines.push(line);
      line = word;
    } else line = line ? `${line} ${word}` : word;
  }
  return line ? [...lines, line] : lines;
}

async function png({ markup, width, height }) {
  const image = new Image();
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`;
  await image.decode();
  const canvas = Object.assign(document.createElement("canvas"), { width: width * PNG_SCALE, height: height * PNG_SCALE });
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

export function initFigures() {
  document.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-figure]");
    const box = button?.closest(".figure-tools")?.parentElement;
    if (!box?.figure) return;
    const out = figureMarkup(box);
    if (!out) return toast("There is no chart to export.");
    const file = `weanage_${box.figure.name}`;
    try {
      if (button.dataset.figure === "svg") download(`${file}.svg`, new Blob([out.markup], { type: "image/svg+xml" }));
      if (button.dataset.figure === "png") download(`${file}.png`, await png(out));
      if (button.dataset.figure === "caption") {
        await navigator.clipboard.writeText(out.caption);
        toast("Caption copied.", "ok");
      }
    } catch (err) {
      toast(`Could not export the figure: ${err.message}`);
    }
  });
}
