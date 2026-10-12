export interface ImageSpec { src: string; alt: string; decorative?: boolean; position?: string }
export interface LinkSpec { label: string; url: string }
export interface Work {
  slug: string; title: string; tagline: string; tier: 'featured' | 'more' | 'side';
  order: number; published: boolean; summary: string[]; link: LinkSpec;
  source?: string; image?: ImageSpec; disclosure?: string;
}
export interface Note {
  slug: string; title: string; date: string | null; series: 'basics' | null;
  published: boolean; url: string; source: string;
}
export interface Page { slug: string; title: string; url: string; source: string }
export interface Site {
  meta: { title: string; description: string };
  header: { brand: string; tagline: string; logo: ImageSpec; telemetry: { day_of_year: boolean; moon_phase: boolean; facts: string[] } };
  hero: { label: string; name: string; title: string; image: ImageSpec; intro: string[]; links: LinkSpec[] };
  pages: Page[];
  sections: { work: { label: string; enabled: boolean }; notes: { label: string; enabled: boolean | 'auto'; max_items: number; archive: LinkSpec } };
  footer: { brand: string; tagline: string; logo: ImageSpec; links: LinkSpec[]; copyright_name: string; credits: string };
}
export interface Content { site: Site; works: Work[]; notes: Note[]; warnings: string[] }
export function loadContent(root?: string, now?: Date): Content;
export function validateContent(data: unknown, root: string, now?: Date): Content;
export function visibleNotes(notes: Note[], now?: Date): Note[];
export function notesState(content: Content, now?: Date): { visible: Note[]; main: Note[]; enabled: boolean };
export function pageEntries(content: Content, now?: Date): (Page & { kind: 'work' | 'note' | 'page'; date?: string | null; series?: string | null })[];
export function todayISO(now?: Date): string;
