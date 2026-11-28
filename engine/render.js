// Contrôle Qualité renderer (headless Chromium + WebGL/SwiftShader).
//   node engine/render.js timeline <config.json> <out.json>          -> duration + sound events
//   node engine/render.js stills   <config.json> <outdir> t1,t2,...  -> PNG stills (checks)
//   node engine/render.js clean    <config.json> <out.png> t           -> scene only, no text (cover)
//   node engine/render.js frames   <config.json> <outdir> [a-b]      -> JPEG frames a..b (inclusive, 30 fps)
//   node engine/render.js video    <config.json> <out.mp4>           -> silent MP4, all frames
const path = require('path'); const fs = require('fs'); const { spawn } = require('child_process');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require('/opt/npm-tools/node_modules/playwright')); }
const FPS = 30;

(async () => {
  const [mode, cfgPath, outArg, extra] = process.argv.slice(2);
  const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 400, height: 400 } });
  page.on('pageerror', e => { console.error('pageerror:', e.message); process.exitCode = 1; });
  await page.goto('file://' + path.join(__dirname, ({ physics: 'physics.html', drop: 'drop.html', snap: 'snap.html', bounce: 'bounce.html', impact: 'impact.html', geyser: 'geyser.html', cradle: 'cradle.html', slinky: 'slinky.html', bottle: 'bottle.html', glass: 'glass.html', toast: 'toast.html', elevator: 'elevator.html', coin: 'coin.html', explainer: 'explainer.html' })[cfg.engine] || 'engine.html'));
  await page.evaluate(() => window.ready);
  const tl = await page.evaluate(c => window.setup(c), cfg);
  const N = Math.round(tl.duration * FPS);
  const grab = async (t, type) => Buffer.from((await page.evaluate(([t, ty]) => window.renderFrame(t, ty), [t, type])).split(',')[1], 'base64');

  if (mode === 'timeline') {
    fs.writeFileSync(outArg, JSON.stringify({ fps: FPS, frames: N, ...tl }, null, 1));
    console.log(`duration ${tl.duration.toFixed(2)} s, ${N} frames`);
  } else if (mode === 'stills') {
    fs.mkdirSync(outArg, { recursive: true });
    for (const t of extra.split(',').map(Number)) {
      const t0 = Date.now(); fs.writeFileSync(path.join(outArg, `still_${t.toFixed(2)}.png`), await grab(t, 'image/png'));
      console.log(`t=${t} ${Date.now() - t0} ms`);
    }
  } else if (mode === 'keys') {                        // bottle engine: which scene image each time shows
    const keys = {};
    for (const t of extra.split(',').map(Number)) keys[t.toFixed(2)] = await page.evaluate(t => window.poseKeyAt(t), t);
    fs.writeFileSync(outArg, JSON.stringify(keys, null, 1));
    console.log(`keys -> ${outArg}`);
  } else if (mode === 'clean') {                       // scene only, no text (cover image)
    fs.mkdirSync(path.dirname(outArg), { recursive: true });
    await page.evaluate(() => { window.CLEAN = true; });
    // Blender engines: never a cover from the grey placeholder (debug pose key on it); take the nearest frame
    // whose real scene image exists (0, +1, -1, +2, ... frames)
    const t0 = Math.round(Number(extra) * FPS);
    let img = null, used = t0;
    for (let k = 0; k <= 90 && !img; k++) for (const s of k ? [k, -k] : [0]) {
      const f = t0 + s; if (f < 0 || f >= N || img) continue;
      await page.evaluate(() => { window.PLACEHOLDER = false; });
      const buf = await grab(f / FPS, 'image/png');
      if (!(await page.evaluate(() => window.PLACEHOLDER))) { img = buf; used = f; }
    }
    if (!img) { console.error('clean: no real scene image near t, cover skipped'); process.exitCode = 1; }
    else { fs.writeFileSync(outArg, img); console.log(`clean t=${(used / FPS).toFixed(2)} (asked ${extra}) -> ${outArg}`); }
  } else if (mode === 'frames') {
    fs.mkdirSync(outArg, { recursive: true });
    let [a, b] = (extra || `0-${N - 1}`).split('-').map(Number); b = Math.min(b, N - 1);
    const t0 = Date.now();
    for (let i = a; i <= b; i++) {
      fs.writeFileSync(path.join(outArg, `f_${String(i).padStart(5, '0')}.jpg`), await grab(i / FPS, 'image/jpeg'));
      if ((i - a) % 60 === 0) console.log(`frame ${i} (${a}-${b}) ${((Date.now() - t0) / 1000).toFixed(0)} s`);
    }
  } else if (mode === 'video') {
    const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', outArg], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let i = 0; i < N; i++) {
      const buf = await grab(i / FPS, 'image/jpeg');
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 60 === 0) console.log(`frame ${i}/${N} ${((Date.now() - t0) / 1000).toFixed(0)} s`);
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
  } else { console.error('unknown mode ' + mode); process.exitCode = 2; }
  await browser.close();
})();
