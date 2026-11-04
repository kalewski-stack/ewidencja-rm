/* Strych — service worker. Trzyma powłokę aplikacji w pamięci, żeby ikona otwierała się od razu (także na strychu bez zasięgu).
   Dane zawsze idą do arkusza przez sieć. Po zmianie plików podbij WERSJA. */
const WERSJA = 'strych-v2';
const POWLOKA = ['./', './index.html', './qrcode.js', './manifest.webmanifest', './ikony/icon-192.png', './ikony/icon-512.png', './ikony/apple-touch-icon.png'];

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
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;   // API i zdjęcia zawsze przez sieć
  // powłoka: najpierw sieć (świeża wersja), w razie braku sieci pamięć
  e.respondWith(fetch(e.request).then(function (r) {
    const kopia = r.clone();
    caches.open(WERSJA).then(function (c) { c.put(e.request, kopia); });
    return r;
  }).catch(function () {
    return caches.match(e.request).then(function (r) { return r || caches.match('./index.html'); });
  }));
});
