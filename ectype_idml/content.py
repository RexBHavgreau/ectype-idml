"""Reading the text of a .docx for the exporter: paragraphs with their runs, formatting, notes,
tables, images and list numbers.

docx_reader summarizes a file for preflight and the outline; this module keeps the content. It
walks the body paragraphs in the same order as docx_reader (text boxes left out), so each
paragraph here carries the same index as docx_reader's, and the outline's units can be cut out
by index. Formatting is kept as features (italic, bold, small caps...); the exporter turns them
into IDML character styles, knowing the paragraph style each run sits in.
"""

import os
import posixpath
import re
import zipfile
from dataclasses import dataclass, field

from .docx_reader import (FALLBACK, NS, P, R, T, TXBX, W, _attr, _in, _local, _main_part,
                          _para_of, _rels, _xml)

# Word run properties kept as features (the rest is direct formatting the book's styles replace).
_TOGGLES = {"i": "italic", "b": "bold", "smallCaps": "smallcaps", "caps": "caps",
            "strike": "strike", "dstrike": "strike"}
EMU_PER_PT = 12700


@dataclass
class CRun:
    text: str = ""
    feats: dict = field(default_factory=dict)  # italic, bold, smallcaps, caps, strike: True/False;
                                               # underline: True; position: superscript/subscript
    char_style: str = None        # Word character style id (as set on the run)
    fonts: dict = field(default_factory=dict)  # rFonts set directly on the run
    footnote: list = None         # a note here: its paragraphs (list of CPara)
    image: object = None          # CImage
    rtl: bool = False


@dataclass
class CImage:
    name: str                     # file name in the .docx (media/image1.png -> image1.png)
    data: bytes = None
    width: float = None           # points, from the drawing's extent
    height: float = None
    floating: bool = False


@dataclass
class CTable:
    rows: list                    # rows of cells; a cell is a list of CPara, or None where a cell
                                  # to its left spans over it
    widths: list                  # points
    header_rows: int = 0
    spans: dict = field(default_factory=dict)   # (row, column) -> columns spanned


@dataclass
class CPara:
    index: int                    # docx_reader's paragraph index (body), or -1 in notes
    style_id: str = None
    runs: list = field(default_factory=list)
    align: str = None             # direct alignment: left, center, right, both
    bidi: bool = False
    page_break_before: bool = False
    label: str = None             # list or heading number as Word shows it ("1.", "•", "Chapter 2")
    list_format: str = None       # bullet, decimal, ...
    list_level: int = 0
    label_suffix: str = "\t"
    table: CTable = None          # this block is a table (runs empty)

    @property
    def text(self):
        return "".join(r.text for r in self.runs)

    @property
    def empty(self):
        return self.table is None and not self.label and \
            not any(r.text.strip() or r.footnote is not None or r.image is not None
                    for r in self.runs)


def _on(el):
    """A toggle property (<w:i/>, <w:i w:val="0"/>) as True/False."""
    return (_attr(el, "val") or "true").lower() not in ("0", "false", "off", "none")


def run_features(rpr):
    """Features set by an rPr element (a run's, or a style's)."""
    feats = {}
    if rpr is None:
        return feats
    for child in rpr:
        name = _local(child.tag)
        if name in _TOGGLES:
            feats[_TOGGLES[name]] = _on(child)
        elif name == "u":
            feats["underline"] = (_attr(child, "val") or "single") != "none"
        elif name == "vertAlign":
            v = _attr(child, "val")
            feats["position"] = v if v in ("superscript", "subscript") else None
    return feats


# ---- list numbering ----

_ROMAN = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"),
          (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
# Bullets Word writes in symbol fonts (private-use characters) -> Unicode.
_BULLETS = {"": "•", "": "▪", "": "❖", "": "➢",
            "": "✓", "o": "◦", "": "◦", "": "□"}


def _roman(n):
    out = ""
    for v, s in _ROMAN:
        while n >= v:
            out += s
            n -= v
    return out


def _letters(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(97 + r) + s
    return s


def format_number(n, fmt):
    if fmt in ("lowerRoman",):
        return _roman(n)
    if fmt == "upperRoman":
        return _roman(n).upper()
    if fmt == "lowerLetter":
        return _letters(n)
    if fmt == "upperLetter":
        return _letters(n).upper()
    if fmt == "decimalZero":
        return "%02d" % n
    if fmt == "none":
        return ""
    if fmt == "ordinal":
        suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return "%d%s" % (n, suffix)
    return str(n)


class Numbering:
    """Word's list numbering (numbering.xml): the label each numbered paragraph shows."""

    def __init__(self, root):
        self.abstract = {}        # abstractNumId -> {level: (start, fmt, text, suffix)}
        self.nums = {}            # numId -> (abstractNumId, {level: start override})
        self.counters = {}
        if root is None:
            return
        for an in root.findall(W + "abstractNum"):
            levels = {}
            for lvl in an.findall(W + "lvl"):
                il = int(_attr(lvl, "ilvl") or 0)
                start = _attr(lvl.find(W + "start"), "val")
                levels[il] = (int(start) if start and start.lstrip("-").isdigit() else 1,
                              _attr(lvl.find(W + "numFmt"), "val") or "decimal",
                              _attr(lvl.find(W + "lvlText"), "val") or "",
                              _attr(lvl.find(W + "suff"), "val") or "tab")
            self.abstract[_attr(an, "abstractNumId")] = levels
        for num in root.findall(W + "num"):
            overrides = {}
            for ov in num.findall(W + "lvlOverride"):
                so = _attr(ov.find(W + "startOverride"), "val")
                if so and so.isdigit():
                    overrides[int(_attr(ov, "ilvl") or 0)] = int(so)
            self.nums[_attr(num, "numId")] = (_attr(num.find(W + "abstractNumId"), "val"),
                                              overrides)

    def label(self, num_id, level):
        """(label, format, suffix) for the next paragraph of this list at this level, or None."""
        if num_id in (None, "0") or num_id not in self.nums:
            return None
        abs_id, overrides = self.nums[num_id]
        levels = self.abstract.get(abs_id, {})
        if level not in levels:
            return None
        # Lists sharing an abstract definition count together, unless one restarts.
        key = num_id if overrides else abs_id
        counts = self.counters.setdefault(key, {})
        start = overrides.get(level, levels[level][0])
        counts[level] = counts.get(level, start - 1) + 1
        for deeper in [k for k in counts if k > level]:
            del counts[deeper]
        _start, fmt, text, suffix = levels[level]
        if fmt == "bullet":
            label = _BULLETS.get(text, text) or "•"
        else:
            def sub(m):
                lv = int(m.group(1)) - 1
                lvl_fmt = levels.get(lv, (1, "decimal", "", ""))[1]
                n = counts.get(lv, levels.get(lv, (1,))[0])
                return format_number(n, lvl_fmt)
            label = re.sub(r"%(\d)", sub, text)
        return label, fmt, {"tab": "\t", "space": " "}.get(suffix, "")


# ---- reading ----

def _style_numbering(styles_root):
    """Paragraph style id -> (numId, level) for styles that carry numbering (numbered headings)."""
    out = {}
    for s in styles_root.findall(W + "style"):
        np_ = s.find("%spPr/%snumPr" % (W, W))
        if np_ is not None:
            out[_attr(s, "styleId")] = (_attr(np_.find(W + "numId"), "val"),
                                        int(_attr(np_.find(W + "ilvl"), "val") or 0))
    based = {_attr(s, "styleId"): _attr(s.find(W + "basedOn"), "val")
             for s in styles_root.findall(W + "style")}
    return out, based


class _Content:
    def __init__(self, z, main, docx):
        self.z, self.docx = z, docx
        self.rels = _rels(z, main)
        by_type = {}
        for rid, (typ, target) in self.rels.items():
            by_type.setdefault(typ, []).append(target)
        num_root = _xml(z, by_type["numbering"][0]) if by_type.get("numbering") else None
        self.numbering = Numbering(num_root)
        styles_root = _xml(z, by_type["styles"][0]) if by_type.get("styles") else None
        self.style_num, self.based = ({}, {}) if styles_root is None else \
            _style_numbering(styles_root)
        self.notes = {}
        for typ in ("footnotes", "endnotes"):
            for target in by_type.get(typ, []):
                root = _xml(z, target)
                if root is None:
                    continue
                note_rels = _rels(z, target)
                for note in root:
                    if _attr(note, "type") in ("separator", "continuationSeparator",
                                               "continuationNotice"):
                        continue
                    self.notes[(typ[:-1], _attr(note, "id"))] = (note, note_rels)
        self.pending_break = False

    def style_numbering(self, style_id):
        seen = set()
        while style_id and style_id not in seen:
            seen.add(style_id)
            if style_id in self.style_num:
                return self.style_num[style_id]
            style_id = self.based.get(style_id)
        return None

    def body(self, body_el):
        paras = [p for p in body_el.iter(P) if not _in(p, TXBX)]
        index = {id(p): i for i, p in enumerate(paras)}
        out, done_tables = [], set()
        for i, p in enumerate(paras):
            tbl = None
            for anc in p.iterancestors(W + "tbl"):
                tbl = anc            # the outermost table, after the loop
            if tbl is not None:
                if id(tbl) not in done_tables:
                    done_tables.add(id(tbl))
                    out.append(CPara(i, table=self.table(tbl, index)))
                continue
            out.append(self.paragraph(p, i, self.rels))
        return out

    def table(self, tbl, index):
        grid = [int(_attr(g, "w") or 0) / 20 for g in tbl.findall("%stblGrid/%sgridCol" % (W, W))]
        rows, spans, header = [], {}, 0
        for r, tr in enumerate(tbl.findall(W + "tr")):
            if tr.find("%strPr/%stblHeader" % (W, W)) is not None and header == r:
                header += 1
            row = []
            for tc in tr.findall(W + "tc"):
                span = _attr(tc.find("%stcPr/%sgridSpan" % (W, W)), "val")
                span = int(span) if span and span.isdigit() else 1
                cell = [self.paragraph(p, index.get(id(p), -1), self.rels)
                        for p in tc.iter(P) if not _in(p, TXBX)]
                if span > 1:
                    spans[(r, len(row))] = span
                row.append(cell)
                row.extend([None] * (span - 1))
            rows.append(row)
        ncols = max([len(r) for r in rows] + [len(grid), 1])
        for row in rows:
            row.extend([[]] * (ncols - len(row)))
        if len(grid) < ncols or not all(grid):
            grid = [None] * ncols
        return CTable(rows, grid, header, spans)

    def paragraph(self, p_el, index, rels, in_note=False):
        ppr = p_el.find(W + "pPr")
        para = CPara(index, page_break_before=self.pending_break)
        self.pending_break = False
        num = None
        if ppr is not None:
            para.style_id = _attr(ppr.find(W + "pStyle"), "val")
            jc = _attr(ppr.find(W + "jc"), "val")
            para.align = {"start": "left", "end": "right", "distribute": "both"}.get(jc, jc)
            bidi = ppr.find(W + "bidi")
            para.bidi = bidi is not None and _on(bidi)
            pbb = ppr.find(W + "pageBreakBefore")
            if pbb is not None and _on(pbb):
                para.page_break_before = True
            np_ = ppr.find(W + "numPr")
            if np_ is not None:
                num = (_attr(np_.find(W + "numId"), "val"),
                       int(_attr(np_.find(W + "ilvl"), "val") or 0))
        if num is None:
            num = self.style_numbering(para.style_id or self.docx.default_style.get("paragraph"))
        if num and not in_note:
            got = self.numbering.label(*num)
            if got:
                para.label, para.list_format, para.label_suffix = got
                para.list_level = num[1]
        for r_el in p_el.iter(R):
            if _para_of(r_el) is not p_el or _in(r_el, W + "del") or _in(r_el, W + "moveFrom") \
                    or _in(r_el, FALLBACK):
                continue
            self.run(r_el, para, rels, in_note)
        return para

    def run(self, r_el, para, rels, in_note):
        rpr = r_el.find(W + "rPr")
        feats = run_features(rpr)
        char_style = _attr(rpr.find(W + "rStyle"), "val") if rpr is not None else None
        fonts = {}
        rtl = False
        if rpr is not None:
            rf = rpr.find(W + "rFonts")
            if rf is not None:
                fonts = {_local(k): v for k, v in rf.attrib.items() if _local(k) != "hint"}
            rtl_el = rpr.find(W + "rtl")
            rtl = rtl_el is not None and _on(rtl_el)
        text = []

        def flush():
            if text:
                para.runs.append(CRun("".join(text), dict(feats), char_style, fonts, rtl=rtl))
                del text[:]

        for el in r_el:
            tag = el.tag
            if not isinstance(tag, str):
                continue
            name = _local(tag)
            if tag == T:
                text.append(el.text or "")
            elif name in ("tab", "ptab"):
                text.append("\t")
            elif name == "br":
                kind = _attr(el, "type")
                if kind == "page":
                    flush()
                    self.pending_break = True
                elif kind != "column":
                    text.append("\n")
            elif name == "cr":
                text.append("\n")
            elif name == "noBreakHyphen":
                text.append("‑")
            elif name == "softHyphen":
                text.append("­")
            elif name == "sym":
                ch = _attr(el, "char") or ""
                try:
                    c = chr(int(ch, 16))
                except ValueError:
                    c = ""
                if 0xF000 <= ord(c or " ") <= 0xF0FF:
                    c = chr(ord(c) - 0xF000)   # symbol-font characters
                text.append(c)
            elif name in ("footnoteReference", "endnoteReference") and not in_note:
                flush()
                note = self.notes.get((name[:-9], _attr(el, "id")))
                paras = []
                if note is not None:
                    note_el, note_rels = note
                    paras = [self.paragraph(p, -1, note_rels, in_note=True)
                             for p in note_el.iter(P) if not _in(p, TXBX)]
                    _strip_note_start(paras)
                para.runs.append(CRun("", {}, None, footnote=paras))
            elif name == "drawing":
                flush()
                img = self.image(el, rels)
                if img is not None:
                    para.runs.append(CRun("", {}, None, image=img))
        flush()

    def image(self, drawing, rels):
        for holder in drawing:
            kind = _local(holder.tag)
            if kind not in ("inline", "anchor"):
                continue
            blip = holder.find(".//{%s}blip" % NS["a"])
            if blip is None:
                return None          # a shape or text box: listed by preflight
            rid = blip.get("{%s}embed" % NS["r"])
            target = rels.get(rid, (None, None))[1]
            extent = holder.find("{%s}extent" % NS["wp"])
            img = CImage(posixpath.basename(target or "image"), floating=(kind == "anchor"))
            if extent is not None:
                try:
                    img.width = int(extent.get("cx")) / EMU_PER_PT
                    img.height = int(extent.get("cy")) / EMU_PER_PT
                except (TypeError, ValueError):
                    pass
            if target:
                try:
                    img.data = self.z.read(target)
                except KeyError:
                    img.data = None
            return img
        return None


def _strip_note_start(paras):
    """Word starts a note with its own number (footnoteRef) and a space; the IDML footnote
    writes the number itself."""
    if not paras:
        return
    runs = paras[0].runs
    while runs and not runs[0].text.strip() and runs[0].footnote is None and runs[0].image is None:
        runs.pop(0)
    if runs and runs[0].text:
        runs[0].text = runs[0].text.lstrip(" \t")


def read_content(docx):
    """Body paragraphs of a DocxFile (from docx_reader.read_docx), as CPara in document order;
    tables come as one CPara each (index of their first paragraph)."""
    with zipfile.ZipFile(docx.path) as z:
        main = _main_part(z)
        root = _xml(z, main)
        c = _Content(z, main, docx)
        return c.body(root.find(W + "body"))


def image_ext(data):
    """File extension for image data the IDML can link (JPEG, PNG), or None."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    return None


def save_image(img, folder, prefix):
    """Write an image's data to folder; returns the path, or None for a format the IDML can't
    link (EMF, WMF, TIFF, GIF...)."""
    if not img.data or not image_ext(img.data):
        return None
    stem = os.path.splitext(img.name)[0]
    path = os.path.join(folder, "%s-%s%s" % (prefix, stem, image_ext(img.data)))
    with open(path, "wb") as f:
        f.write(img.data)
    return path
