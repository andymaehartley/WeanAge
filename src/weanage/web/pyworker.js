// Browser version only: runs WeanAge's Python code inside the web page, using Pyodide
// (Python compiled for the browser). It runs in a background "worker" so the page
// stays responsive during long analyses. api.js sends it requests by name.

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/";
const SAVED_TABLES = "/home/pyodide/.weanage"; // kept in the browser's own storage (IndexedDB)
let downloadFailed = false;
try {
  importScripts(PYODIDE + "pyodide.js");
} catch {
  downloadFailed = true; // reported when the first request arrives
}

const status = (text) => postMessage({ status: text });
let pyodide = null;

// Copy saved files between Python's folder and the browser's storage.
// load = true: storage -> Python (at start). load = false: Python -> storage (after saving).
const syncFiles = (load) => new Promise((resolve) => pyodide.FS.syncfs(load, resolve));

async function start() {
  if (downloadFailed) throw new Error("could not download Python from cdn.jsdelivr.net. Check the internet connection and reload the page");
  status("Downloading the analysis engine (about 40 MB; your browser keeps it for next time)…");
  pyodide = await loadPyodide({ indexURL: PYODIDE });
  status("Loading numpy, scipy and pandas…");
  await pyodide.loadPackage(["numpy", "scipy", "pandas", "pydantic", "micropip"]);
  status("Loading WeanAge…");
  const code = await (await fetch("weanage.zip")).arrayBuffer();
  pyodide.unpackArchive(code, "zip", { extractDir: "/home/pyodide/lib" });
  pyodide.FS.mkdirTree(SAVED_TABLES);
  pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, SAVED_TABLES);
  await syncFiles(true);
  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/home/pyodide/lib")
import micropip
try:
    await micropip.install("openpyxl")  # only needed for Excel files
except Exception as err:
    print("Excel support not available:", err)
`);
  return pyodide.pyimport("weanage.browser");
}

let ready = null; // started by the first request

// Each message: { id, name, request, content? }. Replies: progress updates, then { id, ok, result | error }.
self.onmessage = async ({ data }) => {
  const { id, name, request, content } = data;
  try {
    ready ??= start().finally(() => status(null));
    const weanage = await ready;
    const progress = (done, total) => postMessage({ id, progress: [done, total] });
    const answer = JSON.parse(weanage.call(name, JSON.stringify(request ?? {}), progress, content));
    if (name === "save_table" || name === "delete_table") await syncFiles(false);
    postMessage({ id, ...answer });
  } catch (err) {
    postMessage({ id, ok: false, error: `the analysis engine failed: ${err.message || err}` });
  }
};
