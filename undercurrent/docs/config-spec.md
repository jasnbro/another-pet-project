# undercurrent: config spec

Hand this to the build. Three files drive all homepage content:

| File | Holds | Changes |
|---|---|---|
| `site.yaml` | header, hero, section settings, footer | rarely |
| `works.yaml` | work entries (featured, more, side) | per project |
| `notes.yaml` | notes and series | per post |

Layout, typography, colors, texture, photo treatment, section order, and per-tier rendering stay in code.

**Principle:** invalid config fails the build loudly. Nothing half-finished reaches the live site.

---

## Rendering rules

### Header
- Day of year, moon phase, and copyright year are **computed**, never read from config.
- `facts` rotates one per day, in order, wrapping around.

### Work (`works.yaml`)
- Only `published: true` entries render.
- **Featured:** exactly one entry, rendered as the expanded card with its `image` at full size.
- **More work:** compact rows (title, tagline, first summary paragraph, link), sorted by `order`. If an entry has an `image`, it renders as a small thumbnail. The subsection heading is hidden when there are no entries.
- **Side projects:** same compact row as "more work," under its own heading. Hidden when there are no entries.
- `disclosure`, when present, renders under the summary in every tier.

### Images (all files)
- Every image is an object with `src` and `alt`, plus optional `decorative` and `position`.
- `decorative: true` renders with `alt=""` so screen readers skip it. Use it only when adjacent text already says the same thing (e.g. the logo next to the brand name).
- `position` maps to CSS `object-position`. It controls cropping on narrow screens, which matters most for the hero photo.
- Images below the fold are lazy-loaded. The hero image is not.

### Notes (`notes.yaml`)
- A note is **visible** when `published: true` and `date` is today or earlier.
- The homepage shows up to `sections.notes.max_items` visible notes with `series: null`, newest first.
- Series notes appear only in the archive, labeled with their series.
- `enabled: auto` hides the whole section, heading included, when no visible main notes exist. **No placeholder text, ever.**

### Long-form pages (markdown)
- Notes, case studies, and standalone pages (`site.yaml → pages`) render from their `source` markdown file at their `url`.
- **YAML is the single source of truth for metadata** (title, date, series, published). Markdown files hold the body only, with no frontmatter, so metadata is never defined in two places.
- The markdown's top `#` heading renders as the page title. The page template does not add a second title from YAML.
- Typography: serif for body text; mono for code, labels, dates, and nav.
- Supported: headings, lists, tables, blockquotes, fenced code with syntax highlighting, images (relative to the markdown file or absolute site paths), and inline HTML for lucide icons (`<i data-lucide="…"></i>`).
- Notes show their date and series label under the title, taken from YAML.
- Images inside markdown follow the same image rules: they must exist and have alt text.

---

## Validation (build fails)

### All files
- Valid YAML that matches the expected structure. Unknown keys fail, which catches typos.
- Every published image `src` points to a file that exists. Missing files for unpublished drafts warn; supplied draft files are still validated.
- Every image has a non-empty `alt` unless `decorative: true`.
- Every published `source` markdown file exists, has no frontmatter, and starts with a `#` heading. Missing unpublished sources warn; existing draft Markdown must still meet the format rules.
- A published entry's markdown contains no `TODO`.
- No `TODO` anywhere in a published entry or in `site.yaml`.
- Every internal `url` resolves to an existing page. External URLs must start with `https://`.

### `site.yaml`
- Required: `header.brand`, `hero.name`, `hero.title`, at least one `hero.intro` line, `footer.copyright_name`.
- `sections.notes.enabled` is one of `true`, `false`, `auto`.
- `sections.notes.max_items` is a positive integer.

### `works.yaml`
- `slug` values are unique.
- `tier` is one of `featured`, `more`, `side`.
- **Exactly one** published entry has `tier: featured`.
- The featured entry has an `image`.
- Every published entry has `title`, `tagline`, at least one `summary` paragraph, and a `link`.
- `order` is an integer.

### `notes.yaml`
- `slug` values are unique.
- Published notes have a valid ISO `date` (YYYY-MM-DD) and a `url` whose page exists.
- `series` is `null` or a known series slug (currently: `basics`).

## Warnings (build passes, prints notice)
- An image file is over 500 KB (likely needs compressing).
- A markdown file's `#` heading differs from its YAML `title`. Sometimes this is intentional (e.g. a lowercase case study heading), but it's worth checking.
- A published note is scheduled for a future date.
- Two entries in the same tier share an `order` value.
