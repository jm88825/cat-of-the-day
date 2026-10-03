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

export type Source = 'reddit' | 'x' | 'other';

export function sourceOf(p: CatPick): Source {
  if (p.source === 'x' || /^https:\/\/(x|twitter)\.com\//.test(p.postUrl || p.permalink || '')) return 'x';
  if (p.subreddit || p.source?.startsWith('reddit')) return 'reddit';
  return 'other';
}

/** 1234 -> "1.2K" (X-style). */
export function formatLikes(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}K`;
  if (n >= 1_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}K`;
  return String(n);
}

/** e.g. "❤️ 1.2K likes on X", "▲ 12.3k upvotes", "🔥 #2 on Reddit's top cat list". */
export function popularityLabel(p: CatPick): string {
  if (sourceOf(p) === 'x') {
    const likes = typeof p.likes === 'number' ? p.likes : p.score;
    if (typeof likes === 'number') return `❤️ ${formatLikes(likes)} ${likes === 1 ? 'like' : 'likes'} on X`;
    return '💎 A hidden gem from X';
  }
  if (typeof p.score === 'number') return `▲ ${formatCount(p.score)} ${p.scoreLabel ?? 'upvotes'}`;
  if (p.rank && p.rank <= 10) return `🔥 #${p.rank} on Reddit's top cat list`;
  if (p.rank) return `💎 Hidden gem · #${p.rank} on Reddit's cat list today`;
  return '🔥 Trending today';
}

export function creditLine(p: CatPick): string {
  if (sourceOf(p) === 'x') return `Posted by @${(p.authorHandle || p.author).replace(/^@/, '')} on X`;
  if (p.subreddit) return `Posted by u/${p.author} on r/${p.subreddit}`;
  return `Posted by ${p.author}`;
}

/** Link to the original post. */
export function originalUrl(p: CatPick): string {
  return p.postUrl || p.permalink;
}
