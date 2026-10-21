// The About panel (citation, licences, acknowledgements) and the tooth guide.
//
// The tooth guide shows a real reference figure (not drawn by us): Gray's Anatomy (1918),
// Fig. 1005, public domain. scripts/fetch_tooth_figure.py downloads it from Wikimedia Commons
// with its licence details into figures/tooth.json, which says `available: false` until then.
// That file can also list `labels`: WeanAge terms placed over the figure, at x/y given as %
// of the image width/height.
import { $ } from "./util.js";

const MANIFEST = "figures/tooth.json";
const RELEASE_YEAR = 2026;

export const citation = (version) =>
  `Hartley, A. (${RELEASE_YEAR}). WeanAge: weaning-age estimation from incremental dentine δ15N ` +
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
    for (const label of credit.labels || []) {
      const tag = document.createElement("span");
      tag.className = "figure-label";
      tag.textContent = label.text;
      tag.style.left = `${label.x}%`;
      tag.style.top = `${label.y}%`;
      wrap.appendChild(tag);
    }
  };
  const text = `${credit.title}. ${credit.author}. ${credit.licence}. Source: ${credit.source_url}`;
  $("#tooth-caption").textContent = `${credit.caption || ""} ${text}`.trim();
  $("#about-figure-credit").textContent = text;
}
