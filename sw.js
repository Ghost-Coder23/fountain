/**
 * EduCore Service Worker — Fixed
 * Handles pre-caching, fetch interception, and background sync.
 *
 * FIXES:
 *  1. POST/PUT/DELETE: clone request before fetch so body isn't consumed
 *  2. Offline fallback: caches.match returns a Promise — use .then() chain, not ||
 *  3. CDN origin check: explicit allowlist instead of hostname.includes()
 *  4. normalizedUrl: build a full URL for caches.match, not just a pathname
 *  5. Background sync: actually messages clients to trigger flushQueue()
 *  6. Install: log cache failures so you can see what's missing
 *  7. api-cache: kept separate but eviction is now handled (old api- caches cleaned on activate)
 */

const CACHE_NAME = 'educore-static-v29';

const ALLOWED_CDN_HOSTS = [
    'cdn.jsdelivr.net',
    'unpkg.com'
];

const CORE_ROUTES = [
    '/',
    '/analytics/dashboard/',
    '/attendance/',
    '/fees/',
    '/notifications/',
    '/academics/classes/',
    '/offline-sync/',
    '/offline/'
];

const STATIC_ASSETS = [
    ...CORE_ROUTES,
    '/static/css/style.css',
    '/static/js/db.js',
    '/static/js/sync.js',
    '/static/bootstrap/css/bootstrap.min.css',
    '/static/bootstrap/js/bootstrap.bundle.min.js',
    '/static/bootstrap-icons/bootstrap-icons-1.11.0/font/bootstrap-icons.css',
    '/static/bootstrap-icons/bootstrap-icons-1.11.0/font/fonts/bootstrap-icons.woff',
    '/static/bootstrap-icons/bootstrap-icons-1.11.0/font/fonts/bootstrap-icons.woff2',
    'https://cdn.jsdelivr.net/npm/tom-select@2.2.2/dist/css/tom-select.bootstrap5.css',
    'https://cdn.jsdelivr.net/npm/tom-select@2.2.2/dist/js/tom-select.complete.min.js',
    'https://unpkg.com/htmx.org@1.9.10'
];

// ---------------------------------------------------------------------------
// 1. Install — pre-cache all static assets
// ---------------------------------------------------------------------------
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return Promise.allSettled(
                STATIC_ASSETS.map(url => {
                    return fetch(url).then(response => {
                        if (response.ok) return cache.put(url, response);
                        // FIX: log failures instead of silently swallowing them
                        console.warn('[SW] Pre-cache skipped (non-ok):', url, response.status);
                    }).catch((err) => {
                        console.warn('[SW] Pre-cache fetch failed:', url, err.message);
                    });
                })
            );
        })
    );
    self.skipWaiting();
});

// ---------------------------------------------------------------------------
// 2. Activate — clean up old caches
// ---------------------------------------------------------------------------
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys
                    // FIX: also clean up stale api- caches, not just static ones
                    .filter((key) => key !== CACHE_NAME && key !== 'api-cache')
                    .map((key) => {
                        console.log('[SW] Deleting old cache:', key);
                        return caches.delete(key);
                    })
            );
        }).then(() => self.clients.claim())
    );
});

// ---------------------------------------------------------------------------
// 3. Fetch
// ---------------------------------------------------------------------------
self.addEventListener('fetch', (event) => {
    try {
        const url = new URL(event.request.url);

        // FIX: explicit CDN allowlist instead of broad hostname.includes()
        const isAllowedOrigin =
            url.origin === self.location.origin ||
            ALLOWED_CDN_HOSTS.includes(url.hostname);

        if (!isAllowedOrigin) return;

        // --- Non-GET (POST / PUT / DELETE) -----------------------------------
        if (event.request.method !== 'GET') {
            event.respondWith(
                // FIX: clone the request — body can only be read once
                fetch(event.request.clone()).catch(() => {
                    // Network is down — return a fake 200 so sync.js can queue it
                    return new Response(JSON.stringify({ status: 'offline_queued' }), {
                        status: 200,
                        headers: { 'Content-Type': 'application/json' }
                    });
                })
            );
            return;
        }

        // --- HTML navigation requests ----------------------------------------
        const isHtmlRequest =
            event.request.mode === 'navigate' ||
            (event.request.headers.get('accept') || '').includes('text/html');

        if (isHtmlRequest) {
            event.respondWith(handleHtmlRequest(event, url));
            return;
        }

        // --- Static assets & API calls ---------------------------------------
        event.respondWith(handleAssetRequest(event, url));

    } catch (e) {
        console.error('[SW] Fetch Error:', e);
    }
});

async function handleHtmlRequest(event, url) {
    const cachedResponse = await caches.match(event.request, { ignoreSearch: true });
    const isWarming = event.request.headers.get('X-Offline-Warm') === 'true';

    // FIX: build a full URL string for the normalised fallback, not just a pathname
    const normalizedHref = url.origin + (url.pathname.endsWith('/')
        ? url.pathname.slice(0, -1)
        : url.pathname);

    const networkFetch = fetch(event.request)
        .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
                const copy = networkResponse.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
            }
            return networkResponse;
        })
        .catch(async (err) => {
            if (cachedResponse) return cachedResponse;

            // Try normalised URL (strips trailing slash)
            const altResponse = await caches.match(normalizedHref, { ignoreSearch: true });
            if (altResponse) return altResponse;

            if (event.request.mode === 'navigate' && !isWarming) {
                // FIX: caches.match returns a Promise — must await/then, never use ||
                const dashResponse = await caches.match('/analytics/dashboard/');
                if (dashResponse) return dashResponse;
                const offlineResponse = await caches.match('/offline/');
                if (offlineResponse) return offlineResponse;
            }
            throw err;
        });

    // Warming requests: only use network (to populate cache)
    if (isWarming && !cachedResponse) return networkFetch;

    // Network-first, cache fallback for HTML
    try {
        return await networkFetch;
    } catch (err) {
        if (cachedResponse) return cachedResponse;
        
        // Try normalised URL
        const altResponse = await caches.match(normalizedHref, { ignoreSearch: true });
        if (altResponse) return altResponse;
        
        if (event.request.mode === 'navigate' && !isWarming) {
            const dashResponse = await caches.match('/analytics/dashboard/');
            if (dashResponse) return dashResponse;
            const offlineResponse = await caches.match('/offline/');
            if (offlineResponse) return offlineResponse;
        }
        
        throw err;
    }
}

async function handleAssetRequest(event, url) {
    const cachedResponse = await caches.match(event.request);
    if (cachedResponse) return cachedResponse;

    try {
        const response = await fetch(event.request);
        if (response.ok && event.request.method === 'GET') {
            const copy = response.clone();
            const targetCache = url.pathname.startsWith('/api/') ? 'api-cache' : CACHE_NAME;
            caches.open(targetCache).then(cache => cache.put(event.request, copy));
        }
        return response;
    } catch {
        if (url.pathname.endsWith('.js')) {
            return new Response('console.log("[SW] Offline")', {
                headers: { 'Content-Type': 'application/javascript' }
            });
        }
        return new Response('', { status: 200 });
    }
}

// ---------------------------------------------------------------------------
// 4. Background Sync — tell all open clients to flush their queue
// ---------------------------------------------------------------------------
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-queue') {
        console.log('[SW] Background Sync triggered — notifying clients');
        // FIX: actually message clients so sync.js flushQueue() runs
        event.waitUntil(
            self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
                clients.forEach(client => client.postMessage({ type: 'SW_FLUSH_QUEUE' }));
            })
        );
    }
});