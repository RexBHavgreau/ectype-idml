"""Front matter (build step 6): half-title, title page, copyright page and reserved contents.

The book's details (title, subtitle, author, copyright holder, ISBNs...) come from the book
settings, prefilled from what the outline detected. Anything still missing is written as a
bracketed placeholder ("[ISBN]") and reported, so nothing is left out silently. The tool ships
no notice wording of its own: notices come from the user's library in the profile, ticked per
book.

Book settings (Book.settings["front"]), modelled on a bibliographic record for a book (as
Zotero's Book item) plus the switches a book needs:
    title, subtitle, short_title (verso running head), creators (an ordered list of
    {"role": author/editor/translator/foreword/afterword/preface/introduction/contributor/
    series_editor, "name": "First Last"}),
    series, series_number, volume, volumes, edition, publisher, publisher_address (place),
    year, holder (blank = the authors, else the editors), rights (statement; blank = "All
    rights reserved."), isbn_print, isbn_ebook,
    call_number (blank = no line), credits, printed_in, notices (names from the profile's
    library), half_title (True), copyright_title (False: the title (and subtitle) as the
    copyright page's first line, in italics), contents (True), contents_pages (None = estimated).
    (Before book version 2 a single "author" string; Book.load upgrades it.)

The title page has a byline per role, in the creators' order: authors' names alone, then
"Edited by ...", "Translated by ...", "With a foreword by ..." (and afterword, preface,
introduction); wording per language in TEXT, so another language is a table entry.
Contributors and series editors don't go on the title page.
"""

import datetime
import re
import math

from .idml.model import Paragraph, Run

TEXT = {
    "en": {"contents": "Contents", "rights": "All rights reserved.",
           "copyright": "Copyright © {year} by {holder}", "printed": "Printed in {country}",
           "isbn_print": "ISBN {isbn} (paperback)", "isbn_ebook": "ISBN {isbn} (ebook)",
           "editor": "Edited by {names}", "translator": "Translated by {names}",
           "foreword": "With a foreword by {names}", "afterword": "With an afterword by {names}",
           "preface": "With a preface by {names}",
           "introduction": "With an introduction by {names}",
           "and": "and", "serial_comma": True, "volume": "Volume {n}",
           "volume_of": "Volume {n} of {total}", "series": "{series}",
           "series_number": "{series} {number}", "call_number": "Call number: {number}"},
    "es": {"contents": "Contenido", "rights": "Todos los derechos reservados.",
           "copyright": "© {year} {holder}", "printed": "Impreso en {country}",
           "isbn_print": "ISBN: {isbn} (rústica)", "isbn_ebook": "ISBN: {isbn} (libro electrónico)",
           "editor": "Edición de {names}", "translator": "Traducción de {names}",
           "foreword": "Con prólogo de {names}", "afterword": "Con epílogo de {names}",
           "preface": "Con prefacio de {names}",
           "introduction": "Con introducción de {names}",
           "and": "y", "serial_comma": False, "volume": "Volumen {n}",
           "volume_of": "Volumen {n} de {total}", "series": "{series}",
           "series_number": "{series} {number}", "call_number": "Signatura: {number}"},
}

# Contributor roles, in the order the window offers them; those with a title-page byline.
ROLES = ("author", "editor", "translator", "foreword", "afterword", "preface", "introduction",
         "contributor", "series_editor")
ROLE_LABELS = {"author": "author", "editor": "editor", "translator": "translator",
               "foreword": "foreword by", "afterword": "afterword by", "preface": "preface by",
               "introduction": "introduction by", "contributor": "contributor",
               "series_editor": "series editor"}
BYLINE_ROLES = ("author", "editor", "translator", "foreword", "afterword", "preface",
                "introduction")
LEAD_ROLES = ("author", "editor", "translator")   # whose names stand for "the author"
_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "phd", "ph.d.", "dmin", "d.min.",
             "thd", "th.d.", "md", "m.d."}


def split_names(text):
    """Names in a line: "Nicolas Ellen, Josh Stephens, and Brett Williams" -> three names;
    "John Smith, Jr." stays one."""
    parts = [x.strip() for x in re.split(r",\s*(?:and\s+|&\s*)?|\s+(?:and|&|y)\s+|;\s*",
                                           text or "") if x and x.strip()]
    names = []
    for part in parts:
        if names and part.casefold() in _SUFFIXES:
            names[-1] += ", " + part
        else:
            names.append(part)
    return names


_NOTICE = re.compile(r"scripture|bible|quotations?|used by permission|version", re.I)
_HOLDER = re.compile(r"^(?:copyright\s*)?(?:\u00a9|\(c\)|copyright)\s*((?:\d{4}[,\s\u2013-]*)+)"
                     r"(?:by\s+|por\s+)?(.+?)\.?$", re.I)
_PUBLISHED = re.compile(r"^(?:published|publicado)\s+(?:by|por)\s+(.+?)\.?$", re.I)
_ISBN = re.compile(r"\bisbn(?:-1[03])?:?\s*([\dxX][\d\s-]{8,}[\dxX])\s*(\(([^)]*)\))?", re.I)
_PRINTED = re.compile(r"^(?:printed|impreso)\s+(?:in|en)\s+(.+?)\.?$", re.I)
_EDITION = re.compile(r"^(first|second|third|fourth|fifth|\d+(?:st|nd|rd|th))\s+"
                      r"(edition|printing)\b.*$|^(primera|segunda|tercera)\s+edici[oó]n\b.*$",
                      re.I)
_WEB = re.compile(r"^(?:https?://|www\.)\S+$", re.I)
_EBOOK = re.compile(r"e-?book|epub|kindle|digital|electr[oó]nico|pdf", re.I)


_RIGHTS = re.compile(r"^(all rights reserved|todos los derechos reservados)\b", re.I)
_EDITED_BY = re.compile(r"^(edited by|editors?:|eds?\.?:?|editado por|translated by|"
                        r"traducido por)\s+", re.I)
# The fields parse_copyright fills (besides the lists "notices" and "leftover").
COPYRIGHT_FIELDS = ("year", "holder", "rights", "publisher", "publisher_address", "isbn_print",
                    "isbn_ebook", "printed_in", "edition")


def parse_copyright(lines, known=()):
    """Read a copyright page's lines into the book's details. Returns {field: value} for the
    fields of Book Details (COPYRIGHT_FIELDS: the first "Copyright \u00a9 2026 by X" line's year
    and holder; a rights statement longer than "All rights reserved."; "Published by X" and
    the publisher's web address; ISBNs, print or ebook by their labels; "Printed in ...";
    an edition or printing line), plus "notices": permissions (Bible versions and the like,
    and any later copyright line), and "leftover": the lines that fit nothing, so the page can
    be replaced by a generated one without losing them unseen. known: the book's title and
    subtitle; a line that is the title (or title and subtitle) gives "copyright_title":
    True."""
    out = {"notices": [], "leftover": []}
    known = [" ".join(k.split()) for k in known if k]
    skip = {k.casefold() for k in known}
    if len(known) == 2:
        skip |= {("%s%s %s" % (known[0], sep, known[1])).casefold() for sep in (":", "", ".")}
    isbns = []
    for raw in lines:
        line = " ".join((raw or "").split())
        if not line:
            continue
        if line.casefold() in skip:
            out["copyright_title"] = True
            continue
        if _NOTICE.search(line) and not _ISBN.search(line):
            out["notices"].append(line)
            continue
        m = _HOLDER.match(line)
        if m:
            if "year" in out:
                out["notices"].append(line)     # another work's copyright: a permission
                continue
            out["year"] = m.group(1).strip(" ,\u2013-")
            parts = re.split(r"\.\s+(?=all rights|todos los)", m.group(2), flags=re.I)
            out["holder"] = parts[0].strip(" .")
            if len(parts) > 1 and len(parts[1]) > len("All rights reserved."):
                out["rights"] = parts[1].strip()
            continue
        if _RIGHTS.match(line):
            if len(line) > len("All rights reserved.") + 2:
                out["rights"] = line
            continue
        found = list(_ISBN.finditer(line))
        if found:
            isbns += [(re.sub(r"\s", "", m.group(1)), m.group(3) or "") for m in found]
            continue
        used = False
        for key, rx in (("publisher", _PUBLISHED), ("printed_in", _PRINTED)):
            m = rx.match(line)
            if m and key not in out:
                out[key], used = m.group(1).strip(), True
        if not used and _EDITION.match(line) and "edition" not in out:
            out["edition"], used = line, True
        if not used and _WEB.match(line) and "publisher_address" not in out:
            out["publisher_address"], used = line, True
        if not used and _EDITED_BY.match(line):
            used = True                         # read as contributors by the outline
        if not used:
            out["leftover"].append(line)
    for number, label in isbns:
        key = "isbn_ebook" if _EBOOK.search(label) else "isbn_print"
        if key in out:
            key = "isbn_ebook" if key == "isbn_print" else None
        if key and key not in out:
            out[key] = number
    return out


def notice_name(text):
    """A short name for a permission notice: the version it is for ("Scripture quotations
    marked ESV..." -> "ESV"), else its first words."""
    m = re.search(r"\bmarked\s+\(?([A-Z][A-Z0-9]{1,7})\b", text) or \
        re.search(r"\(([A-Z][A-Z0-9]{1,7})\)", text)
    if m:
        return m.group(1)
    return " ".join(text.split()[:4]).rstrip(".,;:")


def join_names(names, lang="en"):
    """"A", "A and B", "A, B, and C" (Chicago's serial comma; none in Spanish)."""
    t = texts(lang)
    names = [n for n in names if n]
    if len(names) <= 2:
        return (" %s " % t["and"]).join(names)
    last = (", " if t["serial_comma"] else " ") + t["and"] + " " + names[-1]
    return ", ".join(names[:-1]) + last


def creators(front, outline=None):
    """The book's creators: the settings' list, else an old single "author", else what the
    manuscript showed (outline.creators, or its author line)."""
    listed = [c for c in (front or {}).get("creators") or [] if (c.get("name") or "").strip()]
    if listed:
        return [{"role": c.get("role") or "author", "name": c["name"].strip()} for c in listed]
    if (front or {}).get("author"):
        return [{"role": "author", "name": n} for n in split_names(front["author"])]
    found = list(getattr(outline, "creators", None) or []) if outline is not None else []
    if outline is not None and outline.author and \
            not any(c["role"] in LEAD_ROLES for c in found):
        # The author from a title page or style, ahead of a foreword's writer and the like.
        found = [{"role": "author", "name": n} for n in split_names(outline.author)] + found
    return found


def bylines(people, lang="en"):
    """Title-page lines: one per byline role, in the order the roles first appear."""
    t = texts(lang)
    order, names = [], {}
    for c in people:
        if c["role"] in BYLINE_ROLES:
            if c["role"] not in names:
                order.append(c["role"])
            names.setdefault(c["role"], []).append(c["name"])
    lines = []
    for role in order:
        joined = join_names(names[role], lang)
        lines.append(joined if role == "author" else t[role].format(names=joined))
    return lines

def texts(lang):
    return TEXT.get(lang, TEXT["en"])


def book_info(outline, front=None, lang="en"):
    """The book's details: the settings first, then what was detected. Returns (info, notes);
    notes name what had to be left as a placeholder."""
    front = dict(front or {})
    people = creators(front, outline)
    by_role = {}
    for c in people:
        by_role.setdefault(c["role"], []).append(c["name"])
    # "The author" where one name is wanted (copyright holder, a running head): the authors,
    # else the editors, else the translators.
    lead = next((by_role[r] for r in LEAD_ROLES if by_role.get(r)), [])
    found = getattr(outline, "details", None) or {}

    def got(key):
        """Book Details' value, else what the manuscript's copyright page says."""
        return front.get(key) or found.get(key) or ""
    info = {
        "half_title": front.get("half_title", True),
        "copyright_title": bool(front.get("copyright_title", found.get("copyright_title"))),
        "title": front.get("title") or outline.title,
        "subtitle": front.get("subtitle") or outline.subtitle,
        "creators": people,
        "bylines": bylines(people, lang),
        "author": join_names(lead, lang),
        "series": front.get("series") or "",
        "series_number": front.get("series_number") or "",
        "volume": front.get("volume") or "",
        "volumes": front.get("volumes") or "",
        "call_number": front.get("call_number") or "",
        "short_title": front.get("short_title"),
        "publisher": got("publisher"),
        "publisher_address": got("publisher_address"),
        "year": got("year") or datetime.date.today().year,
        "holder": got("holder") or None,
        "edition": got("edition"),
        "isbn_print": got("isbn_print"),
        "isbn_ebook": got("isbn_ebook"),
        "credits": front.get("credits") or "",
        "printed_in": got("printed_in"),
        "notices": list(front.get("notices") or []),
        "rights": got("rights"),
        # Notices found on the manuscript's copyright page, used when the book has none
        # chosen from the library (texts, not library names).
        "notice_texts": [] if front.get("notices") else list(found.get("notices") or []),
        "contents": front.get("contents", True),
        "contents_pages": front.get("contents_pages"),
    }
    notes = []
    if not info["title"]:
        info["title"] = "[Book title]"
        notes.append("No book title was found: the title pages say [Book title]. Enter the title "
                     "in the book settings.")
    if not info["author"]:
        info["author"] = "[Author]"
        info["bylines"] = ["[Author]"]
        notes.append("No author or editor was found: the title page says [Author]. Add the "
                     "contributors in Book Details.")
    if not info["holder"]:
        info["holder"] = info["author"]
    return info, notes


def half_title(info, lang="en"):
    """The half-title: the title, and the series (with its number) when there is one."""
    paras = [Paragraph("Half Title", [Run(info["title"])])]
    if info.get("series"):
        t = texts(lang)
        line = t["series_number"].format(series=info["series"], number=info["series_number"]) \
            if info.get("series_number") else t["series"].format(series=info["series"])
        paras.append(Paragraph("Series", [Run(line)]))
    return paras


def title_page(info, lang="en"):
    t = texts(lang)
    paras = [Paragraph("Book Title", [Run(info["title"])])]
    if info["subtitle"]:
        paras.append(Paragraph("Book Subtitle", [Run(info["subtitle"])]))
    if info.get("volume"):
        line = t["volume_of"].format(n=info["volume"], total=info["volumes"]) \
            if info.get("volumes") else t["volume"].format(n=info["volume"])
        paras.append(Paragraph("Volume", [Run(line)]))
    for line in info.get("bylines") or [info["author"]]:
        paras.append(Paragraph("Author", [Run(line)]))
    if info["publisher"]:
        paras.append(Paragraph("Publisher", [Run(info["publisher"])]))
    return paras


def copyright_page(info, lang, library=()):
    """The generated copyright page. Returns (paragraphs, notes)."""
    t = texts(lang)
    notes = []
    lines = [t["copyright"].format(year=info["year"], holder=info["holder"]),
             info.get("rights") or t["rights"]]
    paras = [Paragraph("Copyright", [Run(line)]) for line in lines]
    if info.get("copyright_title"):
        title = info["title"] + (": " + info["subtitle"] if info.get("subtitle") else "")
        paras.insert(0, Paragraph("Copyright Title", [Run(title)]))
    by_name = {n.get("name"): n.get("text", "") for n in library or ()}
    for name in info["notices"]:
        if name in by_name:
            paras.append(Paragraph("Copyright", [Run(by_name[name])]))
        else:
            notes.append('The notice "%s" is not in the profile\'s notice library; it was left '
                         "out." % name)
    for text in info.get("notice_texts") or ():
        paras.append(Paragraph("Copyright", [Run(text)]))
    if info["credits"]:
        paras.append(Paragraph("Copyright", [Run(info["credits"])]))
    pub = [x for x in (info["publisher"], info["publisher_address"]) if x]
    if pub:
        paras.append(Paragraph("Copyright", [Run("\n".join(pub))]))
    isbns = []
    if info["isbn_print"]:
        isbns.append(t["isbn_print"].format(isbn=info["isbn_print"]))
    if info["isbn_ebook"]:
        isbns.append(t["isbn_ebook"].format(isbn=info["isbn_ebook"]))
    if not isbns:
        isbns.append(t["isbn_print"].format(isbn="[ISBN]"))
        notes.append("The copyright page has [ISBN] where the ISBN goes. Enter it in the book "
                     "settings (or delete the line if the book has none).")
    if info.get("call_number"):
        isbns.append(t["call_number"].format(number=info["call_number"]))
    paras.append(Paragraph("Copyright", [Run("\n".join(isbns))]))
    last = [x for x in (t["printed"].format(country=info["printed_in"])
                        if info["printed_in"] else "", info["edition"]) if x]
    if last:
        paras.append(Paragraph("Copyright", [Run("\n".join(last))]))
    return paras, notes


def copyright_text(info, lang, library=()):
    """The generated copyright page as plain lines (for showing beside the manuscript's)."""
    paras, _notes = copyright_page(info, lang, library)
    return [line for p in paras for line in "".join(r.text for r in p.runs).split("\n")]


def contents_page(lang):
    return [Paragraph("Contents Title", [Run(texts(lang)["contents"])])]


def contents_entries(outline, depth="chapters"):
    """(level, title) of each contents entry: the units after the contents (front matter that
    follows it, parts, chapters, back matter), and first-level sections if depth is
    "sections"."""
    out = []
    for u in outline.units:
        if u.kind == "display" or u.type == "contents":
            continue
        out.append((1, u.title))
        if depth == "sections":
            out += [(2, s) for s in u.subheads]
    return out


def contents_pages(entries, cpl, lead, text_height, sink):
    """Pages to reserve for the contents: the title block, then each entry's lines (long titles
    wrap short of the page number), with a little space above level-1 entries."""
    height = sink + 4 * lead
    for level, title in entries:
        room = max(20, cpl - 8 - (4 if level > 1 else 0))
        height += math.ceil(max(1, len(title)) / room) * lead + (6 if level == 1 else 0)
    return max(1, math.ceil(height / text_height))
