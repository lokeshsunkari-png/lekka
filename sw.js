/* Lekka service worker: app works fully offline; agents' data refreshes when online. */
const VER = "lekka-v1";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icons/icon-192.png", "./icons/icon-512.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(VER).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VER && !k.startsWith("lekka-data")).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  const isData = /\/data\/[^/]+\.(json|csv)$/.test(u.pathname);
  if (isData) {               // network first, fall back to last copy
    e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open("lekka-data").then(x => x.put(e.request, c)); return r; })
      .catch(() => caches.match(e.request)));
    return;
  }
  if (u.origin === location.origin || /fonts\.(googleapis|gstatic)\.com|gstatic\.com\/firebasejs/.test(u.host + u.pathname)) {
    e.respondWith(caches.match(e.request).then(hit => {   // cache first, update in background
      const net = fetch(e.request).then(r => { if (r.ok || r.type === "opaque") { const c = r.clone(); caches.open(VER).then(x => x.put(e.request, c)); } return r; }).catch(() => hit);
      return hit || net;
    }));
  }
});
/* Background agent check (Chrome Android, installed app): notify on new market alerts */
async function checkAlerts() {
  const cfg = await caches.open("lekka-data").then(c => c.match("lekka-config")).then(r => r ? r.json() : null).catch(() => null);
  if (!cfg || !cfg.dataUrl) return;
  try {
    const r = await fetch(cfg.dataUrl + "market.json", { cache: "no-store" }); const d = await r.json();
    const seenRes = await caches.open("lekka-data").then(c => c.match("lekka-seen")); const seen = seenRes ? await seenRes.json() : [];
    const fresh = (d.alerts || []).filter(a => !seen.includes(a.id));
    for (const a of fresh.slice(0, 3)) await self.registration.showNotification("Lekka · " + a.title, { body: a.body, icon: "icons/icon-192.png", badge: "icons/icon-192.png", tag: a.id });
    await caches.open("lekka-data").then(c => c.put("lekka-seen", new Response(JSON.stringify(seen.concat(fresh.map(a => a.id)).slice(-200)))));
  } catch (e) {}
}
self.addEventListener("periodicsync", e => { if (e.tag === "lekka-agents") e.waitUntil(checkAlerts()); });
self.addEventListener("message", e => { if (e.data === "check-alerts") e.waitUntil(checkAlerts()); });
self.addEventListener("notificationclick", e => { e.notification.close(); e.waitUntil(clients.openWindow("./#grow")); });
