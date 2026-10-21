// The About panel (citation, licences, acknowledgements) and the tooth guide.
//
// The tooth guide shows a real, credited figure (not drawn by us): "Tooth Section" by
// Sam Fentress, Wikimedia Commons, CC BY-SA 2.0. figures/tooth.json holds its credit and the
// WeanAge `labels` drawn over it: x/y in % of the image, with an optional line `to` a point.
import { $ } from "./util.js";

const MANIFEST = "figures/tooth.json";
const RELEASE_YEAR = 2026;

export const citation = (version) =>
  `Hartley, A. (${RELEASE_YEAR}). WeanAge: weaning-age estimation from tooth dentine and bone collagen δ15N ` +
  `(version ${version}) [Computer software]. https://github.com/andymaehartley/repotest`;

export function initAbout(config) {
  $("#about-version").textContent = config.version;
  $("#about-citation").textContent = citation(config.version);
  $("#btn-about").addEventListener("click", () => $("#about-dialog").showModal());
  $("#btn-tooth").addEventListener("click", openToothGuide);
  $("#btn-copy-citation").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("#about-citation").textContent);
      $("#copy-msg").textContent = "Copied";
    } catch {
      getSelection().selectAllChildren($("#about-citation")); // copying refused: select it instead
      $("#copy-msg").textContent = "Selected: press Ctrl+C to copy";
    }
  });
  loadFigure();
}

function openToothGuide() {
  $("#tooth-dialog").showModal();
}

/** Show the reference figure if it has been downloaded; the list of terms works without it. */
async function loadFigure() {
  let credit;
  try {
    credit = await (await fetch(MANIFEST)).json();
  } catch {
    return;
  }
  if (!credit.available) return;
  const img = $("#tooth-img");
  img.src = `figures/${credit.file}`;
  img.onload = () => {
    $("#tooth-figure").hidden = false;
    const wrap = img.parentElement;
    const lines = (credit.labels || []).filter((l) => l.to).map((l) =>
      `<line x1="${l.x}" y1="${l.y + 2}" x2="${l.to[0]}" y2="${l.to[1]}" ${l.arrow ? 'marker-end="url(#arrow)"' : ""}/>`);
    wrap.insertAdjacentHTML("beforeend", `<svg class="figure-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto">
      <path d="M0 0 10 5 0 10z"/></marker></defs>${lines.join("")}</svg>`);
    for (const label of credit.labels || []) {
      const tag = document.createElement("span");
      tag.className = "figure-label";
      tag.textContent = label.text;
      tag.style.left = `${label.x}%`;
      tag.style.top = `${label.y}%`;
      wrap.appendChild(tag);
    }
  };
  const source = `<a href="${credit.source_url}" target="_blank" rel="noopener">Wikimedia Commons</a>`;
  const licence = `<a href="${credit.licence_url}" target="_blank" rel="noopener">${credit.licence}</a>`;
  const text = `“${credit.title}” by ${credit.author}, ${source}, ${licence}.`;
  $("#tooth-caption").innerHTML = `${credit.caption || ""} ${text}`;
  $("#about-figure-credit").innerHTML = text;
}
