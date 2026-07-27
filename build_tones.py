#!/usr/bin/env python3
"""
Source of truth for the tone trainer -> data/tones.json.

Two kinds of drill material:

  minimal_sets : single-syllable sets where only the tone changes (mā/má/mǎ/mà).
                 These isolate tone perception perfectly - same base, same
                 initial and final, only the pitch contour differs. Hand-curated
                 with common characters, then proofread.

  pairs        : two-syllable words (the real unit of connected speech) pulled
                 straight from the reader's already-proofread dictionary, so a
                 word drilled for its tones is also a word you have met. Bucketed
                 by tone pattern so the ~20 combinations all get covered.

  singles      : one-syllable words from the same dictionary, for perception
                 drills on real vocabulary rather than the minimal sets.

Run:  uv run build_tones.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TEXTS = os.path.join(HERE, "data", "texts.json")
OUT = os.path.join(HERE, "data", "tones.json")

# --- pinyin -> tone numbers -------------------------------------------------
# map each accented vowel to (plain vowel, tone number); 5 = neutral (no mark)
_TONE = {
    "ā": ("a", 1), "á": ("a", 2), "ǎ": ("a", 3), "à": ("a", 4),
    "ē": ("e", 1), "é": ("e", 2), "ě": ("e", 3), "è": ("e", 4),
    "ī": ("i", 1), "í": ("i", 2), "ǐ": ("i", 3), "ì": ("i", 4),
    "ō": ("o", 1), "ó": ("o", 2), "ǒ": ("o", 3), "ò": ("o", 4),
    "ū": ("u", 1), "ú": ("u", 2), "ǔ": ("u", 3), "ù": ("u", 4),
    "ǖ": ("ü", 1), "ǘ": ("ü", 2), "ǚ": ("ü", 3), "ǜ": ("ü", 4),
}

# valid pinyin finals, longest first, so a syllable splitter is greedy-correct
_FINALS = [
    "iang", "iong", "uang", "uai", "iao", "ian", "uan", "ang", "eng", "ing",
    "ong", "üan", "ua", "uo", "ui", "un", "üe", "ün", "ai", "ei", "ao", "ou",
    "an", "en", "in", "ia", "ie", "iu", "er", "ng", "a", "o", "e", "i", "u",
    "ü", "n",
]
_INITIALS = [
    "zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h",
    "j", "q", "x", "r", "z", "c", "s", "y", "w",
]


def strip_tones(p):
    return "".join(_TONE.get(ch, (ch, 0))[0] for ch in p)


def tone_of_syllable(syl):
    for ch in syl:
        if ch in _TONE:
            return _TONE[ch][1]
    return 5  # no mark -> neutral


def split_syllables(pinyin):
    """Split a hanzi-count-known pinyin string into syllables. Returns list or
    None if it does not cleanly parse (then we skip that word)."""
    plain = strip_tones(pinyin).lower().replace("'", "")
    syls, i, n = [], 0, len(plain)
    while i < n:
        init = ""
        for cand in _INITIALS:
            if plain.startswith(cand, i):
                init = cand
                break
        j = i + len(init)
        fin = ""
        for cand in _FINALS:
            if plain.startswith(cand, j):
                fin = cand
                break
        if not fin:
            return None
        syls.append((i, j + len(fin)))
        i = j + len(fin)
    return syls


def tone_pattern(hanzi, pinyin):
    """Tone number per syllable, aligned to hanzi count. None if uncertain."""
    han = [c for c in hanzi if "一" <= c <= "鿿"]
    spans = split_syllables(pinyin)
    if spans is None or len(spans) != len(han):
        return None
    return [tone_of_syllable(pinyin[a:b]) for a, b in spans]


# --- curated single-syllable minimal sets -----------------------------------
# (base, [ (hanzi, pinyin, tone, gloss) x up to 4 ]). Common characters only.
MINIMAL_SETS = [
    ("ma", [("妈", "mā", 1, "mother"), ("麻", "má", 2, "hemp / numb"),
            ("马", "mǎ", 3, "horse"), ("骂", "mà", 4, "to scold")]),
    ("ba", [("八", "bā", 1, "eight"), ("拔", "bá", 2, "to pull out"),
            ("把", "bǎ", 3, "to hold / handle"), ("爸", "bà", 4, "dad")]),
    ("yi", [("一", "yī", 1, "one"), ("姨", "yí", 2, "aunt"),
            ("椅", "yǐ", 3, "chair"), ("意", "yì", 4, "meaning")]),
    ("wu", [("屋", "wū", 1, "room / house"), ("无", "wú", 2, "without"),
            ("五", "wǔ", 3, "five"), ("雾", "wù", 4, "fog")]),
    ("tang", [("汤", "tāng", 1, "soup"), ("糖", "táng", 2, "sugar"),
              ("躺", "tǎng", 3, "to lie down"), ("烫", "tàng", 4, "scalding hot")]),
    ("bao", [("包", "bāo", 1, "to wrap / bun"), ("薄", "báo", 2, "thin"),
             ("饱", "bǎo", 3, "full (from eating)"), ("抱", "bào", 4, "to hug")]),
    ("shu", [("书", "shū", 1, "book"), ("熟", "shú", 2, "ripe / cooked"),
             ("鼠", "shǔ", 3, "rat / mouse"), ("树", "shù", 4, "tree")]),
    ("qing", [("青", "qīng", 1, "green / blue"), ("晴", "qíng", 2, "clear (sky)"),
              ("请", "qǐng", 3, "please / to invite"), ("庆", "qìng", 4, "to celebrate")]),
    ("xi", [("西", "xī", 1, "west"), ("习", "xí", 2, "to practise"),
            ("洗", "xǐ", 3, "to wash"), ("戏", "xì", 4, "play / drama")]),
    ("fan", [("翻", "fān", 1, "to flip over"), ("烦", "fán", 2, "annoyed"),
             ("反", "fǎn", 3, "reverse / opposite"), ("饭", "fàn", 4, "rice / meal")]),
    ("t[i]ao", [("挑", "tiāo", 1, "to pick / choose"), ("条", "tiáo", 2, "strip / measure word"),
                ("跳", "tiào", 4, "to jump")]),
    ("mai", [("埋", "mái", 2, "to bury"), ("买", "mǎi", 3, "to buy"),
             ("卖", "mài", 4, "to sell")]),
]

TONE_NAMES = {
    1: "flat / high", 2: "rising", 3: "dipping (low)", 4: "falling", 5: "neutral",
}


def build():
    data = json.load(open(TEXTS, encoding="utf-8"))
    words = []
    for group in data["dictionary"]:
        for w in group["words"]:
            words.append(w)

    singles, pairs = [], []
    seen_s, seen_p = set(), set()
    for w in words:
        h, p = w["h"], w["p"]
        han = [c for c in h if "一" <= c <= "鿿"]
        # skip proper names / latin (Jorik, Tom)
        if len(han) != len(h.replace(" ", "")) or not han:
            continue
        pat = tone_pattern(h, p)
        if pat is None:
            continue
        entry = {"h": h, "p": p, "g": w["g"], "pattern": pat, "track": w["track"]}
        if len(han) == 1 and h not in seen_s:
            seen_s.add(h)
            singles.append(entry)
        elif len(han) == 2 and h not in seen_p:
            seen_p.add(h)
            pairs.append(entry)

    # bucket pairs by tone pattern for coverage reporting
    buckets = {}
    for e in pairs:
        buckets.setdefault(tuple(e["pattern"]), []).append(e["p"])

    out = {
        "minimal_sets": [
            {"base": base,
             "options": [{"h": h, "p": p, "t": t, "g": g} for h, p, t, g in items]}
            for base, items in MINIMAL_SETS
        ],
        "singles": singles,
        "pairs": pairs,
        "tone_names": TONE_NAMES,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"minimal sets: {len(out['minimal_sets'])} "
          f"({sum(len(m['options']) for m in out['minimal_sets'])} syllables)")
    print(f"singles: {len(singles)}   pairs: {len(pairs)}")
    print(f"tone-pair patterns covered: {len(buckets)}")
    missing = []
    for a in range(1, 5):
        for b in list(range(1, 5)) + [5]:
            if (a, b) not in buckets:
                missing.append(f"{a}{b}")
    if missing:
        print("  patterns with no example word:", " ".join(missing))


if __name__ == "__main__":
    build()
