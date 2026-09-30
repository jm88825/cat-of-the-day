// Generates original app icons/splash for "Cat of the Day" from inline SVG.
// Usage: node tools/make-icons.mjs   (needs playwright-core + Google Chrome)
import { chromium } from 'playwright-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const assets = path.join(root, 'app', 'assets');
const store = path.join(root, 'store-assets');

const BG = '#FFE3C7';
const ORANGE = '#FF9A4D';
const DARK = '#3B2A26';

// A simple cat face centred in a 1000x1000 box. `mono` = single-colour silhouette.
function cat({ mono = false, color = ORANGE } = {}) {
  const fill = mono ? '#FFFFFF' : color;
  const inner = mono ? 'none' : '#FFC2B0';
  const face = mono ? 'none' : DARK;
  return `
  <g>
    <path d="M230 470 L270 170 Q280 130 320 150 L470 300 Z" fill="${fill}"/>
    <path d="M770 470 L730 170 Q720 130 680 150 L530 300 Z" fill="${fill}"/>
    <path d="M285 400 L305 225 L420 320 Z" fill="${inner}"/>
    <path d="M715 400 L695 225 L580 320 Z" fill="${inner}"/>
    <ellipse cx="500" cy="560" rx="330" ry="290" fill="${fill}"/>
    ${mono ? '' : `
    <path d="M470 290 Q500 330 530 290" stroke="#E07A30" stroke-width="18" fill="none" stroke-linecap="round"/>
    <path d="M440 330 Q500 380 560 330" stroke="#E07A30" stroke-width="18" fill="none" stroke-linecap="round"/>
    <ellipse cx="385" cy="540" rx="48" ry="62" fill="${face}"/>
    <ellipse cx="615" cy="540" rx="48" ry="62" fill="${face}"/>
    <circle cx="400" cy="518" r="16" fill="#fff"/>
    <circle cx="630" cy="518" r="16" fill="#fff"/>
    <ellipse cx="300" cy="640" rx="48" ry="28" fill="#FF7A8A" opacity="0.55"/>
    <ellipse cx="700" cy="640" rx="48" ry="28" fill="#FF7A8A" opacity="0.55"/>
    <path d="M478 625 L522 625 L500 652 Z" fill="#FF6F86" stroke="#FF6F86" stroke-width="10" stroke-linejoin="round"/>
    <path d="M500 652 Q500 690 462 692 M500 652 Q500 690 538 692" stroke="${face}" stroke-width="14" fill="none" stroke-linecap="round"/>
    <g stroke="${face}" stroke-width="10" stroke-linecap="round" opacity="0.8">
      <path d="M240 640 L130 615"/><path d="M240 668 L125 680"/>
      <path d="M760 640 L870 615"/><path d="M760 668 L875 680"/>
    </g>`}
  </g>`;
}

const sun = `<g opacity="0.9"><circle cx="820" cy="190" r="70" fill="#FFD166"/></g>`;

function svg(size, body, bg = null) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 1000 1000">
  ${bg ? `<rect width="1000" height="1000" fill="${bg}"/>` : ''}${body}</svg>`;
}
const scaled = (s, inner) => `<g transform="translate(${500 - 500 * s} ${500 - 500 * s}) scale(${s})">${inner}</g>`;

const jobs = [
  // Full legacy/iOS icon: background + cat
  ['icon.png', 1024, svg(1024, sun + scaled(0.86, cat()), BG)],
  // Android adaptive icon: foreground must sit inside the ~66% safe zone
  ['android-icon-foreground.png', 1024, svg(1024, scaled(0.6, cat()))],
  ['android-icon-background.png', 1024, svg(1024, '', BG)],
  ['android-icon-monochrome.png', 1024, svg(1024, scaled(0.6, cat({ mono: true })))],
  ['splash-icon.png', 1024, svg(1024, scaled(0.9, cat()))],
  ['favicon.png', 48, svg(48, scaled(0.95, cat()), BG)],
];

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
async function render(file, w, h, markup) {
  await page.setViewportSize({ width: w, height: h });
  await page.setContent(`<html><body style="margin:0;background:transparent">${markup}</body></html>`);
  await page.screenshot({ path: file, omitBackground: true, clip: { x: 0, y: 0, width: w, height: h } });
  console.log('wrote', path.relative(root, file));
}
for (const [name, size, markup] of jobs) await render(path.join(assets, name), size, size, markup);

// Google Play listing assets
await render(path.join(store, 'play-icon-512.png'), 512, 512, svg(512, sun + scaled(0.86, cat()), BG));
await render(path.join(store, 'feature-graphic-1024x500.png'), 1024, 500, `
  <div style="width:1024px;height:500px;background:linear-gradient(135deg,#FFE3C7,#FFC9A8);display:flex;align-items:center;font-family:'Trebuchet MS',Arial,sans-serif">
    <div style="width:420px;height:420px;margin-left:40px">${svg(420, scaled(0.95, cat()))}</div>
    <div style="margin-left:20px;color:${DARK}">
      <div style="font-size:68px;font-weight:800;line-height:1">Cat of the Day</div>
      <div style="font-size:34px;margin-top:18px;opacity:.8">One viral cat. Every day. 🐾</div>
    </div>
  </div>`);
await browser.close();
