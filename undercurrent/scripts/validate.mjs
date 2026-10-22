import { loadContent } from '../src/lib/content.mjs';
try {
  const content = loadContent();
  console.log(`Validated ${content.works.length} work entries, ${content.notes.length} notes, and ${content.site.pages.length} standalone pages.`);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
