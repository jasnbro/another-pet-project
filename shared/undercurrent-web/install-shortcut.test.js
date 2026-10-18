// Run with: node --test shared/undercurrent-web/install-shortcut.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { decideInstallMode, isDismissed } = require("./install-shortcut.js");

const UA = {
  iphoneSafari:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
  iphoneChrome:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/130.0.0.0 Mobile/15E148 Safari/604.1",
  ipadOS:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
  macSafari:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
  macChrome:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
  androidChrome:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
  windowsEdge:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
  firefoxDesktop: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
};

function env(overrides) {
  return { isStandalone: false, dismissed: false, hasPrompt: false, maxTouchPoints: 0, ...overrides };
}

test("iPhone Safari and iPhone Chrome get iOS steps", () => {
  assert.equal(decideInstallMode(env({ userAgent: UA.iphoneSafari, maxTouchPoints: 5 })), "ios-steps");
  assert.equal(decideInstallMode(env({ userAgent: UA.iphoneChrome, maxTouchPoints: 5 })), "ios-steps");
});

test("iPadOS (reports as Mac, but has touch) gets iOS steps", () => {
  assert.equal(decideInstallMode(env({ userAgent: UA.ipadOS, maxTouchPoints: 5 })), "ios-steps");
});

test("Safari on Mac gets Mac steps", () => {
  assert.equal(decideInstallMode(env({ userAgent: UA.macSafari })), "mac-steps");
});

test("Android Chrome and desktop Chrome/Edge show the one-tap prompt once available", () => {
  for (const ua of [UA.androidChrome, UA.macChrome, UA.windowsEdge]) {
    assert.equal(decideInstallMode(env({ userAgent: ua, hasPrompt: false })), "hidden", ua);
    assert.equal(decideInstallMode(env({ userAgent: ua, hasPrompt: true })), "prompt", ua);
  }
});

test("Firefox desktop is hidden (no install support)", () => {
  assert.equal(decideInstallMode(env({ userAgent: UA.firefoxDesktop })), "hidden");
});

test("already installed or dismissed is always hidden", () => {
  for (const ua of Object.values(UA)) {
    assert.equal(decideInstallMode(env({ userAgent: ua, hasPrompt: true, isStandalone: true })), "hidden");
    assert.equal(decideInstallMode(env({ userAgent: ua, hasPrompt: true, dismissed: true })), "hidden");
  }
});

test("dismissal lasts 30 days", () => {
  const day = 24 * 60 * 60 * 1000;
  const now = 100 * day;
  assert.equal(isDismissed(null, now), false);
  assert.equal(isDismissed("garbage", now), false);
  assert.equal(isDismissed(String(now - 29 * day), now), true);
  assert.equal(isDismissed(String(now - 31 * day), now), false);
});
