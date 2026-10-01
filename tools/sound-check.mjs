// Web check of the video sound toggle: opens each archived video, reports which
// stream is playing, taps the sound toggle, and checks muted/volume/audio data.
// Usage: node tools/sound-check.mjs [webUrl]
import { chromium } from 'playwright-core';
const url = process.argv[2] || 'http://localhost:8090';
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
const logs = [];
page.on('console', (m) => { if (m.type() !== 'log') logs.push(`[${m.type()}] ${m.text()}`); });
await page.goto(url, { waitUntil: 'networkidle' });
const hls = await page.evaluate(() => document.createElement('video').canPlayType('application/vnd.apple.mpegurl'));
console.log(`Chrome canPlayType(HLS) = "${hls}"`);
await page.getByText('Archive', { exact: true }).last().click();
await page.getByText('Past cats of the day').waitFor();
const rows = page.locator('[role="button"][aria-label*=":"]');
const n = await rows.count();
for (let i = 0; i < n; i++) {
  await page.getByText('Archive', { exact: true }).last().click();
  await page.getByText('Past cats of the day').waitFor();
  const label = await rows.nth(i).getAttribute('aria-label');
  await rows.nth(i).click();
  await page.getByText('view original').first().waitFor();
  const hasVideo = await page.waitForSelector('video', { timeout: 3000 }).then(() => true).catch(() => false);
  if (!hasVideo) continue;
  await page.waitForFunction(() => { const v = document.querySelector('video'); return v && v.currentTime > 1; },
    null, { timeout: 30000 }).catch(() => {});
  const badgeBefore = await page.getByTestId('video-sound-toggle').innerText();
  const toggle = page.getByTestId('video-sound-toggle');
  if (await toggle.isEnabled()) { await toggle.click(); await page.waitForTimeout(2500); }
  const st = await page.evaluate(() => {
    const v = document.querySelector('video');
    return { src: v.currentSrc, muted: v.muted, volume: v.volume, paused: v.paused,
      audioBytes: v.webkitAudioDecodedByteCount ?? null, mozHasAudio: v.mozHasAudio ?? null };
  });
  const badgeAfter = await page.getByTestId('video-sound-toggle').innerText();
  console.log(`${label.slice(0, 60)}\n   before="${badgeBefore}" after="${badgeAfter}"\n   ${JSON.stringify(st)}`);
}
console.log(logs.join('\n') || 'no console warnings/errors');
await browser.close();
