import { readFileSync } from 'node:fs';
import { resolve, posix } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createMarkdownProcessor } from '@astrojs/markdown-remark';
import { iconSVG } from './icons';

const root = fileURLToPath(new URL('../../', import.meta.url));
const assets = import.meta.glob<string>('../../content/**/*.{png,jpg,jpeg,svg,webp,gif,avif}', { eager: true, query: '?url', import: 'default' });
interface Node { type: string; url?: string; value?: string; children?: Node[] }

export async function renderBody(source: string) {
  const assetURL = (url: string) => {
    if (url.startsWith('/') || url.startsWith('https://')) return url;
    const path = '../../' + posix.normalize(posix.join(posix.dirname(source), url));
    if (!assets[path]) throw new Error(`${source}: missing bundled Markdown asset ${url}`);
    return assets[path];
  };
  function contentAssets() {
    return (tree: Node) => {
      const walk = (node: Node) => {
        if (node.type === 'image' && node.url) node.url = assetURL(node.url);
        if (node.type === 'definition' && node.url) {
          // Reference image definitions are resolved below without changing link definitions.
          imageDefinitions.set((node as Node & { identifier: string }).identifier, node);
        }
        if (node.type === 'html' && node.value) node.value = node.value
          .replace(/<i\s+data-lucide=["']([^"']+)["']\s*><\/i>/g, (_, name) => iconSVG(name))
          .replace(/(<img\b[^>]*\bsrc=["'])([^"']+)(["'][^>]*>)/gi, (_, a, url, b) => `${a}${assetURL(url)}${b}`);
        node.children?.forEach(walk);
      };
      const imageDefinitions = new Map<string, Node>();
      walk(tree);
      const references = (node: Node) => {
        if (node.type === 'imageReference') {
          const definition = imageDefinitions.get((node as Node & { identifier: string }).identifier);
          if (definition?.url) definition.url = assetURL(definition.url);
        }
        node.children?.forEach(references);
      };
      references(tree);
    };
  }
  const processor = await createMarkdownProcessor({
    gfm: true, syntaxHighlight: 'shiki', shikiConfig: { theme: 'github-dark' },
    remarkPlugins: [contentAssets]
  });
  const { code } = await processor.render(readFileSync(resolve(root, source), 'utf8'));
  return code.replace(/<img\b/g, '<img loading="lazy" decoding="async"');
}
