// Screenshots for the mixed Reddit/X data model at 390x844.
// Usage: node tools/screenshot-mixed.mjs <webUrl> <outName> [archiveOutName]
//   e.g. node tools/screenshot-mixed.mjs http://localhost:8090 x-home archive-mixed
import { chromium } from 'playwright-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'screenshots');
const [url = 'http://localhost:8090', homeName = 'home', archiveName] = process.argv.slice(2);

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
await page.waitForFunction(() => {
  const v = document.querySelector('video');
  if (v) return v.readyState >= 2 && v.currentTime > 2;
  const imgs = [...document.querySelectorAll('img')];
  return imgs.length > 0 && imgs.every((i) => i.complete);
}, null, { timeout: 30000 }).catch(() => logs.push('media wait timed out'));
await page.waitForTimeout(1000);
await page.screenshot({ path: path.join(out, `${homeName}.png`) });
const text = await page.evaluate(() => document.body.innerText);
console.log(`--- ${homeName} text ---\n${text}`);

if (archiveName) {
  await page.getByText('Archive', { exact: true }).last().click();
  await page.getByText('Past cats of the day').waitFor({ timeout: 20000 });
  await page.waitForFunction(() => [...document.querySelectorAll('img')].every((i) => i.complete), null,
    { timeout: 20000 }).catch(() => logs.push('archive image wait timed out'));
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(out, `${archiveName}.png`) });
}
console.log(logs.filter((l) => !l.includes('[log]')).join('\n') || 'no console errors');
await browser.close();
