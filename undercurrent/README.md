# undercurrent

Astro portfolio in the `another-pet-project` monorepo. This project is independent of Mindless Meals and does not connect to its production database or change its deployment.

## Run

Node 22.12 or newer:

```sh
cd undercurrent
npm install
npm test
npm run validate
npm run check
npm run build
npm run dev
```

Build output is static HTML in `dist/`. No deployment is included in this milestone.

## Content

- `config/site.yaml`: header, Human section, standalone pages, section settings, footer.
- `config/works.yaml`: featured, professional, and side-project entries.
- `config/notes.yaml`: note metadata and publication state.
- `content/**/*.md`: long-form bodies, starting with one H1 and without frontmatter.
- `public/images/`: absolute site images. Relative Markdown images may live beside their Markdown source and are bundled by Vite.

All metadata is read from YAML. Components contain presentation logic only. New entries need no new component or route file. Known note series are `basics`; expanding that controlled vocabulary requires updating the validator and type declaration.

Notes are published only when `published: true` and their date has arrived in America/New_York. Series notes appear in `/notes`, but do not take homepage slots. This is a static site: scheduled notes require a rebuild on or after their date. Telemetry and footer year refresh in the browser so those stay current between builds; moon phase is approximate.

Validation runs on build and development startup, and the development server restarts on content changes. It rejects unknown keys, invalid fields, broken source/image paths, invalid dates/series, publication errors, broken internal links, insecure external URLs, duplicate routes/slugs, missing alt text, frontmatter, and public TODOs. It prints the specified warnings. Missing files for unpublished entries print warnings. Existing draft files still undergo validation; publishing an entry requires all its referenced files. See `docs/config-spec.md`.

## Supplied assets and draft inputs

The approved logo, supplied hillside photograph (converted from HEIC to a compressed JPEG), and original PipelineTools architecture SVG are integrated. The latest How to Work With Me copy and the Disputes and Hot Parts draft case studies are included. The optional Mindless Meals thumbnail is omitted until a real screenshot is supplied.

These unpublished inputs remain missing and produce warnings:

```text
public/images/disputes-architecture.svg
public/images/hot-parts-architecture.svg
public/images/cash-bonus-architecture.svg
content/work/cash-bonus.md
content/notes/what-data-organizations-get-wrong.md
content/notes/ten-years-in-data.md
content/notes/digital-basics.md
```

Drafts remain hidden. No replacement diagrams or note bodies have been invented.

## Visual review

For visual review, verify the homepage and both supplied long-form pages at 320, 390, 768, and 1440 px. Check Human contrast/crop, diagram legibility, image loading, keyboard focus/skip link, mobile overflow, and reduced motion. The real homepage was checked at 320, 390, 768, and 1440 px: no page overflow, all images loaded, and Notes stayed hidden. The two published long-form pages render one H1 each; the PipelineTools SVG and inline Lucide icons load. Keyboard navigation reaches the skip link with a visible focus outline. Human crop and contrast were visually reviewed on desktop and mobile.

## Validation tests

`npm test` runs isolated fixtures. They exercise valid content, publication/date filtering, order/count rules, invalid data, missing files, URLs, Markdown/HTML images, YAML parsing, and telemetry boundaries. Fixture files are temporary and never enter published content.

`npm run test:build` builds and type-checks a separate, temporary fixture application to verify Astro integration without weakening real-content validation. It does not establish visual readiness for the actual homepage.
