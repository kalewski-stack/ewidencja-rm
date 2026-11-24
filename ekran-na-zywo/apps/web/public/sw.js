// Service worker ekranu głównego. Zakres: /screen. Po pierwszym załadowaniu ekran wstaje bez internetu.
const PREFIX = 'ekran-';
self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const m = await (await fetch('/sw-manifest.json', { cache: 'no-store' })).json();
    const cache = await caches.open(PREFIX + m.version);
    await Promise.all(m.files.map((f) => cache.add(new Request(f, { cache: 'reload' })).catch(() => null)));
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const m = await fetch('/sw-manifest.json', { cache: 'no-store' }).then((r) => r.json()).catch(() => null);
    if (m) for (const k of await caches.keys()) if (k.startsWith(PREFIX) && k !== PREFIX + m.version) await caches.delete(k);
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname === '/ws' || url.pathname === '/health') return;
  e.respondWith((async () => {
    const key = url.pathname === '/screen' ? '/screen' : e.request;
    try {
      const res = await fetch(e.request);
      if (res.ok) { const ks = await caches.keys(); const c = await caches.open(ks.filter((k) => k.startsWith(PREFIX)).sort().pop() || PREFIX + 'rt'); c.put(key, res.clone()); }
      return res;
    } catch (err) {
      const hit = await caches.match(key, { ignoreSearch: true });
      if (hit) return hit;
      throw err;
    }
  })());
});
