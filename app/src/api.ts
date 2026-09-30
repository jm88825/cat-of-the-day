import { DATA_BASE_URL } from '../config';
import type { Archive, CatPick } from './types';

const base = DATA_BASE_URL.replace(/\/+$/, '');

async function getJson<T>(file: string): Promise<T> {
  // Cache-bust so a freshly published day shows up on pull-to-refresh.
  const url = `${base}/${file}?t=${Date.now()}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) throw new Error(`Server replied ${res.status}`);
    return (await res.json()) as T;
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw new Error('The request timed out');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export const fetchLatest = () => getJson<CatPick>('latest.json');

export async function fetchArchive(): Promise<CatPick[]> {
  const a = await getJson<Archive>('archive.json');
  return [...(a.days ?? [])].sort((x, y) => (x.date < y.date ? 1 : -1));
}
