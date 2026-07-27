"""Builds data/texts.json from a compact lexicon + sentence definitions.

Each word is stored with:
  h  = hanzi (characters)  -> used ONLY for text-to-speech, never shown
  p  = pinyin              -> what you read on screen
  g  = gloss               -> shown when you double-click it
  sp = leading space?      -> typographic spacing computed at build time

Each sentence also carries an English translation (en), shown when you click it.
The cumulative dictionary is derived automatically: each lesson contributes the
words that first appear in it, in order.
"""

import json
import os

# --- lexicon: key -> (hanzi, pinyin shown, gloss) ----------------------------
# Keys are usually the pinyin. Where one pinyin maps to two different words we
# add a suffixed key (e.g. bu4 vs bu2 for 不, zai4-again 再 vs zai4-at 在).
LEX = {
    "nǐ": ("你", "nǐ", "you"),
    "hǎo": ("好", "hǎo", "good, well"),
    "wǒ": ("我", "wǒ", "I, me"),
    "jiào": ("叫", "jiào", "to be called"),
    "Jorik": ("Jorik", "Jorik", "Jorik (your name)"),
    "shénme": ("什么", "shénme", "what"),
    "míngzi": ("名字", "míngzi", "name"),
    "ma": ("吗", "ma", "(turns a sentence into a yes/no question)"),
    "hái": ("还", "hái", "still, fairly"),
    "tài": ("太", "tài", "too, overly"),
    "bù": ("不", "bù", "not"),
    "bú": ("不", "bú", "not (said bu2 before a 4th-tone word)"),
    "ne": ("呢", "ne", "and you? / what about...?"),
    "xièxie": ("谢谢", "xièxie", "thanks"),
    "shì": ("是", "shì", "to be (am / is / are)"),
    "Zhōngguó": ("中国", "Zhōngguó", "China"),
    "rén": ("人", "rén", "person"),
    "Yīngguó": ("英国", "Yīngguó", "Britain"),
    "shuō": ("说", "shuō", "to speak, to say"),
    "Zhōngwén": ("中文", "Zhōngwén", "Chinese (the language)"),
    "yě": ("也", "yě", "also, too"),
    "yìdiǎn": ("一点", "yìdiǎn", "a little"),
    "tā": ("他", "tā", "he / she"),
    "hěn": ("很", "hěn", "very"),
    "duō": ("多", "duō", "much, many"),
    "kěshì": ("可是", "kěshì", "but"),
    "Xiǎolín": ("小林", "Xiǎolín", "Xiaolin (a name)"),
    "lǎoshī": ("老师", "lǎoshī", "teacher"),
    "de": ("的", "de", "('s / of - links a describer to a noun)"),
    "xuésheng": ("学生", "xuésheng", "student"),
    "Yīngwén": ("英文", "Yīngwén", "English (the language)"),
    "míngbai": ("明白", "míngbai", "to understand"),
    "yìsi": ("意思", "yìsi", "meaning"),
    "a": ("啊", "a", "ah (a soft exclamation)"),
    # --- Text 4 ---
    "yǒu": ("有", "yǒu", "to have"),
    "yíge": ("一个", "yí ge", "one, a"),
    "péngyou": ("朋友", "péngyou", "friend"),
    "WángMěi": ("王美", "Wáng Měi", "Wang Mei (a name)"),
    "hé": ("和", "hé", "and"),
    "dōu": ("都", "dōu", "both, all"),
    "tāmen": ("他们", "tāmen", "they"),
    "méiyǒu": ("没有", "méiyǒu", "to not have"),
    "Tom": ("Tom", "Tom", "Tom (a name)"),
    # --- Text 5 ---
    "zhù": ("住", "zhù", "to live, to stay"),
    "zài": ("在", "zài", "to be at / in (a place)"),
    "Běijīng": ("北京", "Běijīng", "Beijing"),
    "Lúndūn": ("伦敦", "Lúndūn", "London"),
    "nǎr": ("哪儿", "nǎr", "where"),
    # --- Text 6 ---
    "xǐhuan": ("喜欢", "xǐhuan", "to like"),
    "wèishénme": ("为什么", "wèishénme", "why"),
    "yīnwèi": ("因为", "yīnwèi", "because"),
    "yǒuyìsi": ("有意思", "yǒuyìsi", "interesting"),
    "nán": ("难", "nán", "hard, difficult"),
    "duì": ("对", "duì", "right, correct"),
    "cài": ("菜", "cài", "food, dish"),
    "hǎochī": ("好吃", "hǎochī", "tasty, good to eat"),
    "zhīdào": ("知道", "zhīdào", "to know"),
    # --- Text 7 ---
    "měitiān": ("每天", "měitiān", "every day"),
    "xuéxí": ("学习", "xuéxí", "to study"),
    "xiǎng": ("想", "xiǎng", "to want to, would like to"),
    "qù": ("去", "qù", "to go, to go to"),
    "lái": ("来", "lái", "to come"),
    "wǒmen": ("我们", "wǒmen", "we, us"),
    "chī": ("吃", "chī", "to eat"),
    "méiguānxi": ("没关系", "méi guānxi", "no problem, it's ok"),
    "qǐng": ("请", "qǐng", "please"),
    "zàiA": ("再", "zài", "again"),
    "yíbiàn": ("一遍", "yí biàn", "once (one time through)"),
    "huì": ("会", "huì", "will, can"),
    "le": ("了", "le", "(marks something completed or changed)"),
    "shéi": ("谁", "shéi", "who"),
}

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
        h, p, g = LEX[item]
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


# --- the texts ---------------------------------------------------------------
LESSONS = [
    {
        "id": "warmup",
        "title": "Warm-up - greetings",
        "note": "Everything you have already seen. Read it out loud. Click a "
                "sentence to hear it, double-click a word, or drag across a few.",
        "paragraphs": [
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
            ],
        ],
    },
    {
        "id": "text-1",
        "title": "Text 1 - who speaks Chinese",
        "note": "New words appear woven into what you know. Do not memorise - just read.",
        "paragraphs": [
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
            ],
        ],
    },
    {
        "id": "text-2",
        "title": "Text 2 - teacher and student",
        "note": "New here: lǎoshī, xuésheng, de. They repeat many times on purpose.",
        "paragraphs": [
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
            ],
        ],
    },
    {
        "id": "text-3",
        "title": "Text 3 - I don't understand",
        "note": "New here: Yīngwén, míngbai, yìsi. Notice how 'shénme yìsi?' means 'what does it mean?'.",
        "paragraphs": [
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
            ],
        ],
    },
    {
        "id": "text-3-check",
        "title": "Check - answer shì or bú shì",
        "note": "Read each question. Answer out loud with shì (yes) or bú shì (no).",
        "paragraphs": [
            [
                s("Is Xiaolin Chinese?", "Xiǎolín", "shì", "Zhōngguó", "rén", "ma", "?"),
                s("Is Jorik Chinese?", "Jorik", "shì", "Zhōngguó", "rén", "ma", "?"),
                s("Is Xiaolin a student?", "Xiǎolín", "shì", "xuésheng", "ma", "?"),
                s("Is Jorik Xiaolin's teacher?",
                  "Jorik", "shì", "Xiǎolín", "de", "lǎoshī", "ma", "?"),
            ],
        ],
    },
    {
        "id": "text-4",
        "title": "Text 4 - friends",
        "note": "New here: yǒu / méiyǒu (have / not have), péngyou, hé, dōu, tāmen.",
        "paragraphs": [
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
            ],
        ],
    },
    {
        "id": "text-5",
        "title": "Text 5 - where people live",
        "note": "New here: zhù (live), zài (at / in), nǎr (where), Běijīng, Lúndūn.",
        "paragraphs": [
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
            ],
        ],
    },
    {
        "id": "text-6",
        "title": "Text 6 - likes and reasons",
        "note": "New here: xǐhuan (like), wèishénme (why), yīnwèi (because), nán, cài, hǎochī.",
        "paragraphs": [
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
            ],
        ],
    },
    {
        "id": "text-7",
        "title": "Text 7 - wanting to go to China",
        "note": "The longest yet. New here: měitiān, xuéxí, xiǎng, qù, lái, wǒmen, chī, "
                "and the phrase 'qǐng zài shuō yí biàn' (please say it again).",
        "paragraphs": [
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
            ],
        ],
    },
    {
        "id": "text-7-check",
        "title": "Check - answer in English",
        "note": "Read each question and answer in English in your head. No output pressure yet.",
        "paragraphs": [
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
            ],
        ],
    },
]


def build_dictionary(lessons):
    """One section per lesson, listing the words that first appear there.

    Deduped by hanzi so the cumulative dictionary grows by exactly the new
    vocabulary of each text.
    """
    seen = set()
    sections = []
    for lesson in lessons:
        words = []
        for para in lesson["paragraphs"]:
            for sent in para:
                for tok in sent["t"]:
                    if "g" in tok and tok["h"] not in seen:
                        seen.add(tok["h"])
                        words.append({"h": tok["h"], "p": tok["p"], "g": tok["g"]})
        if words:
            sections.append({"title": lesson["title"], "words": words})
    return sections


OUT = {"lessons": LESSONS, "dictionary": build_dictionary(LESSONS)}

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(here, "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "texts.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(OUT, f, ensure_ascii=False, indent=1)
    n = sum(len(p) for L in LESSONS for p in L["paragraphs"])
    v = sum(len(sec["words"]) for sec in OUT["dictionary"])
    print(f"wrote {path}: {len(LESSONS)} lessons, {n} sentences, {v} dictionary words")
