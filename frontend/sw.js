// AI Trip Planner - Service Worker for 100% Offline Access
const CACHE_NAME = 'trip-planner-v5';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/manifest.json',
  '/share.html',
  '/my-trips.html'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Network-First with Cache fallback for all assets & API
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.status === 200 && event.request.method === 'GET') {
          const respClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, respClone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
