# Mandarin reader (Krashen i+1)

A local reader for pinyin-only graded texts, with tap-to-hear speech and
double-tap translations. Every clip is cached to disk, so nothing is
synthesised twice. Works on desktop (three columns) and phones (slide-in
drawers, touch gestures).

## Tracks

Content is organised into **tracks** - themed sequences of short texts that all
draw on one shared vocabulary. Twelve so far, roughly easiest-first:

- **Foundations** - greetings, identity, having, liking, living, wanting.
- **Numbers & age** - zero to thirty-five, the counting word `ge`, asking ages.
- **Family & home** - parents, siblings, how many, how old, where they live.
- **Food & drink** - what you want, what is tasty, ordering a meal.
- **Every day** - today/tomorrow, telling the time, a whole day's routine.
- **Places & directions** - shops, schools, restaurants, and getting there.
- **Shopping & money** - buying, asking the price, expensive vs cheap.
- **Colours & things** - colours, and describing objects (new/old, nice).
- **Weather & seasons** - hot/cold, rain, the four seasons.
- **Days & dates** - days of the week, months, dates, birthdays.
- **Hobbies** - sport, music, films, the weekend.
- **Feelings & body** - happy, tired, busy, and being unwell.

A word learned in any track is a word you know in every track. The dictionary is
global: each distinct word appears once, grouped by kind (pronouns, verbs, food,
numbers...), tagged with the track where you first meet it. The recommended order
is top-to-bottom (later tracks reuse numbers, days, colours...), but nothing stops
you jumping around - the shared dictionary keeps it coherent.

## Speech engines

Pick a voice in the top bar; two engines sit behind the dropdown:

- **Kokoro (neural)** - kokoro-82M, natural sounding, fully offline. Default.
  First clip after a server start waits ~10s while the model loads (warmed up in
  the background at startup), then ~0.3-0.5s per clip.
- **macOS say (system)** - the built-in Chinese voices. Robotic, but instant and
  very reliable on isolated single-word tones.

## Run

```
uv run server.py
```

The first run creates a Python 3.12 virtualenv and installs the neural-TTS stack
(torch etc.) from `pyproject.toml` - a few minutes once, instant after. Then open
http://localhost:8000

Stop with Ctrl-C. (Change the port with `PORT=8080 uv run server.py`.)

## How to use it

- **Tap a sentence** -> hear it and see its English translation.
- **Double-tap a word** -> hear it and see its meaning.
- **Drag across several words** -> hear and translate just those.
  (Same gestures with a mouse: click / double-click / drag-select.)
- **☰ menu** (top left) -> tracks and their lessons, with a progress bar, per-track
  counts, and a difficulty marker (level dots) on each text. Mark texts as read to
  track progress; it survives refreshes.
- **Dictionary** button -> every word so far, grouped by kind, tagged with the
  track that introduced it. Tap a word to hear it. It grows automatically as
  texts are added; nothing to maintain by hand.
- Voice / speed controls live in the menu drawer. "slow" speed is worth using
  early - copy the voice out loud.
- The open text lives in the URL (`#track/lesson`), so a refresh or a shared link
  reopens the same place.

## Why hanzi are hidden under the pinyin

TTS voices pronounce Chinese characters, not pinyin ("wǒ" fed to a Chinese
voice is gibberish). So every word carries three things: the pinyin you read,
the hanzi used only for speech, and a gloss used only for the popup. You never
see the characters.

## Adding more texts

Texts live in `build_texts.py` as a compact lexicon + sentence lists, then get
compiled to `data/texts.json`:

```
uv run build_texts.py
```

To add a lesson: add any new words to `LEX` (keyed by pinyin, with a category
for the dictionary), build a lesson with `L(id, title, level, note, *paragraphs)`
whose sentences are `s("English", "wǒ", "shì", ...)` calls referencing lexicon
keys, and drop the lesson into a track's list (or add a new track to `TRACKS`).
Punctuation tokens are the literal marks (`"."`, `","`, `"?"`, `":"`, `'"'`).
The dictionary and every count rebuild themselves. Re-run the build and refresh.

(The teacher - Claude - normally does this for you as your level grows.)

## Files

- `server.py`     - stdlib HTTP server + `/tts` (say -> AAC, disk-cached)
- `build_texts.py`- corpus source of truth -> `data/texts.json`
- `static/`       - the reader (index.html, reader.css, reader.js)
- `cache/`        - generated audio clips (safe to delete; regenerated on demand)
