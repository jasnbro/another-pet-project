# Codex implementation prompt: undercurrent

You are implementing the Undercurrent portfolio site.

Before coding, read all files I provide, especially:

- `design-decisions.md`
- `config-spec.md`
- `site.yaml`
- `works.yaml`
- `notes.yaml`
- the approved octopus logo asset
- the Human hillside photo
- `pipelinetools-architecture.svg`
- all Markdown content files
- any existing application / repository files

Treat `design-decisions.md` as the visual and product-design contract and `config-spec.md` as the content/rendering contract.

## Goal

Build the Undercurrent homepage and its supporting long-form page system so that routine content changes can be made through YAML and Markdown without editing application code.

The site should feel like an editorial technical archive: quiet, tactile, thoughtful, and technically credible.

Do not redesign the product. Implement the documented decisions.

## First milestone

Deliver a working implementation with:

1. homepage rendered from the YAML config
2. `00 / human`
3. `01 / work`
4. conditional `02 / notes`
5. Markdown-backed long-form pages
6. config validation
7. responsive behavior
8. accessibility
9. the documented visual system

Do not continue adding speculative features after this milestone. Stop when the implementation is ready for visual review.

## Content architecture

Use these files as the content API:

- `site.yaml` — header, Human section, section settings, standalone pages, footer
- `works.yaml` — featured, more, and side-project work entries
- `notes.yaml` — note metadata, publication state, dates, series, URLs, and Markdown source paths
- Markdown — long-form body content only

YAML is the single source of truth for metadata.

Markdown files must not require frontmatter.

Do not hardcode PipelineTools, Mindless Meals, note titles, URLs, or Human copy into UI components.

Components should render generic content types such as featured work, compact work rows, notes, and standalone pages.

## Validation

Implement the validation rules in `config-spec.md`.

Validation should run during build / development startup and fail loudly for invalid content.

Prefer a typed schema solution appropriate to the existing stack.

At minimum:
- reject unknown YAML keys
- validate required fields
- verify image and Markdown source paths
- enforce image alt rules
- enforce publication rules
- reject TODOs in published content and in `site.yaml`
- validate internal and external URLs
- enforce exactly one published featured work item
- enforce valid note dates
- ensure Markdown has no frontmatter and starts with an H1

Do not silently ignore malformed content.

## Homepage

### Header

Render:
- approved octopus logo
- `undercurrent`
- tagline from config

Render telemetry in the upper-right using Lucide icons:
- `calendar` — day of year
- `moon-star` — current moon phase
- `brain` — rotating octopus fact

Day of year, moon phase, and copyright year are computed.

Octopus facts come from `site.yaml` and rotate one per day in a deterministic order.

### 00 / Human

Render from `site.yaml`.

Use the provided black-and-white hillside photo as the background of the Human section.

The photo is atmospheric texture, not a conventional full-width personal-brand hero.

Preserve Jasmine toward the right side of the crop and place copy where the image is quieter.

Use a dark/indigo overlay or subtle text-column gradient where necessary for contrast.

The Human section must remain readable on mobile.

### 01 / Work

Render one published `featured` work item as an always-expanded featured case study preview.

For PipelineTools, use the configured architecture SVG prominently.

Render `more` and `side` entries as compact rows. Do not use accordions.

Compact rows include:
- title
- tagline
- first summary paragraph
- disclosure when present
- optional small thumbnail
- CTA

Do not duplicate the full case study on the homepage.

### 02 / Notes

Honor `sections.notes.enabled`.

For `auto`, hide the entire section if no visible main note exists.

A visible note:
- is `published: true`
- has a date today or earlier

Homepage notes:
- exclude series notes
- newest first
- max count from config
- typography-first rows, not cards

Unpublished note ideas must not appear.

## Long-form pages

Render case studies, notes, and standalone pages from Markdown.

Use the URL and source mappings from YAML.

Typography:
- serif body
- mono for labels, nav, dates, code, and metadata

Support the Markdown features documented in `config-spec.md`.

Do not generate a second page title if the Markdown already begins with `#`.

For notes, show date and series metadata from YAML.

## Visual system

Follow `design-decisions.md`.

Critical points:
- Scientific Indigo, not pure black
- warm cream text
- muted lavender-gray metadata / rules
- Electric Moss only as a restrained interactive accent
- subtle paper texture across the entire page
- no SaaS-style card grid
- thin rules
- generous negative space
- mono for structure
- serif for editorial reading
- expressive italic hover treatment for important project / note titles

Use the supplied approved octopus logo. Do not redraw it.

## Accessibility and responsive behavior

Implement:
- semantic HTML
- keyboard accessibility
- visible focus states
- meaningful alt text
- decorative image handling
- strong color contrast
- reduced-motion support
- no essential hover-only information
- lazy-loading for below-the-fold images
- no lazy-loading for the Human background image
- no page-level horizontal overflow at mobile widths

Test the Human image/text contrast on narrow screens. Add a subtle dark gradient if needed.

## Footer

Render footer content from `site.yaml`.

Keep the maker's mark visually understated:

`designed by me · built with claude code & codex`

## Implementation discipline

Before changing the architecture:
1. inspect the existing repository
2. reuse the existing stack and conventions where reasonable
3. avoid introducing heavy dependencies without a clear need
4. avoid building a CMS, database, or admin UI
5. keep content concerns separate from visual concerns

Do not move layout, color, spacing, typography, texture, responsive behavior, or tier rendering into YAML.

Do not invent missing content.

If a required file or asset is missing, report exactly what is missing instead of substituting a placeholder.

## Quality bar

The result should:
- look intentional at desktop and mobile sizes
- feel like one cohesive editorial system
- make Jasmine's technical credibility obvious within seconds
- keep PipelineTools as the strongest visible proof
- preserve the quieter, more personal Undercurrent identity
- allow new work and notes to be added without modifying rendering components

## Before you finish

Run the project's available checks and add appropriate checks where missing.

Verify:
- config validation fails on bad data
- current config passes
- all published links resolve appropriately
- images load
- PipelineTools architecture SVG renders
- Mindless Meals points to its configured external URL
- Notes remain hidden while no note is published
- responsive layout works at common mobile and desktop widths
- keyboard navigation and focus states work

Then provide:
1. a concise implementation summary
2. files changed
3. commands/tests run and their result
4. any unresolved issue that genuinely requires a design/product decision

Do not make additional design decisions on my behalf.
