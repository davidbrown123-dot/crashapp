// frontend/service-worker.js
const CACHE_NAME = 'crash-app-cache-v1';
// Define assets served by FastAPI static routes
const urlsToCache = [
  '/webapp', // The main HTML route
  '/static/style.css',
  '/static/webapp_script.js',
  '/static/manifest.json', // Cache the manifest too
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

self.addEventListener('install', (event) => {
  console.log('[SW] Install');
  // Optional: Pre-cache assets for offline use
  // event.waitUntil(
  //   caches.open(CACHE_NAME).then((cache) => {
  //     console.log('[SW] Caching app shell');
  //     return cache.addAll(urlsToCache);
  //   })
  // );
  self.skipWaiting(); // Activate immediately
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Activate');
  // Optional: Clean up old caches
  // event.waitUntil(caches.keys().then(/* ... */));
  return self.clients.claim(); // Take control immediately
});

self.addEventListener('fetch', (event) => {
  // console.log('[SW] Fetch:', event.request.url);
  // Basic network-first strategy (adapt later if offline needed)
  event.respondWith(fetch(event.request));
});