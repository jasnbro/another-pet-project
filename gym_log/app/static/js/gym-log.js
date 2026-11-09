/* Gym Log front end. Plain JS, no build step.
 *
 * Views (hash routes): #today (default), #plan, #exercises, #equipment,
 * #history. All data comes from /api/gym/*; nothing about the plan is
 * hard-coded here. Helpers live in logic.js (window.GymLogic) and icons in
 * icons.js (window.GymIcons). */
(function () {
  "use strict";

  var L = window.GymLogic;
  var icon = window.GymIcons.icon;
  var REST_SECONDS = 90;
  var EXTEND_SECONDS = 30;
  var SAVE_DELAY_MS = 800;
  var MUTE_KEY = "gym-log:muted";

  var main = document.getElementById("main");
  var saveStatusEl = document.getElementById("save-status");

  var state = {
    catalog: null,
    today: null, // /api/gym/today response
    date: L.localISODate(new Date()),
    dayOverride: null,
    entries: {}, // exercise key -> [{weight, band, reps}]
    warmup: [],
    rope: [],
    notes: "",
    finished: false,
    view: "today",
  };

  // --- utilities -----------------------------------------------------------

  function esc(value) {
    return String(value === null || value === undefined ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function getJSON(url) {
    return fetch(url, { headers: { Accept: "application/json" } }).then(function (r) {
      if (!r.ok) return r.json().catch(function () { return {}; }).then(function (b) {
        throw new Error(b.error || r.status + " " + r.statusText);
      });
      return r.json();
    });
  }

  function storageGet(key) { try { return window.localStorage.getItem(key); } catch (e) { return null; } }
  function storageSet(key, value) { try { window.localStorage.setItem(key, value); } catch (e) { /* private mode */ } }

  // Looping illustration from the exercise's catalog frames (start, mid, end).
  // CSS plays them start → mid → end → mid on repeat (a rep, there and back);
  // with reduced motion it shows the start pose only. Frames are white on
  // transparent and drawn as CSS masks, so they follow the theme's ink color.
  function demoHtml(name, frames, extraClass) {
    if (!frames || !frames.length) return "";
    var loop = frames.length === 3;
    return '<span class="demo' + (loop ? " demo--loop" : "") + (extraClass ? " " + extraClass : "") +
      '" role="img" aria-label="' + esc(name) + ' demonstration">' +
      frames.slice(0, loop ? 3 : 1).map(function (src, i) {
        return '<span class="demo__frame demo__frame--' + (i + 1) + '" style="--src: url(&quot;' + esc(src) + '&quot;)"></span>';
      }).join("") + "</span>";
  }

  function currentYear() { return L.parseISODate(state.date).getFullYear(); }
  function exName(key) { var ex = state.catalog.exercises[key]; return ex ? ex.name : key; }

  // --- autosave ------------------------------------------------------------

  var STATUS_TEXT = { pending: "Editing…", saving: "Saving…", saved: "Saved", error: "Not saved" };
  var saver = L.createSaver(
    function (payload) {
      return fetch("/api/gym/sessions/" + payload.date, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload.body),
        keepalive: true,
      }).then(function (r) {
        if (!r.ok) return r.json().catch(function () { return {}; }).then(function (b) {
          throw new Error(b.error || "HTTP " + r.status);
        });
      });
    },
    function (status, err) {
      saveStatusEl.hidden = false;
      saveStatusEl.dataset.status = status;
      saveStatusEl.innerHTML = esc(STATUS_TEXT[status]) +
        (status === "error" ? ' <button type="button" class="link-button" data-action="retry-save">Retry</button>' : "");
      saveStatusEl.title = err ? String(err.message || err) : "";
    },
    SAVE_DELAY_MS
  );

  function scheduleSave() {
    var t = state.today;
    if (!t || !t.day) return;
    saver.schedule({
      date: t.date,
      body: {
        plan: t.plan,
        day_code: t.day,
        finished: state.finished,
        warmup_done: state.warmup,
        rope_rounds: state.rope,
        notes: state.notes,
        sets: L.buildSets(state.entries),
      },
    });
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") saver.flush();
  });
  window.addEventListener("pagehide", function () { saver.flush(); });
  window.addEventListener("online", function () { if (saver.hasUnsaved()) saver.flush(); });

  // --- rest timer ------------------------------------------------------------

  var timer = { endAt: null, interval: null, chimed: false, wakeLock: null, audio: null };
  var timerEl = document.getElementById("timer");

  function isMuted() { return storageGet(MUTE_KEY) === "1"; }

  function unlockAudio() {
    // iOS only lets a page make sound after a tap; this runs inside one.
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    if (!timer.audio) { try { timer.audio = new Ctx(); } catch (e) { return; } }
    if (timer.audio.state === "suspended") timer.audio.resume();
    var buf = timer.audio.createBuffer(1, 1, 22050);
    var src = timer.audio.createBufferSource();
    src.buffer = buf; src.connect(timer.audio.destination); src.start(0);
  }

  function chime() {
    if (isMuted() || !timer.audio) return;
    var ctx = timer.audio, t0 = ctx.currentTime;
    [0, 0.22].forEach(function (offset, i) {
      var osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = i ? 1175 : 880;
      gain.gain.setValueAtTime(0.0001, t0 + offset);
      gain.gain.exponentialRampToValueAtTime(0.35, t0 + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + offset + 0.35);
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(t0 + offset); osc.stop(t0 + offset + 0.4);
    });
  }

  function requestWakeLock() {
    if (!("wakeLock" in navigator) || timer.wakeLock) return;
    navigator.wakeLock.request("screen").then(function (lock) {
      timer.wakeLock = lock;
      lock.addEventListener("release", function () { timer.wakeLock = null; });
    }).catch(function () { /* unsupported or denied: fine */ });
  }

  function releaseWakeLock() {
    if (timer.wakeLock) { timer.wakeLock.release().catch(function () {}); timer.wakeLock = null; }
  }

  function startRest(seconds) {
    unlockAudio();
    timer.endAt = L.startTimer(Date.now(), seconds);
    timer.chimed = false;
    requestWakeLock();
    if (!timer.interval) timer.interval = setInterval(tick, 250);
    tick();
  }

  function extendRest() {
    unlockAudio();
    if (timer.endAt === null) return startRest(EXTEND_SECONDS);
    timer.endAt = L.extendTimer(timer.endAt, Date.now(), EXTEND_SECONDS);
    timer.chimed = false;
    requestWakeLock();
    if (!timer.interval) timer.interval = setInterval(tick, 250);
    tick();
  }

  function stopRest() {
    timer.endAt = null;
    if (timer.interval) { clearInterval(timer.interval); timer.interval = null; }
    releaseWakeLock();
    renderTimer();
  }

  function tick() {
    if (timer.endAt === null) return renderTimer();
    var left = L.remainingMs(timer.endAt, Date.now());
    if (left === 0 && !timer.chimed) {
      timer.chimed = true;
      chime();
      if (navigator.vibrate) navigator.vibrate([120, 80, 120]);
      clearInterval(timer.interval); timer.interval = null;
      releaseWakeLock();
    }
    renderTimer();
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && timer.endAt !== null) {
      if (L.remainingMs(timer.endAt, Date.now()) > 0) requestWakeLock();
      tick();
    }
  });

  function renderTimer() {
    var show = state.view === "today" && state.today && state.today.day;
    timerEl.hidden = !show;
    document.body.classList.toggle("has-timer", !!show);
    if (!show) return;
    var running = timer.endAt !== null;
    var left = running ? L.remainingMs(timer.endAt, Date.now()) : 0;
    var done = running && left === 0;
    var muted = isMuted();
    timerEl.dataset.state = done ? "done" : running ? "running" : "idle";
    timerEl.innerHTML =
      '<div class="timer__clock" role="timer" aria-live="off">' + icon("timer") +
      "<span>" + (running ? (done ? "Rest done" : L.formatClock(left)) : "Rest") + "</span></div>" +
      '<div class="timer__buttons">' +
      (running && !done
        ? '<button type="button" class="btn" data-action="rest-extend">+30 s</button>' +
          '<button type="button" class="btn btn--quiet" data-action="rest-stop" aria-label="Stop timer">' + icon("x") + "</button>"
        : '<button type="button" class="btn btn--primary" data-action="rest-start">' + REST_SECONDS + " s</button>" +
          (done ? '<button type="button" class="btn btn--quiet" data-action="rest-stop" aria-label="Dismiss">' + icon("x") + "</button>" : "")) +
      '<button type="button" class="btn btn--quiet" data-action="toggle-mute" aria-pressed="' + muted + '" aria-label="' +
      (muted ? "Unmute chime" : "Mute chime") + '">' + icon(muted ? "volume-x" : "volume-2") + "</button>" +
      "</div>";
  }

  // --- Today -------------------------------------------------------------------

  function loadToday() {
    var url = "/api/gym/today?date=" + encodeURIComponent(state.date);
    if (state.dayOverride) url += "&day=" + encodeURIComponent(state.dayOverride);
    return getJSON(url).then(function (t) {
      state.today = t;
      var s = t.session;
      state.finished = s ? s.finished : false;
      state.notes = s && s.notes ? s.notes : "";
      state.warmup = t.warmup.map(function (_, i) { return !!(s && s.warmup_done[i]); });
      var rounds = t.finisher ? t.finisher.rounds : 0;
      state.rope = Array.from({ length: rounds }, function (_, i) { return !!(s && s.rope_rounds[i]); });
      state.entries = {};
      t.items.forEach(function (item) {
        var logged = s ? s.sets.filter(function (x) { return x.exercise_key === item.key; }) : [];
        var count = Math.max(item.sets, logged.reduce(function (m, x) { return Math.max(m, x.set_no); }, 0));
        var rows = [];
        for (var i = 1; i <= count; i++) {
          var x = logged.find(function (y) { return y.set_no === i; });
          rows.push({
            weight: x && x.weight !== null ? String(x.weight) : "",
            band: x && x.band ? x.band : "",
            reps: x && x.reps !== null ? String(x.reps) : "",
          });
        }
        state.entries[item.key] = rows;
      });
    });
  }

  function renderToday() {
    var t = state.today;
    var y = currentYear();
    var html = '<section class="view today" aria-labelledby="today-title">';
    html += '<header class="today__head">' +
      '<div class="today__date">' +
      '<button type="button" class="btn btn--quiet" data-action="date-prev" aria-label="Previous day">‹</button>' +
      '<div><h2 id="today-title">' + esc(L.formatDate(t.date)) + "</h2>" +
      '<p class="muted">' + (t.week ? "Week " + t.week + " · " : "") + esc(t.plan_name || t.plan) +
      (t.date !== L.localISODate(new Date()) ? ' · <button type="button" class="link-button" data-action="date-today">Back to today</button>' : "") +
      "</p></div>" +
      '<button type="button" class="btn btn--quiet" data-action="date-next" aria-label="Next day">›</button>' +
      "</div>" +
      '<div class="segmented" role="group" aria-label="Workout day">' +
      t.days.map(function (code) {
        return '<button type="button" class="segmented__btn" data-action="pick-day" data-day="' + esc(code) +
          '" aria-pressed="' + (t.day === code) + '">Day ' + esc(code) + "</button>";
      }).join("") + "</div></header>";

    if (t.deload) {
      html += '<p class="banner banner--deload" role="status">' + icon("arrow-up", "icon--flip") +
        "<span><strong>Deload week.</strong> Sets are halved this week (rounded up). Keep the weights, stay well short of failure.</span></p>";
    }

    if (!t.day) {
      html += '<div class="rest-card">' + icon("calendar-check", "icon--lg") +
        "<h3>" + (t.week ? "Rest day" : "Plan starts " + esc(L.formatDate(t.plan_starts, y))) + "</h3>" +
        (t.next ? '<p>Next session: <strong>' + esc(L.formatDate(t.next.date, y)) + "</strong>, Day " + esc(t.next.day) + ".</p>" : "") +
        '<p class="muted">Training anyway? Pick a day above.</p></div>';
      html += "</section>";
      return html;
    }

    if (t.scheduled_day && t.day !== t.scheduled_day) {
      html += '<p class="banner" role="status">Scheduled: Day ' + esc(t.scheduled_day) + ". Showing Day " + esc(t.day) + ".</p>";
    }

    // Warm-up
    if (t.warmup.length) {
      html += '<section class="block" aria-labelledby="warmup-title"><h3 id="warmup-title" class="block__title">Warm-up</h3><ul class="checklist">';
      t.warmup.forEach(function (line, i) {
        html += '<li><label class="check"><input type="checkbox" data-action="warmup" data-index="' + i + '"' +
          (state.warmup[i] ? " checked" : "") + "><span>" + esc(line) + "</span></label></li>";
      });
      html += "</ul></section>";
    }

    // Exercises
    t.items.forEach(function (item) { html += renderExercise(item, y); });

    // Finisher
    if (t.finisher) {
      var f = t.finisher;
      var done = state.rope.filter(Boolean).length;
      html += '<section class="block" aria-labelledby="finisher-title"><h3 id="finisher-title" class="block__title">Finisher: ' + esc(f.name) + "</h3>" +
        '<p class="muted">' + f.rounds + " rounds · " + f.work_sec + " s on, " + f.rest_sec + " s off · " + done + " of " + f.rounds + " done</p>" +
        '<div class="rounds" role="group" aria-label="Rounds done">';
      state.rope.forEach(function (on, i) {
        html += '<button type="button" class="round" data-action="rope" data-index="' + i + '" aria-pressed="' + on +
          '" aria-label="Round ' + (i + 1) + '">' + (on ? icon("check") : String(i + 1)) + "</button>";
      });
      html += "</div></section>";
    }

    // Notes + finish
    html += '<section class="block"><label class="block__title" for="notes">Notes</label>' +
      '<textarea id="notes" rows="3" placeholder="How it felt, pain, sleep (optional)" data-action="notes">' + esc(state.notes) + "</textarea></section>";
    html += '<div class="finish">' + (state.finished
      ? '<p class="finish__done">' + icon("circle-check") + " Finished. Nice work.</p>" +
        '<button type="button" class="link-button" data-action="unfinish">Not done yet</button>'
      : '<button type="button" class="btn btn--primary btn--wide" data-action="finish">Finish workout</button>') + "</div>";
    html += "</section>";
    return html;
  }

  function renderExercise(item, y) {
    var rows = state.entries[item.key] || [];
    var load = item.load;
    var lastSets = item.last ? item.last.sets : [];
    var html = '<article class="exercise" data-key="' + esc(item.key) + '">' +
      '<header class="exercise__head">' +
      (item.pair ? '<span class="pair">' + esc(item.pair) + "</span>" : "") +
      demoHtml(item.name, item.frames) +
      '<div class="exercise__title"><h3>' + esc(item.name) + "</h3>" +
      (item.swapped_for ? '<p class="swap">' + icon("repeat") + " Swap for " + esc(item.swapped_for) + "</p>" : "") +
      "</div>" +
      '<p class="target">' + item.sets + " × " + esc(L.formatRange(item.reps, load)) +
      (item.sets !== item.planned_sets ? ' <span class="muted">(of ' + item.planned_sets + ")</span>" : "") + "</p>" +
      "</header>";

    var meta = [];
    if (item.start && !item.last) meta.push("Start: " + esc(item.start));
    if (item.cue) meta.push(esc(item.cue));
    if (meta.length) html += '<p class="exercise__meta">' + meta.join(" · ") + "</p>";

    if (item.missing_equipment.length) {
      html += '<p class="warn">' + icon("triangle-alert") + " Needs " +
        item.missing_equipment.map(function (k) {
          var eq = state.catalog.equipment[k];
          return esc(eq ? eq.name : k) + " (" + esc(eq ? eq.status : "?") + ")";
        }).join(", ") + "</p>";
    }

    if (item.last) {
      html += '<p class="last"><span class="muted">Last time (' + esc(L.formatDate(item.last.date, y)) + "):</span> " +
        esc(L.formatSets(item.last.sets, load)) + "</p>";
    }
    if (item.progression_text) {
      html += '<p class="cue cue--' + esc(item.progression) + '">' +
        (item.progression === "up" ? icon("arrow-up") : "") + esc(item.progression_text) + "</p>";
    }

    html += '<div class="sets" role="group" aria-label="' + esc(item.name) + ' sets">';
    rows.forEach(function (row, i) {
      var prev = lastSets.find(function (s) { return s.set_no === i + 1; });
      var id = "s-" + item.key + "-" + i;
      html += '<div class="set"><span class="set__no">' + (i + 1) + "</span>";
      if (load === "db_single" || load === "db_per_hand") {
        html += '<label class="field"><span class="field__label">' + (load === "db_per_hand" ? "lb/hand" : "lb") + "</span>" +
          '<input id="' + id + '-w" type="text" inputmode="decimal" autocomplete="off" data-field="weight" data-key="' + esc(item.key) +
          '" data-index="' + i + '" value="' + esc(row.weight) + '" placeholder="' + esc(prev && prev.weight !== null ? L.formatNumber(prev.weight) : "") + '"></label>';
      } else if (load === "band") {
        html += '<label class="field field--band"><span class="field__label">band</span>' +
          '<input id="' + id + '-b" type="text" autocomplete="off" data-field="band" data-key="' + esc(item.key) +
          '" data-index="' + i + '" value="' + esc(row.band) + '" placeholder="' + esc(prev && prev.band ? prev.band : "e.g. red") + '"></label>';
      }
      html += '<label class="field"><span class="field__label">' + (load === "seconds" ? "sec" : "reps") + "</span>" +
        '<input id="' + id + '-r" type="text" inputmode="numeric" autocomplete="off" data-field="reps" data-key="' + esc(item.key) +
        '" data-index="' + i + '" value="' + esc(row.reps) + '" placeholder="' + esc(prev && prev.reps !== null ? prev.reps : L.formatRange(item.reps, "")) + '"></label>' +
        '<button type="button" class="btn btn--quiet set__rest" data-action="rest-start" aria-label="Start ' + REST_SECONDS + ' second rest">' + icon("timer") + "</button>" +
        "</div>";
    });
    html += "</div>" +
      '<details class="how"><summary>How to do it</summary><p>' + esc(item.what) + "</p>" +
      '<p class="muted">Key <code>' + esc(item.key) + "</code> · " + esc(item.muscles.join(", ")) + "</p></details>" +
      "</article>";
    return html;
  }

  // --- Plan ------------------------------------------------------------------------

  var WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
  var WEEKDAY_LABELS = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };

  function renderPlan() {
    var c = state.catalog, p = c.plan;
    var html = '<section class="view" aria-labelledby="plan-title"><h2 id="plan-title">' + icon("calendar-check") + " " + esc(p.name || p.plan) + "</h2>";
    html += '<p class="muted">Starts ' + esc(L.formatDate(p.starts)) +
      (p.session_minutes ? " · about " + p.session_minutes + " min a session" : "") +
      " · weeks count from the start date (week 1 is odd)</p>";

    if (c.warnings.length) {
      // Collapsed by default: the warnings are long, and the plan is what this page is for.
      html += '<details class="banner banner--warn heads-up"><summary>' + icon("triangle-alert") +
        "<strong>Heads up</strong> <span class=\"muted\">(" + c.warnings.length + ")</span></summary><ul>" +
        c.warnings.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("") + "</ul></details>";
    }

    html += '<h3 class="block__title">Schedule</h3><div class="table-wrap"><table class="table schedule"><thead><tr><th scope="col">Week</th>' +
      WEEKDAYS.map(function (d) { return '<th scope="col">' + WEEKDAY_LABELS[d] + "</th>"; }).join("") + "</tr></thead><tbody>";
    ["odd", "even"].forEach(function (parity) {
      html += '<tr><th scope="row">' + (parity === "odd" ? "Odd" : "Even") + "</th>" +
        WEEKDAYS.map(function (d) {
          var code = p.schedule[parity][d];
          return code ? '<td class="schedule__day">' + esc(code) + "</td>" : '<td class="muted">–</td>';
        }).join("") + "</tr>";
    });
    html += "</tbody></table></div>";

    Object.keys(p.days).forEach(function (code) {
      html += '<h3 class="block__title">Day ' + esc(code) + '</h3><div class="table-wrap"><table class="table">' +
        '<thead><tr><th scope="col"></th><th scope="col">Exercise</th><th scope="col">Sets × reps</th><th scope="col">Start</th></tr></thead><tbody>';
      p.days[code].forEach(function (item) {
        var ex = c.exercises[item.key];
        var alt = ex && !ex.owned && ex.alt ? c.exercises[ex.alt] : null;
        html += "<tr><td>" + esc(item.pair || "") + "</td><td>" + esc(ex ? ex.name : item.key) +
          (alt ? '<div class="swap">' + icon("repeat") + " for now: " + esc(alt.name) + "</div>" : "") +
          (item.cue ? '<div class="muted">' + esc(item.cue) + "</div>" : "") + "</td>" +
          "<td>" + item.sets + " × " + esc(L.formatRange(item.reps, ex ? ex.load : "")) + "</td>" +
          "<td>" + esc(item.start || "") + "</td></tr>";
      });
      html += "</tbody></table></div>";
    });

    if (p.warmup.length) {
      html += '<h3 class="block__title">Warm-up</h3><ul class="plain">' +
        p.warmup.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("") + "</ul>";
    }
    html += '<h3 class="block__title">Progression</h3><p>Double progression: when every set reaches the top of the rep range, go up one jump next time. Otherwise keep the weight and beat last time\'s reps.' +
      (p.progression.deload_every_weeks ? " Every " + p.progression.deload_every_weeks + "th week is a deload: half the sets (rounded up)." : "") + "</p>";
    if (p.finisher) {
      html += '<h3 class="block__title">Finisher</h3><p>' + esc(p.finisher.name) + ": " + p.finisher.rounds + " rounds, " +
        p.finisher.work_sec + " s on / " + p.finisher.rest_sec + " s off.</p>";
    }
    html += '<p class="muted small">Plans live in <code>gym_log/data/plans/</code>. Edit the YAML and merge; see the README.</p></section>';
    return html;
  }

  // --- Exercises (the key glossary) ---------------------------------------------------

  function renderExercises() {
    var c = state.catalog;
    var html = '<section class="view" aria-labelledby="ex-title"><h2 id="ex-title">' + icon("book-open") + " Exercises</h2>" +
      '<p class="muted">Every exercise key and what it means. Keys are permanent; retired ones stay listed so old logs still read right.</p><div class="glossary">';
    Object.keys(c.exercises).forEach(function (key) {
      var ex = c.exercises[key];
      html += '<article class="glossary__item' + (ex.retired ? " is-retired" : "") + '" id="ex-' + esc(key) + '">' +
        demoHtml(ex.name, ex.frames, "demo--lg") +
        '<header><code class="key">' + esc(key) + "</code><h3>" + esc(ex.name) + "</h3>" +
        (ex.retired ? '<span class="tag">retired</span>' : "") + "</header>" +
        "<p>" + esc(ex.what) + "</p><dl class=\"facts\">" +
        "<dt>Muscles</dt><dd>" + esc(ex.muscles.join(", ")) + "</dd>" +
        "<dt>Equipment</dt><dd>" + (ex.equipment.length ? ex.equipment.map(function (k) {
          var eq = c.equipment[k];
          return esc(eq ? eq.name : k) + (eq && eq.status !== "owned" ? ' <span class="tag">' + esc(eq.status) + "</span>" : "");
        }).join(", ") : "none (bodyweight)") + "</dd>" +
        "<dt>Load</dt><dd>" + esc(ex.load_label) + "</dd>" +
        (ex.alt ? '<dt>Alt</dt><dd><a href="#ex-' + esc(ex.alt) + '">' + esc(exName(ex.alt)) + "</a> when equipment is missing</dd>" : "") +
        "</dl></article>";
    });
    // Both licenses require this credit (catalog/README.md).
    return html + '</div><p class="credits muted">Exercise illustrations by ' +
      '<a href="https://bryllim.com">Bryl Lim</a> (<a href="https://github.com/bryllim/workout-guide">Workout Guide</a>), ' +
      'based on artwork by <a href="https://github.com/everkinetic/data">Everkinetic</a>, licensed under ' +
      '<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. ' +
      'Exercise data by <a href="https://exercise-api.com">ExerciseAPI</a>, licensed under ' +
      '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p></section>';
  }

  // --- Equipment ---------------------------------------------------------------------

  function renderEquipment() {
    var c = state.catalog;
    var html = '<section class="view" aria-labelledby="eq-title"><h2 id="eq-title">' + icon("package") + " Equipment</h2>";
    [["owned", "Owned"], ["planned", "Planned"], ["retired", "Retired"]].forEach(function (group) {
      var items = Object.keys(c.equipment).filter(function (k) { return c.equipment[k].status === group[0]; });
      html += '<h3 class="block__title">' + group[1] + ' <span class="muted">(' + items.length + ")</span></h3>";
      if (!items.length) { html += '<p class="muted">None.</p>'; return; }
      html += '<ul class="equipment' + (group[0] === "retired" ? " is-retired" : "") + '">';
      items.forEach(function (k) {
        var eq = c.equipment[k];
        html += "<li><div><strong>" + esc(eq.name) + '</strong> <code class="key">' + esc(k) + "</code></div>" +
          (eq.notes ? '<div class="muted">' + esc(eq.notes) + "</div>" : "") +
          '<div class="small">Supports: ' + (eq.supports.length ? eq.supports.map(function (key) {
            return '<a href="#ex-' + esc(key) + '">' + esc(exName(key)) + "</a>";
          }).join(", ") : '<span class="muted">no exercises yet</span>') + "</div></li>";
      });
      html += "</ul>";
    });
    return html + "</section>";
  }

  // --- History -------------------------------------------------------------------------

  function renderHistory(sessions) {
    var c = state.catalog, y = currentYear();
    var html = '<section class="view" aria-labelledby="hist-title"><div class="view__head"><h2 id="hist-title">' + icon("history") + " History</h2>" +
      '<a class="btn" href="/api/gym/export.csv" download>' + icon("download") + " Export CSV</a></div>";
    if (!sessions.length) return html + '<p class="muted">Nothing logged yet. Sessions show up here once you enter a set.</p></section>';
    sessions.forEach(function (s) {
      var byKey = {}, order = [];
      s.sets.forEach(function (x) {
        if (!byKey[x.exercise_key]) { byKey[x.exercise_key] = []; order.push(x.exercise_key); }
        byKey[x.exercise_key].push(x);
      });
      html += '<article class="history"><header><h3>' + esc(L.formatDate(s.date, y)) + "</h3>" +
        '<span class="muted">Day ' + esc(s.day_code) + " · " + esc(s.plan) + "</span>" +
        (s.finished ? '<span class="tag tag--ok">' + icon("check") + " finished</span>" : "") + "</header>";
      if (order.length) {
        html += '<dl class="facts">';
        order.forEach(function (k) {
          var ex = c.exercises[k];
          html += "<dt>" + esc(ex ? ex.name : k) + "</dt><dd>" + esc(L.formatSets(byKey[k], ex ? ex.load : "")) + "</dd>";
        });
        html += "</dl>";
      } else {
        html += '<p class="muted">No sets logged.</p>';
      }
      if (s.notes) html += '<p class="history__notes">' + icon("notebook-pen") + " " + esc(s.notes) + "</p>";
      html += "</article>";
    });
    return html + "</section>";
  }

  // --- routing ---------------------------------------------------------------------------

  var VIEWS = ["today", "plan", "exercises", "equipment", "history"];

  function setNav() {
    document.querySelectorAll("[data-nav]").forEach(function (a) {
      if (a.dataset.nav === state.view) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
  }

  function showError(err) {
    main.innerHTML = '<section class="view"><p class="banner banner--warn">' + icon("triangle-alert") +
      "<span>Couldn't load: " + esc(err.message || err) + ' <button type="button" class="link-button" data-action="reload">Try again</button></span></p></section>';
  }

  function render() {
    setNav();
    var v = state.view;
    var p;
    if (v === "today") p = (state.today ? Promise.resolve() : loadToday()).then(function () { main.innerHTML = renderToday(); });
    else if (v === "plan") p = Promise.resolve().then(function () { main.innerHTML = renderPlan(); });
    else if (v === "exercises") p = Promise.resolve().then(function () { main.innerHTML = renderExercises(); });
    else if (v === "equipment") p = Promise.resolve().then(function () { main.innerHTML = renderEquipment(); });
    else p = getJSON("/api/gym/sessions").then(function (s) { main.innerHTML = renderHistory(s); });
    return p.then(renderTimer).catch(showError);
  }

  function route() {
    var hash = (location.hash || "").replace("#", "");
    var view = VIEWS.indexOf(hash) >= 0 ? hash : hash.indexOf("ex-") === 0 ? "exercises" : "today";
    var changed = view !== state.view;
    state.view = view;
    if (changed || !main.firstElementChild || main.querySelector(".loading")) {
      render().then(function () {
        if (hash.indexOf("ex-") === 0) {
          var el = document.getElementById(hash);
          if (el) el.scrollIntoView({ block: "start" });
        } else if (changed) {
          window.scrollTo(0, 0);
        }
      });
    }
  }

  function changeDate(iso) {
    saver.flush();
    state.date = iso;
    state.dayOverride = null;
    state.today = null;
    render();
  }

  // --- events ----------------------------------------------------------------------------

  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-action]");
    if (!el) return;
    var action = el.dataset.action;
    if (action === "rest-start") startRest(REST_SECONDS);
    else if (action === "rest-extend") extendRest();
    else if (action === "rest-stop") stopRest();
    else if (action === "toggle-mute") { storageSet(MUTE_KEY, isMuted() ? "0" : "1"); unlockAudio(); renderTimer(); }
    else if (action === "retry-save") saver.flush();
    else if (action === "reload") { state.today = null; render(); }
    else if (action === "date-prev") changeDate(L.addDays(state.date, -1));
    else if (action === "date-next") changeDate(L.addDays(state.date, 1));
    else if (action === "date-today") changeDate(L.localISODate(new Date()));
    else if (action === "pick-day") {
      var code = el.dataset.day;
      if (state.today && state.today.day === code) return;
      var logged = L.buildSets(state.entries).length > 0;
      if (logged && !window.confirm("Switch to Day " + code + "? Sets already entered for Day " + state.today.day + " on this date will be cleared.")) return;
      saver.flush();
      state.dayOverride = code;
      state.today = null;
      render().then(function () { if (logged) scheduleSave(); });
    } else if (action === "rope") {
      var i = Number(el.dataset.index);
      state.rope[i] = !state.rope[i];
      main.innerHTML = renderToday();
      scheduleSave();
    } else if (action === "finish" || action === "unfinish") {
      state.finished = action === "finish";
      if (state.finished) stopRest();
      main.innerHTML = renderToday();
      scheduleSave();
      saver.flush();
    }
  });

  document.addEventListener("change", function (e) {
    var el = e.target;
    if (el.dataset.action === "warmup") {
      state.warmup[Number(el.dataset.index)] = el.checked;
      scheduleSave();
    }
  });

  document.addEventListener("input", function (e) {
    var el = e.target;
    if (el.dataset.field && el.dataset.key) {
      var rows = state.entries[el.dataset.key];
      if (rows && rows[Number(el.dataset.index)]) {
        rows[Number(el.dataset.index)][el.dataset.field] = el.value;
        scheduleSave();
      }
    } else if (el.dataset.action === "notes") {
      state.notes = el.value;
      scheduleSave();
    }
  });

  // Coming back to the app on a new day (it stays open on the iPad): jump
  // to the new "today" if the user was looking at the old one.
  var lastSeenToday = state.date;
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible") return;
    var now = L.localISODate(new Date());
    if (now !== lastSeenToday) {
      var wasOnToday = state.date === lastSeenToday;
      lastSeenToday = now;
      if (wasOnToday) changeDate(now);
    }
  });

  window.addEventListener("hashchange", route);

  // --- boot --------------------------------------------------------------------------------

  // (The service worker is registered by undercurrent/install-shortcut.js.)
  document.querySelectorAll("[data-icon]").forEach(function (el) {
    el.insertAdjacentHTML("afterbegin", icon(el.dataset.icon));
  });

  getJSON("/api/gym/catalog").then(function (c) {
    state.catalog = c;
    state.view = null;
    route();
  }).catch(showError);
})();
