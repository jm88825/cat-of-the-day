// Google Play feature graphic (1024x500) from the kitten icon photo.
// Usage: node tools/make-feature-graphic.mjs   (needs playwright-core + Google Chrome)
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const photo = fs.readFileSync(path.join(root, 'app/assets/source/kitten-icon-source.png')).toString('base64');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1024, height: 500 } });
await page.setContent(`<html><body style="margin:0">
  <div style="width:1024px;height:500px;display:flex;align-items:center;overflow:hidden;
      background:linear-gradient(120deg,#EDBB97 0%,#F6D2B6 55%,#FBDCC4 100%);font-family:'Trebuchet MS',Arial,sans-serif">
    <div style="width:500px;height:500px;flex:none;
      background:url(data:image/png;base64,${photo}) center/cover;
      -webkit-mask-image:linear-gradient(90deg,#000 70%,transparent 100%)"></div>
    <div style="margin-left:-10px;color:#3B2A26">
      <div style="font-size:66px;font-weight:800;line-height:1">Cat of the Day</div>
      <div style="font-size:30px;margin-top:18px;opacity:.82">One viral cat. Every day. 🐾</div>
    </div>
  </div></body></html>`);
await page.screenshot({ path: path.join(root, 'store-assets', 'feature-graphic-1024x500.png') });
await browser.close();
console.log('wrote store-assets/feature-graphic-1024x500.png');
