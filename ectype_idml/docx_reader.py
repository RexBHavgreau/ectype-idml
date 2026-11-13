"""Reading a Word .docx by parsing its XML directly (lxml).

The reader collects what preflight and the outline need: styles, body paragraphs with their
style, text and direct formatting, sections, notes, fields, scripts (Hebrew, Greek) and the
items version 1 does not carry over. It does not interpret the content beyond that.
"""

import posixpath
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field

from lxml import etree

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "v": "urn:schemas-microsoft-com:vml",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
W = "{%s}" % NS["w"]
P, R, T = W + "p", W + "r", W + "t"
TXBX = W + "txbxContent"
FALLBACK = "{%s}Fallback" % NS["mc"]

# Run properties that change the look of the type rather than mark emphasis. Runs carrying
# these as direct formatting are "hotspots": they will not follow the book's styles.
FONT_PROPS = {"rFonts", "sz", "szCs", "color", "highlight", "spacing", "w", "kern",
              "position", "shd", "fitText"}
EMPHASIS_PROPS = {"b", "bCs", "i", "iCs", "u", "smallCaps", "caps", "vertAlign", "strike",
                  "dstrike"}
# Paragraph properties that are layout rather than structure.
PARA_LAYOUT_PROPS = {"jc", "ind", "spacing", "keepNext", "keepLines", "pageBreakBefore",
                     "widowControl", "tabs", "shd", "pBdr", "contextualSpacing", "textAlignment"}

TRACKED = {"ins": "insertion", "del": "deletion", "moveFrom": "move", "moveTo": "move",
           "rPrChange": "formatting change", "pPrChange": "formatting change",
           "sectPrChange": "formatting change", "tblPrChange": "formatting change",
           "trPrChange": "formatting change", "tcPrChange": "formatting change"}

# Fields that are understood: replaced by the layout (page numbers, running heads, contents),
# stripped (XE) or kept as their displayed text (cross-references, links).
KNOWN_FIELDS = {"PAGE", "NUMPAGES", "SECTIONPAGES", "STYLEREF", "TOC", "PAGEREF", "XE",
                "HYPERLINK", "REF", "NOTEREF", "TC"}


def is_hebrew(ch):
    o = ord(ch)
    return 0x0590 <= o <= 0x05FF or 0xFB1D <= o <= 0xFB4F


def is_greek(ch):
    o = ord(ch)
    return 0x0370 <= o <= 0x03FF or 0x1F00 <= o <= 0x1FFF


def is_polytonic(ch):
    return 0x1F00 <= ord(ch) <= 0x1FFF


def is_hebrew_mark(ch):
    """Vowel points and cantillation marks."""
    return 0x0591 <= ord(ch) <= 0x05C7


@dataclass
class Style:
    id: str
    name: str
    type: str                    # paragraph, character, table, numbering
    based_on: str = None         # style id
    linked: str = None           # id of the linked paragraph/character style
    custom: bool = False
    is_default: bool = False
    outline_level: int = None    # 0 = Word's level 1
    props: dict = field(default_factory=dict)   # local name -> "attr=value ..."
    fonts: dict = field(default_factory=dict)   # ascii/hAnsi/cs/... -> font (theme names kept)
    numbered: bool = False


@dataclass
class Section:
    index: int
    break_type: str = "nextPage"  # how this section starts: nextPage, oddPage, evenPage, continuous
    page_width: float = None      # inches
    page_height: float = None
    margins: dict = field(default_factory=dict)   # top, bottom, left, right, gutter, header, footer
    title_page: bool = False      # different first page
    columns: int = 1
    header_ids: list = field(default_factory=list)


@dataclass
class Paragraph:
    index: int
    style_id: str
    text: str
    where: str = "body"           # body, footnote, endnote
    in_table: bool = False
    outline_level: int = None     # direct outline level, if set on the paragraph
    section: int = 0
    ends_section: bool = False
    numbered: bool = False
    footnotes: int = 0
    endnotes: int = 0
    char_styles: list = field(default_factory=list)
    direct_emphasis: int = 0      # runs with direct italic/bold/...
    direct_font: list = field(default_factory=list)  # props of runs with direct font/size/color
    direct_layout: list = field(default_factory=list)
    run_count: int = 0
    in_toc_field: bool = False
    # How the paragraph looks, for finding headings set by direct formatting: the look of most
    # of its characters (size in points, bold, italic, caps "caps"/"smallcaps"/None) and its
    # alignment, space before (points) and whether it starts a page.
    look: tuple = None            # (size, bold, italic, caps)
    align: str = None
    space_before: float = 0
    page_break_before: bool = False
    looks: Counter = field(default_factory=Counter)   # look -> characters, while reading

    @property
    def snippet(self):
        s = " ".join(self.text.split())
        return s if len(s) <= 60 else s[:57] + "..."


@dataclass
class Item:
    """Something in the manuscript that needs the user's attention."""
    kind: str
    detail: str = ""
    where: str = "body"
    paragraph: int = None
    snippet: str = ""


@dataclass
class Field:
    code: str                     # first word, upper case
    instruction: str
    where: str
    paragraph: int
    result: str = ""


@dataclass
class ScriptUse:
    runs: int = 0
    chars: int = 0
    fonts: Counter = field(default_factory=Counter)
    polytonic: bool = False       # Greek
    points: bool = False          # Hebrew vowel points or cantillation
    rtl_marked: int = 0           # Hebrew runs marked right-to-left in Word
    samples: list = field(default_factory=list)


@dataclass
class DocxFile:
    path: str
    styles: dict = field(default_factory=dict)      # id -> Style
    default_style: dict = field(default_factory=dict)  # type -> style id
    doc_defaults: dict = field(default_factory=dict)   # fonts, size (half-points), props
    theme_fonts: dict = field(default_factory=dict)    # major/minor -> latin font
    paragraphs: list = field(default_factory=list)     # body paragraphs, document order
    note_paragraphs: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    footnote_count: int = 0
    endnote_count: int = 0
    fields: list = field(default_factory=list)
    items: list = field(default_factory=list)
    images: int = 0
    tables: int = 0
    nested_tables: int = 0
    run_fonts: Counter = field(default_factory=Counter)  # fonts set as direct formatting
    scripts: dict = field(default_factory=lambda: {"hebrew": ScriptUse(), "greek": ScriptUse()})
    styleref: list = field(default_factory=list)  # style names or levels used by STYLEREF in headers
    core: dict = field(default_factory=dict)      # title, creator
    app: dict = field(default_factory=dict)       # pages, words

    @property
    def name(self):
        return posixpath.basename(self.path.replace("\\", "/"))

    def style_name(self, style_id):
        st = self.styles.get(style_id)
        return st.name if st else style_id

    def para_style(self, p):
        """Style id of a paragraph, falling back to the default paragraph style."""
        if p.style_id and p.style_id in self.styles:
            return p.style_id
        return self.default_style.get("paragraph")

    def style_chain(self, style_id):
        seen = []
        while style_id and style_id in self.styles and style_id not in seen:
            seen.append(style_id)
            style_id = self.styles[style_id].based_on
        return seen

    def style_outline_level(self, style_id):
        for sid in self.style_chain(style_id):
            lvl = self.styles[sid].outline_level
            if lvl is not None:
                return lvl
        return None

    def resolve_font(self, style_id, slot="ascii"):
        """The font a style ends up with for Latin text, after inheritance and theme."""
        fonts = None
        for sid in self.style_chain(style_id):
            f = self.styles[sid].fonts
            if slot in f or slot + "Theme" in f:
                fonts = f
                break
        if fonts is None:
            fonts = self.doc_defaults.get("fonts", {})
        if slot + "Theme" in fonts:
            theme = fonts[slot + "Theme"]
            return self.theme_fonts.get("major" if theme.startswith("major") else "minor")
        return fonts.get(slot)

    def resolve_size(self, style_id):
        """Font size in points."""
        for sid in self.style_chain(style_id):
            sz = self.styles[sid].props.get("sz")
            if sz:
                return int(sz.split("=")[1]) / 2
        sz = self.doc_defaults.get("size")
        return int(sz) / 2 if sz else 10.0


class DocxError(Exception):
    """A file that can't be read as a Word document. The message is shown to the user."""


def _attr(el, name):
    return el.get(W + name) if el is not None else None


def _local(tag):
    return etree.QName(tag).localname if isinstance(tag, str) else ""


def _props(el):
    """Summarize a pPr/rPr element as {local name: 'attr=value ...'} (for comparing styles)."""
    out = {}
    if el is None:
        return out
    for child in el:
        name = _local(child.tag)
        if not name or name in ("rPr", "sectPr", "pPrChange", "rPrChange", "rStyle", "pStyle"):
            continue
        attrs = " ".join("%s=%s" % (_local(k), v) for k, v in sorted(child.attrib.items())
                         if "rsid" not in k)
        out[name] = attrs or "on"
    return out


def _val(props):
    """The w:val of a summarized property ("val=center" -> "center"; "on" -> "on")."""
    if props is None:
        return None
    return _prop_val(props, "val") or ("on" if props == "on" else None)


def _prop_val(props, key):
    for part in (props or "").split():
        k, _, v = part.partition("=")
        if k == key:
            return v
    return None


def _on(props):
    return props is not None and _val(props) not in ("0", "false", "off", "none")


def _look(props, size, bold=False, italic=False, caps=None):
    """(size, bold, italic, caps) after the run properties props (summarized by _props)."""
    if "sz" in props and (_val(props["sz"]) or "").isdigit():
        size = int(_val(props["sz"])) / 2
    if "b" in props:
        bold = _on(props["b"])
    if "i" in props:
        italic = _on(props["i"])
    if "caps" in props and _on(props["caps"]):
        caps = "caps"
    elif "smallCaps" in props and _on(props["smallCaps"]):
        caps = "smallcaps"
    return (round(size * 2) / 2, bold, italic, caps)


def _fonts(rpr):
    rf = rpr.find(W + "rFonts") if rpr is not None else None
    if rf is None:
        return {}
    return {_local(k): v for k, v in rf.attrib.items() if _local(k) != "hint"}


def _twips_in(v):
    try:
        return round(int(v) / 1440, 3)
    except (TypeError, ValueError):
        return None


def _para_of(el):
    for anc in el.iterancestors(P):
        return anc
    return None


def _in(el, tag):
    for _ in el.iterancestors(tag):
        return True
    return False


def _xml(z, name):
    try:
        data = z.read(name)
    except KeyError:
        return None
    return etree.fromstring(data, etree.XMLParser(resolve_entities=False, huge_tree=True))


def _rels(z, part):
    """Relationships of a part: {id: (type suffix, target path)}."""
    d, b = posixpath.split(part)
    root = _xml(z, posixpath.join(d, "_rels", b + ".rels"))
    out = {}
    if root is None:
        return out
    for rel in root.findall("{%s}Relationship" % NS["pr"]):
        target = rel.get("Target", "")
        if rel.get("TargetMode") != "External":
            target = posixpath.normpath(posixpath.join(d, target)) if not target.startswith("/") \
                else target.lstrip("/")
        out[rel.get("Id")] = (rel.get("Type", "").rsplit("/", 1)[-1], target)
    return out


def _main_part(z):
    for _id, (typ, target) in _rels(z, "").items():
        if typ == "officeDocument":
            return target
    return "word/document.xml"


def read_docx(path):
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise DocxError("%s can't be opened as a Word document (.docx): %s"
                        % (posixpath.basename(str(path)), e)) from None
    with z:
        doc = DocxFile(path=str(path))
        main = _main_part(z)
        root = _xml(z, main)
        if root is None:
            raise DocxError("%s has no document text. Save it again from Word as .docx."
                            % doc.name)
        rels = _rels(z, main)
        by_type = {}
        for rid, (typ, target) in rels.items():
            by_type.setdefault(typ, []).append(target)
        _read_theme(z, by_type, doc)
        _read_styles(z, by_type, doc)
        _read_props(z, doc)
        body = root.find(W + "body")
        if body is None:
            raise DocxError("%s has no document body. Save it again from Word as .docx." % doc.name)
        _Scanner(doc, "body").scan(body)
        _read_sections(body, doc)
        for typ, where in (("footnotes", "footnote"), ("endnotes", "endnote")):
            for target in by_type.get(typ, []):
                notes = _xml(z, target)
                if notes is None:
                    continue
                count = 0
                for note in notes:
                    if _attr(note, "type") in ("separator", "continuationSeparator",
                                               "continuationNotice"):
                        continue
                    count += 1
                    _Scanner(doc, where, note_mode=True).scan(note)
                if where == "footnote":
                    doc.footnote_count = count
                else:
                    doc.endnote_count = count
        for rid in {h for s in doc.sections for h in s.header_ids}:
            if rid in rels:
                _read_header(z, rels[rid][1], doc)
        doc.images = sum(1 for _ in body.iter("{%s}pic" % NS["pic"])
                         if not _in(_, FALLBACK))
    return doc


def _read_theme(z, by_type, doc):
    for target in by_type.get("theme", []):
        theme = _xml(z, target)
        if theme is None:
            continue
        a = "{%s}" % NS["a"]
        for kind in ("major", "minor"):
            latin = theme.find(".//%s%sFont/%slatin" % (a, kind, a))
            if latin is not None and latin.get("typeface"):
                doc.theme_fonts[kind] = latin.get("typeface")


def _read_styles(z, by_type, doc):
    for target in by_type.get("styles", []):
        root = _xml(z, target)
        if root is None:
            continue
        dd = root.find(W + "docDefaults")
        if dd is not None:
            rpr = dd.find("%srPrDefault/%srPr" % (W, W))
            doc.doc_defaults["fonts"] = _fonts(rpr)
            sz = rpr.find(W + "sz") if rpr is not None else None
            doc.doc_defaults["size"] = _attr(sz, "val")
            props = _props(rpr)
            props.update(_props(dd.find("%spPrDefault/%spPr" % (W, W))))
            doc.doc_defaults["props"] = props
        for s in root.findall(W + "style"):
            sid = _attr(s, "styleId")
            name_el = s.find(W + "name")
            st = Style(
                id=sid,
                name=_attr(name_el, "val") or sid,
                type=_attr(s, "type") or "paragraph",
                based_on=_attr(s.find(W + "basedOn"), "val"),
                linked=_attr(s.find(W + "link"), "val"),
                custom=_attr(s, "customStyle") in ("1", "true"),
                is_default=_attr(s, "default") in ("1", "true"),
            )
            ppr, rpr = s.find(W + "pPr"), s.find(W + "rPr")
            if ppr is not None:
                ol = ppr.find(W + "outlineLvl")
                if ol is not None and (_attr(ol, "val") or "").isdigit() and int(_attr(ol, "val")) < 9:
                    st.outline_level = int(_attr(ol, "val"))
                st.numbered = ppr.find(W + "numPr") is not None
            st.props = _props(ppr)
            st.props.update(_props(rpr))
            st.fonts = _fonts(rpr)
            doc.styles[sid] = st
            if st.is_default:
                doc.default_style[st.type] = sid


def _read_props(z, doc):
    core = _xml(z, "docProps/core.xml")
    if core is not None:
        for key, tag in (("title", "{%s}title" % NS["dc"]), ("creator", "{%s}creator" % NS["dc"])):
            el = core.find(tag)
            if el is not None and (el.text or "").strip():
                doc.core[key] = el.text.strip()
    app = _xml(z, "docProps/app.xml")
    if app is not None:
        for key, tag in (("pages", "Pages"), ("words", "Words")):
            el = app.find("{%s}%s" % (NS["ep"], tag))
            if el is not None and (el.text or "").strip().isdigit():
                doc.app[key] = int(el.text.strip())


def _read_sections(body, doc):
    sect_els = [p.find("%spPr/%ssectPr" % (W, W)) for p in body.iter(P)]
    sect_els = [s for s in sect_els if s is not None and not _in(s, TXBX)]
    final = body.find(W + "sectPr")
    if final is not None:
        sect_els.append(final)
    for i, s in enumerate(sect_els):
        sec = Section(index=i)
        sec.break_type = _attr(s.find(W + "type"), "val") or "nextPage"
        pg = s.find(W + "pgSz")
        if pg is not None:
            sec.page_width, sec.page_height = _twips_in(_attr(pg, "w")), _twips_in(_attr(pg, "h"))
        mar = s.find(W + "pgMar")
        if mar is not None:
            for k in ("top", "bottom", "left", "right", "gutter", "header", "footer"):
                v = _twips_in(_attr(mar, k))
                if v is not None:
                    sec.margins[k] = abs(v)
        tp = s.find(W + "titlePg")
        sec.title_page = tp is not None and _attr(tp, "val") not in ("0", "false")
        cols = s.find(W + "cols")
        num = _attr(cols, "num")
        sec.columns = int(num) if num and num.isdigit() else 1
        sec.header_ids = [h.get("{%s}id" % NS["r"]) for h in s.findall(W + "headerReference")]
        doc.sections.append(sec)
    if not doc.sections:
        doc.sections.append(Section(index=0))


def _read_header(z, target, doc):
    root = _xml(z, target)
    if root is None:
        return
    codes = ["".join(t.text or "" for t in root.iter(W + "instrText"))]
    codes += [_attr(f, "instr") or "" for f in root.iter(W + "fldSimple")]
    for code in codes:
        for m in re.finditer(r'STYLEREF\s+(?:"([^"]+)"|(\S+))', code, re.I):
            ref = m.group(1) or m.group(2)
            if ref not in doc.styleref:
                doc.styleref.append(ref)


class _Scanner:
    """Walks the paragraphs of the body (or of one note) in document order."""

    def __init__(self, doc, where, note_mode=False):
        self.doc, self.where, self.note_mode = doc, where, note_mode
        self.stack = []        # open complex fields: [instruction parts, separated, paragraph]
        self.section = 0
        self.page_break = False  # the last paragraph ended with a page break
        self._looks = {}         # paragraph style id -> its look

    def item(self, kind, detail="", para=None):
        self.doc.items.append(Item(kind, detail, self.where,
                                   para.index if para else None, para.snippet if para else ""))

    def scan(self, container):
        doc = self.doc
        target = doc.note_paragraphs if self.note_mode else doc.paragraphs
        if not self.note_mode:
            for tbl in container.iter(W + "tbl"):
                if _in(tbl, TXBX):
                    continue
                if _in(tbl, W + "tbl"):
                    doc.nested_tables += 1
                else:
                    doc.tables += 1
        for p_el in container.iter(P):
            if _in(p_el, TXBX):
                continue
            para = self.paragraph(p_el, len(target))
            target.append(para)
        if self.stack and not self.note_mode:
            self.item("unclosed field", "a field code that never ends (Word may repair it)")

    def paragraph(self, p_el, index):
        doc = self.doc
        ppr = p_el.find(W + "pPr")
        pstyle = _attr(ppr.find(W + "pStyle"), "val") if ppr is not None else None
        para = Paragraph(index=index, style_id=pstyle, text="", where=self.where,
                         in_table=_in(p_el, W + "tc"), section=self.section,
                         in_toc_field=self.in_toc())
        if ppr is not None:
            ol = ppr.find(W + "outlineLvl")
            if ol is not None and (_attr(ol, "val") or "").isdigit() and int(_attr(ol, "val")) < 9:
                para.outline_level = int(_attr(ol, "val"))
            para.numbered = ppr.find(W + "numPr") is not None
            para.direct_layout = sorted(set(_props(ppr)) & PARA_LAYOUT_PROPS)
            if ppr.find(W + "sectPr") is not None and not self.note_mode:
                para.ends_section = True
                self.section += 1
        if not para.numbered:
            sid = doc.para_style(para)
            para.numbered = any(doc.styles[s].numbered for s in doc.style_chain(sid))
        self._para_layout(para, ppr)

        text = []
        for el in p_el.iter():
            if _para_of(el) is not p_el:
                continue
            tag = el.tag
            if not isinstance(tag, str):
                continue
            name = _local(tag)
            if tag == T:
                if _in(el, W + "del") or _in(el, W + "moveFrom"):
                    continue
                text.append(el.text or "")
                for f in self.stack:
                    if f[1]:
                        f[3].append(el.text or "")
            elif tag in (W + "tab", W + "ptab") and _local(el.getparent().tag) == "r":
                text.append("\t")
            elif tag in (W + "br", W + "cr") and _local(el.getparent().tag) == "r":
                text.append("\n")
            elif tag == R:
                self.run(el, para)
            elif tag == W + "fldChar":
                self.fld_char(el, para)
            elif tag == W + "instrText" and self.stack:
                self.stack[-1][0].append(el.text or "")
            elif tag == W + "fldSimple":
                self.add_field(_attr(el, "instr") or "", para,
                               "".join(t.text or "" for t in el.iter(T)))
            elif tag == W + "footnoteReference":
                para.footnotes += 1
            elif tag == W + "endnoteReference":
                para.endnotes += 1
            elif tag == W + "commentReference":
                self.item("comment", "Word comment (comments are not carried over)", para)
            elif name in TRACKED and tag.startswith(W):
                self.item("tracked change", TRACKED[name], para)
            elif tag == "{%s}oMath" % NS["m"]:
                self.item("equation", "Word equation", para)
            elif tag == W + "object":
                self.item("embedded object", "embedded (OLE) object", para)
            elif tag == W + "altChunk":
                self.item("imported content", "content imported from another file (altChunk)", para)
            elif tag in ("{%s}anchor" % NS["wp"], "{%s}inline" % NS["wp"]):
                self.drawing(el, para)
            elif tag == W + "pict" and not _in(el, FALLBACK):
                kind = "text box" if el.find(".//" + TXBX) is not None else "floating shape"
                self.item(kind, "older Word drawing (VML)", para)
        para.text = "".join(text)
        if para.looks:
            para.look = para.looks.most_common(1)[0][0]
        para.looks = Counter()
        if self.page_break and self.where == "body":
            para.page_break_before = True
        self.page_break = any(br.get(W + "type") == "page" for br in p_el.iter(W + "br")
                              if _para_of(br) is p_el)
        for it in reversed(self.doc.items):
            if it.paragraph != para.index or it.where != self.where or it.snippet:
                break
            it.snippet = para.snippet
        para.in_toc_field = para.in_toc_field or self.in_toc()
        return para

    def _para_layout(self, para, ppr):
        """Alignment, space before and a page break before, direct or from the style."""
        doc = self.doc
        chain = doc.style_chain(doc.para_style(para))
        own = _props(ppr)

        def get(key):
            if key in own:
                return own[key]
            for sid in chain:
                if key in doc.styles[sid].props:
                    return doc.styles[sid].props[key]
            return None
        para.align = _val(get("jc")) or "left"
        before = _prop_val(get("spacing"), "before")
        para.space_before = int(before) / 20 if before and before.lstrip("-").isdigit() else 0
        pbb = get("pageBreakBefore")
        para.page_break_before = pbb is not None and _val(pbb) not in ("0", "false", "off")

    def _style_look(self, sid):
        """(size, bold, italic, caps) a paragraph style gives its text."""
        cache = self._looks
        if sid not in cache:
            doc = self.doc
            props = dict(doc.doc_defaults.get("props") or {})
            for s in reversed(doc.style_chain(sid)):
                props.update(doc.styles[s].props)
            cache[sid] = _look(props, doc.resolve_size(sid))
        return cache[sid]

    def in_toc(self):
        return any(f[0] and "".join(f[0]).strip().upper().startswith("TOC") for f in self.stack)

    def run(self, r_el, para):
        doc = self.doc
        if _in(r_el, W + "del") or _in(r_el, W + "moveFrom"):
            return
        para.run_count += 1
        rpr = r_el.find(W + "rPr")
        props = _props(rpr)
        rstyle = _attr(rpr.find(W + "rStyle"), "val") if rpr is not None else None
        if rstyle:
            para.char_styles.append(rstyle)
        if set(props) & EMPHASIS_PROPS:
            para.direct_emphasis += 1
        font_props = sorted(set(props) & FONT_PROPS)
        run_text = "".join(t.text or "" for t in r_el.findall(T))
        fonts = _fonts(rpr)
        # A font set only for the script slot (cs) of a Hebrew run is not a hotspot: Word keeps
        # right-to-left fonts there.
        if font_props == ["rFonts"] and set(fonts) <= {"cs", "hint"}:
            font_props = []
        if font_props and run_text.strip():
            para.direct_font.append(font_props)
        for slot in ("ascii", "hAnsi"):
            if slot in fonts:
                doc.run_fonts[fonts[slot]] += 1
                break
        if run_text.strip() and self.where == "body":
            size, bold, italic, caps = self._style_look(self.doc.para_style(para))
            if rstyle and rstyle in self.doc.styles:
                cprops = {}
                for s in reversed(self.doc.style_chain(rstyle)):
                    cprops.update(self.doc.styles[s].props)
                size, bold, italic, caps = _look(cprops, size, bold, italic, caps)
            look = _look(props, size, bold, italic, caps)
            para.looks[look] += len(run_text.strip())
        if run_text:
            self.scripts(run_text, rpr, fonts, para)

    def scripts(self, text, rpr, fonts, para):
        heb = sum(1 for c in text if is_hebrew(c))
        grk = sum(1 for c in text if is_greek(c))
        for key, n in (("hebrew", heb), ("greek", grk)):
            if not n:
                continue
            use = self.doc.scripts[key]
            use.runs += 1
            use.chars += n
            font = fonts.get("cs" if key == "hebrew" else "ascii") or fonts.get("hAnsi")
            use.fonts[font or "(style font)"] += 1
            if key == "greek" and any(is_polytonic(c) for c in text):
                use.polytonic = True
            if key == "hebrew":
                if any(is_hebrew_mark(c) for c in text):
                    use.points = True
                if rpr is not None and rpr.find(W + "rtl") is not None:
                    use.rtl_marked += 1
            if len(use.samples) < 3:
                use.samples.append((self.where, para.index, text.strip()[:30]))

    def drawing(self, el, para):
        if _in(el, FALLBACK):
            return
        graphic = el.find(".//{%s}graphicData" % NS["a"])
        uri = graphic.get("uri", "") if graphic is not None else ""
        floating = _local(el.tag) == "anchor"
        if uri.endswith("/picture"):
            if floating:
                self.item("floating image", "will be placed inline at its anchor", para)
        elif el.find(".//" + TXBX) is not None:
            self.item("text box", "floating" if floating else "inline", para)
        elif uri.endswith("/chart"):
            self.item("chart", "Word chart", para)
        elif uri.endswith("/diagram"):
            self.item("SmartArt", "SmartArt diagram", para)
        else:
            self.item("floating shape" if floating else "shape", "drawing shape", para)

    def fld_char(self, el, para):
        kind = _attr(el, "fldCharType")
        if kind == "begin":
            self.stack.append([[], False, para, []])
        elif kind == "separate" and self.stack:
            self.stack[-1][1] = True
        elif kind == "end" and self.stack:
            instr, _sep, start, result = self.stack.pop()
            self.add_field("".join(instr), start, "".join(result))

    def add_field(self, instruction, para, result):
        instruction = " ".join(instruction.split())
        code = instruction.split(" ", 1)[0].upper() if instruction else ""
        self.doc.fields.append(Field(code, instruction, self.where, para.index, result))
        if code == "TOC":
            para.in_toc_field = True
        if code == "XE":
            self.item("index entry (XE)", instruction[2:].strip(), para)
        elif code and code not in KNOWN_FIELDS:
            self.item("field", "%s (its displayed text is kept)" % instruction[:60], para)
