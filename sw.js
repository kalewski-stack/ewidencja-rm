/* Ewidencja RM — service worker. Trzyma powłokę aplikacji w pamięci, żeby ikona otwierała się od razu.
   Dane zawsze idą do arkusza przez sieć. Po zmianie plików podbij WERSJA. */
const WERSJA = 'ewidencja-rm-v21';
const POWLOKA = ['./', './index.html', './manifest.webmanifest', './ikony/icon-192.png', './ikony/icon-512.png',
                 './ikony/apple-touch-icon.png', './logo-ciemne-tlo.png', './logo-jasne-tlo.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(WERSJA).then(function (c) { return c.addAll(POWLOKA); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== WERSJA; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;                       // API (POST) zawsze przez sieć
  if (url.origin !== self.location.origin) {
    // fonty Google: sieć, a w razie braku sieci to, co już było
    if (/fonts\.(googleapis|gstatic)\.com$/.test(url.hostname)) {
      e.respondWith(caches.open(WERSJA).then(function (c) {
        return fetch(e.request).then(function (r) { c.put(e.request, r.clone()); return r; })
          .catch(function () { return c.match(e.request); });
      }));
    }
    return;
  }
  // powłoka: najpierw sieć (świeża wersja), w razie braku sieci pamięć
  e.respondWith(fetch(e.request).then(function (r) {
    const kopia = r.clone();
    caches.open(WERSJA).then(function (c) { c.put(e.request, kopia); });
    return r;
  }).catch(function () {
    return caches.match(e.request).then(function (r) { return r || caches.match('./index.html'); });
  }));
});
