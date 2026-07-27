"use strict";
/* Tone trainer. Four modes, all reusing the /tts engine:
     single  - hear one syllable, tap the tone
     pairs   - hear a two-syllable word, tap each syllable's tone
     shadow  - hear the model, record yourself, compare back to back
     speak   - say the word; browser STT checks the word, mic pitch checks tone
   Perception first (single/pairs) because you cannot produce a contrast you
   cannot hear. Adaptive: tones you miss come back more often. */

const TONE_GLYPH = { 1: "ˉ", 2: "ˊ", 3: "ˇ", 4: "ˋ", 5: "·" };
const TONE_LABEL = { 1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "neutral" };
const TONE_DESC = {
  1: "high, flat", 2: "rising", 3: "low dip", 4: "sharp fall", 5: "light",
};
// Chao pitch shapes (0=low .. 1=high), for drawing the expected contour
const TONE_SHAPE = {
  1: [0.9, 0.9], 2: [0.4, 0.95], 3: [0.35, 0.1, 0.5], 4: [0.95, 0.1],
  5: [0.5, 0.45],
};

const $ = (s, r = document) => r.querySelector(s);
const el = (tag, cls, txt) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt != null) e.textContent = txt;
  return e;
};

// ---- state -----------------------------------------------------------------
let DATA = null;
let ENGINES = { kokoro: true, say: false };
let mode = "single";
const audioCache = new Map();
let current = null;                     // the active question object

const STATS_KEY = "tone-stats-v1";
const stats = loadStats();

function loadStats() {
  try {
    const s = JSON.parse(localStorage.getItem(STATS_KEY));
    if (s && s.miss) return s;
  } catch (_) {}
  return { correct: 0, total: 0, streak: 0, best: 0, miss: { 1: 1, 2: 1, 3: 1, 4: 1, 5: 1 } };
}
function saveStats() { localStorage.setItem(STATS_KEY, JSON.stringify(stats)); }

// ---- voices ----------------------------------------------------------------
const VOICE_KEY = "tone-voice";
function voiceOptions() {
  const list = [];
  if (ENGINES.say) {
    list.push(["say:Tingting", "Tingting (say - clean tones)"]);
    list.push(["say:Meijia", "Meijia (say)"]);
  }
  list.push(["kokoro:zf_xiaoxiao", "Xiaoxiao (neural)"]);
  list.push(["kokoro:zm_yunyang", "Yunyang (neural)"]);
  return list;
}
function currentVoice() {
  const v = localStorage.getItem(VOICE_KEY);
  const opts = voiceOptions().map((o) => o[0]);
  return opts.includes(v) ? v : opts[0];
}

// ---- tts -------------------------------------------------------------------
async function speak(hanzi, rate = 150) {
  const [engine, voice] = currentVoice().split(":");
  const key = `${engine}|${voice}|${rate}|${hanzi}`;
  let url = audioCache.get(key);
  if (!url) {
    const res = await fetch("/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: hanzi, voice, rate, engine }),
    });
    if (!res.ok) { toast("speech failed"); return; }
    url = URL.createObjectURL(await res.blob());
    audioCache.set(key, url);
  }
  await new Promise((resolve) => {
    const a = new Audio(url);
    a.onended = a.onerror = resolve;
    a.play().catch(resolve);
  });
}

// ---- helpers ---------------------------------------------------------------
function toast(msg, ms = 1400) {
  const s = $("#status");
  s.textContent = msg;
  s.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { s.hidden = true; }, ms);
}
function pinyinHTML(p, pattern) {
  // grey out neutral-tone syllables (best-effort: last syllable if pattern ends 5)
  if (pattern && pattern[pattern.length - 1] === 5) {
    return p; // keep simple; neutral marking handled in reveal card separately
  }
  return p;
}
function weightedTone() {
  // pick a target tone, biased toward tones with more misses
  const tones = [1, 2, 3, 4];
  const weights = tones.map((t) => 1 + (stats.miss[t] || 0));
  let r = Math.random() * weights.reduce((a, b) => a + b, 0);
  for (let i = 0; i < tones.length; i++) { if ((r -= weights[i]) < 0) return tones[i]; }
  return 4;
}
function sample(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

function record(correct, tone) {
  stats.total++;
  if (correct) { stats.correct++; stats.streak++; stats.best = Math.max(stats.best, stats.streak); }
  else { stats.streak = 0; if (tone) stats.miss[tone] = (stats.miss[tone] || 0) + 2; }
  if (correct && tone && stats.miss[tone] > 1) stats.miss[tone] -= 0.5; // decay when mastered
  saveStats();
  renderScore();
}
function renderScore() {
  $("#streak").innerHTML = `streak <b>${stats.streak}</b> &middot; best <b>${stats.best}</b>`;
  const pct = stats.total ? Math.round((100 * stats.correct) / stats.total) : 0;
  $("#tally").innerHTML = `<b>${stats.correct}</b>/<b>${stats.total}</b> (${pct}%)`;
  $("#resetStats").hidden = stats.total === 0;
}

// ---- contour drawing -------------------------------------------------------
function drawContour(canvas, expected, measured) {
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  const css = getComputedStyle(document.body);
  const line = css.getPropertyValue("--line").trim() || "#ddd";
  const muted = css.getPropertyValue("--muted").trim() || "#999";
  const accent = css.getPropertyValue("--accent").trim() || "#b23a2e";
  const good = css.getPropertyValue("--good").trim() || "#3f7d4f";
  const pad = 14, top = 10, bot = H - 10;
  // gridlines
  ctx.strokeStyle = line; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = top + ((bot - top) * i) / 4;
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(W - pad, y); ctx.stroke();
  }
  const yOf = (v) => bot - v * (bot - top);
  // expected (concatenated tone shapes across syllables)
  const drawPath = (pts, color, width, dash) => {
    if (!pts || pts.length < 2) return;
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.setLineDash(dash || []);
    ctx.lineJoin = "round"; ctx.lineCap = "round";
    ctx.beginPath();
    pts.forEach((p, i) => {
      const x = pad + (W - 2 * pad) * (i / (pts.length - 1));
      i ? ctx.lineTo(x, yOf(p)) : ctx.moveTo(x, yOf(p));
    });
    ctx.stroke(); ctx.setLineDash([]);
  };
  const expPts = [];
  expected.forEach((t) => TONE_SHAPE[t].forEach((v) => expPts.push(v)));
  drawPath(expPts, muted, 3, [6, 5]);
  if (measured && measured.length > 1) {
    const hz = measured.map((m) => m.hz).filter((h) => h > 0);
    if (hz.length > 1) {
      const lo = Math.min(...hz), hi = Math.max(...hz);
      const span = Math.max(hi - lo, 1);
      const norm = measured.map((m) => (m.hz > 0 ? (m.hz - lo) / span : null));
      // draw as connected segments, skipping unvoiced gaps
      const pts = norm.map((v) => (v == null ? null : v));
      ctx.strokeStyle = good; ctx.lineWidth = 3.5; ctx.lineJoin = "round"; ctx.lineCap = "round";
      ctx.beginPath(); let pen = false;
      pts.forEach((v, i) => {
        const x = pad + (W - 2 * pad) * (i / (pts.length - 1));
        if (v == null) { pen = false; return; }
        const y = yOf(v);
        if (!pen) { ctx.moveTo(x, y); pen = true; } else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
  }
}

// ---- pitch tracking (mic) --------------------------------------------------
function autoCorrelate(buf, sampleRate) {
  // returns fundamental frequency in Hz, or -1 if too quiet/unvoiced
  let rms = 0;
  for (let i = 0; i < buf.length; i++) rms += buf[i] * buf[i];
  rms = Math.sqrt(rms / buf.length);
  if (rms < 0.01) return -1;
  let r1 = 0, r2 = buf.length - 1, thres = 0.2;
  for (let i = 0; i < buf.length / 2; i++) if (Math.abs(buf[i]) < thres) { r1 = i; break; }
  for (let i = 1; i < buf.length / 2; i++) if (Math.abs(buf[buf.length - i]) < thres) { r2 = buf.length - i; break; }
  const b = buf.slice(r1, r2), n = b.length;
  const c = new Array(n).fill(0);
  for (let lag = 0; lag < n; lag++) for (let i = 0; i < n - lag; i++) c[lag] += b[i] * b[i + lag];
  let d = 0; while (d < n - 1 && c[d] > c[d + 1]) d++;
  let maxval = -1, maxpos = -1;
  for (let i = d; i < n; i++) if (c[i] > maxval) { maxval = c[i]; maxpos = i; }
  let T0 = maxpos;
  if (T0 <= 0) return -1;
  const x1 = c[T0 - 1] || 0, x2 = c[T0], x3 = c[T0 + 1] || 0;
  const a = (x1 + x3 - 2 * x2) / 2, bb = (x3 - x1) / 2;
  if (a) T0 = T0 - bb / (2 * a);
  const f = sampleRate / T0;
  return (f > 70 && f < 500) ? f : -1;
}

let micStream = null;
async function getMic() {
  if (micStream) return micStream;
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  return micStream;
}

async function captureUtterance(maxMs = 2200) {
  // record mic, sampling pitch ~every frame; also keep audio for playback.
  const stream = await getMic();
  const ac = new (window.AudioContext || window.webkitAudioContext)();
  const src = ac.createMediaStreamSource(stream);
  const analyser = ac.createAnalyser();
  analyser.fftSize = 2048;
  src.connect(analyser);
  const buf = new Float32Array(analyser.fftSize);
  const measured = [];
  const rec = new MediaRecorder(stream);
  const chunks = [];
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const t0 = performance.now();
  rec.start();
  await new Promise((resolve) => {
    const tick = () => {
      analyser.getFloatTimeDomainData(buf);
      measured.push({ t: performance.now() - t0, hz: autoCorrelate(buf, ac.sampleRate) });
      if (performance.now() - t0 < maxMs) requestAnimationFrame(tick);
      else resolve();
    };
    requestAnimationFrame(tick);
  });
  rec.stop();
  const blob = await new Promise((res) => { rec.onstop = () => res(new Blob(chunks)); });
  ac.close();
  // trim leading/trailing unvoiced frames
  let a = 0, b = measured.length - 1;
  while (a < b && measured[a].hz < 0) a++;
  while (b > a && measured[b].hz < 0) b--;
  return { measured: measured.slice(a, b + 1), audioURL: URL.createObjectURL(blob) };
}

function classifyTone(measured) {
  const hz = measured.filter((m) => m.hz > 0).map((m) => m.hz);
  if (hz.length < 4) return null;
  const semis = hz.map((h) => 12 * Math.log2(h / hz[0]));
  const start = semis[0], end = semis[semis.length - 1];
  const min = Math.min(...semis), minIdx = semis.indexOf(min);
  const delta = end - start;
  const mid = minIdx > semis.length * 0.2 && minIdx < semis.length * 0.85;
  if (delta > 2.5) return 2;
  if (delta < -2.5) return 4;
  if (min < -2 && mid) return 3;
  if (Math.abs(delta) <= 2.5) return 1;
  return null;
}

// ---- web speech (STT) ------------------------------------------------------
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
function recognizeOnce(timeoutMs = 4000) {
  return new Promise((resolve) => {
    if (!SR) return resolve({ ok: false, reason: "nostt" });
    const r = new SR();
    r.lang = "zh-CN"; r.maxAlternatives = 5; r.interimResults = false;
    let done = false;
    const finish = (v) => { if (!done) { done = true; try { r.stop(); } catch (_) {} resolve(v); } };
    r.onresult = (e) => {
      const alts = [];
      for (let i = 0; i < e.results[0].length; i++) alts.push(e.results[0][i].transcript);
      finish({ ok: true, alts });
    };
    r.onerror = (e) => finish({ ok: false, reason: e.error });
    r.onend = () => finish({ ok: false, reason: "noresult" });
    try { r.start(); } catch (_) { finish({ ok: false, reason: "startfail" }); }
    setTimeout(() => finish({ ok: false, reason: "timeout" }), timeoutMs);
  });
}
const stripHan = (s) => (s || "").replace(/[^一-鿿]/g, "");

// ===========================================================================
// MODES
// ===========================================================================
const stage = $("#stage");
function clearStage() { stage.innerHTML = ""; current = null; }

// ---- mode: single ----------------------------------------------------------
function newSingle() {
  clearStage();
  const useReal = Math.random() < 0.5 && DATA.singles.length;
  let hanzi, tone, gloss, pinyin, options;
  if (useReal) {
    const target = weightedTone();
    const pool = DATA.singles.filter((s) => s.pattern[0] === target);
    const w = (pool.length ? sample(pool) : sample(DATA.singles));
    hanzi = w.h; tone = w.pattern[0]; gloss = w.g; pinyin = w.p;
  } else {
    const set = sample(DATA.minimal_sets);
    const target = weightedTone();
    const opt = set.options.find((o) => o.t === target) || sample(set.options);
    hanzi = opt.h; tone = opt.t; gloss = opt.g; pinyin = opt.p;
  }
  options = [1, 2, 3, 4];
  current = { hanzi, tone, gloss, pinyin };

  stage.append(el("p", "prompt-line", "Play it, then tap the tone you hear."));
  const play = el("button", "play-big", "▶");
  play.onclick = () => speak(hanzi);
  stage.append(play, el("p", "replay-hint", "tap to replay"));

  const grid = el("div", "tone-grid");
  const btns = options.map((t) => {
    const b = el("button", "tone-btn");
    b.append(
      Object.assign(el("span", "glyph", TONE_GLYPH[t]), {}),
      el("span", "lbl", TONE_LABEL[t]),
      el("span", "sub", TONE_DESC[t]),
    );
    b.onclick = () => answerSingle(t, btns, play);
    grid.append(b);
    return [t, b];
  });
  stage.append(grid);
  speak(hanzi);
}
function answerSingle(picked, btns, play) {
  const { tone, gloss, pinyin, hanzi } = current;
  const correct = picked === tone;
  btns.forEach(([t, b]) => {
    b.disabled = true;
    if (t === tone) b.classList.add("correct");
    else if (t === picked) b.classList.add("wrong");
  });
  record(correct, tone);
  const card = el("div", "reveal");
  const v = el("div", correct ? "r-verdict good" : "r-verdict bad", correct ? "Yes" : "Not quite");
  card.append(v);
  card.append(el("div", "r-pinyin", pinyin));
  card.append(el("div", "r-gloss", `${gloss}  ·  ${TONE_LABEL[tone]} tone (${TONE_DESC[tone]})`));
  if (!correct) card.append(el("div", "r-note", `You picked ${TONE_LABEL[picked]} (${TONE_DESC[picked]}). Listen again for the ${TONE_DESC[tone]}.`));
  stage.append(card);
  const actions = el("div", "actions");
  const again = el("button", "btn", "▶ again"); again.onclick = () => speak(hanzi);
  const next = el("button", "btn primary", "next →"); next.onclick = newSingle;
  actions.append(again, next); stage.append(actions);
  next.focus();
}

// ---- mode: pairs -----------------------------------------------------------
function newPairs() {
  clearStage();
  const w = sample(DATA.pairs);
  current = { hanzi: w.h, pinyin: w.p, gloss: w.g, pattern: w.pattern, picks: [null, null] };
  stage.append(el("p", "prompt-line", "Play the word, then tap the tone of each syllable."));
  const play = el("button", "play-big", "▶");
  play.onclick = () => speak(w.h);
  stage.append(play, el("p", "replay-hint", "tap to replay"));

  const rows = el("div", "syl-rows");
  const allBtns = [];
  for (let s = 0; s < w.pattern.length; s++) {
    const row = el("div", "syl-row");
    row.append(el("div", "syl-label", `Syllable ${s + 1}`));
    const grid = el("div", "mini-grid");
    const rowBtns = [];
    [1, 2, 3, 4, 5].forEach((t) => {
      const b = el("button", "mini-btn");
      b.append(el("span", "glyph", TONE_GLYPH[t]), el("span", null, TONE_LABEL[t] === "neutral" ? "neu" : t));
      b.onclick = () => pickSyl(s, t, rowBtns, allBtns);
      grid.append(b); rowBtns.push([t, b]);
    });
    row.append(grid); rows.append(row); allBtns.push(rowBtns);
  }
  stage.append(rows);
  speak(w.h);
}
function pickSyl(s, t, rowBtns, allBtns) {
  if (current.done) return;
  current.picks[s] = t;
  rowBtns.forEach(([tt, b]) => b.classList.toggle("picked", tt === t));
  if (current.picks.every((p) => p != null)) gradePairs(allBtns);
}
function gradePairs(allBtns) {
  current.done = true;
  const { pattern, picks, pinyin, gloss, hanzi } = current;
  let allRight = true;
  allBtns.forEach((rowBtns, s) => {
    rowBtns.forEach(([t, b]) => {
      b.disabled = true;
      if (t === pattern[s]) b.classList.add("correct");
      else if (t === picks[s]) { b.classList.add("wrong"); }
    });
    if (picks[s] !== pattern[s]) { allRight = false; if (pattern[s] <= 4) record(false, pattern[s]); }
  });
  if (allRight) record(true, pattern[0]);
  const card = el("div", "reveal");
  card.append(el("div", allRight ? "r-verdict good" : "r-verdict bad", allRight ? "Both right" : "Check the marks"));
  card.append(el("div", "r-pinyin", pinyin));
  card.append(el("div", "r-gloss", `${gloss}  ·  ${pattern.map((t) => TONE_LABEL[t]).join(" + ")}`));
  stage.append(card);
  const cw = el("div", "contour-wrap");
  const cv = el("canvas", "contour"); cw.append(cv); stage.append(cw);
  requestAnimationFrame(() => drawContour(cv, pattern, null));
  const actions = el("div", "actions");
  const again = el("button", "btn", "▶ again"); again.onclick = () => speak(hanzi);
  const next = el("button", "btn primary", "next →"); next.onclick = newPairs;
  actions.append(again, next); stage.append(actions);
}

// ---- mode: shadow ----------------------------------------------------------
function newShadow() {
  clearStage();
  const pool = DATA.pairs.concat(DATA.singles);
  const w = sample(pool);
  current = { w };
  stage.append(el("p", "prompt-line", "Listen, then say it out loud. Record yourself and compare."));
  stage.append(revealTarget(w, true));
  const play = el("button", "play-big small", "▶"); play.onclick = () => speak(w.h);
  stage.append(play, el("p", "replay-hint", "hear the model"));

  const actions = el("div", "actions");
  const rec = el("button", "btn rec", "● record me");
  const cmp = el("button", "btn", "▶ compare"); cmp.disabled = true;
  const next = el("button", "btn primary", "next →"); next.onclick = newShadow;
  let mine = null;
  rec.onclick = async () => {
    if (rec.classList.contains("recording")) return;
    rec.classList.add("recording"); rec.textContent = "● listening…";
    try {
      const cap = await captureUtterance(2000);
      mine = cap.audioURL;
      cmp.disabled = false;
      const cw = $("#shadowContour");
      if (cw) drawContour(cw, w.pattern, cap.measured);
      toast("got it - now compare");
    } catch (e) { toast("mic blocked - allow the microphone"); }
    rec.classList.remove("recording"); rec.textContent = "● record again";
  };
  cmp.onclick = async () => {
    await speak(w.h);
    if (mine) await new Promise((r) => { const a = new Audio(mine); a.onended = a.onerror = r; a.play().catch(r); });
  };
  actions.append(rec, cmp, next); stage.append(actions);
  const cw = el("div", "contour-wrap");
  const cv = el("canvas", "contour"); cv.id = "shadowContour"; cw.append(cv);
  cw.append(legend()); stage.append(cw);
  requestAnimationFrame(() => drawContour(cv, w.pattern, null));
  stage.append(shadowHint());
  speak(w.h);
}
function shadowHint() {
  return Object.assign(el("div", "hint-box"),
    { innerHTML: "The dashed line is the target shape. Match its direction, not its exact height - your voice sits where it sits. Slow speed helps: copy the pitch, exaggerate at first." });
}

// ---- mode: speak -----------------------------------------------------------
function newSpeak() {
  clearStage();
  const single = Math.random() < 0.6;
  const w = sample(single ? DATA.singles : DATA.pairs);
  current = { w };
  stage.append(el("p", "prompt-line", SR
    ? "Say the word. I'll check the word and your tone."
    : "Say the word. I'll show your tone shape (word-check needs Chrome)."));
  stage.append(revealTarget(w, true));
  const model = el("button", "play-big small", "▶"); model.onclick = () => speak(w.h);
  stage.append(model, el("p", "replay-hint", "hear the model first"));

  const actions = el("div", "actions");
  const say = el("button", "btn rec", "● say it");
  const next = el("button", "btn primary", "next →"); next.onclick = newSpeak;
  actions.append(say, next); stage.append(actions);

  const cw = el("div", "contour-wrap");
  const cv = el("canvas", "contour"); cv.id = "speakContour"; cw.append(cv); cw.append(legend());
  stage.append(cw);
  requestAnimationFrame(() => drawContour(cv, w.pattern, null));
  const result = el("div"); result.id = "speakResult"; stage.append(result);

  say.onclick = async () => {
    if (say.classList.contains("recording")) return;
    say.classList.add("recording"); say.textContent = "● listening…";
    result.innerHTML = "";
    let stt = { ok: false, reason: "nostt" };
    try {
      const [cap, sttRes] = await Promise.all([
        captureUtterance(2600),
        SR ? recognizeOnce(4000) : Promise.resolve({ ok: false, reason: "nostt" }),
      ]);
      stt = sttRes;
      drawContour(cv, w.pattern, cap.measured);
      gradeSpeak(w, cap, stt, result);
    } catch (e) { toast("mic blocked - allow the microphone"); }
    say.classList.remove("recording"); say.textContent = "● say it again";
  };
  speak(w.h);
}
function gradeSpeak(w, cap, stt, result) {
  const card = el("div", "reveal");
  // word check via STT
  let wordOk = null, heard = "";
  if (stt.ok) {
    const target = stripHan(w.h);
    wordOk = stt.alts.some((a) => stripHan(a) === target || stripHan(a).includes(target));
    heard = stt.alts[0] || "";
  }
  // tone check via pitch (only meaningful for single syllables)
  let toneMsg = "";
  if (w.pattern.length === 1) {
    const guess = classifyTone(cap.measured);
    if (guess == null) toneMsg = "Tone: couldn't read the pitch - say it a touch longer and louder.";
    else if (guess === w.pattern[0]) toneMsg = `Tone: sounds like the ${TONE_DESC[guess]} - matches. ✓`;
    else toneMsg = `Tone: I heard a ${TONE_DESC[guess]}; the target is a ${TONE_DESC[w.pattern[0]]}. Watch the green line vs the dashed one.`;
  } else {
    toneMsg = "Tone: compare your green line to the dashed target - matching direction on each syllable is the goal.";
  }
  const good = (wordOk === true) || (wordOk == null && w.pattern.length === 1 && classifyTone(cap.measured) === w.pattern[0]);
  card.append(el("div", good ? "r-verdict good" : "r-verdict bad",
    wordOk === true ? "Word recognised" : wordOk === false ? "Word not recognised" : "Recorded"));
  card.append(el("div", "r-pinyin", w.p));
  card.append(el("div", "r-gloss", w.g));
  if (wordOk === false && heard) card.append(el("div", "r-note", `The recogniser heard “${heard}”. That often means the tone or a vowel drifted - the word turned into a different one.`));
  if (wordOk == null) card.append(el("div", "r-note", "Word recognition needs Chrome's speech API (and a connection); the pitch trace above works regardless."));
  card.append(el("div", "r-note", toneMsg));
  result.append(card);
  const replay = el("div", "actions");
  const a1 = el("button", "btn", "▶ model"); a1.onclick = () => speak(w.h);
  const a2 = el("button", "btn", "▶ me"); a2.onclick = () => { const a = new Audio(cap.audioURL); a.play(); };
  replay.append(a1, a2); result.append(replay);
}

// ---- shared bits -----------------------------------------------------------
function revealTarget(w, withGloss) {
  const box = el("div");
  box.append(el("div", "target-word", w.p));
  if (withGloss) box.append(el("div", "target-gloss", w.g));
  return box;
}
function legend() {
  const l = el("div", "contour-legend");
  l.innerHTML = '<span><span class="swatch" style="background:var(--muted)"></span>target</span>' +
                '<span><span class="swatch" style="background:var(--good)"></span>you</span>';
  return l;
}

// ---- wiring ----------------------------------------------------------------
const MODES = { single: newSingle, pairs: newPairs, shadow: newShadow, speak: newSpeak };
function setMode(m) {
  mode = m;
  document.querySelectorAll(".mode").forEach((b) => b.classList.toggle("active", b.dataset.mode === m));
  localStorage.setItem("tone-mode", m);
  MODES[m]();
}

async function init() {
  try { ENGINES = (await (await fetch("/config")).json()).engines || ENGINES; } catch (_) {}
  DATA = await (await fetch("/data/tones.json")).json();

  const vsel = $("#voice");
  voiceOptions().forEach(([val, lbl]) => vsel.append(new Option(lbl, val)));
  vsel.value = currentVoice();
  vsel.onchange = () => localStorage.setItem(VOICE_KEY, vsel.value);

  document.querySelectorAll(".mode").forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));
  $("#resetStats").onclick = () => {
    Object.assign(stats, { correct: 0, total: 0, streak: 0, best: 0, miss: { 1: 1, 2: 1, 3: 1, 4: 1, 5: 1 } });
    saveStats(); renderScore();
  };
  renderScore();
  setMode(localStorage.getItem("tone-mode") || "single");
}
init();
