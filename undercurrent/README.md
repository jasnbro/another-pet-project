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

Validation runs on build and development startup, and the development server restarts on content changes. It rejects unknown keys, invalid fields, broken source/image paths, invalid dates/series, publication errors, broken internal links, insecure external URLs, duplicate routes/slugs, missing alt text, frontmatter, and public TODOs. It prints the specified warnings. Draft entries remain subject to file-existence checks, as required by the config spec.

## Current asset/content blockers

The implementation keeps the supplied content and approved logo PNGs. The build intentionally fails until every file referenced by that content exists. No replacement photos, diagrams, case studies, or note bodies have been invented.

Supply these exact files:

```text
public/images/hero-hillside.jpg
public/images/pipelinetools-architecture.svg
public/images/mindless-meals-home.png
public/images/disputes-architecture.svg
public/images/hot-parts-architecture.svg
public/images/cash-bonus-architecture.svg
content/work/disputes-refactor.md
content/work/hot-parts.md
content/work/cash-bonus.md
content/notes/what-data-organizations-get-wrong.md
content/notes/ten-years-in-data.md
content/notes/digital-basics.md
```

The Library contains `pipelinetools-architecture.jpeg`, but the contract requests the supplied SVG. It has not been substituted or traced. The mockup is visual guidance, not a substitute for its original photo or diagram files. The mockup's example notes have not been published.

If the intended rule is to allow missing files for unpublished entries, change the config contract first; this implementation does not silently relax it.

## Visual review

Once required files are supplied and the build passes, verify the homepage and both supplied long-form pages at 320, 390, 768, and 1440 px. Check Human contrast/crop, diagram legibility, image loading, keyboard focus/skip link, mobile overflow, and reduced motion. The source has responsive rules and accessibility treatments, but browser verification with the real assets is still pending.

## Validation tests

`npm test` runs isolated fixtures. They exercise valid content, publication/date filtering, order/count rules, invalid data, missing files, URLs, Markdown/HTML images, YAML parsing, and telemetry boundaries. Fixture files are temporary and never enter published content.

`npm run test:build` builds and type-checks a separate, temporary fixture application to verify Astro integration without weakening real-content validation. It does not establish visual readiness for the actual homepage.
