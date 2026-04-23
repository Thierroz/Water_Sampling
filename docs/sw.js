// Minimal service worker — enables PWA install prompt
const CACHE = 'water-sampler-v2';
const ASSETS = ['./index.html', './manifest.json', './Neosens.png', './icon-192.png', './icon-512.png'];

self.addEventListener('install', e =>
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)))
);

self.addEventListener('fetch', e => {
  // Network-first for API calls, cache-first for app shell
  if (e.request.url.includes('api.existenz.ch')) {
    e.respondWith(fetch(e.request).catch(() => new Response('', { status: 503 })));
  } else {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request))
    );
  }
});
