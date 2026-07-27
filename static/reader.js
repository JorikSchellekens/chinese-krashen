"use strict";

const els = {
  nav: document.getElementById("lessonNav"),
  list: document.getElementById("lessonList"),
  progress: document.getElementById("progress"),
  reader: document.getElementById("reader"),
  dict: document.getElementById("dict"),
  dictToggle: document.getElementById("dictToggle"),
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

let lessons = [];               // all lessons, in order
const railButtons = new Map();  // lesson id -> rail button
let currentId = null;

// Each value is "engine:voice"; grouped into <optgroup>s. A group is only shown
// if the server reports its engine is available (say is macOS-only).
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

async function speak(hanzi) {
  hanzi = (hanzi || "").trim();
  if (!hanzi) return;
  const [engine, voice] = splitVoice(els.voice.value);
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
function showPopup(x, y, headline, gloss) {
  const p = els.popup;
  p.innerHTML =
    `<div class="pu-head">${escapeHtml(headline)}</div>` +
    (gloss ? `<div class="pu-gloss">${escapeHtml(gloss)}</div>` : "");
  p.hidden = false;
  const pr = p.getBoundingClientRect();
  let left = Math.max(8, Math.min(x - pr.width / 2, window.innerWidth - pr.width - 8));
  let top = y + 14;
  if (top + pr.height > window.innerHeight - 8) top = y - pr.height - 14;
  p.style.left = left + window.scrollX + "px";
  p.style.top = top + window.scrollY + "px";
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

function renderLesson(lesson) {
  els.reader.innerHTML = "";
  els.reader.scrollTop = 0;

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
    progress[lesson.id] = !progress[lesson.id];
    if (!progress[lesson.id]) delete progress[lesson.id];
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
  sub.textContent = `${total} words so far - click to hear`;
  els.dict.appendChild(sub);

  sections.forEach((sec) => {
    const h3 = document.createElement("div");
    h3.className = "dict-section";
    h3.textContent = sec.title.split(" - ")[0];
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
// Progress UI
// ---------------------------------------------------------------------------
function updateProgressUI() {
  const total = lessons.length;
  const done = lessons.filter((l) => progress[l.id]).length;
  els.progress.innerHTML =
    `<div class="progress-bar"><div class="progress-fill" style="width:${
      total ? (done / total) * 100 : 0}%"></div></div>` +
    `<div class="progress-text">${done} of ${total} read</div>`;
  railButtons.forEach((btn, id) => btn.classList.toggle("done", !!progress[id]));
}

// ---------------------------------------------------------------------------
// Routing:  #<lesson-id>  keeps the open text across refresh / sharing
// ---------------------------------------------------------------------------
function idFromHash() {
  return decodeURIComponent(location.hash.replace(/^#\/?/, ""));
}

function selectLesson(id, { updateHash = true } = {}) {
  const lesson = lessons.find((l) => l.id === id) || lessons[0];
  if (!lesson) return;
  currentId = lesson.id;
  railButtons.forEach((btn, lid) => btn.classList.toggle("active", lid === lesson.id));
  hidePopup();
  renderLesson(lesson);
  if (updateHash && idFromHash() !== lesson.id) {
    location.hash = "#" + encodeURIComponent(lesson.id);
  }
}

// ---------------------------------------------------------------------------
// Interactions:  click = sentence,  double-click = word,  drag = selection
// ---------------------------------------------------------------------------
let downAt = null;
let suppressClick = false;
let clickTimer = null;

function handleSentence(target, x, y) {
  const sen = target.closest(".sentence");
  if (sen) { speak(sen.dataset.h); showPopup(x, y, sen.dataset.en); return; }
  const w = target.closest(".word");
  if (w) handleWord(w, x, y);
}
function handleWord(word, x, y) {
  speak(word.dataset.h);
  showPopup(x, y, word.dataset.p, word.dataset.g);
}
function handleDrag(sel, x, y) {
  const hanzi = [], gloss = [];
  els.reader.querySelectorAll(".word").forEach((w) => {
    if (sel.containsNode(w, true)) { hanzi.push(w.dataset.h); gloss.push(w.dataset.g); }
  });
  if (!hanzi.length) return;
  speak(hanzi.join(""));
  showPopup(x, y, sel.toString().trim(), gloss.join("  ·  "));
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
function setDict(open) {
  document.body.classList.toggle("show-dict", open);
  els.dictToggle.setAttribute("aria-pressed", open ? "true" : "false");
  localStorage.setItem(DICT_KEY, open ? "1" : "0");
}

function splitVoice(value) {
  const i = value.indexOf(":");
  return [value.slice(0, i), value.slice(i + 1)];
}

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
}

function init() {
  fetch("/config")
    .then((r) => r.json())
    .then((cfg) => buildVoiceMenu(cfg.engines))
    .catch(() => buildVoiceMenu({ kokoro: true, say: true }));

  // dictionary hidden by default; remember the user's choice
  setDict(localStorage.getItem(DICT_KEY) === "1");
  els.dictToggle.addEventListener("click", () =>
    setDict(!document.body.classList.contains("show-dict")));

  fetch("/data/texts.json")
    .then((r) => r.json())
    .then((data) => {
      lessons = data.lessons;

      lessons.forEach((lesson) => {
        const b = document.createElement("button");
        b.className = "lesson";
        b.innerHTML = `<span class="tick">✓</span><span></span>`;
        b.lastChild.textContent = lesson.title.split(" - ")[0];
        b.title = lesson.title;
        b.addEventListener("click", () =>
          (location.hash = "#" + encodeURIComponent(lesson.id)));
        railButtons.set(lesson.id, b);
        els.list.appendChild(b);
      });

      renderDictionary(data.dictionary);
      updateProgressUI();

      // open the lesson named in the URL, else the first one
      const wanted = idFromHash();
      selectLesson(lessons.some((l) => l.id === wanted) ? wanted : lessons[0].id);
    });

  // hash changes (back/forward, edited URL, rail clicks) drive the selection
  window.addEventListener("hashchange", () => {
    const id = idFromHash();
    if (id && id !== currentId) selectLesson(id, { updateHash: false });
  });

  // reader interactions
  els.reader.addEventListener("mousedown", (e) => {
    downAt = { x: e.clientX, y: e.clientY };
    suppressClick = false;
  });
  els.reader.addEventListener("mouseup", (e) => {
    const sel = window.getSelection();
    const dist = downAt ? Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) : 0;
    if (sel && !sel.isCollapsed && dist > 6) {
      suppressClick = true;
      clearTimeout(clickTimer);
      handleDrag(sel, e.pageX, e.pageY);
    }
  });
  els.reader.addEventListener("click", (e) => {
    if (suppressClick) return;
    const target = e.target, x = e.pageX, y = e.pageY;
    clearTimeout(clickTimer);
    clickTimer = setTimeout(() => handleSentence(target, x, y), 240);
  });
  els.reader.addEventListener("dblclick", (e) => {
    clearTimeout(clickTimer);
    const w = e.target.closest(".word");
    if (w) handleWord(w, e.pageX, e.pageY);
  });

  // dictionary word -> speak + meaning
  els.dict.addEventListener("click", (e) => {
    const w = e.target.closest(".word");
    if (w) handleWord(w, e.pageX, e.pageY);
  });

  // Dismiss the popup on any click outside the popup itself. A click that
  // lands on a word or sentence re-opens a fresh popup via its own handler.
  document.addEventListener("mousedown", (e) => {
    if (!els.popup.hidden && !els.popup.contains(e.target)) hidePopup();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hidePopup();
  });
}

init();
