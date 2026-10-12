import { cpSync, mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { parse, stringify } from 'yaml';

const root = fileURLToPath(new URL('../', import.meta.url));
const fixture = mkdtempSync(join(tmpdir(), 'undercurrent-build-fixture-'));
const put = (path, text) => { const p = join(fixture, path); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, text); };
try {
  for (const p of ['src', 'astro.config.mjs', 'tsconfig.json', 'package.json']) cpSync(join(root, p), join(fixture, p), { recursive: true });
  // Vite must resolve dependencies through the isolated fixture's node_modules.
  cpSync(join(root, 'node_modules'), join(fixture, 'node_modules'), { recursive: true, dereference: true });
  const site = parse(readFileSync(join(root, 'config/site.yaml'), 'utf8'));
  const works = parse(readFileSync(join(root, 'config/works.yaml'), 'utf8')).works;
  const notes = parse(readFileSync(join(root, 'config/notes.yaml'), 'utf8')).notes;
  // Test-only replacements for absent inputs. This directory is always removed.
  const png = readFileSync(join(root, 'public/images/undercurrent-approved-clean-cream.png'));
  for (const im of [site.header.logo, site.footer.logo, site.hero.image, ...works.map(w => w.image).filter(Boolean)]) {
    if (im.src.endsWith('.svg')) put('public' + im.src, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"><text x="5" y="50" fill="white">TEST FIXTURE</text></svg>');
    else { const path = im.src.replace(/\.jpe?g$/, '.png'); if (path !== im.src) im.src = path; put('public' + im.src, png); }
  }
  const allPages = [...site.pages, ...works.filter(w => w.source), ...notes];
  for (const p of allPages) put(p.source, `# ${p.title}\n\nFixture body.\n\n## <i data-lucide="workflow"></i> Fixture heading\n\n| Field | Value |\n|---|---|\n| one | two |\n\n> Fixture quote\n\n\`\`\`python\nprint('fixture')\n\`\`\`\n\n![Fixture diagram](fixture.svg)\n`);
  for (const p of allPages) put(join(dirname(p.source), 'fixture.svg'), '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path d="M1 1L19 19"/></svg>');
  const save = () => { put('config/site.yaml', stringify(site)); put('config/works.yaml', stringify({ works })); put('config/notes.yaml', stringify({ notes })); };
  save();
  const run = (args) => {
    const result = spawnSync(process.execPath, [join(fixture, 'node_modules/astro/bin/astro.mjs'), ...args], { cwd: fixture, stdio: 'inherit', env: { ...process.env, ASTRO_TELEMETRY_DISABLED: '1' } });
    if (result.status !== 0) throw new Error(`Fixture astro ${args.join(' ')} failed`);
  };
  run(['check']); run(['build']);
  const home = readFileSync(join(fixture, 'dist/index.html'), 'utf8');
  if (home.includes('id="notes-label"')) throw new Error('Draft notes leaked into homepage');
  const article = readFileSync(join(fixture, 'dist/work/pipelinetools/index.html'), 'utf8');
  if ((article.match(/<h1\b/g) || []).length !== 1 || !article.includes('<table>') || !/<h2[^>]*><svg/.test(article) || !article.includes('loading="lazy"')) throw new Error('Long-form rendering features missing');
  // A second build proves generic routing/publication changes require only YAML.
  notes[0].published = true; notes[0].date = '2020-01-01'; save(); run(['build']);
  if (!existsSync(join(fixture, 'dist/notes', notes[0].slug, 'index.html'))) throw new Error('Published note did not generate a route');
  const publishedHome = readFileSync(join(fixture, 'dist/index.html'), 'utf8');
  if (!publishedHome.includes('id="notes-label"')) throw new Error('Published main note did not enable homepage Notes');
  const note = readFileSync(join(fixture, 'dist/notes', notes[0].slug, 'index.html'), 'utf8');
  if (!/<\/h1><p class="reading-meta">/.test(note)) throw new Error('Note metadata missing beneath H1');
  console.log('Isolated Astro fixture checks and builds passed; real-content readiness is separate.');
} finally { rmSync(fixture, { recursive: true, force: true }); }
