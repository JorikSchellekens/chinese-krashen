"use strict";

const els = {
  menuToggle: document.getElementById("menuToggle"),
  nav: document.getElementById("lessonNav"),
  trackList: document.getElementById("trackList"),
  progress: document.getElementById("progress"),
  reader: document.getElementById("reader"),
  dict: document.getElementById("dict"),
  dictToggle: document.getElementById("dictToggle"),
  scrim: document.getElementById("scrim"),
  voice: document.getElementById("voice"),
  rate: document.getElementById("rate"),
  popup: document.getElementById("popup"),
  status: document.getElementById("status"),
};

// Client-side audio cache: key -> blob URL. The server caches files too; this
// avoids a round-trip for clips already fetched this session.
const audioCache = new Map();
let currentAudio = null;
let statusTimer = null;

// Persisted state
const PROG_KEY = "mandarin-progress";
const DICT_KEY = "mandarin-dict-open";
const VOICE_KEY = "mandarin-voice";
const RATE_KEY = "mandarin-rate";

let tracks = [];                // [{id,title,blurb,lessons:[...]}]
let flat = [];                  // [{trackId, lesson}] in reading order
const railButtons = new Map();  // lesson id -> rail button
const trackEls = new Map();     // track id -> {wrap, count, lessonBtns:[]}
let currentId = null;
let currentTrackId = null;

const VOICE_GROUPS = [
  { engine: "kokoro", label: "Kokoro - neural", voices: [
    ["kokoro:zf_xiaoxiao", "Xiaoxiao (F)"],
    ["kokoro:zf_xiaoyi", "Xiaoyi (F)"],
    ["kokoro:zf_xiaobei", "Xiaobei (F)"],
    ["kokoro:zm_yunxi", "Yunxi (M)"],
    ["kokoro:zm_yunyang", "Yunyang (M)"],
    ["kokoro:zm_yunjian", "Yunjian (M)"],
  ]},
  { engine: "say", label: "macOS say - system", voices: [
    ["say:Tingting", "Tingting (F)"],
    ["say:Sandy (Chinese (China mainland))", "Sandy (F)"],
    ["say:Flo (Chinese (China mainland))", "Flo (F)"],
    ["say:Reed (Chinese (China mainland))", "Reed (M)"],
    ["say:Eddy (Chinese (China mainland))", "Eddy (M)"],
  ]},
];

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------
function loadJSON(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}
let progress = loadJSON(PROG_KEY, {});
function saveProgress() { localStorage.setItem(PROG_KEY, JSON.stringify(progress)); }

// ---------------------------------------------------------------------------
// Speech
// ---------------------------------------------------------------------------
function showStatus(msg) {
  els.status.textContent = msg;
  els.status.hidden = false;
  clearTimeout(statusTimer);
  statusTimer = setTimeout(() => (els.status.hidden = true), 2500);
}

function splitVoice(value) {
  const i = value.indexOf(":");
  return [value.slice(0, i), value.slice(i + 1)];
}

async function speak(hanzi) {
  hanzi = (hanzi || "").trim();
  if (!hanzi) return;
  const [engine, voice] = splitVoice(els.voice.value || "kokoro:zf_xiaoxiao");
  const rate = els.rate.value;
  const key = `${engine}|${voice}|${rate}|${hanzi}`;

  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  try {
    let url = audioCache.get(key);
    if (!url) {
      showStatus("synthesising...");
      const res = await fetch("/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: hanzi, voice, engine, rate: Number(rate) }),
      });
      if (!res.ok) throw new Error(await res.text());
      url = URL.createObjectURL(await res.blob());
      audioCache.set(key, url);
    }
    els.status.hidden = true;
    currentAudio = new Audio(url);
    await currentAudio.play();
  } catch (err) {
    showStatus("speech failed: " + err.message);
  }
}

// ---------------------------------------------------------------------------
// Popup
// ---------------------------------------------------------------------------
function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
// x,y are viewport coordinates (clientX/clientY). preferAbove keeps the popup
// off the finger on touch.
function showPopup(x, y, headline, gloss, preferAbove) {
  const p = els.popup;
  p.innerHTML =
    `<div class="pu-head">${escapeHtml(headline)}</div>` +
    (gloss ? `<div class="pu-gloss">${escapeHtml(gloss)}</div>` : "");
  p.hidden = false;
  const pr = p.getBoundingClientRect();
  const vw = window.innerWidth, vh = window.innerHeight;
  const left = Math.max(8, Math.min(x - pr.width / 2, vw - pr.width - 8));
  let top;
  if (preferAbove) {
    top = y - pr.height - 16;
    if (top < 8) top = y + 20;
  } else {
    top = y + 16;
    if (top + pr.height > vh - 8) top = y - pr.height - 16;
  }
  top = Math.max(8, Math.min(top, vh - pr.height - 8));
  p.style.left = left + "px";
  p.style.top = top + "px";
}
function hidePopup() { els.popup.hidden = true; }

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function sentenceHanzi(sentence) {
  return sentence.t.map((tok) => tok.h || "").join("");
}

function renderSentence(sentence) {
  const span = document.createElement("span");
  span.className = "sentence";
  span.dataset.h = sentenceHanzi(sentence);
  span.dataset.en = sentence.en;

  sentence.t.forEach((tok) => {
    if (tok.sp) span.appendChild(document.createTextNode(" "));
    const w = document.createElement("span");
    if (tok.g !== undefined) {
      w.className = "word";
      w.dataset.h = tok.h;
      w.dataset.p = tok.p;
      w.dataset.g = tok.g;
    } else {
      w.className = "punct";
    }
    w.textContent = tok.p;
    span.appendChild(w);
  });
  span.appendChild(document.createTextNode(" "));
  return span;
}

function levelDots(level) {
  const n = Math.max(1, Math.min(3, level || 1));
  return "●".repeat(n) + "○".repeat(3 - n);
}

function renderLesson(entry) {
  const { lesson, trackId } = entry;
  const track = tracks.find((t) => t.id === trackId);
  els.reader.innerHTML = "";
  els.reader.scrollTop = 0;

  if (track) {
    const tk = document.createElement("div");
    tk.className = "lesson-track";
    tk.textContent = track.title;
    els.reader.appendChild(tk);
  }

  const head = document.createElement("div");
  head.className = "lesson-head";
  const h2 = document.createElement("h2");
  h2.textContent = lesson.title;
  head.appendChild(h2);

  const mark = document.createElement("button");
  mark.className = "mark-btn";
  const refreshMark = () => {
    const done = !!progress[lesson.id];
    mark.classList.toggle("done", done);
    mark.textContent = done ? "✓ Read" : "Mark as read";
  };
  refreshMark();
  mark.addEventListener("click", () => {
    if (progress[lesson.id]) delete progress[lesson.id];
    else progress[lesson.id] = true;
    saveProgress();
    refreshMark();
    updateProgressUI();
  });
  head.appendChild(mark);
  els.reader.appendChild(head);

  if (lesson.note) {
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = lesson.note;
    els.reader.appendChild(note);
  }

  lesson.paragraphs.forEach((para) => {
    const p = document.createElement("p");
    p.className = "para text";
    para.forEach((s) => p.appendChild(renderSentence(s)));
    els.reader.appendChild(p);
  });

  renderLessonNav(entry);
}

function renderLessonNav(entry) {
  const idx = flat.findIndex((e) => e.lesson.id === entry.lesson.id);
  const prev = idx > 0 ? flat[idx - 1] : null;
  const next = idx < flat.length - 1 ? flat[idx + 1] : null;

  const bar = document.createElement("div");
  bar.className = "lesson-nav-btns";

  const pb = document.createElement("button");
  pb.className = "prev";
  pb.textContent = "← Previous";
  if (prev) pb.addEventListener("click", () => goto(prev.trackId, prev.lesson.id));
  else pb.disabled = true;
  bar.appendChild(pb);

  const nb = document.createElement("button");
  nb.className = "next";
  nb.textContent = "Next →";
  if (next) nb.addEventListener("click", () => goto(next.trackId, next.lesson.id));
  else nb.disabled = true;
  bar.appendChild(nb);

  els.reader.appendChild(bar);
}

function renderDictionary(sections) {
  els.dict.innerHTML = "";
  const head = document.createElement("div");
  head.className = "dict-head";
  head.textContent = "Dictionary";
  els.dict.appendChild(head);

  const total = sections.reduce((n, s) => n + s.words.length, 0);
  const sub = document.createElement("div");
  sub.className = "dict-sub";
  sub.textContent = `${total} words, grouped by kind - tap to hear`;
  els.dict.appendChild(sub);

  sections.forEach((sec) => {
    const h3 = document.createElement("div");
    h3.className = "dict-section";
    h3.textContent = sec.label;
    els.dict.appendChild(h3);
    sec.words.forEach((tok) => {
      const entry = document.createElement("div");
      entry.className = "dict-entry";
      const w = document.createElement("span");
      w.className = "word";
      w.dataset.h = tok.h;
      w.dataset.p = tok.p;
      w.dataset.g = tok.g;
      w.textContent = tok.p;
      const g = document.createElement("span");
      g.className = "dict-gloss";
      g.textContent = tok.g;
      entry.appendChild(w);
      entry.appendChild(g);
      els.dict.appendChild(entry);
    });
  });
}

// ---------------------------------------------------------------------------
// Progress UI (overall bar + per-track counts + ticks)
// ---------------------------------------------------------------------------
function updateProgressUI() {
  const total = flat.length;
  const done = flat.filter((e) => progress[e.lesson.id]).length;
  els.progress.innerHTML =
    `<div class="progress-bar"><div class="progress-fill" style="width:${
      total ? (done / total) * 100 : 0}%"></div></div>` +
    `<div class="progress-text">${done} of ${total} texts read</div>`;
  railButtons.forEach((btn, id) => btn.classList.toggle("done", !!progress[id]));
  tracks.forEach((t) => {
    const d = t.lessons.filter((l) => progress[l.id]).length;
    const te = trackEls.get(t.id);
    if (te) {
      te.count.textContent = `${d}/${t.lessons.length}`;
      te.wrap.classList.toggle("done-all", d === t.lessons.length && d > 0);
    }
  });
}

// ---------------------------------------------------------------------------
// Routing:  #<track>/<lesson>  (old #<lesson> still resolves)
// ---------------------------------------------------------------------------
function parseHash() {
  const raw = decodeURIComponent(location.hash.replace(/^#\/?/, ""));
  if (!raw) return null;
  const slash = raw.indexOf("/");
  if (slash >= 0) return { track: raw.slice(0, slash), lesson: raw.slice(slash + 1) };
  return { track: null, lesson: raw };   // legacy: just a lesson id
}

function findEntry(track, lesson) {
  if (lesson) {
    const byLesson = flat.find((e) => e.lesson.id === lesson);
    if (byLesson) return byLesson;
    // a slashless token might actually be a track id (e.g. #numbers)
    const asTrack = flat.find((e) => e.trackId === lesson);
    if (asTrack) return asTrack;
  }
  if (track) {
    const t = flat.find((e) => e.trackId === track);
    if (t) return t;
  }
  return flat[0];
}

function goto(trackId, lessonId) {
  location.hash = "#" + encodeURIComponent(trackId) + "/" + encodeURIComponent(lessonId);
}

function selectFromHash() {
  const h = parseHash();
  const entry = findEntry(h && h.track, h && h.lesson);
  if (!entry) return;
  currentId = entry.lesson.id;
  currentTrackId = entry.trackId;

  railButtons.forEach((btn, lid) => btn.classList.toggle("active", lid === currentId));
  openTrack(entry.trackId, true);
  hidePopup();
  renderLesson(entry);

  // keep the URL canonical (track/lesson)
  const canonical = "#" + encodeURIComponent(entry.trackId) + "/" + encodeURIComponent(entry.lesson.id);
  if (location.hash !== canonical) history.replaceState(null, "", canonical);
}

// ---------------------------------------------------------------------------
// Nav: track accordion
// ---------------------------------------------------------------------------
function openTrack(trackId, exclusive) {
  trackEls.forEach((te, id) => {
    if (id === trackId) te.wrap.classList.add("open");
    else if (exclusive) te.wrap.classList.remove("open");
  });
}

function buildNav() {
  els.trackList.innerHTML = "";
  tracks.forEach((track) => {
    const wrap = document.createElement("div");
    wrap.className = "track";

    const head = document.createElement("button");
    head.className = "track-head";
    const caret = document.createElement("span");
    caret.className = "caret"; caret.textContent = "▶";
    const title = document.createElement("span");
    title.className = "t-title"; title.textContent = track.title;
    const count = document.createElement("span");
    count.className = "t-count";
    head.append(caret, title, count);
    head.addEventListener("click", () => wrap.classList.toggle("open"));
    wrap.appendChild(head);

    const list = document.createElement("div");
    list.className = "track-lessons";
    track.lessons.forEach((lesson) => {
      const b = document.createElement("button");
      b.className = "lesson";
      const tick = document.createElement("span");
      tick.className = "tick"; tick.textContent = "✓";
      const lt = document.createElement("span");
      lt.className = "l-title";
      lt.textContent = shortLessonTitle(lesson.title);
      const lvl = document.createElement("span");
      lvl.className = "lvl"; lvl.textContent = levelDots(lesson.level);
      b.title = lesson.title;
      b.append(tick, lt, lvl);
      b.addEventListener("click", () => { goto(track.id, lesson.id); closeDrawers(); });
      railButtons.set(lesson.id, b);
      list.appendChild(b);
    });
    wrap.appendChild(list);

    els.trackList.appendChild(wrap);
    trackEls.set(track.id, { wrap, count, });
  });
}

function shortLessonTitle(title) {
  // "Text 3 - I don't understand" -> "I don't understand"; "Warm-up - greetings" -> "greetings"
  const dash = title.indexOf(" - ");
  return dash >= 0 ? title.slice(dash + 3) : title;
}

// ---------------------------------------------------------------------------
// Drawers (mobile) + dictionary column (desktop)
// ---------------------------------------------------------------------------
function isWide() { return window.matchMedia("(min-width: 900px)").matches; }

function updateScrim() {
  const open = document.body.classList.contains("nav-open") ||
               (document.body.classList.contains("dict-open") && !isWide());
  els.scrim.hidden = !open;
}
function setNav(open) {
  document.body.classList.toggle("nav-open", open);
  els.menuToggle.setAttribute("aria-expanded", open ? "true" : "false");
  updateScrim();
}
function setDict(open) {
  document.body.classList.toggle("dict-open", open);
  els.dictToggle.setAttribute("aria-pressed", open ? "true" : "false");
  localStorage.setItem(DICT_KEY, open ? "1" : "0");
  updateScrim();
}
function closeDrawers() { setNav(false); if (!isWide()) setDict(false); }

// ---------------------------------------------------------------------------
// Interactions:  tap = sentence,  double-tap = word,  drag = phrase
// Unified across mouse + touch via Pointer Events.
// ---------------------------------------------------------------------------
function handleSentence(target, x, y, above) {
  const sen = target.closest(".sentence");
  if (sen) { speak(sen.dataset.h); showPopup(x, y, sen.dataset.en, "", above); return; }
  const w = target.closest(".word");
  if (w) handleWord(w, x, y, above);
}
function handleWord(word, x, y, above) {
  speak(word.dataset.h);
  showPopup(x, y, word.dataset.p, word.dataset.g, above);
}
function handleDrag(sel, x, y, above) {
  const hanzi = [], gloss = [];
  els.reader.querySelectorAll(".word").forEach((w) => {
    if (sel.containsNode(w, true)) { hanzi.push(w.dataset.h); gloss.push(w.dataset.g); }
  });
  if (!hanzi.length) return;
  speak(hanzi.join(""));
  showPopup(x, y, sel.toString().trim(), gloss.join("  ·  "), above);
}

let downPt = null;
let pendingTap = null;
let lastTap = null;   // {t, word}

function setupReaderInteractions() {
  els.reader.addEventListener("pointerdown", (e) => {
    downPt = { x: e.clientX, y: e.clientY };
  });

  els.reader.addEventListener("pointerup", (e) => {
    const touch = e.pointerType !== "mouse";
    const x = e.clientX, y = e.clientY;
    const dist = downPt ? Math.hypot(x - downPt.x, y - downPt.y) : 0;
    const sel = window.getSelection();

    // a real drag with a text selection -> phrase
    if (sel && !sel.isCollapsed && dist > 8) {
      clearTimeout(pendingTap); pendingTap = null; lastTap = null;
      handleDrag(sel, x, y, touch);
      return;
    }
    if (dist > 8) return;   // a scroll/swipe, not a tap

    const word = e.target.closest(".word");

    // second tap on the same word within the window -> word lookup
    if (lastTap && word && lastTap.word === word && (performance.now() - lastTap.t) < 350) {
      clearTimeout(pendingTap); pendingTap = null; lastTap = null;
      handleWord(word, x, y, touch);
      return;
    }

    // otherwise: remember this tap, and after the double-tap window, treat it
    // as a sentence tap
    lastTap = word ? { t: performance.now(), word } : null;
    const target = e.target;
    clearTimeout(pendingTap);
    pendingTap = setTimeout(() => {
      pendingTap = null; lastTap = null;
      handleSentence(target, x, y, touch);
    }, word ? 300 : 0);
  });

  // dictionary word -> speak + meaning (single tap is fine here)
  els.dict.addEventListener("click", (e) => {
    const w = e.target.closest(".word");
    if (w) handleWord(w, e.clientX, e.clientY, e.pointerType !== "mouse");
  });
}

// ---------------------------------------------------------------------------
// Voice menu
// ---------------------------------------------------------------------------
function buildVoiceMenu(engines) {
  els.voice.innerHTML = "";
  VOICE_GROUPS.forEach((group) => {
    if (engines[group.engine] === false) return;
    const g = document.createElement("optgroup");
    g.label = group.label;
    group.voices.forEach(([val, name]) => {
      const o = document.createElement("option");
      o.value = val; o.textContent = name;
      g.appendChild(o);
    });
    els.voice.appendChild(g);
  });
  const saved = localStorage.getItem(VOICE_KEY);
  if (saved && [...els.voice.options].some((o) => o.value === saved)) els.voice.value = saved;
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
function init() {
  const savedRate = localStorage.getItem(RATE_KEY);
  if (savedRate) els.rate.value = savedRate;
  els.rate.addEventListener("change", () => localStorage.setItem(RATE_KEY, els.rate.value));
  els.voice.addEventListener("change", () => localStorage.setItem(VOICE_KEY, els.voice.value));

  fetch("/config")
    .then((r) => r.json())
    .then((cfg) => buildVoiceMenu(cfg.engines))
    .catch(() => buildVoiceMenu({ kokoro: true, say: true }));

  // dictionary: remember choice, but never auto-open the overlay on small screens
  setDict(localStorage.getItem(DICT_KEY) === "1" && isWide());
  els.dictToggle.addEventListener("click", () =>
    setDict(!document.body.classList.contains("dict-open")));
  els.menuToggle.addEventListener("click", () =>
    setNav(!document.body.classList.contains("nav-open")));
  els.scrim.addEventListener("click", closeDrawers);

  fetch("/data/texts.json")
    .then((r) => r.json())
    .then((data) => {
      tracks = data.tracks;
      flat = [];
      tracks.forEach((t) => t.lessons.forEach((lesson) => flat.push({ trackId: t.id, lesson })));

      buildNav();
      renderDictionary(data.dictionary);
      updateProgressUI();
      selectFromHash();
    });

  window.addEventListener("hashchange", () => {
    const h = parseHash();
    const entry = findEntry(h && h.track, h && h.lesson);
    if (entry && entry.lesson.id !== currentId) selectFromHash();
  });

  window.addEventListener("resize", updateScrim);
  setupReaderInteractions();

  // dismiss popup on any pointer outside it; Esc also closes
  document.addEventListener("pointerdown", (e) => {
    if (!els.popup.hidden && !els.popup.contains(e.target)) hidePopup();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { hidePopup(); closeDrawers(); } });
}

init();
