// node --test gym_log/tests/*.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../app/static/js/logic.js");
const { icon } = require("../app/static/js/icons.js");

test("localISODate uses the local calendar day, not UTC", () => {
  // 11:30pm local on Nov 9 is Nov 10 in UTC west of Greenwich; must stay Nov 9.
  assert.equal(L.localISODate(new Date(2026, 10, 9, 23, 30)), "2026-11-09");
  assert.equal(L.localISODate(new Date(2027, 0, 1, 0, 5)), "2027-01-01");
});

test("addDays crosses month and year boundaries", () => {
  assert.equal(L.addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(L.addDays("2026-03-01", -1), "2026-02-28");
});

test("formatDate", () => {
  assert.equal(L.formatDate("2026-11-09"), "Mon, Nov 9");
  assert.equal(L.formatDate("2027-01-04", 2026), "Mon, Jan 4, 2027");
  assert.equal(L.formatDate("2026-11-09", 2026), "Mon, Nov 9");
});

test("formatSet per load type", () => {
  assert.equal(L.formatSet({ weight: 25, reps: 12 }, "db_single"), "25 × 12");
  assert.equal(L.formatSet({ weight: 22.5, reps: 10 }, "db_per_hand"), "22.5 × 10");
  assert.equal(L.formatSet({ weight: null, reps: 15 }, "bodyweight"), "15");
  assert.equal(L.formatSet({ reps: 30 }, "seconds"), "30 s");
  assert.equal(L.formatSet({ band: "red", reps: 12 }, "band"), "red × 12");
  assert.equal(L.formatSets([{ weight: 25, reps: 12 }, { weight: 25, reps: null }], "db_single"), "25 × 12, 25 × –");
});

test("formatRange", () => {
  assert.equal(L.formatRange([8, 12], "db_single"), "8–12");
  assert.equal(L.formatRange([8, 8], "bodyweight"), "8");
  assert.equal(L.formatRange([20, 30], "seconds"), "20–30 s");
});

test("rest timer counts toward a fixed end time", () => {
  const t0 = 1_000_000;
  const end = L.startTimer(t0, 90);
  assert.equal(L.formatClock(L.remainingMs(end, t0)), "1:30");
  // The tab was frozen for 60 s (iPad locked): remaining is still right.
  assert.equal(L.formatClock(L.remainingMs(end, t0 + 60_000)), "0:30");
  assert.equal(L.remainingMs(end, t0 + 200_000), 0);
  assert.equal(L.formatClock(L.remainingMs(end, t0 + 89_100)), "0:01");
});

test("+30 s extends a running timer, or restarts from now once expired", () => {
  const t0 = 0;
  const end = L.startTimer(t0, 90);
  assert.equal(L.extendTimer(end, t0 + 10_000, 30), 120_000);
  assert.equal(L.extendTimer(end, t0 + 100_000, 30), 130_000);
});

test("buildSets drops empty rows and parses numbers", () => {
  const sets = L.buildSets({
    goblet: [{ weight: "25", reps: "12" }, { weight: "", reps: "" }, { weight: "27,5", reps: " 10 " }],
    bandcurl: [{ band: " red ", reps: "15" }],
    hollow: [{ reps: "" }],
  });
  assert.deepEqual(sets, [
    { exercise_key: "goblet", set_no: 1, weight: 25, band: null, reps: 12 },
    { exercise_key: "goblet", set_no: 3, weight: 27.5, band: null, reps: 10 },
    { exercise_key: "bandcurl", set_no: 1, weight: null, band: "red", reps: 15 },
  ]);
});

function fakeTimers() {
  let next = 1; const pending = new Map();
  return {
    set(fn) { const id = next++; pending.set(id, fn); return id; },
    clear(id) { pending.delete(id); },
    fire() { const fns = [...pending.values()]; pending.clear(); return Promise.all(fns.map((f) => f())); },
    get size() { return pending.size; },
  };
}

test("autosave debounces and the last edit wins", async () => {
  const timers = fakeTimers(), saved = [], statuses = [];
  const saver = L.createSaver(async (p) => { saved.push(p); }, (s) => statuses.push(s), 800, timers);
  saver.schedule({ n: 1 }); saver.schedule({ n: 2 }); saver.schedule({ n: 3 });
  assert.equal(timers.size, 1);
  await timers.fire();
  assert.deepEqual(saved, [{ n: 3 }]);
  assert.equal(statuses.at(-1), "saved");
  assert.equal(saver.hasUnsaved(), false);
});

test("autosave never overlaps requests and saves edits made mid-flight", async () => {
  const timers = fakeTimers(), saved = [];
  let release;
  const saver = L.createSaver((p) => { saved.push(p); return saved.length === 1 ? new Promise((r) => { release = r; }) : Promise.resolve(); },
    () => {}, 800, timers);
  saver.schedule({ n: 1 });
  const first = timers.fire();
  await Promise.resolve();
  saver.schedule({ n: 2 });
  await timers.fire(); // in flight: does nothing yet
  assert.deepEqual(saved, [{ n: 1 }]);
  release();
  await first;
  assert.deepEqual(saved, [{ n: 1 }, { n: 2 }]);
});

test("autosave keeps the payload after an error and retries on flush", async () => {
  const timers = fakeTimers(), statuses = [];
  let fail = true; const saved = [];
  const saver = L.createSaver(async (p) => { if (fail) throw new Error("offline"); saved.push(p); },
    (s) => statuses.push(s), 800, timers);
  saver.schedule({ n: 1 });
  await timers.fire();
  assert.equal(statuses.at(-1), "error");
  assert.equal(saver.hasUnsaved(), true);
  fail = false;
  await saver.flush();
  assert.deepEqual(saved, [{ n: 1 }]);
  assert.equal(statuses.at(-1), "saved");
});

test("icons render as Lucide SVG at stroke-width 1.5", () => {
  for (const name of ["dumbbell", "timer", "calendar-check"]) {
    const svg = icon(name);
    assert.match(svg, /^<svg [^>]*stroke-width="1\.5"/);
    assert.match(svg, /viewBox="0 0 24 24"/);
  }
  assert.throws(() => icon("not-an-icon"));
  // The header's filled biceps: outer shape filled, detail lines cut out.
  const biceps = icon("biceps-flexed-filled");
  assert.match(biceps, /<path fill="currentColor" d="M12\.409 13\.017/);
  assert.equal((biceps.match(/class="icon__cut"/g) || []).length, 2);
});
