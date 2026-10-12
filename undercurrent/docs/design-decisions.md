# undercurrent: homepage design decisions

## Purpose

Undercurrent is both Jasmine Brooks-Beltran's portfolio and a genuinely useful product ecosystem.

The site should feel like an **editorial technical archive** rather than a SaaS landing page, agency portfolio, or conventional résumé site. The portfolio should demonstrate the same principle the work advocates: quiet systems that reduce unnecessary cognitive load.

The homepage narrative is:

**Human → strongest technical proof → additional useful work → ideas**

---

## Brand

### Name
**undercurrent**

### Tagline
**systems for a quieter life**

### Logo
Use the approved Undercurrent octopus mark exactly as provided.

Do not redraw, reinterpret, regenerate, or substitute the mark.

---

## Visual language

### Overall character
- editorial
- technical
- quiet
- tactile
- slightly archival
- contemporary without feeling trendy
- more museum catalogue / field notebook / technical publication than startup marketing page

### Background
Use a deep **Scientific Indigo**, not pure black.

The entire page should have a subtle **paper-like texture**:
- fine fibers / grain
- slight tonal variation
- low contrast
- no obvious grunge, scratches, distressed edges, or vintage effects
- texture should be felt more than noticed

### Color system
Suggested starting points; tune for contrast and cohesion rather than treating these as immutable hex values.

- Scientific Indigo background: around `#1B1729`, `#1D192B`, or `#201A30`
- warm cream / off-white text: around `#F1EEE7` or `#EAE6DD`
- muted lavender-gray secondary text / rules: around `#A8A1B2` or `#8F899A`
- Electric Moss accent: around `#B8F24A` or `#AEEA3A`

Do **not** default to pure black and white.

### Electric Moss usage
Electric Moss is an interaction color, not a decorative theme color.

Use sparingly for:
- hover underline
- active links
- focus states
- arrows
- tiny status indicators

Do not use it for large text blocks, section backgrounds, or decorative bands.

---

## Typography

Use two complementary modes:

### Structural / metadata typography
Use a modern mono or mono-adjacent face for:
- section labels
- nav
- dates
- telemetry
- metadata
- small utility text
- code

### Editorial typography
Use a readable serif for:
- long-form body text
- essay / case-study reading
- expressive hover states
- selected editorial emphasis

Important project and note titles may shift into an expressive italic treatment on hover, inspired by Unseen Studio.

Do not use italics on every link. Reserve the effect for important titles and editorial interactions.

Long-form pages should **not** be set in monospace. Serif body copy is the default.

---

## Header

The header contains:

- approved octopus logo
- `undercurrent`
- `systems for a quieter life`

Upper-right telemetry contains:

1. Lucide `calendar` icon + day of year, e.g. `285 / 365`
2. Lucide `moon-star` icon + current moon phase
3. Lucide `brain` icon + a short rotating octopus fact

Rules:
- day of year is computed
- moon phase is computed
- octopus facts come from config and rotate one per day
- each fact should explicitly say `octopus` or `octopuses`
- telemetry should feel like quiet margin information, not a separate content section

The header should be compact and restrained.

---

## 00 / Human

This is the personal introduction, not a résumé card.

### Content
**jasmine brooks-beltran**  
**data systems engineer**

> I build systems that quiet the problems you don't want to think about, so you have more space for the ones you do.

> Ten years in data systems: pipelines, orchestration, and the infrastructure underneath them.

Links:
- LinkedIn
- How to work with me

Do not include a GitHub/source link in this section.

Do not expose a personal email address yet. LinkedIn is the public contact path until a custom-domain email exists.

### Photo treatment
Use the provided latest black-and-white hillside photo as a **background texture for the Human section**, not as a standalone hero card.

The photo should:
- remain black and white
- keep Jasmine positioned toward the far right
- preserve the large field of landscape / negative space
- sit behind the Human copy
- be visible enough to add texture, but not dominate the page
- receive an indigo/dark overlay for legibility

Aim for the image to feel atmospheric rather than portrait-first.

On small screens, preserve readability first. Use a subtle dark gradient behind the text column if needed to maintain roughly 4.5:1 contrast.

---

## 01 / Work

Use a **hybrid hierarchy**, not accordions throughout.

### Featured work
Exactly one featured case study is always expanded and visible.

The current featured project is:

**pipelinetools**  
*the plumbing every pipeline kept rewriting*

Summary:

> A shared Python library for connectors, credentials, and environment config, so ETL pipelines stop carrying their own copies.

> A Python migration that meant hand-fixing 182 scripts showed why it matters: shared code should change once, not 182 times.

CTA:
**VIEW CASE STUDY ↗**

Visual:
Use the provided `pipelinetools-architecture.svg` prominently.

Important factual constraint:
The 182-script migration was fixed manually. PipelineTools did **not** perform that migration. The migration is evidence for why shared code matters, not an outcome of the library.

### More work
Professional work beyond the featured project should render as compact rows:
- title
- tagline
- first summary paragraph
- optional small thumbnail
- link

Do not expand inline.

### Side projects
Side projects use the same compact row pattern under their own heading.

Current side project:

**mindless meals**  
*cooking minus the extra thought*

> A small system for remembering and discovering simple meals.

> Designed and directed by me, built with AI coding agents.

CTA:
**VIEW PROJECT ↗**

Link directly to:
`https://meals.undercurrentlabs.dev/`

Mindless Meals is secondary to the featured technical case study.

If the portfolio grows and `side projects` becomes too limiting, the subsection can later be renamed to `more work`.

---

## 02 / Notes

Notes are Markdown-backed long-form pages rendered beautifully.

### Homepage behavior
Do not show placeholders or unpublished ideas publicly.

The entire Notes section should stay hidden until at least one real main note is published.

When visible:
- show up to three published main notes
- newest first
- typography-first layout
- no cards
- date + title + arrow
- expressive italic hover on titles
- `VIEW ARCHIVE →`

Series notes do not occupy homepage top slots.

### Planned topics
These are currently unpublished:
- What data organizations get wrong
- Ten years in data
- The digital basics everyone should know

The Basics material should eventually be treated as a series, e.g.:
`basics: what a database actually is`

### Long-form page treatment
Use:
- serif body copy
- mono for date, series, nav, code, and metadata
- generous margins
- narrow readable text column
- strong hierarchy
- images / diagrams allowed to break wider than the reading column when appropriate
- pull quotes and code blocks where useful

---

## Footer

Keep it minimal.

Content:

**undercurrent**  
**systems for a quieter life**

Links:
- LinkedIn
- How to work with me

Copyright:
`© 2026 jasmine brooks-beltran`
(year should be computed)

Maker's mark:
`designed by me · built with claude code & codex`

The maker's mark should be visually quiet and small. It should read as provenance, not AI branding.

---

## Layout principles

### Desktop
- asymmetric editorial grid
- generous negative space
- thin rules
- restrained section labels
- Human photo integrated into the section
- PipelineTools architecture clearly visible
- no giant marketing headline
- no card-heavy SaaS layout

### Mobile
- single column
- telemetry compresses cleanly
- Human text remains readable over the photo
- PipelineTools diagram scales without clipping
- compact work rows stack cleanly
- no horizontal page overflow
- maintain comfortable touch targets

---

## Interaction

Keep interaction subtle.

Use:
- expressive italic hover on important project / note titles
- Electric Moss for hover / focus / active accents
- slight arrow movement if desired
- clear focus states
- accessible native links and controls

Avoid:
- excessive animation
- parallax
- glowing effects
- decorative motion for its own sake
- interactions that hide essential content behind hover

---

## Content architecture

The site is content-driven.

### `site.yaml`
Owns:
- metadata
- header
- Human section
- page-level section settings
- standalone pages
- footer

### `works.yaml`
Owns:
- featured work
- more work
- side projects
- publication state
- project metadata

### `notes.yaml`
Owns:
- note metadata
- publication state
- scheduling
- series
- note URLs / source files

### Markdown
Owns:
- case-study body content
- note body content
- How to Work With Me body content

### Important separation
Content and publication state live in YAML / Markdown.

Layout, typography, color, paper texture, photo treatment, responsive behavior, and per-tier rendering stay in code.

Do not turn YAML into a page builder.

---

## Validation philosophy

Invalid config should fail loudly at build time.

The implementation should enforce the supplied `config-spec.md`, including:
- schema validation
- unknown keys fail
- required images / sources exist
- alt text requirements
- no TODOs in published content
- valid internal / external URLs
- exactly one published featured work item
- published notes require valid dates
- Markdown has no frontmatter
- Markdown begins with a `#` heading

Warnings may pass the build where specified by the config spec.

---

## Accessibility

Accessibility is part of the design, not a later pass.

Requirements:
- semantic HTML
- keyboard-accessible links and controls
- visible focus states
- decorative logo uses empty alt text
- meaningful images have useful alt text
- adequate contrast
- respect reduced-motion preferences
- images below the fold lazy-load
- hero/Human image does not lazy-load
- no essential information available only on hover

---

## Non-goals

Do not:
- redesign the approved logo
- replace Scientific Indigo with plain black
- make the page look like a generic SaaS site
- add dashboards, cards, chips, or badges without a clear need
- add decorative photography outside the Human section
- invent content not present in the provided YAML / Markdown
- duplicate case-study detail on the homepage
- make unpublished notes visible
- add a CMS or database unless explicitly requested
- move visual design controls into YAML
