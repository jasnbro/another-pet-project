/* Gym Log: pure helpers with no DOM access, so they run under `node --test`
 * (tests/logic.test.js) as well as in the browser (window.GymLogic).
 * Schedule, deload and progression rules live on the server (app/schedule.py);
 * this file only formats, times and saves. */
(function (root) {
  "use strict";

  var DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function pad(n) { return (n < 10 ? "0" : "") + n; }

  /* The device's local calendar date as YYYY-MM-DD. Never toISOString(),
   * which is UTC: at 9pm Eastern that's already tomorrow. */
  function localISODate(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }

  function parseISODate(iso) {
    var p = iso.split("-");
    return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
  }

  function addDays(iso, n) {
    var d = parseISODate(iso);
    d.setDate(d.getDate() + n);
    return localISODate(d);
  }

  /* "Mon, Nov 9" (plus the year when it isn't `currentYear`). */
  function formatDate(iso, currentYear) {
    var d = parseISODate(iso);
    var s = DAY_NAMES[d.getDay()] + ", " + MONTHS[d.getMonth()] + " " + d.getDate();
    if (currentYear !== undefined && d.getFullYear() !== currentYear) s += ", " + d.getFullYear();
    return s;
  }

  function formatNumber(n) {
    return Number.isInteger(n) ? String(n) : String(Math.round(n * 10) / 10);
  }

  /* One logged set as shown in "last time" and History. */
  function formatSet(set, load) {
    var reps = set.reps === null || set.reps === undefined ? "–" : String(set.reps);
    if (load === "seconds") return reps + " s";
    if (load === "band") return set.band ? set.band + " × " + reps : reps;
    if (set.weight !== null && set.weight !== undefined) return formatNumber(set.weight) + " × " + reps;
    return reps;
  }

  function formatSets(sets, load) {
    return sets.map(function (s) { return formatSet(s, load); }).join(", ");
  }

  /* "8–12" reps, or "20–30 s" for timed holds; a single number if low = high. */
  function formatRange(reps, load) {
    var r = reps[0] === reps[1] ? String(reps[0]) : reps[0] + "–" + reps[1];
    return load === "seconds" ? r + " s" : r;
  }

  /* --- rest timer -------------------------------------------------------
   * The timer stores an absolute end time, not a countdown, so it stays right
   * after the iPad locks or Safari pauses the tab: on wake, the remaining
   * time is simply endAt - now. */
  function startTimer(now, seconds) { return now + seconds * 1000; }

  function extendTimer(endAt, now, seconds) {
    return Math.max(endAt, now) + seconds * 1000;
  }

  function remainingMs(endAt, now) { return Math.max(0, endAt - now); }

  function formatClock(ms) {
    var total = Math.ceil(ms / 1000);
    return Math.floor(total / 60) + ":" + pad(total % 60);
  }

  /* --- session payload --------------------------------------------------
   * `entries` maps exercise key -> array of {weight, band, reps} input
   * strings, one per set. Empty rows are dropped server-side too. */
  function toNumber(text) {
    if (text === null || text === undefined) return null;
    var t = String(text).trim().replace(",", ".");
    if (t === "") return null;
    var n = Number(t);
    return isFinite(n) ? n : null;
  }

  function buildSets(entries) {
    var sets = [];
    Object.keys(entries).forEach(function (key) {
      entries[key].forEach(function (row, i) {
        var weight = toNumber(row.weight);
        var reps = toNumber(row.reps);
        var band = row.band ? String(row.band).trim() : "";
        if (weight === null && reps === null && band === "") return;
        sets.push({
          exercise_key: key,
          set_no: i + 1,
          weight: weight,
          band: band || null,
          reps: reps === null ? null : Math.round(reps),
        });
      });
    });
    return sets;
  }

  /* Debounced, one-at-a-time autosave. `save(payload)` returns a Promise.
   * Changes made while a save is in flight are saved right after it, so
   * the last edit always wins and requests never overlap.
   * onStatus receives "pending" | "saving" | "saved" | "error". */
  function createSaver(save, onStatus, delayMs, timers) {
    timers = timers || { set: setTimeout.bind(null), clear: clearTimeout.bind(null) };
    var timer = null, inFlight = false, queued = null;

    function run() {
      timer = null;
      if (inFlight || queued === null) return;
      var payload = queued;
      queued = null;
      inFlight = true;
      onStatus("saving");
      return Promise.resolve()
        .then(function () { return save(payload); })
        .then(function () {
          inFlight = false;
          if (queued !== null) return run();
          onStatus("saved");
        }, function (err) {
          inFlight = false;
          if (queued === null) queued = payload; // keep it for retry
          onStatus("error", err);
        });
    }

    return {
      schedule: function (payload) {
        queued = payload;
        onStatus("pending");
        if (timer !== null) timers.clear(timer);
        timer = timers.set(run, delayMs);
      },
      flush: function () {
        if (timer !== null) { timers.clear(timer); timer = null; }
        return run();
      },
      hasUnsaved: function () { return queued !== null || inFlight; },
    };
  }

  var api = {
    localISODate: localISODate,
    parseISODate: parseISODate,
    addDays: addDays,
    formatDate: formatDate,
    formatNumber: formatNumber,
    formatSet: formatSet,
    formatSets: formatSets,
    formatRange: formatRange,
    startTimer: startTimer,
    extendTimer: extendTimer,
    remainingMs: remainingMs,
    formatClock: formatClock,
    toNumber: toNumber,
    buildSets: buildSets,
    createSaver: createSaver,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.GymLogic = api;
})(this);
