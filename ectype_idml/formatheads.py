"""Headings set by direct formatting instead of styles.

Some manuscripts arrive without heading styles: the author made headings bigger, bold, centered
or in capitals by hand. This module finds such paragraphs and groups them by look, so they can
be mapped like styles (they show in the Style Map tab as "[14 pt bold centered]" and so on).

Only what the styles don't already provide is guessed: if the file has chapter-title styles in
use, guessed groups start at the first heading level below chapters; if it has heading styles
too, nothing is guessed. Only paragraphs whose style maps to body text are candidates.

A candidate is a short paragraph (at most 15 words, no closing period unless it is numbered like
"1." or "Chapter 3."), not in a table or note, with text under it (a paragraph of 20 words or
more, not centered like a title-page line) before the next paragraph of the same look, whose look stands out from the body text: larger, bold, capitals or small caps, centered, or (weakest) italic. Paragraphs
with the same look form a group; a group needs two members unless it is clearly prominent
(larger type or starting a page). Groups are ranked by prominence: the most prominent becomes
chapter titles (when chapters aren't styled), the next Heading A, then B, then C.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

MAX_WORDS = 15
TEXT_WORDS = 20       # a paragraph of at least this many words counts as text under a heading
_NUMBERED = re.compile(r"^(chapter|part|cap[ií]tulo|parte|section|\d+(\.\d+)*|[ivxlc]+|[a-z])"
                       r"[\s.:)]", re.I)
LEVEL_STYLES = {0: "Chapter Title", 1: "Heading A", 2: "Heading B", 3: "Heading C"}


@dataclass
class Group:
    look: tuple                 # (size, bold, italic, caps, centered)
    name: str                   # "[14 pt bold centered]"
    paragraphs: list = field(default_factory=list)   # paragraph indexes
    starts_page: int = 0        # members that start a page
    role: str = "heading"
    level: int = 1

    @property
    def idml(self):
        if self.role == "heading":
            return LEVEL_STYLES[min(self.level, 3)]
        return {"author": "Chapter Author", "subtitle": "Chapter Subtitle"}.get(self.role,
                                                                              LEVEL_STYLES[0])

    def members(self, doc):
        return [i for key, i in self.paragraphs if key == id(doc)]


def describe(look, body_size=None):
    size, bold, italic, caps, centered = look
    parts = ["%g pt" % size] if body_size is None or size != body_size else []
    parts += [w for w, on in (("bold", bold), ("italic", italic)) if on]
    if caps:
        parts.append("capitals" if caps == "caps" else "small caps")
    if centered:
        parts.append("centered")
    return "[%s]" % " ".join(parts or ["%g pt" % size])


def _prominence(g, body):
    size, bold, italic, caps, centered = g.look
    b_size, b_bold, b_italic, b_caps, b_centered = body
    score = (size - b_size) * 10
    score += 6 if bold and not b_bold else 0
    score += 5 if caps and not b_caps else 0
    score += 4 if centered and not b_centered else 0
    score += 2 if italic and not b_italic else 0
    score += 8 * g.starts_page / max(1, len(g.paragraphs))
    return score


def _stands_out(look, body):
    size, bold, italic, caps, centered = look
    return size >= body[0] + 0.5 or (bold and not body[1]) or (caps and not body[3]) or \
        (centered and not body[4]) or (italic and not body[2])


TITLE = "[title line of a file]"
UNDER = {"author": "[author line under a file title]",
         "subtitle": "[subtitle under a file title]"}


@dataclass
class Plan:
    groups: list = field(default_factory=list)       # ranked look groups, then the title group
    by_doc: dict = field(default_factory=dict)       # id(doc) -> {paragraph index: Group}
    book_title: str = None                           # a first line that opens several files
    repeats: dict = field(default_factory=dict)      # id(doc) -> {index} of that line, left out


def plan(docs, role_of):
    """Headings found by formatting across the whole book (so a look means the same level in
    every file). role_of(doc, p): the role a paragraph's style maps to.

    In a book of several files, each file whose chapter title isn't styled may open with a
    title line: the most prominent line before its first text (PREFACE, Contributors, Foreword
    by...). It is the unit's title, whatever its look, and the lines between it and the first
    heading are its author line or subtitle. (In a single file the first heading is just the
    first chapter.) A first line that opens two or
    more files is the book's title, left out where a file title follows it. The other
    candidates are grouped by look over all the files and ranked."""
    out = Plan()
    files = []
    weight = Counter()
    styled = set()
    for doc in docs:
        paras = [p for p in doc.paragraphs if p.where == "body" and not p.in_table and
                 not p.in_toc_field and p.text.strip() and p.look]
        roles = {p.index: role_of(doc, p) for p in paras}
        files.append((doc, paras, roles))
        styled |= set(roles.values())
        for p in paras:
            if roles[p.index] == "body" and len(p.text.split()) >= TEXT_WORDS:
                weight[_look(p)] += len(p.text)
    if not weight:
        for doc, paras, roles in files:
            for p in paras:
                weight[_look(p)] += len(p.text)
    if not weight:
        return out
    body = weight.most_common(1)[0][0]
    want_chapters = not ({"chapter", "part"} & styled)
    want_headings = "heading" not in styled
    firsts = Counter(" ".join(paras[0].text.split()) for _d, paras, _r in files if paras)
    repeated = {t for t, n in firsts.items() if n >= 2 and len(t.split()) <= 25}
    if repeated:
        out.book_title = sorted(repeated, key=lambda t: -firsts[t])[0]
    groups, titles, unders = {}, [], {}
    for doc, paras, roles in files:
        if {"chapter", "part"} & set(roles.values()) and not want_headings:
            continue
        texty = [roles[p.index] == "body" and len(p.text.split()) >= TEXT_WORDS and
                 (p.align != "center" or body[4]) for p in paras]
        cands = []
        for n, p in enumerate(paras):
            text = " ".join(p.text.split())
            look = _look(p)
            if roles[p.index] != "body" or look == body or not _stands_out(look, body):
                continue
            if len(text.split()) > MAX_WORDS or n == len(paras) - 1:
                continue
            if text.endswith(".") and not _NUMBERED.match(text):
                continue
            cands.append(n)
        # A heading has text under it before the next heading of its look (title-page lines
        # and a typed contents' title don't); a file title before the next candidate of any.
        nexts = {}
        for k, n in enumerate(cands):
            same = [m for m in cands[k + 1:] if _look(paras[m]) == _look(paras[n])]
            nexts[n] = (same[0] if same else len(paras), cands[k + 1] if k + 1 < len(cands)
                        else len(paras))
        # The file's title: the most prominent of the lines before its first text (ties: the
        # last, nearest the text), not counting the book's title repeated at the top.
        title, under = None, []
        first_text = next((n for n, t in enumerate(texty) if t), len(paras))
        leading = [n for n in cands if n < first_text and
                   not (n == 0 and " ".join(paras[0].text.split()) in repeated)]
        if leading and len(files) > 1 and not ({"chapter", "part"} & set(roles.values())):
            best = max(_prominence_of(_look(paras[n]), body) for n in leading)
            top = [n for n in leading if _prominence_of(_look(paras[n]), body) == best]
            title = top[0] if len(top) == 1 else top[-1]
            # Lines between the title and the first heading or text: an author line (names)
            # or a subtitle, set as Chapter Author or Chapter Subtitle.
            for n in leading:
                if n <= title:
                    continue
                if any(texty[n + 1:nexts[n][1]]):
                    break                      # a heading with text under it
                under.append(n)
        if title is not None:
            titles.append((doc, paras[title].index))
            if " ".join(paras[0].text.split()) in repeated and title > 0:
                out.repeats.setdefault(id(doc), set()).add(paras[0].index)
        for n in under:
            role = "author" if _names(paras[n].text) else "subtitle"
            unders.setdefault(role, []).append((id(doc), paras[n].index))
        for n in cands:
            if n == title or n in under or not any(texty[n + 1:nexts[n][0]]):
                continue
            p = paras[n]
            g = groups.setdefault(_look(p), Group(_look(p), describe(_look(p), body[0])))
            g.paragraphs.append((id(doc), p.index))
            first_in_section = p.index == 0 or doc.paragraphs[p.index - 1].ends_section
            if p.page_break_before or first_in_section:
                g.starts_page += 1
    kept = [g for g in groups.values()
            if len(g.paragraphs) >= 2 or g.look[0] >= body[0] + 2 or g.starts_page]
    # An italic-only look is weak (titles of works, foreign words set apart): keep it only as
    # a level below a stronger group.
    if all(_only_italic(g.look, body) for g in kept):
        kept = []
    kept.sort(key=lambda g: -_prominence(g, body))
    if not want_headings:
        kept = kept[:1] if want_chapters else []
    level = 1
    if want_chapters and kept and (not titles or 2 * kept[0].starts_page >= len(
            kept[0].paragraphs) or kept[0].look[0] >= body[0] + 2):
        level = 0
    for g in kept:
        g.role, g.level = ("chapter", 0) if level == 0 else ("heading", min(level, 3))
        level += 1
    if titles:
        kept.append(Group(None, TITLE, [(id(d), i) for d, i in titles], role="chapter",
                          level=0))
    for role, members in sorted(unders.items()):
        kept.append(Group(None, UNDER[role], members, role=role, level=0))
    out.groups = kept
    for g in kept:
        for key, i in g.paragraphs:
            out.by_doc.setdefault(key, {})[i] = g
    return out


def _names(text):
    """A line of names ("Nicolas Ellen and Josh Stephens", "John Smith, PhD")."""
    words = text.split()
    if not words or len(words) > 14 or text.rstrip().endswith((".", ":", "?")) or ":" in text:
        return False
    caps = sum(1 for w in words if w[:1].isupper())
    small = sum(1 for w in words if w.lower() in ("and", "y", "&", "with", "con"))
    return caps + small == len(words) and (small or "," in text or len(words) <= 4)


def _prominence_of(look, body):
    return _prominence(Group(look, ""), body)


def _look(p):
    return p.look + (p.align == "center",)


def feats_of(p):
    """Run features of a paragraph's look (dropped from a heading's runs: its style gives them)."""
    size, bold, italic, caps = p.look
    return tuple(f for f, on in (("bold", bold), ("italic", italic)) if on) + \
        ((caps,) if caps else ())


def _only_italic(look, body):
    size, bold, italic, caps, centered = look
    return italic and size < body[0] + 0.5 and not (bold or caps or centered)
