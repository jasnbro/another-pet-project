# Exercise frames

The pictures behind the looping exercise illustrations: 302 exercises × 3
poses (start, mid, end) from Workout Guide 1.0.0 by Bryl Lim. 33 MB in total.
The app serves them at `/frames/<exercise>/frame-N.png`.

## Why they live here, and not in `app/static/`

**Short version: so Atlas stores them once, not five times.**

Every deploy builds a new Docker image, and `deploy/deploy.sh` keeps the last
5 for rollback. An image is a stack of layers, one per `COPY` in the
Dockerfile. Docker keeps one copy of any layer whose contents haven't
changed, and every image that uses it shares that copy.

When the frames were inside `app/static/`, they were part of the `COPY app/`
layer. That layer changes on almost every deploy (any edit to the code, CSS
or JS), so each new image carried its own fresh 33 MB copy of the frames:

| Where the frames are | Disk used on Atlas for frames (5 images kept) |
|---|---|
| inside `app/` | up to about 165 MB (a copy per image) |
| here, in their own layer | about 33 MB (one copy, shared) |

The Dockerfile copies this folder right after the Python dependencies,
before any code. The layer only rebuilds when a file in here changes, which
in practice means only when you update Workout Guide. Deploys are also a
little faster, since that layer is cached.

## Why not mount the folder from Atlas instead?

It would shrink the images, but it breaks two things this repo relies on:

- **Rollback.** Each image is a complete version of the app. With mounted
  frames, rolling back changes the code but not the pictures, so a
  rollback could show frames the old code doesn't expect.
- **No hand-managed files on Atlas.** Everything reaches Atlas through
  `deploy/`. A mounted folder would have to be copied there and kept in
  sync by hand, outside git. `compose.yml` deliberately has no bind mount.

It also wouldn't make the repo any smaller. The 33 MB is in git either way.

## Rules

- **Never edit, recolor, crop or re-encode these files.** They're CC BY-SA
  4.0 (see `LICENSE-ASSETS` and `ATTRIBUTION.md`). They're white on
  transparent; the app colors them with CSS masks.
- **Keep `COPY frames/ frames/` above the code `COPY`s in the Dockerfile.**
  Below them, it would rebuild on every deploy, and the sharing would be
  lost.
- **To update to a newer Workout Guide version,** replace this folder with
  the new version's `assets/` (from the npm package `@bryllim/workout-guide`),
  update `catalog/sources/workout-guide-*/`, and rerun
  `uv run python catalog/build_catalog.py`. That one deploy adds a new
  layer; old images keep the old one until they're cleaned up.
