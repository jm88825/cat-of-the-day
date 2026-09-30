// Verifies the error + retry state by blocking the data server in the browser.
import { chromium } from 'playwright-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
let block = true;
await page.route('**/latest.json*', (r) => (block ? r.abort() : r.continue()));
await page.goto(process.argv[2] || 'http://localhost:8090');
await page.getByText('Couldn’t load the cat').waitFor({ timeout: 20000 });
await page.screenshot({ path: path.join(root, 'screenshots', 'error.png') });
console.log('error state shown');
block = false;
await page.getByText('Try again').click();
await page.getByText('view original').first().waitFor({ timeout: 20000 });
console.log('retry recovered');
await browser.close();
