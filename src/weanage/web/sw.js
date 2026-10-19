// Browser version only: keeps copies of the app and of Python (Pyodide) in the browser,
// so WeanAge still opens and works without an internet connection after the first visit.
//   * the app's own files: fetched fresh when online (so updates arrive), the copy when offline
//   * Python and its packages: these never change for a given version, so the copy is used first

const CACHE = "weanage";
const APP_FILES = []; // filled in by scripts/build_browser.py
const NEVER_CHANGE = ["https://cdn.jsdelivr.net/pyodide/", "https://files.pythonhosted.org/"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(APP_FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const fixed = NEVER_CHANGE.some((start) => event.request.url.startsWith(start));
  event.respondWith(fixed ? copyFirst(event.request) : internetFirst(event.request));
});

async function copyFirst(request) {
  const cache = await caches.open(CACHE);
  const copy = await cache.match(request);
  if (copy) return copy;
  const response = await fetch(request);
  if (response.ok || response.type === "opaque") cache.put(request, response.clone());
  return response;
}

async function internetFirst(request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (offline) {
    const copy = await cache.match(request, { ignoreSearch: true });
    if (copy) return copy;
    throw offline;
  }
}
