import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
const docker = (...args) => execFileSync('docker', args, { encoding: 'utf8' }).trim();
const suffix = `${process.pid}-${Date.now()}`;
const image = `undercurrent-test:${suffix}`;
const network = `undercurrent-test-${suffix}`;
const container = `undercurrent-test-${suffix}`;
try {
  execFileSync('docker', ['build', '-t', image, '.'], { stdio: 'inherit' });
  docker('network', 'create', network);
  docker('run', '-d', '--name', container, '--network', network, '--network-alias', 'undercurrent', '-p', '127.0.0.1::8080', image);
  const mapping = docker('port', container, '8080/tcp');
  const port = mapping.match(/127\.0\.0\.1:(\d+)/)?.[1];
  assert.ok(port, `Unexpected port mapping: ${mapping}`);
  const base = `http://127.0.0.1:${port}`;
  for (let attempt = 0; ; attempt++) {
    const health = docker('inspect', '--format', '{{.State.Health.Status}}', container);
    if (health === 'healthy') break;
    assert.ok(attempt < 45 && health !== 'unhealthy', `Container health: ${health}`);
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  const get = path => fetch(base + path, { redirect: 'manual', signal: AbortSignal.timeout(5000) });
  for (const path of ['/', '/work/pipelinetools/', '/how-to-work-with-me/', '/notes/', '/images/hero-hillside.jpg', '/images/pipelinetools-architecture.svg']) {
    assert.equal((await get(path)).status, 200, path);
  }
  const home = await get('/');
  assert.equal(home.headers.get('cache-control'), 'no-cache');
  assert.equal(home.headers.get('x-content-type-options'), 'nosniff');
  assert.match(home.headers.get('content-security-policy') ?? '', /frame-ancestors 'none'/);
  const html = await home.text();
  assert.ok(!html.includes('id="notes-label"'), 'Draft notes leaked');
  const css = html.match(/href="([^"\s]*\/_astro\/[^"\s]+\.css)"/)?.[1];
  assert.ok(css, 'Missing fingerprinted CSS');
  const asset = await get(css);
  assert.equal(asset.status, 200);
  assert.match(asset.headers.get('cache-control'), /immutable/);
  assert.equal(asset.headers.get('x-content-type-options'), 'nosniff');
  for (const path of ['/missing', '/notes/what-data-organizations-get-wrong/', '/work/disputes-refactor/', '/_astro/missing.css']) assert.equal((await get(path)).status, 404, path);
  const redirect = await get('/work/pipelinetools');
  assert.equal(redirect.status, 301);
  assert.equal(redirect.headers.get('location'), '/work/pipelinetools/');
  // A second container resolves the service name over the shared network,
  // matching how cloudflared reaches the production service.
  docker('run', '--rm', '--network', network, '--entrypoint', 'wget', image, '-q', '-O', '/dev/null', 'http://undercurrent:8080/');
  console.log('Container health, static routes/assets, draft exclusion, 404s, redirects, cache and security headers, and tunnel-network DNS passed.');
} finally {
  for (const args of [['rm', '-f', container], ['network', 'rm', network], ['image', 'rm', image]]) {
    try { docker(...args); } catch { /* Preserve the original failure; clean only test resources. */ }
  }
}
