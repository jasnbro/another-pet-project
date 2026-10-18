/* Undercurrent minimal service worker (shared; see README.md).
 *
 * Exists only so browsers treat the app as installable. It deliberately
 * caches nothing and has no fetch handler: every request goes straight
 * to the network, so the app never shows stale data.
 */
self.addEventListener("install", function () {
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});
