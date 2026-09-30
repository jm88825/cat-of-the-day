import type { CatPick } from './types';

export function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}k`;
  if (n >= 1_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  return String(n);
}

export function formatDate(iso: string, style: 'long' | 'short' = 'long'): string {
  const [y, m, d] = iso.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString(undefined, style === 'long'
    ? { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }
    : { month: 'short', day: 'numeric' });
}

/** e.g. "▲ 12.3k upvotes", or an honest fallback when the score is unknown. */
export function popularityLabel(p: CatPick): string {
  if (typeof p.score === 'number') return `▲ ${formatCount(p.score)} ${p.scoreLabel ?? 'upvotes'}`;
  if (p.rank) return `🔥 #${p.rank} on Reddit's top cat list`;
  return '🔥 Trending today';
}

export function creditLine(p: CatPick): string {
  if (p.subreddit) return `Posted by u/${p.author} on r/${p.subreddit}`;
  if (p.source === 'x') return `Posted by @${p.author} on X`;
  return `Posted by ${p.author}`;
}
