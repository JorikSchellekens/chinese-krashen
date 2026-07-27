# Mandarin reader (Krashen i+1)

A local reader for pinyin-only graded texts, with click-to-hear speech and
double-click translations. Every clip is cached to disk, so nothing is
synthesised twice.

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

- **Click a sentence** -> hear it and see its English translation.
- **Double-click a word** -> hear it and see its meaning.
- **Drag across several words** -> hear and translate just those.
- **Dictionary** (last nav button) -> every word so far, grouped by the text
  that introduced it. Click a word to hear it. It grows automatically as texts
  are added; nothing to maintain by hand.
- Voice / speed controls are in the top bar. "slow" speed is worth using early -
  copy the voice out loud.

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

To add a lesson: add any new words to `LEX` (keyed by pinyin), then add a
lesson dict to `LESSONS` whose sentences are `s("wǒ", "shì", ...)` calls
referencing lexicon keys. Punctuation tokens are the literal marks (`"."`,
`","`, `"?"`, `":"`, `'"'`). Re-run the build and refresh the page.

(The teacher - Claude - normally does this for you as your level grows.)

## Files

- `server.py`     - stdlib HTTP server + `/tts` (say -> AAC, disk-cached)
- `build_texts.py`- corpus source of truth -> `data/texts.json`
- `static/`       - the reader (index.html, reader.css, reader.js)
- `cache/`        - generated audio clips (safe to delete; regenerated on demand)
