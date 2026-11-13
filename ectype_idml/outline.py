"""The book's outline, built across all input files: front matter, parts, chapters, back matter.

Headings are found in each file by the first of these that finds any (in order of trust):
1. the style map (styles whose role is chapter or part, including custom styles based on them
   or given outline level 1);
2. Word's own running heads: the style a STYLEREF field in a header points to;
3. paragraphs given outline level 1 directly;
4. section breaks (the first line after each page break of a section is the title);
5. the whole file as one unit, titled by its first line.
Units are then classified by title (Preface, Bibliography, Part II...) in English and Spanish.
The manuscript doesn't need running heads set up in Word.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from .stylemap import StyleMap, norm

# Normalized title -> (kind, type). "display" pages carry no folio.
_FRONT = {
    "endorsements": ("display", "endorsements"), "praise": ("display", "endorsements"),
    "advance praise": ("display", "endorsements"),
    "what people are saying": ("display", "endorsements"),
    "what others are saying": ("display", "endorsements"),
    "elogios": ("display", "endorsements"), "recomendaciones": ("display", "endorsements"),
    "lo que dicen": ("display", "endorsements"),
    "dedication": ("display", "dedication"), "dedicatoria": ("display", "dedication"),
    "epigraph": ("display", "epigraph"), "epígrafe": ("display", "epigraph"),
    "copyright": ("display", "copyright"),
    "contents": ("front", "contents"), "table of contents": ("front", "contents"),
    "contenido": ("front", "contents"), "contenidos": ("front", "contents"),
    "índice general": ("front", "contents"), "tabla de contenido": ("front", "contents"),
    "foreword": ("front", "foreword"), "prólogo": ("front", "foreword"),
    "contributors": ("front", "contributors"), "list of contributors": ("front", "contributors"),
    "colaboradores": ("front", "contributors"),
    "presentación": ("front", "foreword"),
    "preface": ("front", "preface"), "prefacio": ("front", "preface"),
    "acknowledgments": ("front", "acknowledgments"), "acknowledgements": ("front", "acknowledgments"),
    "agradecimientos": ("front", "acknowledgments"),
    "abbreviations": ("front", "abbreviations"), "abreviaturas": ("front", "abbreviations"),
    "siglas y abreviaturas": ("front", "abbreviations"),
    "list of illustrations": ("front", "illustrations"), "list of figures": ("front", "illustrations"),
    "list of tables": ("front", "tables"),
}
_BACK = {
    "bibliography": "bibliography", "select bibliography": "bibliography",
    "works cited": "bibliography", "references": "bibliography", "bibliografía": "bibliography",
    "obras citadas": "bibliography", "referencias": "bibliography",
    "glossary": "glossary", "glosario": "glossary",
    "notes": "notes", "notas": "notes",
    "afterword": "afterword", "epílogo": "afterword",
    "index": "index", "subject index": "index", "scripture index": "index",
    "author index": "index", "index of ancient sources": "index", "índice analítico": "index",
    "índice de autores": "index", "índice de citas": "index", "índice onomástico": "index",
    "about the author": "about", "sobre el autor": "about", "acerca del autor": "about",
}
_PRAISE = re.compile(r"^(advance praise|praise|endorsements|elogios|recomendaciones)\s+(for|of|para|de)\b")
_APPENDIX = re.compile(r"^(appendix|appendices|apéndice|apéndices|anexo)\b")
_PART = re.compile(r"^(part|parte|book|libro)\s+(\S+)")
_PART_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
               "first", "second", "third", "fourth", "fifth", "uno", "dos", "tres", "cuatro",
               "cinco", "primera", "segunda", "tercera", "cuarta", "quinta", "i", "ii", "iii",
               "iv", "v", "vi", "vii", "viii", "ix", "x"}
ENDORSEMENT_MIN_WORDS = 25    # less than this above the title is part of the title page

MAX_TITLE_WORDS = 15
_BY = re.compile(r"^(by|por)\s+(.+)$", re.I)
_EDITED = re.compile(r"^(edited by|editors?:|eds?\.?:?|editado por|editores:?)\s+(.+)$", re.I)
_COPYRIGHT = re.compile(r"\u00a9|all rights reserved|derechos reservados|\bisbn\b", re.I)


def file_title(name):
    """A unit title from a file's name: "00.5 Abbreviations.docx" -> "Abbreviations";
    "00.2 Foreword by Lance Quinn - BH.docx" -> "Foreword by Lance Quinn"."""
    base = re.sub(r"\.docx$", "", name, flags=re.I)
    base = re.sub(r"^[\d.\s_-]+", "", base)                      # leading numbers
    base = re.sub(r"(\s+-\s+[A-Z]{1,4}|_[a-z]{1,4})$", "", base)  # initials: " - BH", "_rk"
    return base.strip() or name


def title_key(text):
    """A title for matching: lower case, no trailing punctuation or numbers ("Notes:", "PREFACE")."""
    s = " ".join(text.split()).casefold()
    s = re.sub(r"[\s.:;,\-–—]+$", "", s)
    return unicodedata.normalize("NFC", s)


def classify(title, chapter_seen):
    """(kind, type) for a chapter-level heading."""
    key = title_key(title)
    # "Foreword by Lance Quinn", "Preface: Why This Book": the word that names the part.
    lead = re.split(r"\s+(?:by|por)\s+|:\s*|\s+[\u2013\u2014-]\s+", key, maxsplit=1)[0]
    if lead in _FRONT and lead != key and not chapter_seen and _FRONT[lead][0] == "front":
        key = lead
    if key in _FRONT and not chapter_seen:
        return _FRONT[key]
    if not chapter_seen and _PRAISE.match(key):
        return ("display", "endorsements")
    if key == "índice":   # Spanish: the contents at the front, an index at the back
        return ("back", "index") if chapter_seen else ("front", "contents")
    if key in _BACK:
        return ("back", _BACK[key])
    if _APPENDIX.match(key):
        return ("back", "appendix")
    m = _PART.match(key)
    if m and (m.group(2).strip(".:") in _PART_WORDS or m.group(2).strip(".:").isdigit()):
        return ("part", "part")
    return ("chapter", "chapter")


# Kinds the user can give a unit (book settings "unit_kinds": {unit title: key}).
KINDS = {"chapter": ("chapter", "chapter"), "part": ("part", "part"),
         "front": ("front", "front matter"), "back": ("back", "back matter"),
         "display": ("display", "display page"), "endorsements": ("display", "endorsements")}
KIND_LABELS = {"chapter": "chapter", "part": "part", "front": "front matter",
               "back": "back matter", "display": "display page", "endorsements": "endorsements"}


def kind_key(unit):
    """The KINDS key a unit has now."""
    if unit.type == "endorsements":
        return "endorsements"
    return unit.kind if unit.kind in KINDS else "chapter"


def apply_kinds(outline, kinds):
    """The user's choices of kind for units (by title), over what was detected."""
    for u in outline.units:
        key = (kinds or {}).get(u.title)
        if key in KINDS and key != kind_key(u):
            u.kind, u.type = KINDS[key]
            u.detected_by += " (kind set in the book settings)"
    return outline


@dataclass
class Unit:
    kind: str           # display, front, part, chapter, back
    type: str           # preface, contents, chapter, part, bibliography, opening...
    title: str
    file: str
    start: int          # body paragraph index of the heading in its file
    detected_by: str
    words: int = 0
    note_refs: int = 0
    subheads: list = field(default_factory=list)   # first-level section titles
    page_break_before: bool = True   # starts at a section break or at the top of a file


@dataclass
class Outline:
    units: list = field(default_factory=list)
    title: str = None
    title_source: str = None
    subtitle: str = None
    subtitle_source: str = None
    author: str = None
    author_source: str = None
    creators: list = field(default_factory=list)
    details: dict = field(default_factory=dict)
    copyright_lines: list = field(default_factory=list)   # the manuscript's, as written    # read from a copyright page (frontmatter fields)   # [{"role", "name"}] when the role is known
    file_creator: str = None        # docProps creator: usually whoever made the file
    copyright_found: bool = False
    toc_field: bool = False         # a Word contents field (it will be replaced)
    notes: list = field(default_factory=list)
    first_heading: dict = field(default_factory=dict)   # file name -> first heading text

    @property
    def words(self):
        return sum(u.words for u in self.units)

    def present(self):
        types = {u.type for u in self.units}
        if self.title:
            types.add("title page")
        if self.copyright_found:
            types.add("copyright")
        if self.toc_field:
            types.add("contents")
        return types


def plural(n, word, words=None):
    return "%d %s" % (n, word if n == 1 else (words or word + "s"))


def _word_count(text):
    return len(text.split())


class _FileOutline:
    def __init__(self, doc, sm):
        self.doc, self.sm = doc, sm
        self.maps = {}
        self.paras = [p for p in doc.paragraphs]

    def mapping(self, p):
        if p.index in self.sm.format_groups(self.doc)[1] or self.sm.repeated_title(self.doc, p):
            return self.sm.paragraph_mapping(self.doc, p)
        sid = self.doc.para_style(p)
        if sid not in self.maps:
            self.maps[sid] = self.sm.paragraph_style(self.doc, sid)
        return self.maps[sid]

    def usable(self, p):
        return not p.in_table and not p.in_toc_field and \
            self.mapping(p).role not in ("toc", "toc_title", "skip")

    def heads(self):
        """[(paragraph index, role, detected_by)] by the first method that finds any."""
        doc = self.doc
        found = []
        for p in self.paras:
            m = self.mapping(p)
            if self.usable(p) and m.role in ("chapter", "part") and p.text.strip():
                by = "style %s" % m.word if m.source in ("default", "profile") else \
                    "formatting %s" % m.word if m.source in ("formatting", "book") else \
                    "style %s (%s)" % (m.word, m.source)
                found.append((p.index, m.role, by))
        if found:
            return found
        for ref in doc.styleref:
            if ref.isdigit():
                ids = {sid for sid, st in doc.styles.items()
                       if norm(st.name) == "heading %s" % ref}
            else:
                ids = {sid for sid, st in doc.styles.items()
                       if norm(st.name) == norm(ref) or sid == ref}
            found = [(p.index, "chapter", 'Word running head (STYLEREF "%s")' % ref)
                     for p in self.paras
                     if self.usable(p) and doc.para_style(p) in ids and p.text.strip()]
            if found:
                return found
        found = [(p.index, "chapter", "outline level 1") for p in self.paras
                 if self.usable(p) and p.outline_level == 0 and p.text.strip()]
        if found:
            return found
        starts = [0]
        for p in self.paras:
            if p.ends_section and p.section + 1 < len(doc.sections) and \
                    doc.sections[p.section + 1].break_type != "continuous":
                starts.append(p.index + 1)
        by = "section break" if len(starts) > 1 else "whole file"
        for s in starts:
            for p in self.paras[s:]:
                if p.text.strip() and self.usable(p):
                    if not found or found[-1][0] != p.index:
                        found.append((p.index, "chapter", by))
                    break
        if by == "section break" and found:
            found[0] = (found[0][0], "chapter", "section break (start of file)")
        return found

    def page_break_before(self, index):
        if index == 0 or not any(p.text.strip() for p in self.paras[:index]):
            return True
        prev = self.paras[index - 1]
        if prev.ends_section and prev.section + 1 < len(self.doc.sections):
            return self.doc.sections[prev.section + 1].break_type != "continuous"
        return False


def build_outline(docs, stylemap=None):
    sm = stylemap or StyleMap()
    sm.prepare(docs)
    out = Outline()
    chapter_seen = False
    for doc in docs:
        fo = _FileOutline(doc, sm)
        heads = fo.heads()
        units_before, seen_before = len(out.units), chapter_seen
        if any(f.code == "TOC" for f in doc.fields):
            out.toc_field = True
        if heads:
            out.first_heading[doc.name] = fo.paras[heads[0][0]].text.strip()
        if doc.core.get("creator") and not out.file_creator:
            out.file_creator = doc.core["creator"]

        # Title material anywhere before the first chapter.
        for p in fo.paras:
            m = fo.mapping(p)
            text = " ".join(p.text.split())
            if not text or m.source in ("formatting", "book"):
                continue          # a chapter's own author line, found by its look
            if m.role == "book_title" and not out.title:
                out.title, out.title_source = text, "style %s in %s" % (m.word, doc.name)
            elif m.role == "subtitle" and not out.subtitle:
                out.subtitle, out.subtitle_source = text, "style %s in %s" % (m.word, doc.name)
            elif m.role == "author" and not out.author:
                out.author, out.author_source = text, "style %s in %s" % (m.word, doc.name)

        boundaries = [h[0] for h in heads] + [len(fo.paras)] if heads else [len(fo.paras)]
        lead = fo.paras[:boundaries[0]]
        lead_text = [p for p in lead if p.text.strip() and fo.usable(p)]
        if lead_text:
            titled = any(fo.mapping(p).role in ("book_title", "subtitle") for p in lead_text)
            ti = next((i for i, p in enumerate(lead_text)
                       if fo.mapping(p).role == "book_title"), None)
            strong = any(u.detected_by.startswith("style") for u in out.units)
            if ti is not None and not strong and \
                    not any(u.type == "title page" for u in out.units) and \
                    _is_title_page(fo, lead_text[ti:]):
                # The title page, found by its title line. Whatever comes before it
                # (endorsements, seldom with a heading) is preliminary matter.
                # A line or two above the title (a school's or publisher's name) is part of
                # the title page; endorsements run to sentences or are quotations.
                if ti and not _endorsement_like(lead_text[:ti]):
                    ti = 0
                start = lead_text[ti].index
                if ti:
                    pre = Unit("display", "endorsements", "(endorsements)", doc.name,
                               lead_text[0].index, "text before the title page")
                    _fill(pre, fo, lead[:start])
                    out.units.append(pre)
                unit = Unit("display", "title page", "(title page)", doc.name, start,
                            "title style")
                _fill(unit, fo, lead[start:])
                _scan_opening(out, lead[start:])
                out.units.append(unit)
                chapter_seen = False    # anything before the title page was preliminary
            elif out.units and not titled and _is_title_page(fo, lead_text):
                # A stray line or two before a later file's first heading stays with the
                # previous unit.
                prev = out.units[-1]
                _fill(prev, fo, lead)
                out.notes.append("%s starts with %s of text before its first heading; %s "
                                 "kept with the previous unit (\"%s\")."
                                 % (doc.name, plural(len(lead_text), "paragraph"),
                                    "it is" if len(lead_text) == 1 else "they are", prev.title))
            elif not out.units and _is_title_page(fo, lead_text):
                is_title = any(fo.mapping(p).role in ("book_title", "subtitle") for p in lead)
                unit = Unit("display", "title page" if is_title else "opening",
                            "(title page)" if is_title else "(text before the first heading)",
                            doc.name, 0, "start of book")
                out.units.append(unit)
                _fill(unit, fo, lead)
                _scan_opening(out, lead)
            else:
                # Text before a file's first chapter heading with a title, headings or more
                # than a page's worth (an article's title and body, say) is a unit of its own,
                # not added to the previous file's last unit (which may be a bibliography).
                first = _lead_title(fo, lead_text)
                title = " ".join(first.text.split())
                kind, typ = classify(title, chapter_seen)
                if kind == "chapter":
                    chapter_seen = True
                unit = Unit(kind, typ, title, doc.name, lead_text[0].index,
                            "start of file (%s)" % ("title style" if fo.mapping(first).role ==
                                                    "book_title" else "first line"))
                _fill(unit, fo, lead)
                out.units.append(unit)
                if out.units[0] is not unit:
                    out.notes.append("%s starts with %s before its first chapter heading; "
                                     "they begin a unit of their own (\"%s\")."
                                     % (doc.name, plural(len(lead_text), "paragraph"), title))
        if not heads:
            continue
        for i, (idx, role, by) in enumerate(heads):
            title = " ".join(fo.paras[idx].text.split())
            if by == "whole file" and (len(title.split()) > MAX_TITLE_WORDS or
                                       "\t" in fo.paras[idx].text):
                # The first line isn't a title (an abbreviations list's first entry, say):
                # the file's name is.
                title, by = file_title(doc.name), "whole file (title from the file name)"
            if role == "part":
                kind, typ = "part", "part"
            else:
                kind, typ = classify(title, chapter_seen)
            if kind == "chapter":
                chapter_seen = True
            unit = Unit(kind, typ, title, doc.name, idx, by,
                        page_break_before=fo.page_break_before(idx))
            body = fo.paras[idx:boundaries[i + 1]]
            _fill(unit, fo, body)
            if kind == "display" or (kind == "front" and not out.units):
                _scan_opening(out, body)
            out.units.append(unit)
        if _copyright_file(out, fo, out.units[units_before:]):
            chapter_seen = seen_before      # it was no chapter after all
    _by_lines(out)
    if not out.title and sm.book_title_line:
        out.title, out.title_source = sm.book_title_line, "the first line of several files"
    if out.details.get("leftover"):
        known = {" ".join((t or "").split()).casefold() for t in (out.title, out.subtitle)}
        out.details["leftover"] = [x for x in out.details["leftover"]
                                   if x.casefold() not in known]
    _before_title_page(out)
    if not out.title:
        for doc in docs:
            if doc.core.get("title"):
                out.title, out.title_source = doc.core["title"], \
                    "document properties of %s (check it)" % doc.name
                break
    _check_outline(out)
    return out


_PART_BY = re.compile(r"^(foreword|afterword|preface|introduction|pr[oó]logo|ep[ií]logo|"
                      r"prefacio|introducci[oó]n)\s+(?:by|por|de)\s+(.+)$", re.I)
_PART_ROLE = {"prólogo": "foreword", "prologo": "foreword", "epílogo": "afterword",
              "epilogo": "afterword", "prefacio": "preface", "introducción": "introduction",
              "introduccion": "introduction"}


def _by_lines(out):
    """"Foreword by Lance Quinn" (an afterword, preface or introduction by someone) as a unit
    title: that person, in that role, for the title page's bylines."""
    from .frontmatter import split_names
    for u in out.units:
        m = _PART_BY.match(u.title.strip())
        if m and u.kind in ("front", "back"):
            word = m.group(1).casefold()
            role = _PART_ROLE.get(word, word)
            for name in split_names(m.group(2)):
                person = {"role": role, "name": name}
                if person not in out.creators:
                    out.creators.append(person)


def _copyright_file(out, fo, units):
    """A file that is a copyright page (short, with a copyright line, "All rights reserved"
    or an ISBN) is the book's copyright page: the export uses it instead of making one. Its
    "Edited by ..." line gives the author when none was found."""
    paras = [p for p in fo.paras if p.text.strip()]
    text = "\n".join(p.text for p in paras)
    if len(units) != 1 or len(text.split()) > 800 or len(_COPYRIGHT.findall(text)) < 2:
        return False
    u = units[0]
    if u.kind == "display" and u.type == "copyright":
        return True
    u.kind, u.type = "display", "copyright"
    u.detected_by += " (copyright lines: the book's copyright page)"
    out.copyright_found = True
    _read_copyright(out, [p.text for p in paras])
    for p in paras:
        line = " ".join(p.text.split())
        m = _EDITED.match(line)
        if m and not out.author and len(line) < 160:
            from .frontmatter import split_names
            out.author, out.author_source = m.group(2).strip(), \
                "the copyright page's \u201c%s\u201d line" % m.group(1).strip().capitalize()
            out.creators = [{"role": "editor", "name": n} for n in split_names(m.group(2))]
    return True


def _before_title_page(out):
    """Units before the title page (a file of endorsements with no headings, say) are
    preliminary matter: endorsements."""
    tp = next((n for n, u in enumerate(out.units) if u.type == "title page"), None)
    for u in out.units[:tp or 0]:
        if u.type != "endorsements":
            u.kind, u.type = "display", "endorsements"
            u.detected_by += " (before the title page: endorsements)"


def _endorsement_like(paras):
    """Text above the title that reads as endorsements: some sentences, or a quotation or an
    attribution ("\u2014 A. Reader"). Not a school's or publisher's name."""
    if sum(_word_count(p.text) for p in paras) >= ENDORSEMENT_MIN_WORDS:
        return True
    for p in paras:
        t = p.text.strip()
        if t[:1] in "\u201c\"\u00ab\u2018'" or t[:1] in "\u2014\u2013" or \
                re.search(r"[\u201d\"\u00bb]\s*[\u2014\u2013-]\s*\S", t):
            return True
    return False


def _is_title_page(fo, lead_text):
    """Text before the book's first chapter heading is a title page when it is short and has
    no headings; otherwise (an article's title and body, say) it is a unit of its own."""
    if any(fo.mapping(p).role in ("heading", "chapter", "part") for p in lead_text):
        return False
    words = sum(_word_count(p.text) for p in lead_text
                if fo.mapping(p).role not in ("book_title", "subtitle", "author"))
    return words <= 150


def _lead_title(fo, lead_text):
    """The paragraph that titles a unit made from text before a file's first chapter heading:
    a title-style line, else the first line."""
    for p in lead_text:
        if fo.mapping(p).role in ("book_title", "chapter", "part"):
            return p
    return lead_text[0]


def _fill(unit, fo, paras):
    for p in paras:
        if p.in_toc_field or fo.mapping(p).role in ("toc", "toc_title", "skip"):
            continue
        unit.words += _word_count(p.text)
        unit.note_refs += p.footnotes
        m = fo.mapping(p)
        if m.role == "heading" and m.level == 1 and p.text.strip():
            unit.subheads.append(" ".join(p.text.split()))


def _read_copyright(out, lines):
    """Book details from copyright lines (frontmatter.parse_copyright), keeping what was found
    first; the notices and lines that fit nothing are collected."""
    from .frontmatter import parse_copyright
    out.copyright_lines += [" ".join(x.split()) for x in lines if x and x.strip()]
    got = parse_copyright(lines, known=(out.title, out.subtitle))
    for key in ("notices", "leftover"):
        out.details.setdefault(key, []).extend(x for x in got.pop(key)
                                               if x not in out.details[key])
    for key, value in got.items():
        out.details.setdefault(key, value)


def _scan_opening(out, paras):
    lines = []
    for p in paras:
        text = " ".join(p.text.split())
        if not text:
            continue
        if lines or "©" in text or re.match(r"^copyright\b", text, re.I) or \
                "derechos reservados" in text.lower():
            out.copyright_found = True
            lines.append(text)          # from the copyright line on: the copyright lines
        m = _BY.match(text)
        if m and not out.author and len(text) < 80:
            out.author, out.author_source = m.group(2).strip(), "title page text"
    if lines:
        _read_copyright(out, lines)


def _check_outline(out):
    chapters = [u for u in out.units if u.kind == "chapter"]
    if not chapters:
        out.notes.append("No chapters were found. Check the style map: the style used for "
                         "chapter titles should have the role \"chapter\".")
    by = {u.detected_by.split(" (")[0] for u in out.units if u.kind != "display"}
    if any(b.startswith(("section break", "whole file")) for b in by):
        out.notes.append("Some files have no recognized headings; their units were found by "
                         "section breaks or taken as whole files. Map the chapter-title style "
                         "to make this reliable.")
    titles = {}
    for u in chapters:
        titles.setdefault(title_key(u.title), []).append(u)
    for key, us in titles.items():
        if len(us) > 1:
            out.notes.append('"%s" is the title of %d chapters; running heads will repeat.'
                             % (us[0].title, len(us)))
