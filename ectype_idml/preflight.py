"""Preflight: read every input file and report what the book contains and what needs attention.

Reports the styles in use and how they map, direct-formatting hotspots, fonts, Hebrew and Greek,
the outline, style conflicts between files, and everything version 1 doesn't carry over.
Nothing disappears silently.
"""

import dataclasses
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .docx_reader import read_docx
from .outline import build_outline, plural
from .stylemap import StyleMap, display_name, norm

# Fonts Word templates set by default; a body font among these is probably not the author's
# choice for the book.
TEMPLATE_FONTS = {"calibri", "times new roman", "aptos", "cambria", "arial", "calibri light",
                  "aptos display", "liberation serif", "liberation sans"}

# What happens to each kind of item, and whether it's left out.
ITEM_INFO = {
    "text box": ("Text boxes are left out in version 1. Move the text into the body if it belongs "
                 "in the book.", True),
    "floating shape": ("Floating shapes are left out in version 1.", True),
    "shape": ("Drawing shapes are left out in version 1.", True),
    "chart": ("Charts are left out in version 1. Insert them as images.", True),
    "SmartArt": ("SmartArt is left out in version 1. Insert it as an image.", True),
    "embedded object": ("Embedded objects are left out in version 1. Insert them as images.", True),
    "imported content": ("Content imported from another file is left out. Paste it into the "
                         "document.", True),
    "equation": ("Equations are left out in version 1. Insert them as images.", True),
    "comment": ("Comments are not carried over.", True),
    "tracked change": ("Tracked changes are read as if accepted. Accept or reject them in Word "
                       "first to be sure.", False),
    "floating image": ("Floating images are placed inline at their anchor.", False),
    "index entry (XE)": ("Index entries (XE fields) are removed. Index the book in InDesign with "
                         "Indicat.", True),
    "field": ("Unusual fields are replaced by the text they show.", False),
    "unclosed field": ("A field code is broken; Word may repair it if the file is saved again.",
                       False),
}


@dataclass
class StyleUse:
    word: str
    idml: str
    role: str
    level: int
    source: str
    warning: bool
    count: int = 0
    files: list = field(default_factory=list)


@dataclass
class FileSummary:
    name: str
    path: str
    first_heading: str
    paragraphs: int
    words: int
    footnotes: int
    endnotes: int
    sections: int
    word_pages: int = None


@dataclass
class Report:
    files: list = field(default_factory=list)
    outline: object = None
    paragraph_styles: list = field(default_factory=list)
    guessed_heads: dict = field(default_factory=dict)  # file -> heading groups found by formatting
    character_styles: list = field(default_factory=list)
    direct: dict = field(default_factory=dict)
    fonts: dict = field(default_factory=dict)
    scripts: dict = field(default_factory=dict)
    items: dict = field(default_factory=dict)     # kind -> [{file, where, paragraph, snippet, detail}]
    conflicts: list = field(default_factory=list)
    page: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)  # most important first
    errors: list = field(default_factory=list)    # files that couldn't be read

    def to_json(self):
        def conv(o):
            if dataclasses.is_dataclass(o):
                return {k: conv(v) for k, v in dataclasses.asdict(o).items()}
            if isinstance(o, dict):
                return {str(k): conv(v) for k, v in o.items()}
            if isinstance(o, (list, tuple, set)):
                return [conv(v) for v in o]
            return o
        return json.dumps(conv(self), ensure_ascii=False, indent=2)


def preflight(paths, profile=None, docs=None, settings=None):
    """Read the files (in book order) and build the report. docs: already-read DocxFiles;
    settings: the book's settings (its map for headings found by formatting)."""
    from .docx_reader import DocxError
    rep = Report()
    if docs is None:
        docs = []
        for p in paths:
            try:
                docs.append(read_docx(p))
            except DocxError as e:
                rep.errors.append(str(e))
    sm = StyleMap.from_profile(profile, settings)
    out = build_outline(docs, sm)
    rep.outline = out

    for doc in docs:
        words = sum(len(p.text.split()) for p in doc.paragraphs)
        rep.files.append(FileSummary(doc.name, doc.path, out.first_heading.get(doc.name, ""),
                                     len(doc.paragraphs), words, doc.footnote_count,
                                     doc.endnote_count, len(doc.sections), doc.app.get("pages")))

    _styles(rep, docs, sm)
    rep.guessed_heads = _guessed_heads(docs, sm)
    _direct(rep, docs, sm)
    _fonts(rep, docs, sm)
    _scripts(rep, docs)
    _items(rep, docs)
    _conflicts(rep, docs)
    _page(rep, docs)
    _warnings(rep, docs)
    return rep


def _styles(rep, docs, sm):
    para, char = {}, {}
    for doc in docs:
        for p in doc.paragraphs + doc.note_paragraphs:
            m = sm.paragraph_mapping(doc, p)
            use = para.setdefault(norm(m.word), StyleUse(m.word, m.idml, m.role, m.level, m.source,
                                                         m.warning))
            use.count += 1
            if doc.name not in use.files:
                use.files.append(doc.name)
            for cs in p.char_styles:
                cm = sm.character_style(doc, cs)
                cu = char.setdefault(norm(cm.word), StyleUse(cm.word, cm.idml, cm.role, 0,
                                                             cm.source, cm.warning))
                cu.count += 1
                if doc.name not in cu.files:
                    cu.files.append(doc.name)
    rep.paragraph_styles = sorted(para.values(), key=lambda u: -u.count)
    rep.character_styles = sorted(char.values(), key=lambda u: -u.count)


def _direct(rep, docs, sm):
    emphasis = font_runs = layout = 0
    by_style = Counter()
    layout_by_style = Counter()
    hotspots = []
    for doc in docs:
        heads = sm.format_groups(doc)[1]      # headings found by formatting: expected
        for p in doc.paragraphs + doc.note_paragraphs:
            if p.where == "body" and (p.index in heads or sm.repeated_title(doc, p)):
                continue
            emphasis += p.direct_emphasis
            style = display_name(doc.style_name(doc.para_style(p)) or "Normal")
            if p.direct_layout:
                layout += 1
                layout_by_style[style] += 1
            if p.direct_font:
                font_runs += len(p.direct_font)
                by_style[style] += 1
                props = sorted({x for run in p.direct_font for x in run})
                hotspots.append({"file": doc.name, "where": p.where, "paragraph": p.index,
                                 "style": style, "runs": len(p.direct_font),
                                 "props": [_PROP_NAMES.get(x, x) for x in props],
                                 "snippet": p.snippet})
    hotspots.sort(key=lambda h: -h["runs"])
    rep.direct = {"emphasis_runs": emphasis, "font_runs": font_runs, "layout_paragraphs": layout,
                  "font_by_style": dict(by_style.most_common()),
                  "layout_by_style": dict(layout_by_style.most_common()),
                  "hotspots": hotspots[:15], "hotspot_paragraphs": len(hotspots)}


_PROP_NAMES = {"rFonts": "font", "sz": "size", "szCs": "size", "color": "color",
               "highlight": "highlight", "spacing": "letter spacing", "w": "width",
               "kern": "kerning", "position": "raised/lowered", "shd": "shading",
               "fitText": "fit text"}


def _fonts(rep, docs, sm):
    body, heads = Counter(), Counter()
    direct = Counter()
    for doc in docs:
        used = Counter(doc.para_style(p) for p in doc.paragraphs)
        for sid, n in used.items():
            m = sm.paragraph_style(doc, sid)
            font = doc.resolve_font(sid)
            if not font:
                continue
            key = (font, doc.resolve_size(sid))
            if m.role == "body":
                body[key] += n
            elif m.role in ("chapter", "part", "heading", "book_title"):
                heads[font] += n
        direct.update(doc.run_fonts)
    rep.fonts = {"body": None, "body_size": None, "template_default": False,
                 "headings": [f for f, _ in heads.most_common()],
                 "direct": dict(direct.most_common())}
    if body:
        (font, size), _ = body.most_common(1)[0]
        rep.fonts.update(body=font, body_size=size,
                         template_default=font.casefold() in TEMPLATE_FONTS)


def _scripts(rep, docs):
    for key in ("hebrew", "greek"):
        runs = chars = rtl = 0
        fonts = Counter()
        poly = points = False
        samples = []
        for doc in docs:
            s = doc.scripts[key]
            runs += s.runs
            chars += s.chars
            rtl += s.rtl_marked
            fonts.update(s.fonts)
            poly = poly or s.polytonic
            points = points or s.points
            samples += [{"file": doc.name, "where": w, "paragraph": i, "text": t}
                        for w, i, t in s.samples]
        rep.scripts[key] = {"runs": runs, "chars": chars, "fonts": dict(fonts.most_common()),
                            "samples": samples[:3]}
        if key == "greek":
            rep.scripts[key]["polytonic"] = poly
        else:
            rep.scripts[key].update(points=points, rtl_marked=rtl)


def _items(rep, docs):
    items = defaultdict(list)
    for doc in docs:
        for it in doc.items:
            items[it.kind].append({"file": doc.name, "where": it.where, "paragraph": it.paragraph,
                                   "snippet": it.snippet, "detail": it.detail})
        if doc.endnote_count:
            items["endnotes"].append({"file": doc.name, "where": "endnote", "paragraph": None,
                                      "snippet": "", "detail": plural(doc.endnote_count, "endnote")})
    rep.items = dict(items)


def _conflicts(rep, docs):
    if len(docs) < 2:
        return
    in_use = set()
    for doc in docs:
        for p in doc.paragraphs + doc.note_paragraphs:
            in_use.add(norm(doc.style_name(doc.para_style(p)) or ""))
            in_use.update(norm(doc.style_name(c)) for c in p.char_styles)
    defs = defaultdict(list)
    for doc in docs:
        for st in doc.styles.values():
            if norm(st.name) in in_use:
                sig = dict(st.props)
                sig["based on"] = display_name(doc.style_name(st.based_on)) if st.based_on else ""
                defs[norm(st.name)].append((doc.name, display_name(st.name), sig))
    for key, entries in sorted(defs.items()):
        if len(entries) < 2:
            continue
        first = entries[0][2]
        differing = sorted({k for _f, _n, sig in entries[1:] for k in set(sig) | set(first)
                            if sig.get(k) != first.get(k)})
        if differing:
            rep.conflicts.append({
                "style": entries[0][1],
                "differences": [{"property": k,
                                 "values": {f: sig.get(k, "(not set)") for f, _n, sig in entries}}
                                for k in differing]})
    sizes = {d.name: d.doc_defaults.get("size") for d in docs}
    fonts = {d.name: d.resolve_font(d.default_style.get("paragraph")) for d in docs}
    for label, vals in (("default font size (half-points)", sizes), ("body font", fonts)):
        if len(set(vals.values())) > 1:
            rep.conflicts.append({"style": "(document defaults)",
                                  "differences": [{"property": label, "values": vals}]})


def _page(rep, docs):
    if not docs:
        return
    sec = docs[0].sections[0]
    rep.page = {"width": sec.page_width, "height": sec.page_height, "margins": sec.margins,
                "facing": None, "word_pages": sum(d.app.get("pages", 0) for d in docs) or None,
                "sizes": sorted({(s.page_width, s.page_height) for d in docs for s in d.sections
                                 if s.page_width})}
    if any(s.margins.get("gutter") for d in docs for s in d.sections):
        rep.page["facing"] = True
    if any(s.columns > 1 for d in docs for s in d.sections):
        rep.page["columns"] = max(s.columns for d in docs for s in d.sections)


def _guessed_heads(docs, sm):
    """{file name: [group names]} for files whose headings were found by formatting."""
    out = {}
    for doc in docs:
        groups = sm.format_groups(doc)[0]
        if groups:
            out[doc.name] = [g.name for g in groups]
    return out


def _warnings(rep, docs):
    w = rep.warnings
    for e in rep.errors:
        w.append(e)
    heb = rep.scripts.get("hebrew", {})
    if heb.get("runs"):
        w.append("This book has Hebrew (%s). Lay it out in InDesign: Affinity does not "
                 "support Hebrew and sets it left to right with the letters reversed."
                 % plural(heb["runs"], "run"))
    nested = sum(d.nested_tables for d in docs)
    if nested:
        w.append("%s inside other tables: the text is kept in the outer table's cell, without "
                 "the inner table's rows and columns. Rebuild them in InDesign, or unnest them "
                 "in Word." % plural(nested, "table"))
    if any(d.endnote_count for d in docs):
        n = sum(d.endnote_count for d in docs)
        w.append("%s. Endnotes are not supported; they will be converted to footnotes."
                 % plural(n, "endnote"))
    if rep.guessed_heads:
        names = sorted({g for groups in rep.guessed_heads.values() for g in groups})
        files = list(rep.guessed_heads)
        w.append("Headings set by formatting rather than styles were found by their look in "
                 "%s (%s): %s. Check them in the Style Map tab." % (
                     plural(len(files), "file"), ", ".join(files) if len(files) <= 3 else
                     ", ".join(files[:3]) + "..." , ", ".join(names)))
    unmapped = [u for u in rep.paragraph_styles if u.warning and u.source != "formatting"]
    for u in unmapped:
        if u.source == "fallback":
            w.append('Style "%s" (%s) is not in the style map; it will be set as '
                     'body text. Map it if it should look different.'
                     % (u.word, plural(u.count, "paragraph")))
        else:
            w.append('Style "%s" (%s) is not in the style map; it is treated as '
                     '%s (%s).' % (u.word, plural(u.count, "paragraph"), u.idml, u.source))
    for c in rep.conflicts:
        props = ", ".join(d["property"] for d in c["differences"])
        w.append('Style "%s" is defined differently in different files (%s). The style map '
                 'uses one definition for all files.' % (c["style"], props))
    for kind, entries in rep.items.items():
        if kind == "endnotes":
            continue
        info, left_out = ITEM_INFO.get(kind, ("", False))
        if left_out:
            w.append("%s: %s" % (_count(kind, len(entries)), info))
    for kind, entries in rep.items.items():
        info, left_out = ITEM_INFO.get(kind, ("", False))
        if kind != "endnotes" and not left_out:
            w.append("%s: %s" % (_count(kind, len(entries)), info))
    if rep.direct.get("hotspot_paragraphs"):
        n = rep.direct["hotspot_paragraphs"]
        w.append("%s by direct formatting instead of styles (listed below). %s follow the "
                 "book's styles." % (plural(n, "paragraph changes font, size or color",
                                            "paragraphs change font, size or color"),
                                     "It won't" if n == 1 else "They won't"))
    w.extend(rep.outline.notes)


def _count(kind, n):
    if n == 1 or kind.endswith(")"):
        return "%d %s" % (n, kind)
    return plural(n, kind, kind + "es" if kind.endswith("x") else None)


# ---- plain-text report ----

def render_text(rep):
    lines = []
    add = lines.append
    out = rep.outline

    add("PREFLIGHT")
    add("")
    if rep.warnings:
        add("Needs attention")
        for w in rep.warnings:
            add("  - " + w)
        add("")

    add("Files (in book order)")
    for i, f in enumerate(rep.files, 1):
        extra = ", " + plural(f.footnotes, "footnote") if f.footnotes else ""
        extra += ", " + plural(f.endnotes, "endnote") if f.endnotes else ""
        add("  %d. %s  [%s]  %s%s" % (i, f.name, f.first_heading or "no heading",
                                     plural(f.words, "word"), extra))
    add("")

    add("Book")
    add("  Title:    %s" % (_src(out.title, out.title_source) if out.title else "(not found)"))
    if out.subtitle:
        add("  Subtitle: %s" % out.subtitle)
    add("  Author:   %s" % (_src(out.author, out.author_source) if out.author else "(not found)"))
    if out.file_creator:
        add("            (the file's author property says %s, but that is usually whoever "
            "made the file)" % out.file_creator)
    if getattr(out, "details", None):
        names = {"year": "year", "holder": "holder", "publisher": "publisher",
                 "publisher_address": "place", "isbn_print": "ISBN (print)",
                 "isbn_ebook": "ISBN (ebook)", "printed_in": "printed in", "edition": "edition"}
        found = ["%s %s" % (names.get(k, k), v) for k, v in out.details.items() if k in names]
        if out.details.get("notices"):
            found.append(plural(len(out.details["notices"]), "notice"))
        add("  Copyright page (found; replaced by one made from Book Details): %s"
            % "; ".join(found))
    add("  Words:    %d in the text" % out.words)
    if rep.page:
        pg = rep.page
        if pg.get("width"):
            add("  Word page: %.2f x %.2f in%s" % (pg["width"], pg["height"],
                                                    ", %d pages in Word" % pg["word_pages"]
                                                    if pg.get("word_pages") else ""))
        if len(pg.get("sizes", [])) > 1:
            add("  (sections use %d different page sizes)" % len(pg["sizes"]))
    add("")

    add("Outline")
    for u in out.units:
        label = {"display": "display", "front": "front", "part": "PART", "chapter": "chapter",
                 "back": "back"}[u.kind]
        typ = "" if u.type in ("chapter", "part") or u.title.strip("()") == u.type \
            else " (%s)" % u.type
        notes = ", " + plural(u.note_refs, "note") if u.note_refs else ""
        add("  %-8s %s%s  -- %s%s; %s, by %s" % (label, u.title, typ, plural(u.words, "word"),
                                                  notes, u.file, u.detected_by))
        if u.subheads:
            add("           sections: " + "; ".join(u.subheads[:6])
                + (" ..." if len(u.subheads) > 6 else ""))
    present = out.present()
    missing = [x for x in ("title page", "copyright", "contents") if x not in present]
    if missing:
        add("  Not found (can be generated): " + ", ".join(missing))
    add("")

    add("Paragraph styles in use -> IDML style (role)")
    for u in rep.paragraph_styles:
        mark = "  !" if u.warning else "   "
        target = u.idml or "(not carried over)"
        add("%s %-28s %5d  -> %s (%s)%s" % (mark, u.word, u.count, target, _role(u),
                                            "" if u.source in ("default", "profile")
                                            else "  [%s]" % u.source))
    add("")
    if rep.character_styles:
        add("Character styles in use")
        for u in rep.character_styles:
            target = u.idml or "(none)"
            add("    %-28s %5d  -> %s%s" % (u.word, u.count, target,
                                            "" if u.source in ("default", "profile")
                                            else "  [%s]" % u.source))
        add("")

    d = rep.direct
    add("Direct formatting")
    add("  %s with direct italic/bold/small caps etc. (normal; carried over)"
        % plural(d.get("emphasis_runs", 0), "run"))
    add("  %s with direct alignment/indent/spacing" % plural(d.get("layout_paragraphs", 0),
                                                           "paragraph")
        + _by(d.get("layout_by_style")))
    add("  %s with direct font/size/color changes in %s"
        % (plural(d.get("font_runs", 0), "run"), plural(d.get("hotspot_paragraphs", 0), "paragraph"))
        + _by(d.get("font_by_style")))
    for h in d.get("hotspots", [])[:10]:
        add("    %s %s %s: %s -- \"%s\"" % (h["file"], _loc(h["where"], h["paragraph"]),
                                            h["style"], ", ".join(h["props"]), h["snippet"]))
    add("")

    f = rep.fonts
    add("Fonts")
    if f.get("body"):
        add("  Body: %s %g pt%s" % (f["body"], f["body_size"],
                                    " (Word template default?)" if f["template_default"] else ""))
    if f.get("headings"):
        add("  Headings: " + ", ".join(f["headings"]))
    if f.get("direct"):
        add("  Set directly in the text: " + ", ".join("%s (%d)" % kv for kv in f["direct"].items()))
    add("")

    heb, grk = rep.scripts.get("hebrew", {}), rep.scripts.get("greek", {})
    if heb.get("runs") or grk.get("runs"):
        add("Scripts")
        if heb.get("runs"):
            add("  Hebrew: %s, %s%s; fonts: %s" % (
                plural(heb["runs"], "run"), plural(heb["chars"], "letter"), ", with vowel points/accents" if heb["points"] else "",
                ", ".join(heb["fonts"])))
        if grk.get("runs"):
            add("  Greek: %s, %s%s; fonts: %s" % (
                plural(grk["runs"], "run"), plural(grk["chars"], "letter"), ", polytonic" if grk["polytonic"] else "",
                ", ".join(grk["fonts"])))
        add("")

    if rep.items:
        add("Items needing attention (first 5 of each)")
        for kind, entries in rep.items.items():
            add("  %s (%d)" % (kind, len(entries)))
            for e in entries[:5]:
                where = _loc(e["where"], e["paragraph"]) if e["paragraph"] is not None else ""
                text = (' "%s"' % e["snippet"]) if e["snippet"] else ""
                add("    %s %s%s%s" % (e["file"], where, text,
                                       " -- " + e["detail"] if e["detail"] else ""))
        add("")

    if rep.conflicts:
        add("Style conflicts between files")
        for c in rep.conflicts:
            add("  %s" % c["style"])
            for diff in c["differences"]:
                vals = "; ".join("%s: %s" % kv for kv in diff["values"].items())
                add("    %s -- %s" % (diff["property"], vals))
        add("")
    return "\n".join(lines).rstrip() + "\n"


def _src(value, source):
    return "%s  (from %s)" % (value, source) if source else value


def _role(u):
    if u.role == "heading":
        return "heading level %d" % u.level
    return u.role


def _by(counter):
    if not counter:
        return ""
    return "; most in " + ", ".join("%s (%d)" % kv for kv in list(counter.items())[:3])


def _loc(where, para):
    if para is None:
        return ""
    return ("para %d" % (para + 1)) if where == "body" else ("%s para %d" % (where, para + 1))
