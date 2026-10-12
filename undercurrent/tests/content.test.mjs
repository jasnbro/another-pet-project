import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { stringify } from 'yaml';
import { validateContent, notesState, pageEntries, loadContent } from '../src/lib/content.mjs';
import { telemetry } from '../src/lib/telemetry.mjs';

const now = new Date('2026-10-12T18:00:00Z');
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'undercurrent-test-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const put = (path, value) => { const p = join(root, path); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, value); };
  // These assets are test-only: never copied into the application content.
  put('public/images/test.svg', '<svg xmlns="http://www.w3.org/2000/svg"></svg>');
  const image = { src: '/images/test.svg', alt: 'Test diagram' };
  const logo = { ...image, decorative: true, alt: '' };
  const page = { slug: 'about', title: 'About', url: '/about', source: 'content/pages/about.md' };
  const work = { slug: 'test-work', title: 'Test work', tagline: 'Test tagline', tier: 'featured', order: 1, published: true, summary: ['Test summary'], link: { label: 'Read', url: '/work/test-work' }, source: 'content/work/test-work.md', image };
  const note = (slug, published, date, series = null) => ({ slug, title: slug, published, date, series, url: `/notes/${slug}`, source: `content/notes/${slug}.md` });
  const data = {
    site: {
      meta: { title: 'Test site', description: 'Test description' },
      header: { brand: 'Test site', tagline: 'Test tagline', logo, telemetry: { day_of_year: true, moon_phase: true, facts: ['an octopus has no bones'] } },
      hero: { label: '00 / human', name: 'Test name', title: 'Test role', image, intro: ['Test introduction'], links: [{ label: 'About', url: '/about' }] },
      pages: [page], sections: { work: { label: '01 / work', enabled: true }, notes: { label: '02 / notes', enabled: 'auto', max_items: 2, archive: { label: 'Archive', url: '/notes' } } },
      footer: { brand: 'Test site', tagline: 'Test tagline', logo, links: [], copyright_name: 'Test name', credits: 'Test credits' }
    }, works: [work], notes: [note('draft', false, null), note('future', true, '2026-10-13'), note('series-only', true, '2026-10-12', 'basics')]
  };
  for (const p of [page, work, ...data.notes]) put(p.source, `# ${p.title}\n\nTest body.\n`);
  return { root, put, data, validate: () => validateContent(data, root, now) };
}

test('complete valid content passes; draft/future pages are excluded; series stays off homepage', t => {
  const f = fixture(t), content = f.validate();
  const state = notesState(content, now);
  assert.equal(state.enabled, false);
  assert.deepEqual(state.visible.map(n => n.slug), ['series-only']);
  assert.deepEqual(state.main, []);
  assert.deepEqual(pageEntries(content, now).map(p => p.url), ['/about', '/work/test-work', '/notes/series-only']);
  assert.ok(content.warnings.some(w => w.includes('scheduled')));
});
test('published main notes sort newest-first, obey max_items, and enable auto', t => {
  const f = fixture(t);
  f.data.notes[0].published = true; f.data.notes[0].date = '2026-10-11';
  f.data.notes[1].date = '2026-10-12'; f.data.site.sections.notes.max_items = 1;
  const state = notesState(f.validate(), now);
  assert.equal(state.enabled, true); assert.deepEqual(state.main.map(n => n.slug), ['future']);
  f.data.site.sections.notes.enabled = false; assert.equal(notesState(f.validate(), now).enabled, false);
});
for (const [label, mutate, pattern] of [
  ['unknown nested keys', f => { f.data.site.hero.typo = true; }, /unknown key/],
  ['missing required fields', f => { delete f.data.site.hero.title; }, /required field/],
  ['empty hero introduction', f => { f.data.site.hero.intro = []; }, /at least/],
  ['noninteger work order', f => { f.data.works[0].order = 1.5; }, /integer/],
  ['invalid tier', f => { f.data.works[0].tier = 'card'; }, /featured, more, or side/],
  ['invalid notes enabled', f => { f.data.site.sections.notes.enabled = 'yes'; }, /true, false, or auto/],
  ['nonpositive note count', f => { f.data.site.sections.notes.max_items = 0; }, /positive/],
  ['zero featured work', f => { f.data.works[0].published = false; }, /exactly one/],
  ['multiple featured work', f => { const w = structuredClone(f.data.works[0]); w.slug = 'another'; delete w.source; w.link.url = 'https://example.com/'; f.data.works.push(w); }, /exactly one/],
  ['featured image required', f => { delete f.data.works[0].image; }, /requires an image/],
  ['duplicate slugs', f => { f.data.notes.push(structuredClone(f.data.notes[0])); }, /duplicate slug/],
  ['unknown series', f => { f.data.notes[0].series = 'other'; }, /null or basics/],
  ['invalid calendar date', f => { f.data.notes[1].date = '2026-02-30'; }, /real ISO date/],
  ['missing published date', f => { f.data.notes[1].date = null; }, /real ISO date/],
  ['published TODO metadata', f => { f.data.works[0].summary = ['TODO']; }, /TODO/],
  ['site TODO', f => { f.data.site.meta.description = 'TODO'; }, /TODO/],
  ['published Markdown TODO', f => f.put('content/pages/about.md', '# About\n\nTODO'), /TODO/],
  ['frontmatter', f => f.put('content/pages/about.md', '---\ntitle: About\n---\n# About'), /frontmatter/],
  ['missing H1', f => f.put('content/pages/about.md', '## About'), /start with an H1/],
  ['missing image', f => { f.data.site.hero.image = { src: '/images/missing.jpg', alt: 'Missing' }; }, /missing file/],
  ['missing alt', f => { f.data.site.hero.image = { src: '/images/test.svg', alt: '' }; }, /non-empty/],
  ['decorative image alt', f => { f.data.site.header.logo = { src: '/images/test.svg', alt: 'Logo', decorative: true }; }, /empty alt/],
  ['HTTP external links', f => { f.data.site.hero.links[0].url = 'http://example.com'; }, /https/],
  ['protocol-relative links', f => { f.data.site.hero.links[0].url = '//example.com'; }, /https/],
  ['broken internal links', f => { f.data.site.hero.links[0].url = '/missing'; }, /no published page/],
  ['public link to draft', f => { f.data.site.hero.links[0].url = '/notes/draft'; }, /no published page/],
  ['route collision', f => { f.data.works[0].link.url = '/about'; }, /duplicate or reserved/],
  ['path traversal', f => { f.data.site.hero.image = { src: '/../outside.svg', alt: 'Outside' }; }, /escapes/],
  ['missing Markdown image', f => f.put('content/pages/about.md', '# About\n\n![Description](missing.svg)'), /missing file/],
  ['Markdown image alt', f => f.put('content/pages/about.md', '# About\n\n![](/images/test.svg)'), /requires alt/],
  ['Markdown reference image alt', f => f.put('content/pages/about.md', '# About\n\n![][diagram]\n\n[diagram]: /images/test.svg'), /requires alt/],
  ['HTML image alt', f => f.put('content/pages/about.md', '# About\n\n<img src="/images/test.svg">'), /requires alt/],
  ['Markdown internal link', f => f.put('content/pages/about.md', '# About\n\n[Read](/missing)'), /no published page/],
  ['fact missing octopus', f => { f.data.site.header.telemetry.facts = ['has three hearts']; }, /mention octopus/]
]) test(`rejects ${label}`, t => { const f = fixture(t); mutate(f); assert.throws(f.validate, pattern); });
test('draft TODOs are allowed; mismatched H1, duplicate order, and large images warn', t => {
  const f = fixture(t);
  f.put(f.data.notes[0].source, '# Different heading\n\nTODO');
  f.put('public/images/test.svg', Buffer.alloc(512001));
  const w = structuredClone(f.data.works[0]); w.slug = 'draft-work'; w.published = false; w.link.url = 'https://example.com'; delete w.source; f.data.works.push(w);
  const warnings = f.validate().warnings;
  assert.ok(warnings.some(w => w.includes('differs'))); assert.ok(warnings.some(w => w.includes('500 KB'))); assert.ok(warnings.some(w => w.includes('duplicate order')));
});
test('Markdown fenced code is not mistaken for a broken image', t => {
  const f = fixture(t); f.put('content/pages/about.md', '# About\n\n```md\n![fake](missing.svg)\n```'); f.validate();
});
test('YAML loader rejects duplicate keys and malformed indentation', t => {
  const f = fixture(t);
  for (const [name, data] of [['site', f.data.site], ['works', { works: f.data.works }], ['notes', { notes: f.data.notes }]]) f.put(`config/${name}.yaml`, stringify(data));
  assert.equal(loadContent(f.root, now).works.length, 1);
  f.put('config/notes.yaml', 'notes: []\nnotes: []\n'); assert.throws(() => loadContent(f.root, now), /unique|duplicate/i);
  f.put('config/notes.yaml', 'notes:\n  - slug: a\n   - slug: b\n'); assert.throws(() => loadContent(f.root, now));
});
test('telemetry computes leap years and rotates deterministically across local midnight', () => {
  const facts = ['octopus A', 'octopus B', 'octopus C'];
  const a = telemetry(facts, new Date('2024-12-31T18:00:00Z')); assert.equal(a.dayNumber, 366); assert.equal(a.daysInYear, 366);
  const b = telemetry(facts, now); assert.equal(b.dayNumber, 285); assert.equal(b.daysInYear, 365);
  assert.equal(telemetry(facts, new Date('2026-10-13T03:59:00Z')).fact, b.fact);
  assert.notEqual(telemetry(facts, new Date('2026-10-13T04:00:00Z')).fact, b.fact);
});

test('missing draft files warn; publishing the same entry requires its files', t => {
  const f = fixture(t);
  rmSync(join(f.root, f.data.notes[0].source));
  const draft = structuredClone(f.data.works[0]);
  draft.slug = 'draft-work'; draft.published = false; draft.tier = 'more';
  draft.source = 'content/work/draft-work.md'; draft.link.url = '/work/draft-work';
  draft.image = { src: '/images/draft.svg', alt: 'Draft diagram' };
  f.data.works.push(draft);
  assert.equal(f.validate().warnings.filter(w => w.includes('draft file not supplied')).length, 3);
  draft.published = true;
  assert.throws(f.validate, /missing file public\/images\/draft.svg/);
  draft.published = false; draft.image.src = '/../outside.svg';
  assert.throws(f.validate, /escapes/);
});
