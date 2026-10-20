/* Undercurrent "Add to Home Screen" shortcut — shared across every
 * Undercurrent web app (see shared/undercurrent-web/README.md).
 *
 * Canonical copy lives in shared/undercurrent-web/. Apps get a copy via
 * shared/undercurrent-web/sync.sh; don't edit the app copies directly.
 *
 * Behavior:
 *   - Browsers with a real install prompt (Android, Chrome/Edge desktop):
 *     one-tap "Install app" button.
 *   - iPhone/iPad (any browser) and Safari on Mac: no programmatic install
 *     exists, so the button opens short step-by-step instructions.
 *   - Everything else (e.g. Firefox desktop): hidden.
 *   - Hidden once installed, and for 30 days after the user dismisses it.
 *
 * decideInstallMode() is pure so it can be unit tested with node --test.
 */
(function (root) {
  "use strict";

  var DISMISS_KEY = "uc-install-dismissed-at";
  var DISMISS_DAYS = 30;

  function isIOS(env) {
    var ua = env.userAgent || "";
    if (/iPhone|iPad|iPod/.test(ua)) return true;
    // iPadOS reports itself as a Mac; touch support gives it away.
    return /Macintosh/.test(ua) && (env.maxTouchPoints || 0) > 1;
  }

  function isMacSafari(env) {
    var ua = env.userAgent || "";
    return (
      /Macintosh/.test(ua) &&
      /Safari\//.test(ua) &&
      !/Chrome|Chromium|CriOS|Edg|Firefox|FxiOS|OPR/.test(ua) &&
      (env.maxTouchPoints || 0) <= 1
    );
  }

  /** Returns "hidden" | "prompt" | "ios-steps" | "mac-steps". */
  function decideInstallMode(env) {
    if (env.isStandalone || env.dismissed) return "hidden";
    if (isIOS(env)) return "ios-steps";
    if (isMacSafari(env)) return "mac-steps";
    if (env.hasPrompt) return "prompt";
    return "hidden";
  }

  /** Dismissed if a dismissal timestamp is younger than DISMISS_DAYS. */
  function isDismissed(storedValue, now) {
    var at = parseInt(storedValue, 10);
    if (!at) return false;
    return now - at < DISMISS_DAYS * 24 * 60 * 60 * 1000;
  }

  // ---- Browser wiring (skipped under Node tests) ----------------------

  function readStorage() {
    try { return root.localStorage.getItem(DISMISS_KEY); } catch (e) { return null; }
  }
  function writeStorage(value) {
    try { root.localStorage.setItem(DISMISS_KEY, value); } catch (e) { /* private mode etc. */ }
  }

  function isStandalone() {
    try {
      if (root.matchMedia && root.matchMedia("(display-mode: standalone)").matches) return true;
    } catch (e) { /* ignore */ }
    return root.navigator && root.navigator.standalone === true;
  }

  function init() {
    var doc = root.document;
    var bar = doc.getElementById("uc-install");
    if (!bar) return;
    var button = bar.querySelector("[data-uc-install-button]");
    var dismiss = bar.querySelector("[data-uc-install-dismiss]");
    var dialog = doc.getElementById("uc-install-steps");
    var deferredPrompt = null;

    function env() {
      return {
        isStandalone: isStandalone(),
        dismissed: isDismissed(readStorage(), Date.now()),
        hasPrompt: !!deferredPrompt,
        userAgent: root.navigator.userAgent,
        maxTouchPoints: root.navigator.maxTouchPoints,
      };
    }

    function render() {
      var mode = decideInstallMode(env());
      bar.hidden = mode === "hidden";
      bar.dataset.mode = mode;
      button.textContent = mode === "prompt" ? "Install app" : "Add to Home Screen";
      if (dialog) {
        var ios = dialog.querySelector("[data-uc-steps='ios']");
        var mac = dialog.querySelector("[data-uc-steps='mac']");
        if (ios) ios.hidden = mode !== "ios-steps";
        if (mac) mac.hidden = mode !== "mac-steps";
      }
    }

    root.addEventListener("beforeinstallprompt", function (event) {
      event.preventDefault();
      deferredPrompt = event;
      render();
    });

    root.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      bar.hidden = true;
    });

    button.addEventListener("click", function () {
      var mode = bar.dataset.mode;
      if (mode === "prompt" && deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () {
          deferredPrompt = null;
          render();
        });
      } else if (dialog && typeof dialog.showModal === "function") {
        dialog.showModal();
      }
    });

    dismiss.addEventListener("click", function () {
      writeStorage(String(Date.now()));
      bar.hidden = true;
    });

    if (dialog) {
      var close = dialog.querySelector("[data-uc-install-close]");
      if (close) close.addEventListener("click", function () { dialog.close(); });
    }

    if ("serviceWorker" in root.navigator) {
      root.navigator.serviceWorker.register("/sw.js").catch(function () { /* non-fatal */ });
    }

    render();
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { decideInstallMode: decideInstallMode, isDismissed: isDismissed };
  } else if (root.document) {
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
