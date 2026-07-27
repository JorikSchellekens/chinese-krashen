"""Builds data/texts.json from a compact lexicon + sentence definitions.

Each word is stored with:
  h  = hanzi (characters)  -> used ONLY for text-to-speech, never shown
  p  = pinyin              -> what you read on screen
  g  = gloss               -> shown when you double-click it
  sp = leading space?      -> typographic spacing computed at build time

Content is organised into TRACKS. A track is a themed sequence of lessons
(greetings, numbers, family, food, daily life...). Every track draws on ONE
shared lexicon, so a word learned in any track is a word you know everywhere.

The dictionary is derived automatically and is GLOBAL: every distinct word,
deduped by hanzi across all tracks, grouped by meaning-category, tagged with the
track where you first meet it. That way it stays coherent no matter which order
you read the tracks in.
"""

import json
import os

# --- lexicon: key -> (hanzi, pinyin shown, gloss, category) ------------------
# Keys are usually the pinyin. Where one pinyin maps to two different words we
# add a suffixed key (e.g. bu4 vs bu2 for 不, zai4-again 再 vs zai4-at 在).
# The category groups the word in the dictionary (see CATS below).
LEX = {
    # --- pronouns ---
    "nǐ": ("你", "nǐ", "you", "pron"),
    "wǒ": ("我", "wǒ", "I, me", "pron"),
    "tā": ("他", "tā", "he / she", "pron"),
    "tāmen": ("他们", "tāmen", "they", "pron"),
    "wǒmen": ("我们", "wǒmen", "we, us", "pron"),
    # --- names ---
    "Jorik": ("Jorik", "Jorik", "Jorik (your name)", "name"),
    "Xiǎolín": ("小林", "Xiǎolín", "Xiaolin (a name)", "name"),
    "WángMěi": ("王美", "Wáng Měi", "Wang Mei (a name)", "name"),
    "Tom": ("Tom", "Tom", "Tom (a name)", "name"),
    # --- greetings & everyday expressions ---
    "hǎo": ("好", "hǎo", "good, well", "desc"),
    "xièxie": ("谢谢", "xièxie", "thanks", "social"),
    "qǐng": ("请", "qǐng", "please", "social"),
    "méiguānxi": ("没关系", "méi guānxi", "no problem, it's ok", "social"),
    "wǎn'ān": ("晚安", "wǎn'ān", "goodnight", "social"),
    "a": ("啊", "a", "ah (a soft exclamation)", "social"),
    # --- verbs ---
    "jiào": ("叫", "jiào", "to be called", "verb"),
    "shì": ("是", "shì", "to be (am / is / are)", "verb"),
    "shuō": ("说", "shuō", "to speak, to say", "verb"),
    "yǒu": ("有", "yǒu", "to have", "verb"),
    "méiyǒu": ("没有", "méiyǒu", "to not have", "verb"),
    "zhù": ("住", "zhù", "to live, to stay", "verb"),
    "xǐhuan": ("喜欢", "xǐhuan", "to like", "verb"),
    "zhīdào": ("知道", "zhīdào", "to know", "verb"),
    "xuéxí": ("学习", "xuéxí", "to study", "verb"),
    "xiǎng": ("想", "xiǎng", "to want to, would like to", "verb"),
    "qù": ("去", "qù", "to go, to go to", "verb"),
    "lái": ("来", "lái", "to come", "verb"),
    "chī": ("吃", "chī", "to eat", "verb"),
    "míngbai": ("明白", "míngbai", "to understand", "verb"),
    "huì": ("会", "huì", "will, can", "verb"),
    # --- question words ---
    "shénme": ("什么", "shénme", "what", "ask"),
    "ma": ("吗", "ma", "(turns a sentence into a yes/no question)", "ask"),
    "ne": ("呢", "ne", "and you? / what about...?", "ask"),
    "wèishénme": ("为什么", "wèishénme", "why", "ask"),
    "nǎr": ("哪儿", "nǎr", "where", "ask"),
    "shéi": ("谁", "shéi", "who", "ask"),
    # --- describing words (adjectives / adverbs) ---
    "hái": ("还", "hái", "still, fairly", "desc"),
    "tài": ("太", "tài", "too, overly", "desc"),
    "hěn": ("很", "hěn", "very", "desc"),
    "duō": ("多", "duō", "much, many", "desc"),
    "yě": ("也", "yě", "also, too", "desc"),
    "yìdiǎn": ("一点", "yìdiǎn", "a little", "desc"),
    "dōu": ("都", "dōu", "both, all", "desc"),
    "nán": ("难", "nán", "hard, difficult", "desc"),
    "hǎochī": ("好吃", "hǎochī", "tasty, good to eat", "desc"),
    "yǒuyìsi": ("有意思", "yǒuyìsi", "interesting", "desc"),
    "duì": ("对", "duì", "right, correct", "desc"),
    # --- grammar / function words ---
    "bù": ("不", "bù", "not", "fn"),
    "bú": ("不", "bú", "not (said bu2 before a 4th-tone word)", "fn"),
    "de": ("的", "de", "('s / of - links a describer to a noun)", "fn"),
    "le": ("了", "le", "(marks something completed or changed)", "fn"),
    "hé": ("和", "hé", "and", "fn"),
    "kěshì": ("可是", "kěshì", "but", "fn"),
    "yīnwèi": ("因为", "yīnwèi", "because", "fn"),
    "zài": ("在", "zài", "to be at / in (a place)", "fn"),
    "zàiA": ("再", "zài", "again", "fn"),
    "yíbiàn": ("一遍", "yí biàn", "once (one time through)", "fn"),
    "yíge": ("一个", "yí ge", "one, a", "num"),
    "měitiān": ("每天", "měitiān", "every day", "time"),
    # --- people & roles ---
    "rén": ("人", "rén", "person", "people"),
    "lǎoshī": ("老师", "lǎoshī", "teacher", "people"),
    "xuésheng": ("学生", "xuésheng", "student", "people"),
    "péngyou": ("朋友", "péngyou", "friend", "people"),
    # --- places ---
    "Zhōngguó": ("中国", "Zhōngguó", "China", "place"),
    "Yīngguó": ("英国", "Yīngguó", "Britain", "place"),
    "Běijīng": ("北京", "Běijīng", "Beijing", "place"),
    "Lúndūn": ("伦敦", "Lúndūn", "London", "place"),
    # --- other nouns ---
    "míngzi": ("名字", "míngzi", "name", "misc"),
    "yìsi": ("意思", "yìsi", "meaning", "misc"),
    "Zhōngwén": ("中文", "Zhōngwén", "Chinese (the language)", "misc"),
    "Yīngwén": ("英文", "Yīngwén", "English (the language)", "misc"),
    "cài": ("菜", "cài", "food, dish", "food"),

    # === Track: Numbers & age ===============================================
    "líng": ("零", "líng", "zero", "num"),
    "yī": ("一", "yī", "one", "num"),
    "èr": ("二", "èr", "two", "num"),
    "sān": ("三", "sān", "three", "num"),
    "sì": ("四", "sì", "four", "num"),
    "wǔ": ("五", "wǔ", "five", "num"),
    "liù": ("六", "liù", "six", "num"),
    "qī": ("七", "qī", "seven", "num"),
    "bā": ("八", "bā", "eight", "num"),
    "jiǔ": ("九", "jiǔ", "nine", "num"),
    "shí": ("十", "shí", "ten", "num"),
    "liǎng": ("两", "liǎng", "two (of things: liǎng ge)", "num"),
    "shíbā": ("十八", "shíbā", "eighteen", "num"),
    "èrshí": ("二十", "èrshí", "twenty", "num"),
    "èrshíbā": ("二十八", "èrshíbā", "twenty-eight", "num"),
    "sānshí": ("三十", "sānshí", "thirty", "num"),
    "sānshíwǔ": ("三十五", "sānshíwǔ", "thirty-five", "num"),
    "shíyī": ("十一", "shíyī", "eleven", "num"),
    "shí'èr": ("十二", "shí'èr", "twelve", "num"),
    "ge": ("个", "ge", "(the everyday counting word: sān ge rén)", "fn"),
    "jǐ": ("几", "jǐ", "how many (small number)", "ask"),
    "suì": ("岁", "suì", "years old", "num"),
    "dà": ("大", "dà", "big; old (of age)", "desc"),
    "xiǎo": ("小", "xiǎo", "small; young", "desc"),

    # === Track: Family & home ==============================================
    "jiā": ("家", "jiā", "home, family", "place"),
    "bàba": ("爸爸", "bàba", "dad", "people"),
    "māma": ("妈妈", "māma", "mum", "people"),
    "gēge": ("哥哥", "gēge", "older brother", "people"),
    "dìdi": ("弟弟", "dìdi", "younger brother", "people"),
    "jiějie": ("姐姐", "jiějie", "older sister", "people"),
    "mèimei": ("妹妹", "mèimei", "younger sister", "people"),

    # === Track: Food & drink ===============================================
    "hē": ("喝", "hē", "to drink", "verb"),
    "yào": ("要", "yào", "to want, to need, to order", "verb"),
    "chá": ("茶", "chá", "tea", "food"),
    "kāfēi": ("咖啡", "kāfēi", "coffee", "food"),
    "shuǐ": ("水", "shuǐ", "water", "food"),
    "mǐfàn": ("米饭", "mǐfàn", "rice", "food"),
    "miàn": ("面", "miàn", "noodles", "food"),
    "ròu": ("肉", "ròu", "meat", "food"),
    "yú": ("鱼", "yú", "fish", "food"),
    "jīdàn": ("鸡蛋", "jīdàn", "egg", "food"),
    "è": ("饿", "è", "hungry", "desc"),
    "kě": ("渴", "kě", "thirsty", "desc"),
    "hǎohē": ("好喝", "hǎohē", "nice to drink", "desc"),

    # === Track: Every day (time & routine) =================================
    "jīntiān": ("今天", "jīntiān", "today", "time"),
    "míngtiān": ("明天", "míngtiān", "tomorrow", "time"),
    "zuótiān": ("昨天", "zuótiān", "yesterday", "time"),
    "xiànzài": ("现在", "xiànzài", "now", "time"),
    "zǎoshang": ("早上", "zǎoshang", "(early) morning", "time"),
    "shàngwǔ": ("上午", "shàngwǔ", "morning (forenoon)", "time"),
    "xiàwǔ": ("下午", "xiàwǔ", "afternoon", "time"),
    "wǎnshang": ("晚上", "wǎnshang", "evening", "time"),
    "diǎn": ("点", "diǎn", "o'clock", "time"),
    "bàn": ("半", "bàn", "half (half past)", "time"),
    "qǐchuáng": ("起床", "qǐchuáng", "to get up", "verb"),
    "shuìjiào": ("睡觉", "shuìjiào", "to sleep", "verb"),
    "gōngzuò": ("工作", "gōngzuò", "to work; work", "verb"),
    "kàn": ("看", "kàn", "to look, watch, read", "verb"),
    "shū": ("书", "shū", "book", "misc"),
    "zuò": ("做", "zuò", "to do", "verb"),
    "fàn": ("饭", "fàn", "a meal, cooked rice", "food"),

    # === Track: Places & directions ========================================
    "shāngdiàn": ("商店", "shāngdiàn", "shop", "place"),
    "xuéxiào": ("学校", "xuéxiào", "school", "place"),
    "fànguǎn": ("饭馆", "fànguǎn", "restaurant", "place"),
    "yīyuàn": ("医院", "yīyuàn", "hospital", "place"),
    "lǐ": ("里", "lǐ", "inside (X lǐ = in X)", "fn"),
    "pángbiān": ("旁边", "pángbiān", "next to, beside", "place"),
    "zǒu": ("走", "zǒu", "to walk, to go", "verb"),
    "zǒulù": ("走路", "zǒulù", "to walk, to go on foot", "verb"),
    "zuòB": ("坐", "zuò", "to sit; to travel by (zuò chē)", "verb"),
    "chē": ("车", "chē", "car, vehicle", "misc"),
    "yuǎn": ("远", "yuǎn", "far", "desc"),
    "jìn": ("近", "jìn", "near, close", "desc"),

    # === Track: Shopping & money ===========================================
    "mǎi": ("买", "mǎi", "to buy", "verb"),
    "qián": ("钱", "qián", "money", "misc"),
    "kuài": ("块", "kuài", "yuan (unit of money)", "num"),
    "duōshao": ("多少", "duōshao", "how much, how many", "ask"),
    "guì": ("贵", "guì", "expensive", "desc"),
    "piányi": ("便宜", "piányi", "cheap", "desc"),
    "zhège": ("这个", "zhège", "this, this one", "fn"),
    "nàge": ("那个", "nàge", "that, that one", "fn"),

    # === Track: Colours & things ===========================================
    "yánsè": ("颜色", "yánsè", "colour", "misc"),
    "hóngsè": ("红色", "hóngsè", "red", "desc"),
    "lánsè": ("蓝色", "lánsè", "blue", "desc"),
    "báisè": ("白色", "báisè", "white", "desc"),
    "hēisè": ("黑色", "hēisè", "black", "desc"),
    "xīn": ("新", "xīn", "new", "desc"),
    "jiù": ("旧", "jiù", "old (of things)", "desc"),
    "hǎokàn": ("好看", "hǎokàn", "good-looking, nice", "desc"),
    "háishì": ("还是", "háishì", "or (in a question)", "ask"),

    # === Track: Weather & seasons ==========================================
    "tiānqì": ("天气", "tiānqì", "weather", "misc"),
    "rè": ("热", "rè", "hot", "desc"),
    "lěng": ("冷", "lěng", "cold", "desc"),
    "xiàyǔ": ("下雨", "xiàyǔ", "to rain", "verb"),
    "chūntiān": ("春天", "chūntiān", "spring", "time"),
    "xiàtiān": ("夏天", "xiàtiān", "summer", "time"),
    "qiūtiān": ("秋天", "qiūtiān", "autumn", "time"),
    "dōngtiān": ("冬天", "dōngtiān", "winter", "time"),

    # === Track: Hobbies ====================================================
    "dǎ": ("打", "dǎ", "to play (a ball game), to hit", "verb"),
    "qiú": ("球", "qiú", "ball", "misc"),
    "lánqiú": ("篮球", "lánqiú", "basketball", "misc"),
    "tī": ("踢", "tī", "to kick", "verb"),
    "zúqiú": ("足球", "zúqiú", "football", "misc"),
    "tīng": ("听", "tīng", "to listen", "verb"),
    "yīnyuè": ("音乐", "yīnyuè", "music", "misc"),
    "chàng": ("唱", "chàng", "to sing", "verb"),
    "gē": ("歌", "gē", "song", "misc"),
    "diànyǐng": ("电影", "diànyǐng", "film, movie", "misc"),
    "yóuyǒng": ("游泳", "yóuyǒng", "to swim", "verb"),

    # === Track: Feelings & body ============================================
    "gāoxìng": ("高兴", "gāoxìng", "happy, glad", "desc"),
    "lèi": ("累", "lèi", "tired", "desc"),
    "máng": ("忙", "máng", "busy", "desc"),
    "tóu": ("头", "tóu", "head", "misc"),
    "téng": ("疼", "téng", "to ache, to hurt", "verb"),
    "bìng": ("病", "bìng", "illness; to be ill", "misc"),
    "shūfu": ("舒服", "shūfu", "comfortable (bù shūfu = unwell)", "desc"),

    # === Track: Days & dates ===============================================
    "xīngqī": ("星期", "xīngqī", "week", "time"),
    "xīngqīyī": ("星期一", "xīngqīyī", "Monday", "time"),
    "xīngqī'èr": ("星期二", "xīngqī'èr", "Tuesday", "time"),
    "xīngqīsān": ("星期三", "xīngqīsān", "Wednesday", "time"),
    "xīngqīsì": ("星期四", "xīngqīsì", "Thursday", "time"),
    "xīngqīwǔ": ("星期五", "xīngqīwǔ", "Friday", "time"),
    "xīngqīliù": ("星期六", "xīngqīliù", "Saturday", "time"),
    "xīngqītiān": ("星期天", "xīngqītiān", "Sunday", "time"),
    "yuè": ("月", "yuè", "month", "time"),
    "hào": ("号", "hào", "day (of the month)", "time"),
    "shēngrì": ("生日", "shēngrì", "birthday", "misc"),
}

# dictionary categories, in display order: (key, human label)
CATS = [
    ("pron", "Pronouns"),
    ("name", "Names"),
    ("people", "People & family"),
    ("place", "Places"),
    ("food", "Food & drink"),
    ("time", "Time"),
    ("num", "Numbers & counting"),
    ("verb", "Verbs"),
    ("desc", "Describing words"),
    ("ask", "Questions"),
    ("social", "Everyday expressions"),
    ("fn", "Grammar words"),
    ("misc", "Other"),
]

# punctuation: display mark -> full-width mark for the TTS voice
PUNCT = {
    ".": "。",
    ",": "，",
    "!": "！",
    "?": "？",
    ":": "：",
    '"': "",   # quotes: shown, silent for TTS
    "'": "",
}

QUOTES = {'"', "'"}
HARD_CLOSERS = {".", ",", "!", "?", ":"}  # always hug the preceding token


def _tok(item):
    if item in PUNCT:
        return {"p": item, "h": PUNCT[item]}
    if item in LEX:
        h, p, g, _cat = LEX[item]
        return {"h": h, "p": p, "g": g}
    raise KeyError(f"unknown token: {item!r}")


def s(en, *items):
    """A sentence: English translation + tokens, with spacing worked out.

    A token gets a leading space unless it is a closing mark (. , ! ? : or a
    closing quote) or it directly follows an opening quote.
    """
    toks = []
    qopen = {'"': False, "'": False}
    prev_opener = False
    for idx, item in enumerate(items):
        is_opener = is_closer = False
        if item in QUOTES:
            if not qopen[item]:
                is_opener = True
                qopen[item] = True
            else:
                is_closer = True
                qopen[item] = False
        elif item in HARD_CLOSERS:
            is_closer = True

        if idx == 0 or is_closer or prev_opener:
            sp = False
        else:
            sp = True

        t = _tok(item)
        t["sp"] = sp
        toks.append(t)
        prev_opener = is_opener
    return {"en": en, "t": toks}


def L(id, title, level, note, *paragraphs):
    """A lesson. level 1-3 is a rough difficulty for the track's own progression."""
    return {"id": id, "title": title, "level": level, "note": note,
            "paragraphs": list(paragraphs)}


# ===========================================================================
# TRACK 1 - Foundations (the original graded reader)
# ===========================================================================
FOUNDATIONS = [
    L("warmup", "Warm-up - greetings", 1,
      "Everything you have already seen. Read it out loud. Tap a sentence to hear "
      "it, double-tap a word for its meaning, or drag across a few.",
      [
          s("Hello!", "nǐ", "hǎo", "!"),
          s("My name is Jorik.", "wǒ", "jiào", "Jorik", "."),
          s("What is your name?", "nǐ", "jiào", "shénme", "míngzi", "?"),
      ],
      [
          s("How are you?", "nǐ", "hǎo", "ma", "?"),
          s("I am very well.", "wǒ", "hěn", "hǎo", "."),
          s("I am okay.", "wǒ", "hái", "hǎo", "."),
          s("I am not very well.", "wǒ", "bù", "tài", "hǎo", "."),
          s("And you?", "nǐ", "ne", "?"),
          s("Thanks!", "xièxie", "!"),
      ]),
    L("text-1", "Text 1 - who speaks Chinese", 1,
      "New words appear woven into what you know. Do not memorise - just read.",
      [
          s("My name is Xiaolin.", "wǒ", "jiào", "Xiǎolín", "."),
          s("I am Chinese.", "wǒ", "shì", "Zhōngguó", "rén", "."),
      ],
      [
          s("Your name is Jorik.", "nǐ", "jiào", "Jorik", "."),
          s("You are not Chinese.", "nǐ", "bú", "shì", "Zhōngguó", "rén", "."),
          s("You are British.", "nǐ", "shì", "Yīngguó", "rén", "."),
      ],
      [
          s("Xiaolin is Chinese.", "Xiǎolín", "shì", "Zhōngguó", "rén", "."),
          s("Xiaolin speaks Chinese.", "Xiǎolín", "shuō", "Zhōngwén", "."),
      ],
      [
          s("Jorik is British.", "Jorik", "shì", "Yīngguó", "rén", "."),
          s("Jorik also speaks Chinese.", "Jorik", "yě", "shuō", "Zhōngwén", "."),
      ],
      [
          s("Jorik speaks a little Chinese.", "Jorik", "shuō", "yìdiǎn", "Zhōngwén", "."),
          s("He does not speak much Chinese, but he speaks a little.",
            "tā", "bù", "shuō", "hěn", "duō", "Zhōngwén", ",",
            "kěshì", "tā", "shuō", "yìdiǎn", "."),
      ],
      [
          s("Xiaolin speaks a lot of Chinese.",
            "Xiǎolín", "shuō", "hěn", "duō", "Zhōngwén", "."),
          s("He is Chinese!", "tā", "shì", "Zhōngguó", "rén", "!"),
      ]),
    L("text-2", "Text 2 - teacher and student", 2,
      "New here: lǎoshī, xuésheng, de. They repeat many times on purpose.",
      [
          s("Xiaolin is a teacher.", "Xiǎolín", "shì", "lǎoshī", "."),
          s("She is a Chinese teacher.", "tā", "shì", "Zhōngwén", "lǎoshī", "."),
          s("She is a very good teacher.", "tā", "shì", "hěn", "hǎo", "de", "lǎoshī", "."),
      ],
      [
          s("Jorik is a student.", "Jorik", "shì", "xuésheng", "."),
          s("He is not a teacher.", "tā", "bú", "shì", "lǎoshī", "."),
          s("He is Xiaolin's student.", "tā", "shì", "Xiǎolín", "de", "xuésheng", "."),
      ],
      [
          s("Xiaolin is Jorik's teacher.", "Xiǎolín", "shì", "Jorik", "de", "lǎoshī", "."),
          s("Jorik is Xiaolin's student.", "Jorik", "shì", "Xiǎolín", "de", "xuésheng", "."),
      ],
      [
          s('Xiaolin says: "How are you?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "hǎo", "ma", "?", '"'),
      ],
      [
          s('Jorik says: "I am very well. And you?"',
            "Jorik", "shuō", ":", '"', "wǒ", "hěn", "hǎo", ".",
            "nǐ", "ne", "?", '"'),
      ],
      [
          s('Xiaolin says: "I am very well too."',
            "Xiǎolín", "shuō", ":", '"', "wǒ", "yě", "hěn", "hǎo", ".", '"'),
      ],
      [
          s("Jorik speaks a little Chinese.", "Jorik", "shuō", "yìdiǎn", "Zhōngwén", "."),
          s('Xiaolin says: "Your Chinese is very good!"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "de", "Zhōngwén",
            "hěn", "hǎo", "!", '"'),
      ],
      [
          s('Jorik says: "Thanks! But I speak a little. I do not speak much."',
            "Jorik", "shuō", ":", '"', "xièxie", "!", "kěshì", "wǒ",
            "shuō", "yìdiǎn", ".", "wǒ", "bù", "shuō", "hěn", "duō", ".", '"'),
      ],
      [
          s('Xiaolin says: "A little is very good. A little is also Chinese!"',
            "Xiǎolín", "shuō", ":", '"', "yìdiǎn", "hěn", "hǎo", ".",
            "yìdiǎn", "yě", "shì", "Zhōngwén", "!", '"'),
      ]),
    L("text-3", "Text 3 - I don't understand", 2,
      "New here: Yīngwén, míngbai, yìsi. Notice how 'shénme yìsi?' means 'what does it mean?'.",
      [
          s("Xiaolin is a teacher.", "Xiǎolín", "shì", "lǎoshī", "."),
          s("She speaks Chinese, and she also speaks a little English.",
            "tā", "shuō", "Zhōngwén", ",", "tā", "yě", "shuō",
            "yìdiǎn", "Yīngwén", "."),
      ],
      [
          s("Jorik is a student.", "Jorik", "shì", "xuésheng", "."),
          s("He speaks English, and he also speaks a little Chinese.",
            "tā", "shuō", "Yīngwén", ",", "tā", "yě", "shuō",
            "yìdiǎn", "Zhōngwén", "."),
      ],
      [
          s("Xiaolin speaks Chinese.", "Xiǎolín", "shuō", "Zhōngwén", "."),
          s("Jorik does not understand.", "Jorik", "bù", "míngbai", "."),
      ],
      [
          s('Jorik says: "I do not understand. What does it mean?"',
            "Jorik", "shuō", ":", '"', "wǒ", "bù", "míngbai", ".",
            "shénme", "yìsi", "?", '"'),
      ],
      [
          s("Xiaolin speaks English.", "Xiǎolín", "shuō", "Yīngwén", "."),
          s("Jorik understands.", "Jorik", "míngbai", "."),
      ],
      [
          s('Jorik says: "Ah, I understand!"',
            "Jorik", "shuō", ":", '"', "a", ",", "wǒ", "míngbai", "!", '"'),
      ],
      [
          s('Xiaolin says: "You are a very good student."',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "shì", "hěn", "hǎo",
            "de", "xuésheng", ".", '"'),
      ],
      [
          s('Jorik says: "Thanks, teacher."',
            "Jorik", "shuō", ":", '"', "xièxie", ",", "lǎoshī", ".", '"'),
      ]),
    L("text-3-check", "Check - answer shì or bú shì", 2,
      "Read each question. Answer out loud with shì (yes) or bú shì (no).",
      [
          s("Is Xiaolin Chinese?", "Xiǎolín", "shì", "Zhōngguó", "rén", "ma", "?"),
          s("Is Jorik Chinese?", "Jorik", "shì", "Zhōngguó", "rén", "ma", "?"),
          s("Is Xiaolin a student?", "Xiǎolín", "shì", "xuésheng", "ma", "?"),
          s("Is Jorik Xiaolin's teacher?",
            "Jorik", "shì", "Xiǎolín", "de", "lǎoshī", "ma", "?"),
      ]),
    L("text-4", "Text 4 - friends", 2,
      "New here: yǒu / méiyǒu (have / not have), péngyou, hé, dōu, tāmen.",
      [
          s("Xiaolin has a friend.", "Xiǎolín", "yǒu", "yíge", "péngyou", "."),
          s("Her friend is called Wang Mei.",
            "tā", "de", "péngyou", "jiào", "WángMěi", "."),
      ],
      [
          s("Wang Mei is also a teacher.", "WángMěi", "yě", "shì", "lǎoshī", "."),
          s("Xiaolin and Wang Mei are both teachers.",
            "Xiǎolín", "hé", "WángMěi", "dōu", "shì", "lǎoshī", "."),
          s("They are very good friends.",
            "tāmen", "shì", "hěn", "hǎo", "de", "péngyou", "."),
      ],
      [
          s("Jorik also has a friend.", "Jorik", "yě", "yǒu", "yíge", "péngyou", "."),
          s("His friend is called Tom.", "tā", "de", "péngyou", "jiào", "Tom", "."),
          s("Tom is British.", "Tom", "shì", "Yīngguó", "rén", "."),
      ],
      [
          s("Tom does not speak Chinese.", "Tom", "bù", "shuō", "Zhōngwén", "."),
          s("Tom does not have a Chinese teacher.",
            "Tom", "méiyǒu", "Zhōngwén", "lǎoshī", "."),
          s("Jorik has a Chinese teacher.", "Jorik", "yǒu", "Zhōngwén", "lǎoshī", "."),
      ],
      [
          s('Jorik says: "I have a teacher, but you do not have a teacher."',
            "Jorik", "shuō", ":", '"', "wǒ", "yǒu", "lǎoshī", ",",
            "kěshì", "nǐ", "méiyǒu", "lǎoshī", ".", '"'),
      ],
      [
          s('Tom says: "I do not have a teacher, but I have you! You are my Chinese teacher."',
            "Tom", "shuō", ":", '"', "wǒ", "méiyǒu", "lǎoshī", ",",
            "kěshì", "wǒ", "yǒu", "nǐ", "!", "nǐ", "shì", "wǒ", "de",
            "Zhōngwén", "lǎoshī", ".", '"'),
      ],
      [
          s('Jorik says: "I am not a teacher! I am a student. I speak a little Chinese, I do not speak much."',
            "Jorik", "shuō", ":", '"', "wǒ", "bú", "shì", "lǎoshī", "!",
            "wǒ", "shì", "xuésheng", ".", "wǒ", "shuō", "yìdiǎn", "Zhōngwén", ",",
            "wǒ", "bù", "shuō", "hěn", "duō", ".", '"'),
      ]),
    L("text-5", "Text 5 - where people live", 2,
      "New here: zhù (live), zài (at / in), nǎr (where), Běijīng, Lúndūn.",
      [
          s("Xiaolin lives in Beijing.", "Xiǎolín", "zhù", "zài", "Běijīng", "."),
          s("Beijing is in China.", "Běijīng", "zài", "Zhōngguó", "."),
      ],
      [
          s("Jorik lives in London.", "Jorik", "zhù", "zài", "Lúndūn", "."),
          s("London is in Britain.", "Lúndūn", "zài", "Yīngguó", "."),
      ],
      [
          s('Wang Mei says: "Where does Jorik live?"',
            "WángMěi", "shuō", ":", '"', "Jorik", "zhù", "zài", "nǎr", "?", '"'),
      ],
      [
          s('Xiaolin says: "He lives in London."',
            "Xiǎolín", "shuō", ":", '"', "tā", "zhù", "zài", "Lúndūn", ".", '"'),
      ],
      [
          s('Wang Mei says: "Where is London?"',
            "WángMěi", "shuō", ":", '"', "Lúndūn", "zài", "nǎr", "?", '"'),
      ],
      [
          s('Xiaolin says: "London is in Britain. London is not in China."',
            "Xiǎolín", "shuō", ":", '"', "Lúndūn", "zài", "Yīngguó", ".",
            "Lúndūn", "bú", "zài", "Zhōngguó", ".", '"'),
      ],
      [
          s("Tom also lives in London.", "Tom", "yě", "zhù", "zài", "Lúndūn", "."),
          s("Jorik and Tom both live in London; they both live in Britain.",
            "Jorik", "hé", "Tom", "dōu", "zhù", "zài", "Lúndūn", ",",
            "tāmen", "dōu", "zhù", "zài", "Yīngguó", "."),
      ],
      [
          s("Xiaolin and Wang Mei both live in Beijing; they are both Chinese.",
            "Xiǎolín", "hé", "WángMěi", "dōu", "zhù", "zài", "Běijīng", ",",
            "tāmen", "dōu", "shì", "Zhōngguó", "rén", "."),
          s("Jorik does not live in Beijing, but his teacher lives in Beijing.",
            "Jorik", "bú", "zhù", "zài", "Běijīng", ",", "kěshì", "tā", "de",
            "lǎoshī", "zhù", "zài", "Běijīng", "."),
      ]),
    L("text-6", "Text 6 - likes and reasons", 3,
      "New here: xǐhuan (like), wèishénme (why), yīnwèi (because), nán, cài, hǎochī.",
      [
          s("Jorik likes Chinese.", "Jorik", "xǐhuan", "Zhōngwén", "."),
          s("He likes Chinese a lot.", "tā", "hěn", "xǐhuan", "Zhōngwén", "."),
      ],
      [
          s('Tom says: "Why do you like Chinese?"',
            "Tom", "shuō", ":", '"', "nǐ", "wèishénme", "xǐhuan", "Zhōngwén", "?", '"'),
      ],
      [
          s('Jorik says: "Because Chinese is very interesting."',
            "Jorik", "shuō", ":", '"', "yīnwèi", "Zhōngwén", "hěn", "yǒuyìsi", ".", '"'),
      ],
      [
          s('Tom says: "But Chinese is very hard!"',
            "Tom", "shuō", ":", '"', "kěshì", "Zhōngwén", "hěn", "nán", "!", '"'),
      ],
      [
          s('Jorik says: "Right, Chinese is very hard. Very hard, but very interesting."',
            "Jorik", "shuō", ":", '"', "duì", ",", "Zhōngwén", "hěn", "nán", ".",
            "hěn", "nán", ",", "kěshì", "hěn", "yǒuyìsi", ".", '"'),
      ],
      [
          s("Jorik also likes Chinese food.", "Jorik", "yě", "xǐhuan", "Zhōngguó", "cài", "."),
          s('He says: "Chinese food is very tasty."',
            "tā", "shuō", ":", '"', "Zhōngguó", "cài", "hěn", "hǎochī", ".", '"'),
      ],
      [
          s("Tom does not like Chinese food.", "Tom", "bù", "xǐhuan", "Zhōngguó", "cài", "."),
          s("Tom likes British food.", "Tom", "xǐhuan", "Yīngguó", "cài", "."),
      ],
      [
          s('Jorik says: "British food is not tasty!"',
            "Jorik", "shuō", ":", '"', "Yīngguó", "cài", "bù", "hǎochī", "!", '"'),
      ],
      [
          s('Tom says: "I do not understand. Why is it not tasty?"',
            "Tom", "shuō", ":", '"', "wǒ", "bù", "míngbai", ".",
            "wèishénme", "bù", "hǎochī", "?", '"'),
      ],
      [
          s('Jorik says: "Because I am British, I know."',
            "Jorik", "shuō", ":", '"', "yīnwèi", "wǒ", "shì", "Yīngguó", "rén", ",",
            "wǒ", "zhīdào", ".", '"'),
      ]),
    L("text-7", "Text 7 - wanting to go to China", 3,
      "The longest yet. New here: měitiān, xuéxí, xiǎng, qù, lái, wǒmen, chī, "
      "and the phrase 'qǐng zài shuō yí biàn' (please say it again).",
      [
          s("Jorik studies Chinese every day.", "Jorik", "měitiān", "xuéxí", "Zhōngwén", "."),
          s("Every day!", "měitiān", "!"),
          s("He really likes studying Chinese.", "tā", "hěn", "xǐhuan", "xuéxí", "Zhōngwén", "."),
          s("Xiaolin is in Beijing, Jorik is in London, but they speak Chinese every day.",
            "Xiǎolín", "zài", "Běijīng", ",", "Jorik", "zài", "Lúndūn", ",",
            "kěshì", "tāmen", "měitiān", "shuō", "Zhōngwén", "."),
      ],
      [
          s('Xiaolin says: "Do you want to go to China?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "xiǎng", "qù", "Zhōngguó", "ma", "?", '"'),
      ],
      [
          s('Jorik says: "I really want to go to China! I want to go to Beijing."',
            "Jorik", "shuō", ":", '"', "wǒ", "hěn", "xiǎng", "qù", "Zhōngguó", "!",
            "wǒ", "xiǎng", "qù", "Běijīng", ".", '"'),
      ],
      [
          s('Xiaolin says: "Why do you want to go to Beijing?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "wèishénme", "xiǎng", "qù", "Běijīng", "?", '"'),
      ],
      [
          s('Jorik says: "Because you live in Beijing, because Beijing has many Chinese '
            'people, and because Beijing has very tasty food."',
            "Jorik", "shuō", ":", '"', "yīnwèi", "nǐ", "zhù", "zài", "Běijīng", ",",
            "yīnwèi", "Běijīng", "yǒu", "hěn", "duō", "Zhōngguó", "rén", ",",
            "hé", "yīnwèi", "Běijīng", "yǒu", "hěn", "hǎochī", "de", "cài", ".", '"'),
      ],
      [
          s('Xiaolin says: "Good! You come to Beijing, we eat Chinese food."',
            "Xiǎolín", "shuō", ":", '"', "hǎo", "!", "nǐ", "lái", "Běijīng", ",",
            "wǒmen", "chī", "Zhōngguó", "cài", ".", '"'),
      ],
      [
          s('Jorik says: "But my Chinese is not good. In Beijing, I do not understand '
            'Chinese people. They speak a lot, I speak a little."',
            "Jorik", "shuō", ":", '"', "kěshì", "wǒ", "de", "Zhōngwén", "bù", "hǎo", ".",
            "zài", "Běijīng", ",", "wǒ", "bù", "míngbai", "Zhōngguó", "rén", ".",
            "tāmen", "shuō", "hěn", "duō", ",", "wǒ", "shuō", "yìdiǎn", ".", '"'),
      ],
      [
          s('Xiaolin says: "No problem. You say: \'I do not understand. Please say it once '
            'more.\' Chinese people are very nice, they will say it again."',
            "Xiǎolín", "shuō", ":", '"', "méiguānxi", ".", "nǐ", "shuō", ":",
            "'", "wǒ", "bù", "míngbai", ".", "qǐng", "zàiA", "shuō", "yíbiàn", ".", "'",
            "Zhōngguó", "rén", "hěn", "hǎo", ",", "tāmen", "huì", "zàiA", "shuō", "yíbiàn", ".", '"'),
      ],
      [
          s('Jorik says: "Good. I understand now."',
            "Jorik", "shuō", ":", '"', "hǎo", ".", "wǒ", "míngbai", "le", ".", '"'),
      ],
      [
          s('Xiaolin says: "Your Chinese is very good. You are a very good student."',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "de", "Zhōngwén", "hěn", "hǎo", ".",
            "nǐ", "shì", "hěn", "hǎo", "de", "xuésheng", ".", '"'),
      ]),
    L("text-7-check", "Check - answer in English", 3,
      "Read each question and answer in English in your head. No output pressure yet.",
      [
          s("Does Tom have a Chinese teacher?",
            "Tom", "yǒu", "Zhōngwén", "lǎoshī", "ma", "?"),
          s("Where does Xiaolin live?", "Xiǎolín", "zhù", "zài", "nǎr", "?"),
          s("Why does Jorik like Chinese?",
            "Jorik", "wèishénme", "xǐhuan", "Zhōngwén", "?"),
          s("Who does not like Chinese food?",
            "shéi", "bù", "xǐhuan", "Zhōngguó", "cài", "?"),
          s("Where does Jorik want to go? Why?",
            "Jorik", "xiǎng", "qù", "nǎr", "?", "wèishénme", "?"),
      ]),
]

# ===========================================================================
# TRACK 2 - Numbers & age
# ===========================================================================
NUMBERS = [
    L("num-1", "One to ten", 1,
      "New: the numbers yī to shí, líng (zero), ge (the everyday counting word), "
      "and liǎng (the 'two' you use before ge). Read them out loud.",
      [
          s("One, two, three, four, five.", "yī", ",", "èr", ",", "sān", ",", "sì", ",", "wǔ", "."),
          s("Six, seven, eight, nine, ten.", "liù", ",", "qī", ",", "bā", ",", "jiǔ", ",", "shí", "."),
          s("Zero.", "líng", "."),
      ],
      [
          s("I have one friend.", "wǒ", "yǒu", "yíge", "péngyou", "."),
          s("I have two friends.", "wǒ", "yǒu", "liǎng", "ge", "péngyou", "."),
          s("I have three friends.", "wǒ", "yǒu", "sān", "ge", "péngyou", "."),
      ],
      [
          s("Jorik has three friends.", "Jorik", "yǒu", "sān", "ge", "péngyou", "."),
          s("One is Chinese, two are British.",
            "yíge", "shì", "Zhōngguó", "rén", ",", "liǎng", "ge", "shì", "Yīngguó", "rén", "."),
      ],
      [
          s("Xiaolin has many students.", "Xiǎolín", "yǒu", "hěn", "duō", "xuésheng", "."),
          s("Tom does not have a Chinese friend; he does not have a single one.",
            "Tom", "méiyǒu", "Zhōngguó", "péngyou", ",", "yíge", "dōu", "méiyǒu", "."),
      ]),
    L("num-2", "How old are you?", 2,
      "New: suì (years old), jǐ (how many, for small numbers), dà / xiǎo (big / small, "
      "also old / young), and the bigger numbers shíbā, èrshí, èrshíbā, sānshí, sānshíwǔ.",
      [
          s("Ten, eleven, twelve.", "shí", ",", "shíyī", ",", "shí'èr", "."),
          s("Eighteen, twenty, twenty-eight.", "shíbā", ",", "èrshí", ",", "èrshíbā", "."),
          s("Thirty, thirty-five.", "sānshí", ",", "sānshíwǔ", "."),
      ],
      [
          s('Xiaolin says: "How old are you?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "duō", "dà", "?", '"'),
          s('Jorik says: "I am thirty years old. And you?"',
            "Jorik", "shuō", ":", '"', "wǒ", "sānshí", "suì", ".", "nǐ", "ne", "?", '"'),
          s('Xiaolin says: "I am thirty-five years old."',
            "Xiǎolín", "shuō", ":", '"', "wǒ", "sānshíwǔ", "suì", ".", '"'),
      ],
      [
          s("Tom is twenty-eight years old.", "Tom", "èrshíbā", "suì", "."),
          s("Jorik is thirty; Tom is twenty-eight.",
            "Jorik", "sānshí", "suì", ",", "Tom", "èrshíbā", "suì", "."),
          s("Jorik is older, Tom is younger.", "Jorik", "dà", ",", "Tom", "xiǎo", "."),
      ]),
    L("num-3", "Check - numbers", 2,
      "Read each question and answer out loud. Use liǎng (not èr) before ge.",
      [
          s("How old are you?", "nǐ", "duō", "dà", "?"),
          s("How many friends do you have?", "nǐ", "yǒu", "jǐ", "ge", "péngyou", "?"),
          s("Is Xiaolin thirty-five?", "Xiǎolín", "sānshíwǔ", "suì", "ma", "?"),
          s("How old is Xiaolin?", "Xiǎolín", "duō", "dà", "?"),
      ]),
]

# ===========================================================================
# TRACK 3 - Family & home
# ===========================================================================
FAMILY = [
    L("fam-1", "My family", 1,
      "New: jiā (home / family), bàba, māma, gēge. 'wǒ jiā yǒu ... ge rén' = "
      "'in my family there are ... people'.",
      [
          s("In my family there are four people.", "wǒ", "jiā", "yǒu", "sì", "ge", "rén", "."),
          s("Dad, mum, older brother, and me.",
            "bàba", ",", "māma", ",", "gēge", ",", "hé", "wǒ", "."),
      ],
      [
          s("I have one older brother.", "wǒ", "yǒu", "yíge", "gēge", "."),
          s("My older brother is British.", "wǒ", "gēge", "shì", "Yīngguó", "rén", "."),
          s("My dad and mum both live in London.",
            "wǒ", "bàba", "hé", "māma", "dōu", "zhù", "zài", "Lúndūn", "."),
      ],
      [
          s('Xiaolin says: "How many people are in your family?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "jiā", "yǒu", "jǐ", "ge", "rén", "?", '"'),
          s('Jorik says: "In my family there are four people."',
            "Jorik", "shuō", ":", '"', "wǒ", "jiā", "yǒu", "sì", "ge", "rén", ".", '"'),
      ]),
    L("fam-2", "Brothers and sisters", 2,
      "New: dìdi, jiějie, mèimei. Ages come back here - dà / xiǎo also mean older / younger.",
      [
          s("I have an older brother and a younger sister.",
            "wǒ", "yǒu", "yíge", "gēge", "hé", "yíge", "mèimei", "."),
          s("I do not have a younger brother.", "wǒ", "méiyǒu", "dìdi", "."),
          s("My older brother is twenty, my younger sister is eighteen.",
            "wǒ", "gēge", "èrshí", "suì", ",", "wǒ", "mèimei", "shíbā", "suì", "."),
      ],
      [
          s("My older brother is older, my younger sister is younger.",
            "wǒ", "gēge", "dà", ",", "wǒ", "mèimei", "xiǎo", "."),
          s("They are both students.", "tāmen", "dōu", "shì", "xuésheng", "."),
      ],
      [
          s("Wang Mei has an older sister.", "WángMěi", "yǒu", "yíge", "jiějie", "."),
          s("Her older sister is a teacher too.", "tā", "jiějie", "yě", "shì", "lǎoshī", "."),
          s("Wang Mei and her older sister both live in Beijing.",
            "WángMěi", "hé", "tā", "jiějie", "dōu", "zhù", "zài", "Běijīng", "."),
      ]),
    L("fam-3", "Whose family", 2,
      "Everything so far, woven together: who is in the family, how old they are, "
      "where they live, and what they do.",
      [
          s('Xiaolin says: "Is your dad Chinese?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "bàba", "shì", "Zhōngguó", "rén", "ma", "?", '"'),
          s('Jorik says: "No, my dad is British. My whole family is British."',
            "Jorik", "shuō", ":", '"', "bú", "shì", ",", "wǒ", "bàba", "shì",
            "Yīngguó", "rén", ".", "wǒ", "jiā", "dōu", "shì", "Yīngguó", "rén", ".", '"'),
      ],
      [
          s("Jorik's mum is a teacher.", "Jorik", "de", "māma", "shì", "lǎoshī", "."),
          s("She is an English teacher, but she also speaks a little Chinese.",
            "tā", "shì", "Yīngwén", "lǎoshī", ",", "kěshì", "tā", "yě", "shuō",
            "yìdiǎn", "Zhōngwén", "."),
      ],
      [
          s("Jorik really likes his family.", "Jorik", "hěn", "xǐhuan", "tā", "de", "jiā", "."),
          s('He says: "My family is small, but very good."',
            "tā", "shuō", ":", '"', "wǒ", "jiā", "xiǎo", ",", "kěshì", "hěn", "hǎo", ".", '"'),
      ]),
]

# ===========================================================================
# TRACK 4 - Food & drink
# ===========================================================================
FOOD = [
    L("food-1", "What do you drink?", 1,
      "New: hē (drink), yào (want / order), chá, kāfēi, shuǐ, kě (thirsty), "
      "hǎohē (nice to drink).",
      [
          s("I drink tea.", "wǒ", "hē", "chá", "."),
          s("I like drinking tea.", "wǒ", "xǐhuan", "hē", "chá", "."),
          s("Chinese tea is very nice.", "Zhōngguó", "chá", "hěn", "hǎohē", "."),
      ],
      [
          s('Tom says: "What do you want to drink?"',
            "Tom", "shuō", ":", '"', "nǐ", "xiǎng", "hē", "shénme", "?", '"'),
          s('Jorik says: "I am thirsty. I want water."',
            "Jorik", "shuō", ":", '"', "wǒ", "kě", "le", ".", "wǒ", "yào", "shuǐ", ".", '"'),
      ],
      [
          s("Tom does not drink tea; he drinks coffee.",
            "Tom", "bù", "hē", "chá", ",", "tā", "hē", "kāfēi", "."),
          s("He drinks a lot of coffee every day.",
            "tā", "měitiān", "hē", "hěn", "duō", "kāfēi", "."),
      ]),
    L("food-2", "What do you eat?", 2,
      "New: è (hungry), mǐfàn, miàn, ròu, yú, jīdàn. chī and hǎochī come back.",
      [
          s("I am hungry.", "wǒ", "è", "le", "."),
          s("I want to eat noodles.", "wǒ", "xiǎng", "chī", "miàn", "."),
          s("Chinese noodles are very tasty.", "Zhōngguó", "miàn", "hěn", "hǎochī", "."),
      ],
      [
          s('Xiaolin says: "What do you want to eat?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "xiǎng", "chī", "shénme", "?", '"'),
          s('Jorik says: "I want rice, fish, and an egg."',
            "Jorik", "shuō", ":", '"', "wǒ", "yào", "mǐfàn", ",", "yú", ",", "hé", "jīdàn", ".", '"'),
      ],
      [
          s("Tom does not eat fish.", "Tom", "bù", "chī", "yú", "."),
          s("He eats meat; he really likes meat.", "tā", "chī", "ròu", ",", "tā", "hěn", "xǐhuan", "ròu", "."),
          s('He says: "Fish is not tasty, meat is tasty!"',
            "tā", "shuō", ":", '"', "yú", "bù", "hǎochī", ",", "ròu", "hǎochī", "!", '"'),
      ]),
    L("food-3", "Ordering food", 2,
      "Put it together: at a meal, saying what you are, what you want, and thanking. "
      "yào here means 'to order'.",
      [
          s("Jorik and Tom are hungry.", "Jorik", "hé", "Tom", "dōu", "è", "le", "."),
          s("They want to eat Chinese food.", "tāmen", "xiǎng", "chī", "Zhōngguó", "cài", "."),
      ],
      [
          s('Jorik says: "I want rice and fish. I want tea too."',
            "Jorik", "shuō", ":", '"', "wǒ", "yào", "mǐfàn", "hé", "yú", ".",
            "wǒ", "yě", "yào", "chá", ".", '"'),
      ],
      [
          s('Tom says: "I want noodles and meat. I do not want fish."',
            "Tom", "shuō", ":", '"', "wǒ", "yào", "miàn", "hé", "ròu", ".",
            "wǒ", "bú", "yào", "yú", ".", '"'),
      ],
      [
          s("The Chinese food is very tasty.", "Zhōngguó", "cài", "hěn", "hǎochī", "."),
          s('Jorik says: "This is really tasty. Thanks!"',
            "Jorik", "shuō", ":", '"', "hěn", "hǎochī", ".", "xièxie", "!", '"'),
      ]),
]

# ===========================================================================
# TRACK 5 - Every day (time & routine)
# ===========================================================================
DAILY = [
    L("day-1", "Today and tomorrow", 1,
      "New: jīntiān (today), míngtiān (tomorrow), zuótiān (yesterday).",
      [
          s("Today I study Chinese.", "jīntiān", "wǒ", "xuéxí", "Zhōngwén", "."),
          s("Yesterday I also studied Chinese.", "zuótiān", "wǒ", "yě", "xuéxí", "Zhōngwén", "."),
          s("I study Chinese every day.", "wǒ", "měitiān", "xuéxí", "Zhōngwén", "."),
      ],
      [
          s('Xiaolin says: "What do you want to do tomorrow?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "míngtiān", "xiǎng", "zuò", "shénme", "?", '"'),
          s('Jorik says: "Tomorrow I want to eat Chinese food with you."',
            "Jorik", "shuō", ":", '"', "míngtiān", "wǒ", "xiǎng", "hé", "nǐ",
            "chī", "Zhōngguó", "cài", ".", '"'),
      ],
      [
          s("Today Tom is hungry, tomorrow Tom wants to eat noodles.",
            "jīntiān", "Tom", "è", "le", ",", "míngtiān", "Tom", "xiǎng", "chī", "miàn", "."),
      ]),
    L("day-2", "What time is it?", 2,
      "New: xiànzài (now), diǎn (o'clock), bàn (half past). 'xiànzài jǐ diǎn?' = "
      "'what time is it now?'. Remember: 2 o'clock is liǎng diǎn.",
      [
          s('Jorik says: "What time is it now?"',
            "Jorik", "shuō", ":", '"', "xiànzài", "jǐ", "diǎn", "?", '"'),
          s('Tom says: "It is seven o\'clock now."',
            "Tom", "shuō", ":", '"', "xiànzài", "qī", "diǎn", ".", '"'),
      ],
      [
          s("Now it is eight o'clock.", "xiànzài", "bā", "diǎn", "."),
          s("Now it is half past eight.", "xiànzài", "bā", "diǎn", "bàn", "."),
          s("Now it is two o'clock.", "xiànzài", "liǎng", "diǎn", "."),
      ],
      [
          s("At twelve o'clock Jorik eats.", "shí'èr", "diǎn", ",", "Jorik", "chī", "fàn", "."),
          s("At eleven o'clock at night he sleeps.",
            "wǎnshang", "shíyī", "diǎn", ",", "tā", "shuìjiào", "."),
      ]),
    L("day-3", "My day", 3,
      "The longest here. New: zǎoshang, shàngwǔ, xiàwǔ, wǎnshang, qǐchuáng (get up), "
      "shuìjiào (sleep), gōngzuò (work), kàn (read / watch), shū (book).",
      [
          s("Every day Jorik gets up at seven in the morning.",
            "Jorik", "měitiān", "zǎoshang", "qī", "diǎn", "qǐchuáng", "."),
          s("In the morning he studies Chinese.", "shàngwǔ", "tā", "xuéxí", "Zhōngwén", "."),
          s("He really likes studying Chinese.", "tā", "hěn", "xǐhuan", "xuéxí", "Zhōngwén", "."),
      ],
      [
          s("In the afternoon Jorik works.", "xiàwǔ", "Jorik", "gōngzuò", "."),
          s("His mum works too.", "tā", "māma", "yě", "gōngzuò", "."),
      ],
      [
          s("In the evening he drinks tea and reads a book.",
            "wǎnshang", "tā", "hē", "chá", ",", "kàn", "shū", "."),
          s("He reads Chinese books.", "tā", "kàn", "Zhōngwén", "shū", "."),
          s("Chinese books are hard, but very interesting.",
            "Zhōngwén", "shū", "hěn", "nán", ",", "kěshì", "hěn", "yǒuyìsi", "."),
      ],
      [
          s("At eleven at night he sleeps.", "wǎnshang", "shíyī", "diǎn", ",", "tā", "shuìjiào", "."),
          s('He says: "I am going to sleep now. Goodnight!"',
            "tā", "shuō", ":", '"', "wǒ", "yào", "shuìjiào", "le", ".", "wǎn'ān", "!", '"'),
      ]),
]

# ===========================================================================
# TRACK 6 - Places & directions
# ===========================================================================
PLACES = [
    L("place-1", "Places in town", 1,
      "New: shāngdiàn (shop), xuéxiào (school), fànguǎn (restaurant), yīyuàn "
      "(hospital). Use zài (at / in) to say where someone is.",
      [
          s("Xiaolin is a teacher; she is at the school.",
            "Xiǎolín", "shì", "lǎoshī", ",", "tā", "zài", "xuéxiào", "."),
          s("The school is in Beijing.", "xuéxiào", "zài", "Běijīng", "."),
      ],
      [
          s("Jorik is hungry; he is at the restaurant.",
            "Jorik", "è", "le", ",", "tā", "zài", "fànguǎn", "."),
          s("The restaurant's food is very tasty.", "fànguǎn", "de", "cài", "hěn", "hǎochī", "."),
      ],
      [
          s("Tom is at the shop.", "Tom", "zài", "shāngdiàn", "."),
          s("He wants to drink coffee, but the shop has no coffee.",
            "tā", "xiǎng", "hē", "kāfēi", ",", "kěshì", "shāngdiàn", "méiyǒu", "kāfēi", "."),
      ],
      [
          s("Xiaolin's mum works at the hospital.",
            "Xiǎolín", "de", "māma", "zài", "yīyuàn", "gōngzuò", "."),
      ]),
    L("place-2", "Where is it?", 2,
      "New: lǐ (inside - 'X lǐ' means 'in X') and pángbiān (next to). "
      "'zài nǎr?' comes back.",
      [
          s('Xiaolin says: "Where is Jorik?"',
            "Xiǎolín", "shuō", ":", '"', "Jorik", "zài", "nǎr", "?", '"'),
          s('Tom says: "He is inside the school."',
            "Tom", "shuō", ":", '"', "tā", "zài", "xuéxiào", "lǐ", ".", '"'),
      ],
      [
          s('Jorik says: "Where is the tea?"',
            "Jorik", "shuō", ":", '"', "chá", "zài", "nǎr", "?", '"'),
          s('Tom says: "The tea is in the shop."',
            "Tom", "shuō", ":", '"', "chá", "zài", "shāngdiàn", "lǐ", ".", '"'),
      ],
      [
          s('Wang Mei says: "Where is the restaurant?"',
            "WángMěi", "shuō", ":", '"', "fànguǎn", "zài", "nǎr", "?", '"'),
          s('Xiaolin says: "The restaurant is next to the school."',
            "Xiǎolín", "shuō", ":", '"', "fànguǎn", "zài", "xuéxiào", "pángbiān", ".", '"'),
      ]),
    L("place-3", "Going places", 2,
      "New: zǒulù (to walk, on foot), zuò chē (to go by car / bus), chē (vehicle), "
      "yuǎn (far), jìn (near).",
      [
          s("Jorik wants to go to the restaurant.", "Jorik", "xiǎng", "qù", "fànguǎn", "."),
          s("The restaurant is near; he walks there.",
            "fànguǎn", "hěn", "jìn", ",", "tā", "zǒulù", "qù", "."),
      ],
      [
          s("Jorik wants to go to the school.", "Jorik", "xiǎng", "qù", "xuéxiào", "."),
          s("The school is far; he goes by car.",
            "xuéxiào", "hěn", "yuǎn", ",", "tā", "zuòB", "chē", "qù", "."),
      ],
      [
          s("Xiaolin walks to school every day.",
            "Xiǎolín", "měitiān", "zǒulù", "qù", "xuéxiào", "."),
          s("She likes walking.", "tā", "xǐhuan", "zǒulù", "."),
      ]),
]

# ===========================================================================
# TRACK 7 - Shopping & money
# ===========================================================================
SHOPPING = [
    L("shop-1", "Buying things", 1,
      "New: mǎi (to buy), zhège (this one), nàge (that one).",
      [
          s("Jorik is at the shop; he wants to buy tea.",
            "Jorik", "zài", "shāngdiàn", ",", "tā", "xiǎng", "mǎi", "chá", "."),
          s('He says: "I want this one."', "tā", "shuō", ":", '"', "wǒ", "yào", "zhège", ".", '"'),
      ],
      [
          s("Xiaolin buys coffee; Tom buys water.",
            "Xiǎolín", "mǎi", "kāfēi", ",", "Tom", "mǎi", "shuǐ", "."),
          s("This one is tea, that one is coffee.",
            "zhège", "shì", "chá", ",", "nàge", "shì", "kāfēi", "."),
      ]),
    L("shop-2", "How much?", 2,
      "New: duōshao (how much), qián (money), kuài (yuan). "
      "'duōshao qián?' = 'how much money?'.",
      [
          s('Jorik says: "How much is this one?"',
            "Jorik", "shuō", ":", '"', "zhège", "duōshao", "qián", "?", '"'),
          s('The shopkeeper says: "This tea is five yuan."',
            "tā", "shuō", ":", '"', "zhège", "chá", "wǔ", "kuài", ".", '"'),
      ],
      [
          s("That coffee is thirty yuan.", "nàge", "kāfēi", "sānshí", "kuài", "."),
          s('Jorik says: "I want the tea. Here is five yuan. Thanks!"',
            "Jorik", "shuō", ":", '"', "wǒ", "yào", "chá", ".", "wǔ", "kuài", ".", "xièxie", "!", '"'),
      ]),
    L("shop-3", "Expensive or cheap", 2,
      "New: guì (expensive), piányi (cheap).",
      [
          s("The coffee is expensive; the tea is cheap.",
            "kāfēi", "hěn", "guì", ",", "chá", "hěn", "piányi", "."),
          s('Jorik says: "The coffee is too expensive, I do not want it."',
            "Jorik", "shuō", ":", '"', "kāfēi", "tài", "guì", "le", ",", "wǒ", "bú", "yào", ".", '"'),
      ],
      [
          s("Tea is cheap and nice to drink; Jorik wants tea.",
            "chá", "piányi", ",", "yě", "hǎohē", ",", "Jorik", "yào", "chá", "."),
      ],
      [
          s('Tom says: "British food is expensive, and it is not tasty!"',
            "Tom", "shuō", ":", '"', "Yīngguó", "cài", "hěn", "guì", ",", "yě", "bù", "hǎochī", "!", '"'),
      ]),
]

# ===========================================================================
# TRACK 8 - Colours & things
# ===========================================================================
COLOURS = [
    L("colour-1", "Colours", 1,
      "New: yánsè (colour) and hóngsè, lánsè, báisè, hēisè (red, blue, white, black).",
      [
          s("I like red.", "wǒ", "xǐhuan", "hóngsè", "."),
          s('Xiaolin says: "What colour do you like?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "xǐhuan", "shénme", "yánsè", "?", '"'),
      ],
      [
          s("Tom likes blue; Xiaolin likes white.",
            "Tom", "xǐhuan", "lánsè", ",", "Xiǎolín", "xǐhuan", "báisè", "."),
          s("Coffee is black; tea is not black.",
            "kāfēi", "shì", "hēisè", "de", ",", "chá", "bú", "shì", "hēisè", "de", "."),
      ]),
    L("colour-2", "Describing things", 2,
      "New: xīn (new), jiù (old), hǎokàn (nice-looking). "
      "'hóngsè de shū' = 'a red book'.",
      [
          s("Jorik's book is red.", "Jorik", "de", "shū", "shì", "hóngsè", "de", "."),
          s("His book is new; my book is old.",
            "tā", "de", "shū", "shì", "xīn", "de", ",", "wǒ", "de", "shū", "shì", "jiù", "de", "."),
      ],
      [
          s("The new book is very nice.", "xīn", "de", "shū", "hěn", "hǎokàn", "."),
          s("The old book is not nice.", "jiù", "de", "shū", "bù", "hǎokàn", "."),
      ]),
    L("colour-3", "Which one?", 2,
      "New: háishì (or, in a question). 'A háishì B?' asks you to choose.",
      [
          s("This one is a red book, that one is a blue book.",
            "zhège", "shì", "hóngsè", "de", "shū", ",", "nàge", "shì", "lánsè", "de", "shū", "."),
      ],
      [
          s('Xiaolin says: "Which do you like, the red one or the black one?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "xǐhuan", "hóngsè", "de", ",",
            "háishì", "hēisè", "de", "?", '"'),
          s('Jorik says: "I like the blue one. It is very nice."',
            "Jorik", "shuō", ":", '"', "wǒ", "xǐhuan", "lánsè", "de", ".",
            "hěn", "hǎokàn", ".", '"'),
      ]),
]

# ===========================================================================
# TRACK 9 - Weather & seasons
# ===========================================================================
WEATHER = [
    L("weather-1", "Today's weather", 1,
      "New: tiānqì (weather), rè (hot), lěng (cold).",
      [
          s("Today the weather is very good.", "jīntiān", "tiānqì", "hěn", "hǎo", "."),
          s("Today it is very hot.", "jīntiān", "hěn", "rè", "."),
      ],
      [
          s("Beijing is hot; London is cold.",
            "Běijīng", "hěn", "rè", ",", "Lúndūn", "hěn", "lěng", "."),
          s("Today Beijing's weather is very hot.", "jīntiān", "Běijīng", "tiānqì", "hěn", "rè", "."),
      ]),
    L("weather-2", "Rain", 2,
      "New: xiàyǔ (to rain).",
      [
          s("Today it is raining.", "jīntiān", "xiàyǔ", "."),
          s('Jorik says: "I do not like rain."',
            "Jorik", "shuō", ":", '"', "wǒ", "bù", "xǐhuan", "xiàyǔ", ".", '"'),
      ],
      [
          s("Tomorrow it will not rain; the weather will be good.",
            "míngtiān", "bú", "xiàyǔ", ",", "tiānqì", "hěn", "hǎo", "."),
          s("When it rains, Jorik reads at home.",
            "xiàyǔ", ",", "Jorik", "zài", "jiā", "kàn", "shū", "."),
      ]),
    L("weather-3", "The seasons", 2,
      "New: chūntiān, xiàtiān, qiūtiān, dōngtiān (spring, summer, autumn, winter).",
      [
          s("Spring is not hot and not cold.", "chūntiān", "bú", "rè", ",", "yě", "bù", "lěng", "."),
          s("Summer is very hot.", "xiàtiān", "hěn", "rè", "."),
      ],
      [
          s("Winter is very cold; Beijing is very cold in winter.",
            "dōngtiān", "hěn", "lěng", ",", "Běijīng", "dōngtiān", "hěn", "lěng", "."),
      ],
      [
          s("Jorik likes autumn; autumn is not hot and not cold.",
            "Jorik", "xǐhuan", "qiūtiān", ",", "qiūtiān", "bú", "rè", ",", "yě", "bù", "lěng", "."),
      ]),
]

# ===========================================================================
# TRACK 10 - Hobbies
# ===========================================================================
HOBBIES = [
    L("hobby-1", "What do you like to do?", 1,
      "New: dǎ (play a ball game), qiú (ball), lánqiú (basketball), tī (kick), "
      "zúqiú (football).",
      [
          s("Jorik likes to play basketball.", "Jorik", "xǐhuan", "dǎ", "lánqiú", "."),
          s("Tom likes to play football.", "Tom", "xǐhuan", "tī", "zúqiú", "."),
      ],
      [
          s('Xiaolin says: "Do you like playing ball?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "xǐhuan", "dǎ", "qiú", "ma", "?", '"'),
          s("Jorik plays basketball every day.", "Jorik", "měitiān", "dǎ", "lánqiú", "."),
      ]),
    L("hobby-2", "Music and films", 2,
      "New: tīng (listen), yīnyuè (music), chàng (sing), gē (song), diànyǐng (film).",
      [
          s("Xiaolin likes to listen to music.", "Xiǎolín", "xǐhuan", "tīng", "yīnyuè", "."),
          s("She also likes to sing.", "tā", "yě", "xǐhuan", "chàng", "gē", "."),
      ],
      [
          s("Jorik likes to watch films.", "Jorik", "xǐhuan", "kàn", "diànyǐng", "."),
          s("He watches Chinese films; they are very interesting.",
            "tā", "kàn", "Zhōngwén", "diànyǐng", ",", "hěn", "yǒuyìsi", "."),
      ]),
    L("hobby-3", "The weekend", 3,
      "New: yóuyǒng (to swim). Days of the week come back (see the Days & dates track).",
      [
          s("On Saturday Jorik plays basketball.", "xīngqīliù", "Jorik", "dǎ", "lánqiú", "."),
          s("On Sunday he watches a film and listens to music.",
            "xīngqītiān", "tā", "kàn", "diànyǐng", ",", "tīng", "yīnyuè", "."),
      ],
      [
          s("Tom likes swimming; he swims every day.",
            "Tom", "xǐhuan", "yóuyǒng", ",", "tā", "měitiān", "yóuyǒng", "."),
          s('Xiaolin says: "What do you like to do?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "xǐhuan", "zuò", "shénme", "?", '"'),
      ]),
]

# ===========================================================================
# TRACK 11 - Feelings & body
# ===========================================================================
FEELINGS = [
    L("feel-1", "How do you feel?", 1,
      "New: gāoxìng (happy), lèi (tired), máng (busy).",
      [
          s("Today I am very happy.", "jīntiān", "wǒ", "hěn", "gāoxìng", "."),
          s("Jorik studies every day; he is very busy.",
            "Jorik", "měitiān", "xuéxí", ",", "tā", "hěn", "máng", "."),
      ],
      [
          s("In the evening he is very tired.", "wǎnshang", "tā", "hěn", "lèi", "."),
          s("He is tired, but he is happy.", "tā", "hěn", "lèi", ",", "kěshì", "hěn", "gāoxìng", "."),
      ]),
    L("feel-2", "Not feeling well", 2,
      "New: tóu (head), téng (to ache), bìng (to be ill), shūfu (comfortable; "
      "bù shūfu = unwell).",
      [
          s("Tom is unwell today.", "Tom", "jīntiān", "bù", "shūfu", "."),
          s("His head aches.", "tā", "tóu", "téng", "."),
      ],
      [
          s("He is ill; he is at the hospital.", "tā", "bìng", "le", ",", "tā", "zài", "yīyuàn", "."),
          s('Xiaolin says: "No problem. Drink a little water."',
            "Xiǎolín", "shuō", ":", '"', "méiguānxi", ".", "hē", "yìdiǎn", "shuǐ", ".", '"'),
      ]),
    L("feel-3", "Tired but happy", 2,
      "Everything together: study, feelings, and being a good student.",
      [
          s("Jorik studies Chinese every day; he is tired, but very happy.",
            "Jorik", "měitiān", "xuéxí", "Zhōngwén", ",", "tā", "hěn", "lèi", ",",
            "kěshì", "hěn", "gāoxìng", "."),
      ],
      [
          s('He says: "Chinese is hard, but I am happy."',
            "tā", "shuō", ":", '"', "Zhōngwén", "hěn", "nán", ",", "kěshì", "wǒ", "hěn", "gāoxìng", ".", '"'),
      ],
      [
          s("Xiaolin is happy too.", "Xiǎolín", "yě", "hěn", "gāoxìng", "."),
          s('She says: "You are a very good student."',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "shì", "hěn", "hǎo", "de", "xuésheng", ".", '"'),
      ]),
]

# ===========================================================================
# TRACK 12 - Days & dates
# ===========================================================================
CALENDAR = [
    L("cal-1", "Days of the week", 1,
      "New: xīngqī (week) and the days xīngqīyī to xīngqītiān. Read them out loud.",
      [
          s("Monday, Tuesday, Wednesday.", "xīngqīyī", ",", "xīngqī'èr", ",", "xīngqīsān", "."),
          s("Thursday, Friday.", "xīngqīsì", ",", "xīngqīwǔ", "."),
          s("Saturday, Sunday.", "xīngqīliù", ",", "xīngqītiān", "."),
      ]),
    L("cal-2", "What day is it?", 2,
      "New: 'jīntiān xīngqī jǐ?' = 'what day is it today?'.",
      [
          s('Jorik says: "What day is it today?"',
            "Jorik", "shuō", ":", '"', "jīntiān", "xīngqī", "jǐ", "?", '"'),
          s('Xiaolin says: "Today is Wednesday."',
            "Xiǎolín", "shuō", ":", '"', "jīntiān", "xīngqīsān", ".", '"'),
      ],
      [
          s("Tomorrow is Thursday.", "míngtiān", "xīngqīsì", "."),
          s("On Saturday and Sunday I do not work.",
            "xīngqīliù", ",", "xīngqītiān", "wǒ", "bù", "gōngzuò", "."),
      ]),
    L("cal-3", "Months and dates", 2,
      "New: yuè (month), hào (day of the month), shēngrì (birthday). "
      "Numbers make the dates: 'sān yuè shí hào' = March 10th.",
      [
          s("It is January now.", "xiànzài", "shì", "yī", "yuè", "."),
          s("Today is the fifth.", "jīntiān", "wǔ", "hào", "."),
      ],
      [
          s("Jorik's birthday is March tenth.",
            "Jorik", "de", "shēngrì", "shì", "sān", "yuè", "shí", "hào", "."),
          s('Xiaolin says: "When is your birthday?"',
            "Xiǎolín", "shuō", ":", '"', "nǐ", "de", "shēngrì", "shì", "jǐ", "yuè", "jǐ", "hào", "?", '"'),
      ]),
]

TRACKS = [
    {
        "id": "foundations",
        "title": "Foundations",
        "blurb": "Start here. Greetings, who you are, what you speak, having, "
                 "liking, living, and wanting - the backbone of everything.",
        "lessons": FOUNDATIONS,
    },
    {
        "id": "numbers",
        "title": "Numbers & age",
        "blurb": "Zero to thirty-five, the counting word ge, and asking how old "
                 "someone is.",
        "lessons": NUMBERS,
    },
    {
        "id": "family",
        "title": "Family & home",
        "blurb": "Your family: parents, brothers and sisters, how many, how old, "
                 "and where they live.",
        "lessons": FAMILY,
    },
    {
        "id": "food",
        "title": "Food & drink",
        "blurb": "Eating and drinking: what you want, what is tasty, and ordering "
                 "a meal.",
        "lessons": FOOD,
    },
    {
        "id": "daily",
        "title": "Every day",
        "blurb": "Today and tomorrow, telling the time, and a walk through a whole "
                 "day from morning to night.",
        "lessons": DAILY,
    },
    {
        "id": "places",
        "title": "Places & directions",
        "blurb": "Shops, schools, restaurants and hospitals: where things are, and "
                 "how you get there.",
        "lessons": PLACES,
    },
    {
        "id": "shopping",
        "title": "Shopping & money",
        "blurb": "Buying things, asking the price, and whether something is "
                 "expensive or cheap.",
        "lessons": SHOPPING,
    },
    {
        "id": "colours",
        "title": "Colours & things",
        "blurb": "Colours, and describing objects: new or old, and nice to look at.",
        "lessons": COLOURS,
    },
    {
        "id": "weather",
        "title": "Weather & seasons",
        "blurb": "Hot and cold, rain, and the four seasons.",
        "lessons": WEATHER,
    },
    {
        "id": "calendar",
        "title": "Days & dates",
        "blurb": "Days of the week, months, dates, and birthdays.",
        "lessons": CALENDAR,
    },
    {
        "id": "hobbies",
        "title": "Hobbies",
        "blurb": "Sport, music and films - and talking about your weekend.",
        "lessons": HOBBIES,
    },
    {
        "id": "feelings",
        "title": "Feelings & body",
        "blurb": "Happy, tired, busy, and saying when you are unwell.",
        "lessons": FEELINGS,
    },
]

def build_dictionary(tracks):
    """One global dictionary, deduped by hanzi across every track.

    Words are grouped by meaning-category (CATS order) and each entry is tagged
    with the track where you first meet it. This keeps the dictionary coherent
    no matter which order the tracks are read in.
    """
    seen = {}          # hanzi -> entry dict
    order_in_cat = {}  # cat -> list of hanzi in first-seen order
    for track in tracks:
        for lesson in track["lessons"]:
            for para in lesson["paragraphs"]:
                for sent in para:
                    for tok in sent["t"]:
                        if "g" not in tok or tok["h"] in seen:
                            continue
                        cat = _cat_for(tok["p"], tok["h"])
                        seen[tok["h"]] = {
                            "h": tok["h"], "p": tok["p"], "g": tok["g"],
                            "track": track["title"], "cat": cat,
                        }
                        order_in_cat.setdefault(cat, []).append(tok["h"])

    sections = []
    for cat, label in CATS:
        words = [seen[h] for h in order_in_cat.get(cat, [])]
        if words:
            sections.append({"cat": cat, "label": label, "words": words})
    # any category not in CATS (shouldn't happen) goes last
    leftovers = [h for c, hs in order_in_cat.items()
                 if c not in dict(CATS) for h in hs]
    if leftovers:
        sections.append({"cat": "misc", "label": "Other",
                         "words": [seen[h] for h in leftovers]})
    return sections


def _cat_for(pinyin, hanzi):
    """Find a word's category from the lexicon, matching on pinyin then hanzi."""
    for key, (h, p, g, cat) in LEX.items():
        if h == hanzi:
            return cat
    return "misc"


OUT = {
    "tracks": TRACKS,
    "dictionary": build_dictionary(TRACKS),
    "categories": [{"cat": c, "label": l} for c, l in CATS],
}

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(here, "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "texts.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(OUT, f, ensure_ascii=False, indent=1)
    n_lessons = sum(len(t["lessons"]) for t in TRACKS)
    n_sent = sum(len(p) for t in TRACKS for L_ in t["lessons"] for p in L_["paragraphs"])
    v = sum(len(sec["words"]) for sec in OUT["dictionary"])
    print(f"wrote {path}: {len(TRACKS)} tracks, {n_lessons} lessons, "
          f"{n_sent} sentences, {v} dictionary words")
