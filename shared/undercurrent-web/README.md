# Undercurrent web snippet

Shared pieces every Undercurrent web app uses, so each app is installable
and shows an **"Add to Home Screen"** shortcut (Undercurrent web standard,
decided Oct 18, 2026 — see the Undercurrent Product Vision page in Notion).

| File | What it is |
|---|---|
| `install-shortcut.js` | Decides which shortcut to show and wires it up |
| `install-shortcut.css` | Styling; themeable with `--uc-install-*` variables |
| `_install_shortcut.html` | Jinja partial: the button and the step-by-step dialog |
| `sw.js` | Minimal service worker (no caching) so browsers allow install |
| `sync.sh` | Copies the files above into an app |

## What users see

| Browser | Shortcut |
|---|---|
| Android, Chrome/Edge desktop | One-tap **Install app** prompt |
| iPhone/iPad (Safari, Chrome, others) | Button opens "Share → Add to Home Screen" steps |
| Safari on Mac | Button opens "File → Add to Dock" steps |
| Firefox desktop, others | Hidden |
| Already installed | Hidden |
| Dismissed (×) | Hidden for 30 days |

## Adding it to an app (Flask)

1. `shared/undercurrent-web/sync.sh <app_dir>` — copies files into
   `<app_dir>/app/static/undercurrent/` and `<app_dir>/app/templates/`.
2. Serve `/sw.js` (from `static/undercurrent/sw.js`) and
   `/manifest.webmanifest` at the site root. See `mindless_meals/app/app.py`
   (`service_worker` and `manifest` routes) for the pattern.
3. Add icons: `icon-192.png`, `icon-512.png`, `icon-maskable-512.png`,
   `apple-touch-icon.png` (180×180).
4. In the page `<head>`: manifest link, `theme-color`, `apple-touch-icon`,
   `apple-mobile-web-app-*` tags, and `install-shortcut.css`.
5. Near the end of `<body>`: `{% include "_install_shortcut.html" %}` and
   `install-shortcut.js` (pass `uc_app_name` to the template).
6. Optionally set `--uc-install-*` CSS variables to match the app's palette.

## Editing

Edit the files **here**, then re-run `sync.sh` for each app. Each app has a
test that fails if its copy drifts from this folder.

Test the logic: `node --test shared/undercurrent-web/install-shortcut.test.js`
