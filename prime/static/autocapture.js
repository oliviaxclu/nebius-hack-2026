/* Auto-capture for the camera checks: decides WHEN to take the picture, from tiny measurements of the live video.
   The measurements are made on this device. Nothing is sent to the model until step() says "capture".
   measure(): turns one video frame into {mean, std, sharp, luma} (brightness, contrast, sharpness, a small grey image).
   step():    given those numbers and the previous state, says what to do next. Pure, so it can be tested without a camera. */
(function (root) {
  const W = 128, H = 96;
  // Calibrated in Chrome on real product photos at 128x96: sharp 1.8k-6.5k, mild blur 190-770, heavy blur 50-170, dark mean 9-20,
  // sensor noise diff 1.3-3.5, a 6 px hand shift 10.4. A blur below 100 is rejected; the model also reports blur itself.
  const CFG = { steadyDiff: 4, moveDiff: 8, steadyFrames: 8, minWaitMs: 5000, dark: 35, bright: 225, flatStd: 14, blur: 100, sampleMs: 150 };

  function measure(source, canvas) {
    canvas.width = W; canvas.height = H;
    const g = canvas.getContext("2d", { willReadFrequently: true });
    g.drawImage(source, 0, 0, W, H);
    const px = g.getImageData(0, 0, W, H).data, luma = new Uint8ClampedArray(W * H);
    let sum = 0;
    for (let i = 0, j = 0; i < px.length; i += 4, j++) { const v = 0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2]; luma[j] = v; sum += v; }
    const mean = sum / luma.length; let varSum = 0;
    for (let j = 0; j < luma.length; j++) varSum += (luma[j] - mean) ** 2;
    // sharpness: variance of a 4-neighbour Laplacian over the interior
    let lsum = 0, lsq = 0, n = 0;
    for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) {
      const i = y * W + x, l = 4 * luma[i] - luma[i - 1] - luma[i + 1] - luma[i - W] - luma[i + W];
      lsum += l; lsq += l * l; n++;
    }
    const lm = lsum / n;
    return { mean, std: Math.sqrt(varSum / luma.length), sharp: lsq / n - lm * lm, luma };
  }

  function diff(a, b) {
    if (!a || !b || a.length !== b.length) return null;
    let s = 0; for (let i = 0; i < a.length; i++) s += Math.abs(a[i] - b[i]);
    return s / a.length;
  }

  // requireMotion: after a try that was not "ok", wait for the person to move and settle again rather than re-sending the same view.
  function newState(now, requireMotion) { return { t0: now, steady: 0, moved: 0, sawMotion: false, requireMotion: !!requireMotion }; }

  // m = { mean, std, sharp, diff }  (diff = change since the previous sample, or null on the first)
  function step(st, m, now, cfg = CFG) {
    if (m.mean < cfg.dark) { st.steady = 0; return { action: "hint", say: "It is too dark. Turn on a light." }; }
    if (m.mean > cfg.bright) { st.steady = 0; return { action: "hint", say: "There is glare. Tilt it a little away from the light." }; }
    if (m.std < cfg.flatStd) { st.steady = 0; return { action: "hint", say: "I can't see anything yet. Hold it in front of the camera." }; }
    if (m.diff == null) return { action: "wait" };
    if (m.diff >= cfg.moveDiff) { st.steady = 0; if (++st.moved >= 2) st.sawMotion = true; return { action: "wait" }; }
    if (m.diff <= cfg.steadyDiff) st.steady++; else st.steady = 0;
    const ready = st.sawMotion || (!st.requireMotion && now - st.t0 >= cfg.minWaitMs);
    if (st.steady < cfg.steadyFrames || !ready) return { action: "wait" };
    if (m.sharp < cfg.blur) { st.steady = 0; return { action: "hint", say: "It looks blurry. Hold it still, a little farther from the camera." }; }
    return { action: "capture" };
  }

  const api = { CFG, W, H, measure, diff, newState, step };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.AutoCapture = api;
})(typeof window !== "undefined" ? window : globalThis);
