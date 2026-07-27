#!/usr/bin/env python3
"""Local Mandarin reader server.

Serves the static reader and a /tts endpoint with two interchangeable engines:

  kokoro : neural TTS (kokoro-82M), natural sounding, fully offline. A little
           slower on the very first clip (model load) then ~0.3-0.5s per clip.
  say    : macOS `say` Chinese voices - robotic but instant and rock-solid on
           isolated single-word tones.

Every clip is cached on disk keyed by (engine, voice, rate, text), so nothing is
ever synthesised twice. The neural model is warmed up in a background thread at
startup so the first real click is fast.

Run:  uv run server.py       (uv reads pyproject.toml and sets up the env)
Then open http://localhost:8000
"""

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

# macOS-only: the `say` engine needs both `say` and `afconvert`.
SAY_AVAILABLE = (
    sys.platform == "darwin"
    and shutil.which("say") is not None
    and shutil.which("afconvert") is not None
)

# --- say (macOS) -------------------------------------------------------------
SAY_VOICES = {
    "Tingting", "Meijia", "Sinji",
    "Reed (Chinese (China mainland))", "Sandy (Chinese (China mainland))",
    "Flo (Chinese (China mainland))", "Eddy (Chinese (China mainland))",
    "Grandma (Chinese (China mainland))", "Grandpa (Chinese (China mainland))",
}
SAY_DEFAULT = "Tingting"

# --- kokoro (neural) ---------------------------------------------------------
KOKORO_VOICES = {
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
    "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
}
KOKORO_DEFAULT = "zf_xiaoxiao"
_kokoro_pipeline = None
_kokoro_lock = threading.Lock()
_kokoro_error = None


def get_kokoro():
    """Lazily build (once) and return the Kokoro pipeline, or raise."""
    global _kokoro_pipeline, _kokoro_error
    with _kokoro_lock:
        if _kokoro_pipeline is None:
            if _kokoro_error is not None:
                raise _kokoro_error
            try:
                from kokoro import KPipeline
                _kokoro_pipeline = KPipeline(lang_code="z")  # Mandarin
            except Exception as exc:  # remember the failure, don't retry forever
                _kokoro_error = exc
                raise
        return _kokoro_pipeline


def synth_kokoro(text, voice, rate):
    import numpy as np
    import soundfile as sf
    if voice not in KOKORO_VOICES:
        voice = KOKORO_DEFAULT
    speed = max(0.6, min(1.3, rate / 170.0))  # map wpm-ish control to a factor
    pipe = get_kokoro()
    chunks = [a for _, _, a in pipe(text, voice=voice, speed=speed)]
    if not chunks:
        raise RuntimeError("kokoro produced no audio")
    audio = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, audio, 24000, format="WAV")
    return buf.getvalue()


def synth_say(text, voice, rate):
    if voice not in SAY_VOICES:
        voice = SAY_DEFAULT
    aiff = os.path.join(CACHE, "_tmp_%d.aiff" % threading.get_ident())
    m4a = aiff[:-5] + ".m4a"
    try:
        subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", aiff, "--", text], check=True)
        subprocess.run(["afconvert", aiff, m4a, "-f", "m4af", "-d", "aac"], check=True)
        with open(m4a, "rb") as f:
            return f.read()
    finally:
        for p in (aiff, m4a):
            if os.path.exists(p):
                os.remove(p)


def synth(text, voice, rate, engine):
    """Return (audio_bytes, content_type), from cache when possible."""
    rate = max(80, min(300, int(rate)))
    # Fall back to kokoro when say isn't available (e.g. Linux).
    engine = "say" if (engine == "say" and SAY_AVAILABLE) else "kokoro"
    key = hashlib.sha1(f"{engine}|{voice}|{rate}|{text}".encode("utf-8")).hexdigest()
    if engine == "kokoro":
        path, ctype = os.path.join(CACHE, key + ".wav"), "audio/wav"
    else:
        path, ctype = os.path.join(CACHE, key + ".m4a"), "audio/mp4"

    if not os.path.exists(path):
        data = synth_kokoro(text, voice, rate) if engine == "kokoro" else synth_say(text, voice, rate)
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    with open(path, "rb") as f:
        return f.read(), ctype


STATIC = {
    "/": ("static/index.html", "text/html; charset=utf-8"),
    "/index.html": ("static/index.html", "text/html; charset=utf-8"),
    "/reader.css": ("static/reader.css", "text/css; charset=utf-8"),
    "/reader.js": ("static/reader.js", "application/javascript; charset=utf-8"),
    "/data/texts.json": ("data/texts.json", "application/json; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/config":
            body = json.dumps({"engines": {"kokoro": True, "say": SAY_AVAILABLE}}).encode()
            self._send(200, body, "application/json; charset=utf-8")
            return
        route = STATIC.get(path)
        if not route:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        rel, ctype = route
        try:
            with open(os.path.join(HERE, rel), "rb") as f:
                self._send(200, f.read(), ctype)
        except FileNotFoundError:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/tts":
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            text = (payload.get("text") or "").strip()
            if not text:
                self._send(400, b"empty text", "text/plain; charset=utf-8")
                return
            audio, ctype = synth(
                text[:2000],
                payload.get("voice") or "",
                payload.get("rate") or 170,
                payload.get("engine") or "say",
            )
            self._send(200, audio, ctype,
                       {"Cache-Control": "public, max-age=31536000, immutable"})
        except Exception as exc:
            self._send(500, str(exc).encode("utf-8"), "text/plain; charset=utf-8")


def warmup():
    try:
        get_kokoro()
        print("kokoro ready")
    except Exception as exc:
        print(f"kokoro unavailable ({exc}); the neural voices will fall back to an error, "
              f"macOS 'say' voices still work")


def main():
    os.makedirs(CACHE, exist_ok=True)
    threading.Thread(target=warmup, daemon=True).start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Mandarin reader running at http://{HOST}:{PORT}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
