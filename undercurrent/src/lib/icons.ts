import { Calendar, MoonStar, Brain, Workflow, Wrench, MessageSquareText, Target, Sparkles, Handshake, Coffee, CircleHelp, ArrowUpRight, ArrowRight } from 'lucide';

const nodes: Record<string, typeof Calendar> = {
  calendar: Calendar, 'moon-star': MoonStar, brain: Brain, workflow: Workflow,
  wrench: Wrench, 'message-square-text': MessageSquareText, target: Target,
  sparkles: Sparkles, handshake: Handshake, coffee: Coffee, 'circle-help': CircleHelp,
  'arrow-up-right': ArrowUpRight, 'arrow-right': ArrowRight
};
export function escapeHTML(value: string) {
  return value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}
export function iconSVG(name: string) {
  const node = nodes[name];
  if (!node) throw new Error(`Unsupported Lucide icon: ${name}`);
  const children = (node[2] || []).map(([tag, attrs]) => `<${tag} ${Object.entries(attrs).map(([k, v]) => `${k}="${escapeHTML(String(v))}"`).join(' ')} />`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" class="icon">${children}</svg>`;
}
