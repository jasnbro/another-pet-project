import { readFileSync, existsSync, statSync, realpathSync } from 'node:fs';
import { resolve, relative, sep } from 'node:path';
import { parseDocument } from 'yaml';
import { todayISO } from './dates.mjs';
export { todayISO } from './dates.mjs';

// npm/Astro commands run from the project root. import.meta.url would point
// inside dist after bundling, so it cannot locate source YAML during prerender.
const projectRoot = process.cwd();
export const validDate = (value) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
export const visibleNotes = (notes, now = new Date()) => notes
  .filter(n => n.published && validDate(n.date) && n.date <= todayISO(now))
  .sort((a, b) => b.date.localeCompare(a.date) || a.slug.localeCompare(b.slug));
export function notesState({ site, notes }, now = new Date()) {
  const visible = visibleNotes(notes, now);
  const main = visible.filter(n => n.series === null).slice(0, site.sections.notes.max_items);
  return { visible, main, enabled: site.sections.notes.enabled === true || (site.sections.notes.enabled === 'auto' && main.length > 0) };
}
export function pageEntries({ site, works, notes }, now = new Date()) {
  return [
    ...site.pages.map(p => ({ ...p, kind: 'page' })),
    ...works.filter(w => w.published && w.source).map(w => ({ ...w, url: w.link.url, kind: 'work' })),
    ...visibleNotes(notes, now).map(n => ({ ...n, kind: 'note' }))
  ];
}

// A strict, dependency-light runtime schema. The adjacent declaration defines
// the same content API for Astro/TypeScript; validation never drops unknown keys.
export function validateContent(data, root = projectRoot, now = new Date()) {
  const errors = [], warnings = [], sources = [], images = [], urls = [];
  const err = (path, message) => errors.push(`${path}: ${message}`);
  const text = (v, p, empty = false) => {
    if (typeof v !== 'string' || (!empty && !v.trim())) err(p, 'must be a non-empty string');
  };
  const bool = (v, p) => { if (typeof v !== 'boolean') err(p, 'must be a boolean'); };
  const integer = (v, p, positive = false) => { if (!Number.isInteger(v) || (positive && v < 1)) err(p, 'must be ' + (positive ? 'a positive ' : 'an ') + 'integer'); };
  const object = (v, p, keys, required = keys) => {
    if (!v || typeof v !== 'object' || Array.isArray(v)) { err(p, 'must be an object'); return false; }
    for (const k of Object.keys(v)) if (!keys.includes(k)) err(`${p}.${k}`, 'unknown key');
    for (const k of required) if (!(k in v)) err(`${p}.${k}`, 'required field is missing');
    return true;
  };
  const array = (v, p, each, min = 0) => {
    if (!Array.isArray(v)) { err(p, 'must be an array'); return; }
    if (v.length < min) err(p, `requires at least ${min} item(s)`);
    v.forEach((item, i) => each(item, `${p}[${i}]`));
  };
  const link = (v, p) => {
    if (!object(v, p, ['label', 'url'])) return;
    text(v.label, `${p}.label`); text(v.url, `${p}.url`); urls.push({ value: v.url, path: `${p}.url`, active: true });
  };
  const image = (v, p, published = true) => {
    if (!object(v, p, ['src', 'alt', 'decorative', 'position'], ['src', 'alt'])) return;
    text(v.src, `${p}.src`); text(v.alt, `${p}.alt`, v.decorative === true);
    if ('decorative' in v) bool(v.decorative, `${p}.decorative`);
    if (v.decorative && v.alt !== '') err(`${p}.alt`, 'decorative images must use an empty alt');
    if ('position' in v) {
      text(v.position, `${p}.position`);
      if (typeof v.position === 'string' && !/^(?:left|right|top|bottom|center|\d+(?:\.\d+)?%)(?:\s+(?:left|right|top|bottom|center|\d+(?:\.\d+)?%)){0,3}$/.test(v.position)) err(`${p}.position`, 'invalid object-position');
    }
    images.push({ value: v.src, path: `${p}.src`, base: 'public', published });
  };
  const noTODO = (v, p) => { if (/TODO/i.test(JSON.stringify(v))) err(p, 'TODO is not allowed in public content'); };
  const slug = (v, p) => { text(v, p); if (typeof v === 'string' && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(v)) err(p, 'must be a lowercase hyphenated slug'); };
  const source = (value, p, title, published) => { text(value, p); sources.push({ value, path: p, title, published }); };
  const unique = (items, p) => {
    if (!Array.isArray(items)) return;
    const seen = new Set();
    for (const item of items) { if (seen.has(item?.slug)) err(p, `duplicate slug ${item?.slug}`); seen.add(item?.slug); }
  };
  object(data, 'content', ['site', 'works', 'notes']);
  const site = data?.site ?? {}, works = data?.works ?? [], notes = data?.notes ?? [];
  if (object(site, 'site', ['meta', 'header', 'hero', 'pages', 'sections', 'footer'])) {
    noTODO(site, 'site');
    if (object(site.meta, 'site.meta', ['title', 'description'])) { text(site.meta.title, 'site.meta.title'); text(site.meta.description, 'site.meta.description'); }
    if (object(site.header, 'site.header', ['brand', 'tagline', 'logo', 'telemetry'])) {
      text(site.header.brand, 'site.header.brand'); text(site.header.tagline, 'site.header.tagline'); image(site.header.logo, 'site.header.logo');
      const t = site.header.telemetry;
      if (object(t, 'site.header.telemetry', ['day_of_year', 'moon_phase', 'facts'])) {
        bool(t.day_of_year, 'site.header.telemetry.day_of_year'); bool(t.moon_phase, 'site.header.telemetry.moon_phase');
        array(t.facts, 'site.header.telemetry.facts', (v, p) => { text(v, p); if (typeof v === 'string' && !/\boctopus(?:es)?\b/i.test(v)) err(p, 'must explicitly mention octopus or octopuses'); }, 1);
      }
    }
    if (object(site.hero, 'site.hero', ['label', 'name', 'title', 'image', 'intro', 'links'])) {
      for (const k of ['label', 'name', 'title']) text(site.hero[k], `site.hero.${k}`);
      image(site.hero.image, 'site.hero.image'); array(site.hero.intro, 'site.hero.intro', text, 1); array(site.hero.links, 'site.hero.links', link);
    }
    array(site.pages, 'site.pages', (v, p) => {
      if (!object(v, p, ['slug', 'title', 'url', 'source'])) return;
      slug(v.slug, `${p}.slug`); text(v.title, `${p}.title`); text(v.url, `${p}.url`);
      urls.push({ value: v.url, path: `${p}.url`, active: true }); source(v.source, `${p}.source`, v.title, true);
    });
    unique(site.pages, 'site.pages');
    if (object(site.sections, 'site.sections', ['work', 'notes'])) {
      if (object(site.sections.work, 'site.sections.work', ['label', 'enabled'])) { text(site.sections.work.label, 'site.sections.work.label'); bool(site.sections.work.enabled, 'site.sections.work.enabled'); }
      const n = site.sections.notes;
      if (object(n, 'site.sections.notes', ['label', 'enabled', 'max_items', 'archive'])) {
        text(n.label, 'site.sections.notes.label');
        if (![true, false, 'auto'].includes(n.enabled)) err('site.sections.notes.enabled', 'must be true, false, or auto');
        integer(n.max_items, 'site.sections.notes.max_items', true); link(n.archive, 'site.sections.notes.archive');
      }
    }
    if (object(site.footer, 'site.footer', ['brand', 'tagline', 'logo', 'links', 'copyright_name', 'credits'])) {
      for (const k of ['brand', 'tagline', 'copyright_name', 'credits']) text(site.footer[k], `site.footer.${k}`);
      image(site.footer.logo, 'site.footer.logo'); array(site.footer.links, 'site.footer.links', link);
    }
  }
  array(works, 'works', (w, p) => {
    if (!object(w, p, ['slug', 'title', 'tagline', 'tier', 'order', 'published', 'summary', 'link', 'source', 'image', 'disclosure'], ['slug', 'title', 'tagline', 'tier', 'order', 'published', 'summary', 'link'])) return;
    slug(w.slug, `${p}.slug`); text(w.title, `${p}.title`); text(w.tagline, `${p}.tagline`);
    if (!['featured', 'more', 'side'].includes(w.tier)) err(`${p}.tier`, 'must be featured, more, or side');
    integer(w.order, `${p}.order`); bool(w.published, `${p}.published`); array(w.summary, `${p}.summary`, text, 1);
    if (object(w.link, `${p}.link`, ['label', 'url'])) { text(w.link.label, `${p}.link.label`); text(w.link.url, `${p}.link.url`); urls.push({ value: w.link.url, path: `${p}.link.url`, active: w.published }); }
    if (w.source !== undefined) source(w.source, `${p}.source`, w.title, w.published);
    if (w.image !== undefined) image(w.image, `${p}.image`, w.published);
    if (w.disclosure !== undefined) text(w.disclosure, `${p}.disclosure`);
    if (w.tier === 'featured' && !w.image) err(`${p}.image`, 'featured work requires an image');
    if (w.published) noTODO(w, p);
  });
  unique(works, 'works');
  if (Array.isArray(works) && works.filter(w => w?.published && w?.tier === 'featured').length !== 1) err('works', 'requires exactly one published featured entry');
  for (const tier of ['featured', 'more', 'side']) {
    const orders = new Set();
    for (const w of Array.isArray(works) ? works.filter(w => w?.tier === tier) : []) {
      if (orders.has(w.order)) warnings.push(`works.${w.slug}: duplicate order ${w.order} in ${tier}`);
      orders.add(w.order);
    }
  }
  array(notes, 'notes', (n, p) => {
    if (!object(n, p, ['slug', 'title', 'date', 'series', 'published', 'url', 'source'])) return;
    slug(n.slug, `${p}.slug`); text(n.title, `${p}.title`); bool(n.published, `${p}.published`);
    if (n.series !== null && n.series !== 'basics') err(`${p}.series`, 'must be null or basics');
    if ((n.published || n.date !== null) && !validDate(n.date)) err(`${p}.date`, 'must be a real ISO date (YYYY-MM-DD)');
    text(n.url, `${p}.url`); urls.push({ value: n.url, path: `${p}.url`, active: n.published && validDate(n.date) && n.date <= todayISO(now) });
    source(n.source, `${p}.source`, n.title, n.published);
    if (n.published) { noTODO(n, p); if (n.date > todayISO(now)) warnings.push(`${p}: scheduled for ${n.date}; hidden until that date (rebuild to publish)`); }
  });
  unique(notes, 'notes');

  const safeFile = (value, base, p, allowMissing = false) => {
    if (typeof value !== 'string') return null;
    if (base === 'public' && (!value.startsWith('/') || value.startsWith('//'))) { err(p, 'must be an absolute site asset path'); return null; }
    const clean = base === 'public' ? value.slice(1) : value;
    if (clean.includes('\\') || clean.includes('\0') || (base !== 'public' && clean.startsWith('/'))) { err(p, 'invalid local path'); return null; }
    const boundary = resolve(root, base), file = resolve(boundary, clean);
    const inside = (f) => { const r = relative(boundary, f); return r !== '..' && !r.startsWith('..' + sep) && !r.startsWith(sep); };
    if (!inside(file)) { err(p, 'path escapes its content directory'); return null; }
    if (!existsSync(file) && allowMissing) { warnings.push(`${p}: draft file not supplied: ${base === 'public' ? 'public/' + clean : clean}`); return null; }
    if (!existsSync(file) || !statSync(file).isFile()) { err(p, `missing file ${base === 'public' ? 'public/' + clean : clean}`); return null; }
    const realBoundary = realpathSync(boundary);
    const realRelative = relative(realBoundary, realpathSync(file));
    if (realRelative === '..' || realRelative.startsWith('..' + sep) || realRelative.startsWith(sep)) { err(p, 'symlink escapes its content directory'); return null; }
    return file;
  };
  const routeKey = v => typeof v === 'string' ? v.replace(/\/$/, '') || '/' : '';
  const allEntries = [
    ...(Array.isArray(site.pages) ? site.pages : []),
    ...(Array.isArray(works) ? works.filter(w => w?.source).map(w => ({ ...w, url: w.link?.url })) : []),
    ...(Array.isArray(notes) ? notes : [])
  ];
  const allRoutes = new Set(['/', '/notes']);
  for (const entry of allEntries) {
    const key = routeKey(entry?.url);
    if (!key.startsWith('/') || key.startsWith('//') || /[?#]/.test(key)) err(`route.${entry?.slug}`, 'Markdown pages require a clean internal URL');
    if (allRoutes.has(key)) err(`route.${entry?.slug}`, `duplicate or reserved URL ${key}`);
    allRoutes.add(key);
  }
  const publicRoutes = new Set(['/', '/notes',
    ...(Array.isArray(site.pages) ? site.pages.map(p => routeKey(p.url)) : []),
    ...(Array.isArray(works) ? works.filter(w => w?.published && w?.source).map(w => routeKey(w.link?.url)) : []),
    ...(Array.isArray(notes) ? visibleNotes(notes, now).map(n => routeKey(n.url)) : [])
  ]);
  const checkURL = ({ value, path, active }) => {
    if (typeof value !== 'string') return;
    if (value.startsWith('/') && !value.startsWith('//')) {
      if (/[\\\s]/.test(value) || /(?:^|\/)\.\.(?:\/|$)/.test(value)) err(path, 'invalid internal URL');
      else if (!(active ? publicRoutes : allRoutes).has(routeKey(value.split(/[?#]/)[0]))) err(path, `internal URL has no ${active ? 'published ' : ''}page: ${value}`);
    } else {
      try { const u = new URL(value); if (u.protocol !== 'https:' || !u.hostname || u.username || u.password) throw new Error(); }
      catch { err(path, 'external URL must be a valid https:// URL'); }
    }
  };
  urls.forEach(checkURL);
  for (const im of images) {
    const f = safeFile(im.value, im.base, im.path, im.published === false);
    if (f && statSync(f).size > 500 * 1024) warnings.push(`${im.path}: image exceeds 500 KB`);
  }
  for (const s of sources) {
    if (typeof s.value === 'string' && (!s.value.startsWith('content/') || !s.value.endsWith('.md'))) err(s.path, 'source must be content/**/*.md');
    const f = safeFile(s.value, '.', s.path, s.published === false); if (!f) continue;
    const md = readFileSync(f, 'utf8').replace(/^\uFEFF/, '');
    if (/^\s*(?:---|\+\+\+)\s*\n/.test(md)) err(s.path, 'Markdown must not have frontmatter');
    if (!/^# [^\n]+/.test(md)) err(s.path, 'Markdown must start with an H1');
    const heading = md.match(/^# (.+)/)?.[1].trim();
    if (heading && heading !== s.title) warnings.push(`${s.path}: H1 "${heading}" differs from YAML title "${s.title}"`);
    if (s.published && /TODO/i.test(md)) err(s.path, 'published Markdown contains TODO');
    // Strip fenced code before finding Markdown/HTML assets and links.
    const body = md.replace(/(^|\n)(`{3,}|~{3,})[^\n]*\n[\s\S]*?\n\2[^\n]*(?=\n|$)/g, '$1');
    const defs = new Map([...body.matchAll(/^\s*\[([^\]]+)\]:\s*<?([^\s>]+)>?/gm)].map(m => [m[1].toLowerCase(), m[2]]));
    const refs = [];
    for (const m of body.matchAll(/(!?)\[([^\]]*)\]\(\s*<?([^\s)>]+)>?(?:\s+["'][^\n]*?["'])?\s*\)/g)) refs.push({ image: m[1] === '!', alt: m[2], url: m[3] });
    for (const m of body.matchAll(/(!?)\[([^\]]*)\]\[([^\]]*)\]/g)) {
      const url = defs.get((m[3] || m[2]).toLowerCase());
      if (!url) err(s.path, `undefined Markdown reference ${m[3] || m[2]}`);
      else refs.push({ image: m[1] === '!', alt: m[2], url });
    }
    for (const m of body.matchAll(/<img\b[^>]*>/gi)) {
      const src = m[0].match(/\bsrc=["']([^"']+)["']/i)?.[1], alt = m[0].match(/\balt=["']([^"']*)["']/i)?.[1];
      if (!src) err(s.path, 'HTML image requires src'); else refs.push({ image: true, alt, url: src });
    }
    for (const ref of refs) {
      if (ref.image) {
        if (!ref.alt?.trim()) err(s.path, `Markdown image requires alt: ${ref.url}`);
        const base = ref.url.startsWith('/') ? 'public' : relative(root, resolve(f, '..'));
        const asset = safeFile(ref.url, base, s.path, s.published === false);
        if (asset && statSync(asset).size > 500 * 1024) warnings.push(`${s.path}: image exceeds 500 KB: ${ref.url}`);
      } else if (!ref.url.startsWith('#')) checkURL({ value: ref.url, path: s.path, active: s.published });
    }
  }
  if (errors.length) throw new Error(`Undercurrent content validation failed (${errors.length}):\n- ${errors.join('\n- ')}`);
  return { site, works, notes, warnings };
}

export function loadContent(root = projectRoot, now = new Date()) {
  const read = (name, keys) => {
    const path = resolve(root, 'config', `${name}.yaml`);
    const doc = parseDocument(readFileSync(path, 'utf8'), { uniqueKeys: true });
    if (doc.errors.length) throw new Error(`${name}.yaml: ${doc.errors.map(e => e.message).join('\n')}`);
    const value = doc.toJS();
    if (keys && (!value || typeof value !== 'object' || Object.keys(value).some(k => !keys.includes(k)) || keys.some(k => !(k in value)))) throw new Error(`${name}.yaml: missing or unknown top-level key`);
    return value;
  };
  const content = validateContent({ site: read('site'), works: read('works', ['works']).works, notes: read('notes', ['notes']).notes }, root, now);
  for (const w of content.warnings) console.warn(`[content warning] ${w}`);
  return content;
}
