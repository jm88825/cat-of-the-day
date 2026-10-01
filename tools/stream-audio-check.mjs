// Plays Reddit HLS/DASH/MP4 streams in Chrome (native, hls.js, dash.js) and reports
// whether audio is actually decoded (webkitAudioDecodedByteCount > 0).
import { chromium } from 'playwright-core';
const ids = process.argv.slice(2);
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage();
await page.setContent('<html><body></body></html>');
await page.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/hls.js@1/dist/hls.min.js' });
await page.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/dashjs@4/dist/dash.all.min.js' });
for (const id of ids) {
  const base = `https://v.redd.it/${id}`;
  for (const [name, mode, src] of [
    ['HLS native', 'native', `${base}/HLSPlaylist.m3u8`],
    ['HLS hls.js', 'hlsjs', `${base}/HLSPlaylist.m3u8`],
    ['DASH dash.js', 'dash', `${base}/DASHPlaylist.mpd`],
    ['MP4', 'native', `${base}/CMAF_720.mp4`],
  ]) {
    const r = await page.evaluate(async ({ mode, src }) => {
      document.body.innerHTML = '';
      const v = document.createElement('video');
      v.muted = false; v.volume = 1; v.autoplay = true; v.playsInline = true;
      document.body.appendChild(v);
      let err = null;
      v.onerror = () => { err = v.error && `${v.error.code} ${v.error.message}`; };
      if (mode === 'hlsjs') { const h = new Hls(); h.on(Hls.Events.ERROR, (e, d) => { if (d.fatal) err = d.details; }); h.loadSource(src); h.attachMedia(v); }
      else if (mode === 'dash') { const p = dashjs.MediaPlayer().create(); p.initialize(v, src, true); }
      else v.src = src;
      v.play().catch((e) => { err = err || String(e); });
      const t0 = Date.now();
      while (Date.now() - t0 < 12000 && !(v.currentTime > 3)) await new Promise((r) => setTimeout(r, 250));
      return { t: +v.currentTime.toFixed(1), audioBytes: v.webkitAudioDecodedByteCount, videoBytes: v.webkitVideoDecodedByteCount, muted: v.muted, err };
    }, { mode, src });
    console.log(`${id} ${name.padEnd(13)} ${JSON.stringify(r)}`);
  }
}
await browser.close();
