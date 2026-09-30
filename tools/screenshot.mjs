// Headless screenshots of the web build at a phone viewport (390x844).
// Usage: node tools/screenshot.mjs [webUrl]   (default http://localhost:8090)
import { chromium } from 'playwright-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'screenshots');
const url = process.argv[2] || 'http://localhost:8090';

// channel 'chrome' = system Google Chrome, which can decode Reddit's H.264 MP4s.
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
  isMobile: true, hasTouch: true });
const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));
page.on('requestfailed', (r) => logs.push(`[requestfailed] ${r.url()} ${r.failure()?.errorText}`));

await page.goto(url, { waitUntil: 'networkidle' });
await page.getByText('view original').first().waitFor({ timeout: 20000 });
// Wait for the video's first frame (or the image) to paint.
await page.waitForFunction(() => {
  const v = document.querySelector('video');
  if (v) return v.readyState >= 2 && v.currentTime > 4;
  const imgs = [...document.querySelectorAll('img')];
  return imgs.length > 0 && imgs.every((i) => i.complete);
}, null, { timeout: 30000 }).catch(() => logs.push('media wait timed out'));
await page.waitForTimeout(800);
const video = await page.evaluate(() => {
  const v = document.querySelector('video');
  return v ? { src: v.currentSrc, muted: v.muted, paused: v.paused, loop: v.loop, t: v.currentTime,
    w: v.videoWidth, h: v.videoHeight } : null;
});
await page.screenshot({ path: path.join(out, 'home.png') });
console.log('home video state:', JSON.stringify(video));

await page.getByText('Archive', { exact: true }).last().click();
await page.getByText('Past cats of the day').waitFor({ timeout: 20000 });
await page.waitForFunction(() => [...document.querySelectorAll('img')].every((i) => i.complete), null,
  { timeout: 20000 }).catch(() => logs.push('archive image wait timed out'));
await page.waitForTimeout(1200);
const rows = await page.locator('[role="button"][aria-label*=":"]').count();
await page.screenshot({ path: path.join(out, 'archive.png') });
console.log('archive rows:', rows);

// Open a past day from the archive to check the detail view.
await page.locator('[role="button"][aria-label*=":"]').nth(1).click();
await page.getByText('view original').first().waitFor({ timeout: 20000 });
await page.waitForTimeout(1500);
await page.screenshot({ path: path.join(out, 'archive-day.png') });

console.log(logs.filter((l) => !l.includes('[log]')).join('\n') || 'no console errors');
await browser.close();
