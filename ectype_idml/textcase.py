"""Title case and sentence case for running heads.

Title case follows Chicago (8.159): capitalize the first and last words and all others except
articles, prepositions, coordinating conjunctions, "to" and "as"; the first word after a colon
is capitalized too. Words with capitals inside them (McDonald, iPhone, NT) are left as they
are. Sentence case lowers every word but the first (and the first after a colon), except
proper nouns: words the manuscript itself writes with a capital in mid-sentence
(`proper_nouns`), and words with capitals inside them. A text typed all in capitals is read
as lower case first. Hebrew and other scripts without case pass through unchanged.
"""

import re
from collections import Counter

MINOR = {
    "en": set("a an the and but or nor for as at by from in into like near of on onto over "
              "past per than to upon via with within without about above across after against "
              "along among around before behind below beneath beside between beyond during "
              "except inside outside since through throughout toward towards under "
              "underneath until unto versus vs".split()),
    "es": set("a al ante bajo con contra de del desde durante e el en entre hacia hasta la "
              "las lo los mediante ni o para por que según sin so sobre tras u un una unas "
              "unos y".split()),
}
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.U)
_SENTENCE_END = re.compile(r"[.!?:;—]\s*$")


def _cased(word):
    return any(c.isupper() for c in word[1:])


def _upper_first(word):
    return word[:1].upper() + word[1:]


def _plain(text):
    """An all-capitals text as lower case (so its words can be cased again)."""
    letters = [c for c in text if c.isalpha() and c.lower() != c.upper()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 3:
        return text.lower()
    return text


def _words(text):
    """(start, end, word, first) for each word; first: it opens the text or follows a colon
    (or a full stop, question mark, dash)."""
    out = []
    for m in _WORD.finditer(text):
        before = text[:m.start()]
        first = not before.strip(" \"'“‘([") or bool(_SENTENCE_END.search(before))
        out.append((m.start(), m.end(), m.group(), first))
    return out


def _rebuild(text, words, new):
    parts, at = [], 0
    for (s, e, _w, _f), w in zip(words, new):
        parts += [text[at:s], w]
        at = e
    return "".join(parts) + text[at:]


def title_case(text, lang="en"):
    text = _plain(text)
    minor = MINOR.get(lang, MINOR["en"])
    words = _words(text)
    new = []
    for k, (_s, _e, w, first) in enumerate(words):
        # Each part of a hyphenated word is a word here: capitalized unless minor (Chicago).
        last = k == len(words) - 1
        if _cased(w) or not w[:1].isalpha():
            new.append(w)
        elif w.lower() in minor and not first and not last:
            new.append(w.lower())
        else:
            new.append(_upper_first(w))
    return _rebuild(text, words, new)


def sentence_case(text, proper=()):
    text = _plain(text)
    words = _words(text)
    new = []
    for _s, _e, w, first in words:
        if first:
            new.append(_upper_first(w))
        elif _cased(w) or w in proper or (w.lower() == "i" and len(w) == 1):
            new.append(w if w != "i" else "I")
        else:
            new.append(w.lower())
    return _rebuild(text, words, new)


def apply(text, case, lang="en", proper=()):
    """case: "title", "sentence", else (as typed) unchanged."""
    if not text or case not in ("title", "sentence"):
        return text
    return title_case(text, lang) if case == "title" else sentence_case(text, proper)


def proper_nouns(texts):
    """Words written with a capital in mid-sentence in the running text, more often than in
    lower case (God, Ezekiel, Jerusalem; not a word that merely opens sentences)."""
    capital, lower = Counter(), Counter()
    for text in texts:
        for _s, _e, w, first in _words(text):
            if first or _cased(w):
                continue
            if w[:1].isupper():
                capital[w] += 1
            else:
                lower[_upper_first(w)] += 1
    return {w for w, n in capital.items() if n > lower[w]}
