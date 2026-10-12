import { defineConfig } from 'astro/config';
import { loadContent } from './src/lib/content.mjs';

export default defineConfig({
  output: 'static',
  markdown: { shikiConfig: { theme: 'github-dark' } },
  integrations: [{
    name: 'undercurrent-content-validation',
    hooks: {
      'astro:config:setup': ({ command }) => {
        if (command !== 'preview') loadContent();
      },
      'astro:server:setup': ({ server }) => {
        // Restart after content edits so validation also gates the development server.
        server.watcher.add(['config', 'content', 'public/images']);
        server.watcher.on('all', (event, path) => {
          if (/(?:^|[/\\])(config|content|public[/\\]images)[/\\]/.test(path)) {
            void server.restart();
          }
        });
      }
    }
  }]
});
