"""The exporter core: Word manuscript -> IDML model -> export folder."""

import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from docx_builder import (NUMBERING, endnote_ref, footnote_ref, image, make_docx, numbered, para,
                          run, run_tests, table)
from ectype_idml.content import Numbering, read_content
from ectype_idml.docx_reader import read_docx
from ectype_idml import layout
from ectype_idml.layout import _half
from ectype_idml.export import ExportError, Exporter, export, segments
from ectype_idml.profile import default_profile

TMP = tempfile.mkdtemp()
SAMPLE = os.path.join(ROOT, "tests", "data", "sample.jpg")
HEB = "בְּרֵאשִׁ֖ית בָּרָ֣א"
GRK = "ἐν ἀρχῇ"

EXTRA = [
    '<w:style w:type="paragraph" w:customStyle="1" w:styleId="Epigraph"><w:name w:val="Epigraph"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/><w:ind w:left="1440" w:right="1440"/>'
    '</w:pPr><w:rPr><w:i/><w:sz w:val="20"/></w:rPr></w:style>',
    '<w:style w:type="character" w:customStyle="1" w:styleId="ScriptureRef">'
    '<w:name w:val="Scripture Ref"/><w:rPr><w:smallCaps/></w:rPr></w:style>',
    '<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/>'
    '<w:basedOn w:val="Normal"/></w:style>',
    '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/></w:pPr></w:style>',
]


def chapter_one(path):
    with open(SAMPLE, "rb") as f:
        jpg = f.read()
    body = [
        para("The Covenant", "Title"),
        para("Chapter One", "Heading1"),
        para("Words spoken long ago.", "Epigraph"),
        para(run("The first paragraph has ") + run("italic", "<w:i/>") + run(", ")
             + run("bold", "<w:b/>") + run(", ") + run("small caps", "<w:smallCaps/>")
             + run(" and an emphasis ") + run("style", '<w:rStyle w:val="Emphasis"/>')
             + run(".") + footnote_ref(1)),
        para(run("Genesis 1:1 reads ") + run(HEB, "<w:rtl/>") + run(", and John 1:1 ")
             + run(GRK) + run(". See ") + run("Gen 1:1", '<w:rStyle w:val="ScriptureRef"/>')
             + run(".") + endnote_ref(1)),
        para("A Section", "Heading2"),
        para(run("Italic heading text ") + run("inside", "<w:i/>")),
        numbered("First bullet", 1, style="ListParagraph"),
        numbered("Second bullet", 1, style="ListParagraph"),
        numbered("Step one", 2, style="ListParagraph"),
        numbered("Sub-step", 2, 1, style="ListParagraph"),
        numbered("Step two", 2, style="ListParagraph"),
        para(""),
        table([["Book", "Verses"], ["Genesis", "1533"], ["A long merged cell"]], header=1,
              widths=[3000, 2000], spans={(2, 0): 2}),
        para(image(rid="rIdImg1")),
        para("Figure 1. A picture.", "Caption"),
        para("* * *", ppr='<w:jc w:val="center"/>'),
        para("Closing words of the chapter."),
    ]
    note = (run("A note with ") + run("italic", "<w:i/>") + run(" and Greek ") + run(GRK)
            + run("."))
    return make_docx(path, body, extra_styles=EXTRA, footnotes=[note],
                     endnotes=["An endnote, converted."], numbering=NUMBERING,
                     media={"rIdImg1": ("image1.jpeg", jpg)})


def chapter_two(path):
    body = [para("Chapter Two", "Heading1"),
            para(run("Second chapter text.") + footnote_ref(1)),
            para("Bibliography", "Heading1"),
            para("Author, A. A Book. City: Press, 2020.")]
    return make_docx(path, body, footnotes=["Note one of chapter two."])


import docx_builder  # noqa: E402


def _files():
    a = chapter_one(os.path.join(TMP, "01 Chapter One.docx"))
    b = chapter_two(os.path.join(TMP, "02 Chapter Two.docx"))
    return [a, b]


def test_segments():
    assert segments("Gen " + HEB + ", then") == [(None, "Gen "), ("hebrew", HEB), (None, ", then")]
    assert segments(GRK + ".") == [("greek", GRK), (None, ".")]
    assert segments("plain") == [(None, "plain")]
    assert segments("λ́x") == [("greek", "λ́"), (None, "x")]


def test_numbering_labels():
    from lxml import etree
    root = etree.fromstring('<w:numbering %s>%s</w:numbering>' % (docx_builder.WNS, NUMBERING))
    n = Numbering(root)
    assert n.label("1", 0)[0] == "•"
    assert [n.label("2", 0)[0], n.label("2", 1)[0], n.label("2", 1)[0], n.label("2", 0)[0],
            n.label("2", 1)[0]] == ["1.", "a.", "b.", "2.", "a."]
    assert n.label("9", 0) is None


def test_content_indexes_match_reader():
    a, _b = _files()
    docx = read_docx(a)
    content = read_content(docx)
    for cp in content:
        if cp.table is None:
            assert docx.paragraphs[cp.index].text.replace("\t", "") == \
                cp.text.replace("\t", "").replace("‑", "-"), cp.index
    tables = [cp for cp in content if cp.table is not None]
    assert len(tables) == 1 and tables[0].table.header_rows == 1
    assert tables[0].table.spans == {(2, 0): 2} and tables[0].table.rows[2][1] is None
    notes = [r.footnote for cp in content for r in cp.runs if r.footnote is not None]
    assert len(notes) == 2                     # the footnote and the endnote
    assert notes[0][0].text.startswith("A note with")


def _build():
    ex = Exporter(_files(), default_profile())
    doc = ex.build()
    return ex, doc


GENERATED = 4      # half-title, title, copyright and contents come first


def _all_paras(doc):
    """Paragraphs from the manuscript (after the generated front matter)."""
    for st in doc.stories[GENERATED:]:
        for p in st.paragraphs:
            yield p


def test_model():
    ex, doc = _build()
    try:
        assert [len(s.paragraphs) > 0 for s in doc.stories] == [True] * 7
        styles = [p.style for p in _all_paras(doc)]
        # Chapter one; chapter two; bibliography (the manuscript's title went to the title page).
        assert styles[0:3] == ["Chapter Title", "Epigraph", "Body First"]
        assert "Heading A" in styles and "List Bullet" in styles and "List Number" in styles
        assert "Table" in styles and "Figure" in styles and "Caption" in styles
        assert styles[-2:] == ["Chapter Title", "Bibliography"]
        # A custom Word style with no book counterpart (based on Normal) keeps what makes it
        # distinct, in book terms: centered, italic, indents in proportion to the book's line
        # (Word's is 6.5 in), 10 pt against Word's 12 pt body = 11 * 10/12; never Word's font.
        epi = doc.style("Epigraph")
        assert epi.based_on == "Body" and epi.font is None
        assert epi.attrs["Justification"] == "CenterAlign" and epi.attrs["FontStyle"] == "Italic"
        scale = min(1, ex.measure / 468)
        assert epi.attrs["LeftIndent"] == round(72 * scale * 2) / 2 < 72
        assert epi.attrs["PointSize"] == 9
        paras = list(_all_paras(doc))
        first = paras[2]
        got = [(r.text, r.style, r.attrs) for r in first.runs if r.footnote is None]
        assert ("italic", "Italic", {}) in got and ("bold", "Bold", {}) in got
        assert ("small caps", "Small Caps", {}) in got
        # The short last word is kept with the one before it (No Break).
        assert ("emphasis ", "No Break", {}) in got and ("style", "Italic", {"NoBreak": True}) in got
        note = [r.footnote for r in first.runs if r.footnote is not None][0]
        assert note[0].style == "Footnote"
        assert [(r.text, r.style) for r in note[0].runs][:2] == [("A note with ", None),
                                                                 ("italic", "Italic")]
        assert ("ἐν ἀρχῇ", "Greek") in \
            [(r.text, r.style) for r in note[0].runs]
        heb = paras[3]
        assert (HEB, "Hebrew") in [(r.text, r.style) for r in heb.runs]
        assert heb.attrs.get("Composer") == "HL Composer Optyca"
        assert ("Gen 1:1", "Scripture Ref") in [(r.text, r.style) for r in heb.runs]
        assert doc.style("Hebrew", "character").attrs["CharacterDirection"] == "RightToLeftDirection"
        assert doc.style("Scripture Ref", "character").attrs == {"Capitalization": "SmallCaps"}
        # The endnote became a footnote.
        assert any(r.footnote for r in heb.runs)
        # Italic inside a bold heading is bold italic.
        sec = [p for p in paras if p.style == "Heading A"][0]
        assert sec.runs[0].text == "A Section"
        after = paras[paras.index(sec) + 1]
        assert after.style == "Body First"
        assert [(r.text, r.style) for r in after.runs] == [("Italic heading text ", None),
                                                           ("inside", "Italic")]
        lists = [("".join(r.text for r in p.runs), p.attrs.get("LeftIndent")) for p in paras
                 if p.style.startswith("List")]
        assert lists == [("•\tFirst bullet", None), ("•\tSecond bullet", None),
                         ("1.\tStep one", None), ("a.\tSub-step", 36), ("2.\tStep two", None)]
        tbl = [r.table for p in paras for r in p.runs if r.table is not None][0]
        assert tbl.header_rows == 1 and tbl.rows[0][0][0].style == "Table Head"
        assert tbl.rows[1][0][0].style == "Table Body" and tbl.spans == {(2, 0): 2}
        assert tbl.widths == [150, 100]
        star = [p for p in paras if "".join(r.text for r in p.runs) == "* * *"][0]
        assert star.attrs["Justification"] == "CenterAlign"
        # Sections per unit; pages run on; a section's first page is its story's first page.
        assert [s.page for s in doc.sections] == [st.pages[0] for st in doc.stories]
        assert doc.page_count == doc.stories[-1].pages[-1] + 1
        assert doc.sections[GENERATED].marker == "Chapter One"
        img = [r.image for p in paras for r in p.runs if r.image is not None][0]
        assert img.width == 162 and os.path.exists(img.path)
        assert any("endnote" in line for line in ex.report)
    finally:
        ex.cleanup()


def test_export_folder_validates():
    from idml_check import check
    out = os.path.join(TMP, "out")
    path, report = export(_files(), out, default_profile())
    assert os.path.basename(path) == "The Covenant.idml"
    assert os.path.exists(os.path.join(out, "The Covenant", "Links", "01 Chapter One-image1.jpg"))
    problems = check(path)
    assert not problems, problems[:5]
    with zipfile.ZipFile(path) as z:
        stories = "".join(z.read(n).decode("utf-8") for n in z.namelist()
                          if n.startswith("Stories/"))
    assert 'AppliedCharacterStyle="CharacterStyle/Hebrew"' in stories
    assert "<Footnote>" in stories
    assert 'LinkResourceURI="file:Links/01 Chapter One-image1.jpg"' in stories
    assert any("pages" in line for line in report)


def test_unsupported_image_listed():
    body = [para("Chapter", "Heading1"), para(image(rid="rIdE"))]
    path = make_docx(os.path.join(TMP, "emf.docx"), body,
                     media={"rIdE": ("image1.emf", b"\x01\x00\x00\x00 not an image")})
    ex = Exporter([path], default_profile())
    try:
        doc = ex.build()
        texts = ["".join(r.text for r in p.runs) for p in _all_paras(doc)]
        assert "[Image not carried over: image1.emf]" in texts
        assert any("image1.emf" in line for line in ex.report)
    finally:
        ex.cleanup()


def test_profile_fonts_and_trim():
    prof = default_profile()
    prof["fonts"].update({"body": "Arno Pro", "hebrew": "Taamey David CLM"})
    prof["page"]["trim"] = "5.5x8.5"
    ex = Exporter(_files(), prof)
    try:
        doc = ex.build()
        assert (doc.width, doc.height) == (396, 612)
        assert doc.style("Body").font == "Arno Pro"
        assert doc.style("Hebrew", "character").font == "Taamey David CLM"
        assert not any(line.startswith("Body font") for line in ex.report)
    finally:
        ex.cleanup()


def test_pagination_and_bleed():
    from idml_check import check
    prof = default_profile()
    prof["page"]["bleed"] = True
    prof["page"]["spare_pages"] = 1
    ex = Exporter(_files(), prof)
    try:
        doc = ex.build()
        # Half-title i, blank ii, title iii, copyright iv, contents v, blank vi (roman, display
        # pages without folios); chapter one arabic 1 on a recto.
        assert [(s.numbering, s.start) for s in doc.sections] == \
            [("LowerRoman", 1)] + [("LowerRoman", None)] * 3 + [("Arabic", 1)] + \
            [("Arabic", None)] * 2
        assert [doc.page_masters[i] for i in range(8)] == [
            "D-Display", "E-Blank", "D-Display", "D-Display", "B-Opener", "E-Blank", "B-Opener",
            "A-Body"]
        assert [st.pages[0] for st in doc.stories] == [0, 2, 3, 4, 6, 10, 12]
        assert doc.stories[2].valign == "BottomAlign"
        assert doc.toc_styles and doc.toc_styles[0].title_style == "Contents Title"
        assert [m.name for m in doc.masters] == ["A-Body", "B-Opener", "C-Front", "D-Display",
                                                 "E-Blank"]
        assert doc.bleed == 9
        assert any(line.startswith("Margins (in)") for line in ex.report)
        from ectype_idml.idml.writer import write_idml
        path = write_idml(doc, os.path.join(TMP, "bleed.idml"))
        assert not check(path)
        with zipfile.ZipFile(path) as z:
            prefs = z.read("Resources/Preferences.xml").decode("utf-8")
        assert 'DocumentBleedTopOffset="9"' in prefs
        assert 'DocumentBleedInsideOrLeftOffset="0"' in prefs
    finally:
        ex.cleanup()


def test_no_runt():
    from ectype_idml.idml.model import Paragraph, Run
    ex, doc = _build()
    try:
        long = "word " * 20
        p = Paragraph("Body", [Run(long + "and so it "), Run("ends", "Italic"), Run(".")])
        ex._no_runt(p, 10)
        got = [(r.text, r.style, r.attrs) for r in p.runs]
        assert got == [(long + "and ", None, {}), ("so it ", "No Break", {}),
                       ("ends", "Italic", {"NoBreak": True}), (".", "No Break", {})]
        # A long last word, a short paragraph, a heading: left alone.
        for para in (Paragraph("Body", [Run(long + "extraordinarily.")]),
                     Paragraph("Body", [Run("Short text ends here.")]),
                     Paragraph("Heading A", [Run(long + "a b")])):
            before = [(r.text, r.style) for r in para.runs]
            ex._no_runt(para, 10)
            assert [(r.text, r.style) for r in para.runs] == before
        # A footnote marker at the end stays where it is.
        p = Paragraph("Footnote", [Run(long + "see p. 4."), Run(footnote=[])])
        ex._no_runt(p, 10)
        assert p.runs[-1].footnote == []
        assert (p.runs[-2].text, p.runs[-2].style) == ("word see p. 4.", "No Break")
        body = doc.style("Body").attrs
        assert body["KeepLinesTogether"] is True and body["KeepFirstLines"] == 2
        assert body["HyphenateLastWord"] is False
        # World-Ready composer by default (Hebrew sets right everywhere).
        assert body["Composer"] == "HL Composer Optyca"
        assert doc.style("Footnote").attrs["Composer"] == "HL Composer Optyca"
    finally:
        ex.cleanup()


def test_front_matter_and_heads():
    from idml_check import check
    from ectype_idml.idml.writer import write_idml
    prof = default_profile()
    prof["notices"] = [{"name": "ESV", "text": "Scripture quotations are from the ESV."}]
    prof["running_heads"]["verso"] = "author"
    settings = {"front": {"author": "A. N. Author", "isbn_print": "978-0-00-000000-0",
                          "publisher": "Small Press", "notices": ["ESV", "Missing"],
                          "printed_in": "the United States of America", "half_title": False,
                          "contents_pages": 2},
                "short_titles": {"Chapter One": "One"}}
    ex = Exporter(_files(), prof, settings)
    try:
        doc = ex.build()
        texts = lambda st: ["".join(r.text for r in p.runs) for p in st.paragraphs]  # noqa
        assert texts(doc.stories[0])[:2] == ["The Covenant", "A. N. Author"]
        cp = texts(doc.stories[1])
        assert cp[0].startswith("Copyright \u00a9") and cp[0].endswith("by A. N. Author")
        assert "Scripture quotations are from the ESV." in cp
        assert "ISBN 978-0-00-000000-0 (paperback)" in cp
        assert "Printed in the United States of America" in cp
        assert any("Missing" in line for line in ex.report)
        assert doc.stories[2].pages == [2, 3]               # contents: 2 pages as set
        assert [s.marker for s in doc.sections][3] == "One"
        a = [m for m in doc.masters if m.name == "A-Body"][0]
        heads = {f.key: f.paragraphs[0].runs[0] for f in a.frames if f.key in ("vhead", "rhead")}
        assert heads["vhead"].text == "A. N. Author"
        assert heads["rhead"].special == "section_marker"
        b = [m for m in doc.masters if m.name == "B-Opener"][0]
        assert not [f for f in b.frames if f.key and f.key.endswith("head")]
        path = write_idml(doc, os.path.join(TMP, "front.idml"))
        assert not check(path)
    finally:
        ex.cleanup()


def test_hebrew_in_generated_text():
    """Hebrew in the book's title gets the Hebrew style on the half-title and title pages and
    in a running head, as in the manuscript's own headings (a chapter's own head: see
    test_hebrew_running_head_master)."""
    from idml_check import check
    from ectype_idml.idml.writer import write_idml
    path = make_docx(os.path.join(TMP, "heb-title.docx"), [
        para("The " + HEB + " Covenant", "Title"),
        para("Chapter One: " + HEB, "Heading1"),
        para("Text of the chapter.")])
    ex = Exporter([path], default_profile())
    try:
        doc = ex.build()
        titles = [p for st in doc.stories for p in st.paragraphs
                  if p.style in ("Half Title", "Book Title", "Chapter Title")]
        assert len(titles) == 3
        for p in titles:
            assert (HEB, "Hebrew") in [(r.text, r.style) for r in p.runs], p
            assert p.attrs.get("Composer") == "HL Composer Optyca"
        a = [m for m in doc.masters if m.name == "A-Body"][0]
        vhead = [f for f in a.frames if f.key == "vhead"][0].paragraphs[0]
        assert [(r.text, r.style) for r in vhead.runs] == [
            ("The ", None), (HEB, "Hebrew"), (" Covenant", None)]
        assert not check(write_idml(doc, os.path.join(TMP, "heb-title.idml")))
    finally:
        ex.cleanup()


def test_paper_cover_page():
    """A seminary paper's cover: the school's name above the title is part of the title page
    (not endorsements); an "Author" style gives the author; a bare "by" line and the typed
    contents' title are dropped with the contents."""
    styles = ['<w:style w:type="paragraph" w:customStyle="1" w:styleId="Caratula">'
              '<w:name w:val="Car\u00e1tula"/><w:basedOn w:val="Normal"/></w:style>',
              '<w:style w:type="paragraph" w:customStyle="1" w:styleId="AuthorS">'
              '<w:name w:val="Author"/><w:basedOn w:val="Normal"/></w:style>',
              '<w:style w:type="paragraph" w:styleId="TOC2"><w:name w:val="toc 2"/>'
              '<w:basedOn w:val="Normal"/></w:style>']
    path = make_docx(os.path.join(TMP, "paper.docx"), [
        para("The Master\u2019s Seminary", "Caratula"),
        para("A Study of the " + HEB, "Title"),
        para("by", "Caratula"),
        para("Beaux Hargrove", "AuthorS"),
        para("July 2026", "Caratula"),
        para("CONTENTS", "Caratula"),
        para("Introduction\t1", "TOC2"),
        para("Introduction", "Heading1"),
        para("Text of the paper.")], extra_styles=styles)
    ex = Exporter([path], default_profile())
    try:
        doc = ex.build()
        assert [u.type for u in ex.outline.units][:2] == ["title page", "chapter"]
        assert ex.outline.author == "Beaux Hargrove"
        texts = ["".join(r.text for r in p.runs) for st in doc.stories for p in st.paragraphs]
        assert "Beaux Hargrove" in texts and "[Author]" not in " ".join(texts)
        assert "by" not in texts and "CONTENTS" not in texts
        assert "The Master\u2019s Seminary" not in texts and "July 2026" not in texts
        assert any("Left out" in line and "July 2026" in line for line in ex.report)
    finally:
        ex.cleanup()


def test_openers_lowered_by_style():
    """Chapter openings are lowered by the title's style (Space Before for Affinity, an
    invisible rule kept in the frame for InDesign), not by a shorter frame, so the drop moves
    with the title. Styles based on Chapter Title don't inherit it."""
    from idml_check import check
    from ectype_idml.idml.writer import write_idml
    long = [para("Text of the chapter goes on for a while. " * 30)] * 3
    path = make_docx(os.path.join(TMP, "openers.docx"),
                     [para("The Book", "Title"), para("A Subtitle", "Subtitle"),
                      para("Part One: The Start", "Heading1")] + long +
                     [para("A Chapter", "Heading1"), para("Its Subtitle", "Subtitle")] + long)
    ex = Exporter([path], default_profile())
    try:
        doc = ex.build()
        assert all(st.sink == 0 for st in doc.stories)
        sink = _half(ex.body_lead * 6)
        ct = doc.resolved("Chapter Title")[0]
        assert ct["SpaceBefore"] == sink and ct["RuleAbove"] is True
        assert ct["KeepRuleAboveInFrame"] is True and ct["RuleAboveLineWeight"] == 0
        assert ct["RuleAboveOffset"] > sink
        checked = [n for n in ("Part Title", "Chapter Subtitle", "Book Subtitle")
                   if doc.style(n)]
        assert len(checked) >= 2, checked
        for name in checked:
            a = doc.resolved(name)[0]
            assert a.get("RuleAbove") is False and a.get("SpaceBefore") == 0, name
        assert doc.resolved("Half Title")[0]["SpaceBefore"] == _half(ex.text_height / 4)
        assert doc.resolved("Book Title")[0]["SpaceBefore"] == _half(ex.text_height / 5)
        assert any("Only at column top" in line for line in ex.report)
        assert doc.resolved("Contents Title")[0]["SpaceBefore"] == sink
        out = os.path.join(TMP, "openers.idml")
        write_idml(doc, out)
        assert check(out) == []
    finally:
        ex.cleanup()


def test_last_pages_to_check():
    """The report names units whose estimated last page is nearly full (may run past it in
    Affinity and DesignCraft) or nearly empty (may be left blank), with the page."""
    from types import SimpleNamespace as NS
    from ectype_idml.layout import Placed
    ex = Exporter(_files(), default_profile())
    try:
        ex.build()
        ex.report = []
        blocks = [NS(title="Full One", kind="chapter", est=2, fill=0.95),
                  NS(title="Empty One", kind="chapter", est=3, fill=0.05),
                  NS(title="Fine", kind="chapter", est=2, fill=0.5),
                  NS(title="(title page)", kind="display", est=1, fill=None)]
        placed = [Placed(6, 2), Placed(8, 3), Placed(11, 2), Placed(0, 1)]
        ex._fit_note(blocks, placed)
        full = [l for l in ex.report if l.startswith("Check where these end")]
        empty = [l for l in ex.report if l.startswith("Check these last pages")]
        names = __import__("ectype_idml.idml.writer", fromlist=["page_names"]).page_names(ex.doc)
        assert len(full) == 1 and "Full One (to page %s)" % names[7] in full[0]
        assert len(empty) == 1 and "Empty One (page %s)" % names[10] in empty[0]
        assert "Fine" not in full[0] + empty[0]
    finally:
        ex.cleanup()


def test_opener_drop_from_profile():
    prof = default_profile()
    prof["page"]["opener_drop"] = 72
    ex = Exporter(_files(), prof)
    try:
        doc = ex.build()
        assert doc.resolved("Chapter Title")[0]["SpaceBefore"] == 72
    finally:
        ex.cleanup()


def test_running_head_style_from_profile():
    prof = default_profile()
    ex = Exporter(_files(), prof)
    try:
        doc = ex.build()
        attrs = doc.style("Running Head").attrs
        # Spaced small caps at the text size (Bringhurst 8.5.4); page numbers at text size.
        assert attrs["Capitalization"] == "SmallCaps" and attrs["Tracking"] == 75
        assert attrs["PointSize"] == 11 and doc.style("Folio").attrs["PointSize"] == 11
    finally:
        ex.cleanup()
    prof["running_heads"]["style"].update({"caps": None, "italic": True, "size": 8,
                                           "tracking": 0, "font": "Arno Pro", "bold": True,
                                           "underline": True})
    ex = Exporter(_files(), prof)
    try:
        st = ex.build().style("Running Head")
        assert "Capitalization" not in st.attrs and st.attrs["FontStyle"] == "Bold Italic"
        assert st.attrs["PointSize"] == 8 and st.attrs["Tracking"] == 0
        assert st.font == "Arno Pro" and st.attrs["Underline"] is True
    finally:
        ex.cleanup()
    # Title and sentence case change the heads' text, not the style (small caps still on).
    long = [para("Then God spoke to Ezekiel by the river, and the word went on at length. " * 3)]
    path = make_docx(os.path.join(TMP, "case.docx"),
                     [para("THE BOOK OF THE PROPHET", "Title"),
                      para("the vision of the throne", "Heading1")] + long * 6 +
                     [para("Ezekiel Sees the Glory of God", "Heading1")] + long * 6)
    for case, want in (("title", ["The Vision of the Throne", "Ezekiel Sees the Glory of God"]),
                       ("sentence", ["The vision of the throne", "Ezekiel sees the glory of God"]),
                       ("as_typed", ["the vision of the throne", "Ezekiel Sees the Glory of God"])):
        prof = default_profile()
        prof["running_heads"]["style"]["case"] = case
        ex = Exporter([path], prof)
        try:
            doc = ex.build()
            assert [s.marker for s in doc.sections if s.marker in want or s.marker.lower() in
                    [w.lower() for w in want]] == want, case
            assert doc.style("Running Head").attrs["Capitalization"] == "SmallCaps"
            verso = [f for f in doc.masters[0].frames if f.key == "vhead"][0]
            title = "".join(r.text for r in verso.paragraphs[0].runs)
            assert title == {"title": "The Book of the Prophet", "sentence": "The book of the "
                             "prophet", "as_typed": "THE BOOK OF THE PROPHET"}[case], title
        finally:
            ex.cleanup()


def test_export_folder_name():
    """The export's folder and file name: short title, else the title before a colon; cut at
    a word; never ending in a space or dot (Windows drops them from a folder's name, and the
    export then failed: Beaux's "The Broken Heart: or, David's Penance..." cut at 80
    characters ended in a space)."""
    from ectype_idml.export import file_name
    title = ("The Broken Heart: or, David's Penance, Fully Expressed in Holy Meditations upon "
             "the Fifty-First Psalm")
    assert file_name(title) == "The Broken Heart"
    assert file_name(title, "Broken Heart") == "Broken Heart"
    long = "A Very Long Title Without Any Colon That Goes On and On Past the Limit of Sixty"
    got = file_name(long)
    assert len(got) <= 60 and long.startswith(got) and not got.endswith((" ", "."))
    assert file_name("Ends with dots...") == "Ends with dots"
    assert file_name('What? Why/How "now"') == "What- Why-How -now-"
    assert file_name("nul") == "nul book" and file_name("") == "Book"
    path = make_docx(os.path.join(TMP, "broken.docx"),
                     [para(title, "Title"), para("Chapter", "Heading1"),
                      para("Text of the chapter. " * 40)])
    idml, _report = export([path], os.path.join(TMP, "named"), default_profile())
    assert os.path.basename(idml) == "The Broken Heart.idml" and os.path.exists(idml)
    assert os.path.basename(os.path.dirname(idml)) == "The Broken Heart"


def test_web_addresses_can_break():
    """Chicago 6.8 break points in web addresses (zero-width spaces), so a justified line
    with a long link isn't spaced out letter by letter."""
    from ectype_idml.export import url_breaks
    z = "\u200b"
    assert url_breaks("See https://search.ebscohost.com/login.aspx?db=rfh&AN=1.") == (
        "See https://" + z + "search" + z + ".ebscohost" + z + ".com" + z + "/login" + z +
        ".aspx" + z + "?db" + z + "=" + z + "rfh" + z + "&" + z + "AN" + z + "=" + z + "1.")
    assert url_breaks("no address here: a/b.") == "no address here: a/b."
    path = make_docx(os.path.join(TMP, "url.docx"), [para("Book", "Title"),
                     para("Chapter", "Heading1"),
                     para("Available at www.jstor.org/stable/1234 in full. " * 3)])
    ex = Exporter([path], default_profile())
    try:
        doc = ex.build()
        text = "".join(r.text for st in doc.stories for p in st.paragraphs for r in p.runs)
        assert "www" + z + ".jstor" + z + ".org" + z + "/stable" + z + "/1234 in" in text
    finally:
        ex.cleanup()


def test_title_and_sentence_case():
    from ectype_idml import textcase as t
    assert t.title_case("the objectives of soul care: a look into the church") == \
        "The Objectives of Soul Care: A Look into the Church"
    assert t.title_case("SOUL CARE AND WORLDVIEWS") == "Soul Care and Worldviews"
    assert t.title_case("what is it for") == "What Is It For"        # last word
    assert t.title_case("a well-known man-of-the-hour") == "A Well-Known Man-of-the-Hour"
    assert t.title_case("McDonald and the NT") == "McDonald and the NT"
    assert t.title_case("la visión de la gloria", "es") == "La Visión de la Gloria"
    proper = t.proper_nouns(["Later God spoke to Ezekiel. The Lord said so. Then the man "
                             "left, and God was there."])
    assert {"God", "Ezekiel", "Lord"} <= proper and "Then" not in proper
    assert t.sentence_case("Ezekiel Sees the Glory of God: The River", proper) == \
        "Ezekiel sees the glory of God: The river"
    assert t.sentence_case("Foreword by Lance Quinn", {"Lance", "Quinn"}) == \
        "Foreword by Lance Quinn"
    assert t.sentence_case("What I Saw in the NT") == "What I saw in the NT"
    assert t.apply("Keep As Typed", "as_typed") == "Keep As Typed"


def test_hebrew_running_head_master():
    """A running head with Hebrew the head font lacks (or can't be checked): by default the
    chapter gets R1-Body (A-Body's frames, the head as text in the Hebrew style) and the
    report says so in an Alert (a pop-up in the window); other chapters keep A-Body and the
    section marker. With script_masters off, only a warning."""
    from idml_check import check
    from ectype_idml.idml.writer import write_idml
    from ectype_idml.pagination import Alert
    long = [para("Text of the chapter goes on for a while. " * 30)] * 8
    path = make_docx(os.path.join(TMP, "heb-head.docx"),
                     [para("Book", "Title"), para("One: " + HEB, "Heading1")] + long +
                     [para("Two", "Heading1")] + long)
    # Off: no extra master; the report warns (a font not installed anywhere, so it couldn't
    # be checked: the same on every machine).
    prof = default_profile()
    prof["running_heads"]["style"]["font"] = "No Such Font"
    prof["running_heads"]["script_masters"] = False
    ex = Exporter([path], prof)
    try:
        doc = ex.build()
        assert not [m for m in doc.masters if m.name.startswith("R")]
        assert any("A running head can use only one font" in line and HEB in line and
                   "couldn't be checked" in line for line in ex.report)
        assert not [line for line in ex.report if isinstance(line, Alert)]
    finally:
        ex.cleanup()
    prof = default_profile()
    prof["running_heads"]["style"]["font"] = "No Such Font"
    assert prof["running_heads"]["script_masters"] is True          # the default
    ex = Exporter([path], prof)
    try:
        doc = ex.build()
        r = [m for m in doc.masters if m.name == "R1-Body"][0]
        rhead = [f for f in r.frames if f.key == "rhead"][0].paragraphs[0]
        assert [(x.text, x.style) for x in rhead.runs] == [("One: ", None), (HEB, "Hebrew")]
        assert any(f.primary for f in r.frames)
        used = set(doc.page_masters.values())
        assert "R1-Body" in used and "A-Body" in used        # chapter two keeps A-Body
        a = [m for m in doc.masters if m.name == "A-Body"][0]
        assert [f for f in a.frames if f.key == "rhead"][0].paragraphs[0].runs[0].special == \
            "section_marker"
        assert not check(write_idml(doc, os.path.join(TMP, "heb-head.idml")))
        alerts = [line for line in ex.report if isinstance(line, Alert)]
        assert len(alerts) == 1 and "R1-Body" in alerts[0] and HEB in alerts[0]
    finally:
        ex.cleanup()


def test_hebrew_takes_the_face_around_it():
    """The Hebrew style sets no face: Hebrew in italic text is italic, in roman text roman,
    by the Hebrew font's own face names (Culmus: "Medium", "Medium Oblique")."""
    from ectype_idml import fonts
    index = {"taamey david clm": {"medium": 1, "medium oblique": 2, "bold": 3},
             "noitalic hebrew": {"regular": 1}}
    assert fonts.matching_face("Taamey David CLM", "Italic", index) == ("Medium Oblique", True)
    assert fonts.matching_face("Taamey David CLM", "Regular", index) == ("Medium", True)
    assert fonts.matching_face("Taamey David CLM", "Bold Italic", index) == ("Bold", False)
    assert fonts.matching_face("NoItalic Hebrew", "Italic", index) == ("Regular", False)
    assert fonts.matching_face("Not Installed", "Italic", index) == (None, True)
    path = make_docx(os.path.join(TMP, "heb-italic.docx"), [
        para("Chapter", "Heading1"),
        para(run("roman " + HEB + " and ") + run("italic " + HEB, "<w:i/>"))])
    ex = Exporter([path], default_profile())
    try:
        doc = ex.build()
        assert "FontStyle" not in doc.style("Hebrew", "character").attrs
        p = [p for st in doc.stories for p in st.paragraphs
             if any(r.text == "italic " for r in p.runs)][0]
        heb = [r for r in p.runs if r.style == "Hebrew"]
        assert "FontStyle" not in heb[0].attrs                 # roman: the paragraph's face
        assert heb[1].attrs.get("FontStyle") == "Italic"       # (font not installed here)
    finally:
        ex.cleanup()


def test_headings_by_formatting_exported():
    """Headings found by their look become Chapter Title and Heading A; the bold and size
    that made them headings don't become character styles on their text."""
    from test_outline import unstyled_book
    path = unstyled_book("unstyled-export.docx")
    ex = Exporter([path], default_profile())
    try:
        doc = ex.build()
        heads = [(p.style, [(r.text, r.style) for r in p.runs]) for st in doc.stories
                 for p in st.paragraphs if p.style in ("Chapter Title", "Heading A")]
        assert ("Chapter Title", [("Introduction", None)]) in heads
        assert ("Heading A", [("The First Question", None)]) in heads
        body = [r for st in doc.stories for p in st.paragraphs for r in p.runs
                if r.text == "Note well."]
        assert body and body[0].style == "Bold"               # a bold line in the text stays
    finally:
        ex.cleanup()


def test_manuscript_copyright_page_not_duplicated():
    """A copyright file in the manuscript is read into Book Details and replaced by the page
    made from them: one copyright line, its rights statement and notices kept."""
    from test_outline import front_matter_book
    docs = front_matter_book()
    ex = Exporter([d.path for d in docs], default_profile())
    try:
        doc = ex.build()
        lines = ["".join(r.text for r in p.runs) for st in doc.stories for p in st.paragraphs
                 if p.style == "Copyright"]
        assert sum("Copyright \u00a9" in t for t in lines) == 1, lines
        assert lines[0] == "Copyright \u00a9 2026 by A Seminary"
        assert lines[1].startswith("All rights reserved. No part of this publication")
        assert any("ISBN 978-1-934952-94-8" in t for t in lines)
        assert any(t.startswith("Scripture quotations marked ESV") for t in lines)
        assert any("replaced by one made from Book Details" in r for r in ex.report)
        texts = ["".join(r.text for r in p.runs) for st in doc.stories for p in st.paragraphs]
        fw = texts.index("Foreword by Lance Quinn")
        assert texts[fw - 1] != "A Theology of Soul Care: Essays in Biblical Counseling"
    finally:
        ex.cleanup()


def test_bylines_and_book_record():
    """Title-page bylines by role in the contributors' order (Chicago: serial comma); volume,
    series and call number lines; wording per language."""
    from ectype_idml import frontmatter as fm
    from ectype_idml.outline import Outline
    assert fm.split_names("Nicolas Ellen, Josh Stephens, and Brett Williams") == [
        "Nicolas Ellen", "Josh Stephens", "Brett Williams"]
    assert fm.split_names("John Smith, Jr. and Ann Lee") == ["John Smith, Jr.", "Ann Lee"]
    front = {"title": "T", "creators": [
        {"role": "editor", "name": "A. One"}, {"role": "editor", "name": "B. Two"},
        {"role": "editor", "name": "C. Three"}, {"role": "translator", "name": "D. Four"},
        {"role": "contributor", "name": "E. Five"}],
        "volume": "2", "volumes": "3", "series": "Studies in Soul Care", "series_number": "4",
        "call_number": "BV4012.2 .T44 2026", "isbn_print": "978-0"}
    info, notes = fm.book_info(Outline(), front)
    assert info["bylines"] == ["Edited by A. One, B. Two, and C. Three", "Translated by D. Four"]
    assert info["author"] == "A. One, B. Two, and C. Three" == info["holder"]   # editors
    lines = [("".join(r.text for r in p.runs), p.style) for p in fm.title_page(info)]
    assert lines[1] == ("Volume 2 of 3", "Volume") and lines[2][1] == "Author"
    assert ("Studies in Soul Care 4", "Series") in [
        ("".join(r.text for r in p.runs), p.style) for p in fm.half_title(info)]
    cp = "\n".join("".join(r.text for r in p.runs) for p in fm.copyright_page(info, "en")[0])
    assert "Call number: BV4012.2 .T44 2026" in cp
    assert fm.copyright_page(info, "en")[0][0].style == "Copyright"    # no title (the default)
    info, _ = fm.book_info(Outline(), dict(front, copyright_title=True, title="A Book",
                                            subtitle="Its Subtitle"))
    first = fm.copyright_page(info, "en")[0][0]
    assert (first.style, first.runs[0].text) == ("Copyright Title", "A Book: Its Subtitle")
    del front["call_number"]
    info, _ = fm.book_info(Outline(), front)
    assert "Call number" not in "".join(
        "".join(r.text for r in p.runs) for p in fm.copyright_page(info, "en")[0])
    assert fm.bylines(info["creators"], "es") == ["Edici\u00f3n de A. One, B. Two y C. Three",
                                                 "Traducci\u00f3n de D. Four"]
    # Foreword, afterword, preface and introduction writers have bylines of their own, in
    # the list's order; they don't stand for "the author".
    people = [{"role": "author", "name": "A. Writer"}, {"role": "introduction", "name": "I. One"},
              {"role": "foreword", "name": "F. One"}, {"role": "foreword", "name": "F. Two"}]
    assert fm.bylines(people) == ["A. Writer", "With an introduction by I. One",
                                  "With a foreword by F. One and F. Two"]
    info, _ = fm.book_info(Outline(), {"title": "T", "creators": people[1:]})
    assert info["author"] == "[Author]"
    # Found in the manuscript: a title page's author comes before a foreword's writer.
    o = Outline()
    o.author, o.creators = "Jane Smith", [{"role": "foreword", "name": "Lance Quinn"}]
    assert fm.creators({}, o) == [{"role": "author", "name": "Jane Smith"},
                                  {"role": "foreword", "name": "Lance Quinn"}]


def test_regular_face_by_its_own_name():
    """InDesign wants a face's own name: the Culmus Hebrew fonts' upright face is "Medium"."""
    from ectype_idml import fonts
    index = {"taamey david clm": {"medium": ("a", 0), "bold": ("b", 0)},
             "minion pro": {"regular": ("c", 0), "italic": ("d", 0)}}
    assert fonts.regular_face("Taamey David CLM", index) == "Medium"
    assert fonts.regular_face("Minion Pro", index) == "Regular"
    assert fonts.regular_face("Not Installed", index) == "Regular"


def test_short_title_flagged_and_part_heads():
    from ectype_idml.outline import Unit
    from ectype_idml.export import Block
    prof = default_profile()
    prof["running_heads"]["verso"] = "part"
    prof["page"]["spare_pages"] = 1
    ex = Exporter(_files(), prof)
    try:
        ex.build()
        assert ex._too_long("A Very Long Chapter Title That Goes On and On and On, Well Past "
                            "the Measure of the Page")
        assert not ex._too_long("Chapter One")
        part = Block(Unit("part", "part", "Part One", "", 0, "test"), [])
        ch = Block(Unit("chapter", "chapter", "Inside", "", 0, "test"), [])
        ex.report = []
        ex._paginate([part, ch])
        assert "P1-Body" in [m.name for m in ex.doc.masters]
        assert "P1-Body" in ex.doc.page_masters.values()
    finally:
        ex.cleanup()


def test_single_line_composer_gives_way_to_hebrew():
    prof = default_profile()
    prof["typography"]["paragraph_composer"] = False
    ex = Exporter(_files(), prof)              # chapter one has Hebrew
    try:
        doc = ex.build()
        assert doc.style("Body").attrs["Composer"] == "HL Composer Optyca"
        assert sum("World-Ready" in line for line in ex.report) == 1
    finally:
        ex.cleanup()
    path = make_docx(os.path.join(TMP, "latin.docx"), [para("Chapter", "Heading1"),
                                                         para("English only.")])
    ex = Exporter([path], prof)
    try:
        assert ex.build().style("Body").attrs["Composer"] == "HL Single"
    finally:
        ex.cleanup()


def test_spare_pages_and_odd_page_start():
    counts = {}
    for spare in (0, 1, 2):
        prof = default_profile()
        prof["page"]["spare_pages"] = spare
        ex = Exporter(_files(), prof)
        try:
            doc = ex.build()
            counts[spare] = [len(st.pages) for st in doc.stories]
            assert all(st.pages[0] % 2 == 0 for st in doc.stories[GENERATED:])
            assert doc.style("Chapter Title").attrs["StartParagraph"] == "NextOddPage"
        finally:
            ex.cleanup()
    # Chapters, preface-like units and the bibliography grow by the spare pages; display pages
    # and the reserved contents don't.
    assert [b - a for a, b in zip(counts[0], counts[1])] == [0, 0, 0, 0, 1, 1, 1]
    assert [b - a for a, b in zip(counts[0], counts[2])] == [0, 0, 0, 0, 2, 2, 2]
    prof = default_profile()
    prof["chapters_open"] = "next_page"
    ex = Exporter(_files(), prof)
    try:
        doc = ex.build()
        assert doc.style("Chapter Title").attrs["StartParagraph"] == "NextPage"
        assert doc.style("Chapter Subtitle") is None or \
            doc.style("Chapter Subtitle").attrs["StartParagraph"] == "Anywhere"
    finally:
        ex.cleanup()


def test_styles_from_template():
    """The styles of an IDML InDesign wrote (reference 12) replace the tool's of the same name;
    its other styles are added; the result validates."""
    from idml_check import check
    template = os.path.join(ROOT, "reference", "idml", "12-character-styles.idml")
    prof = default_profile()
    prof["styles_template"] = template
    ex = Exporter(_files(), prof)
    try:
        doc = ex.build()
        body = doc.style("Body")
        assert body.font == "Arno Pro" and body.leading == 14 and body.attrs["PointSize"] == 11
        assert body.attrs["FirstLineIndent"] == 18
        assert body.attrs["Composer"] == "HL Composer Optyca"     # the book has Hebrew
        assert doc.style("Sans Heading").based_on == "Heading A"  # added from the template
        assert doc.style("Chapter Title").attrs["PointSize"] == 20
        assert doc.style("Italic", "character").attrs == {"FontStyle": "Italic"}
        assert doc.style("Footnote") is not None                  # not in the template: the tool's
        assert not any(line.startswith("Body font") for line in ex.report)
        assert any(line.startswith("Styles from 12-character-styles.idml") for line in ex.report)
        assert any("World-Ready" in line for line in ex.report)
        from ectype_idml.idml.writer import write_idml
        assert not check(write_idml(doc, os.path.join(TMP, "tpl.idml")))
    finally:
        ex.cleanup()
    prof["styles_template"] = os.path.join(TMP, "missing.idml")
    try:
        Exporter(_files(), prof)
        assert False, "a missing template must stop the export"
    except ExportError as e:
        assert "can't be read as an IDML file" in str(e)


def test_endorsements_first_without_heads():
    path = make_docx(os.path.join(TMP, "praise.docx"), [
        para("Praise for the Book", "Heading1"), para("A fine book, says a reader of books."),
        para("More Praise From Readers Who Liked It Very Much Indeed", "Heading1"),
        para("Another fine word."),
        para("Chapter One", "Heading1"), para("Text of chapter one.")])
    ex = Exporter([path], default_profile(),
                  {"unit_kinds": {"More Praise From Readers Who Liked It Very Much Indeed":
                                  "endorsements"}})
    try:
        doc = ex.build()
        first = ["".join(r.text for r in st.paragraphs[0].runs) for st in doc.stories[:3]]
        assert first[:2] == ["Praise for the Book",
                             "More Praise From Readers Who Liked It Very Much Indeed"]
        assert doc.page_masters[doc.stories[0].pages[0]] == "D-Display"
        assert doc.page_masters[doc.stories[1].pages[0]] == "D-Display"
        assert doc.sections[0].marker == "" and doc.sections[1].marker == ""
        assert not any("too long" in line for line in ex.report)
        # The half-title follows, on a recto.
        assert doc.stories[2].paragraphs[0].style == "Half Title"
        assert doc.stories[2].pages[0] % 2 == 0
    finally:
        ex.cleanup()


def test_endorsements_before_title_without_heading():
    path = make_docx(os.path.join(TMP, "pre.docx"), [
        para("\u201cA wonderful book.\u201d \u2014 A. Reader"),
        para("The Covenant Formula", "Title"), para("by A. N. Author"),
        para("Chapter One", "Heading1"), para("Text of chapter one.")])
    ex = Exporter([path], default_profile())
    try:
        doc = ex.build()
        texts = ["".join(r.text for r in st.paragraphs[0].runs) for st in doc.stories]
        assert texts[0] == "\u201cA wonderful book.\u201d \u2014 A. Reader"
        assert doc.page_masters[0] == "D-Display"
        assert doc.stories[1].paragraphs[0].style == "Half Title" and doc.stories[1].pages[0] == 2
        # The manuscript's title line went to the generated title page, not the endorsements.
        assert all(p.style != "Book Title" for p in doc.stories[0].paragraphs)
    finally:
        ex.cleanup()


def test_body_size_leading_and_baseline_grid():
    prof = default_profile()
    prof["body_size"] = 10
    prof["leading"]["feel"] = "open"
    prof["baseline_grid"] = True
    ex = Exporter(_files(), prof)
    try:
        doc = ex.build()
        body = doc.style("Body")
        # Open at 10 pt: 13 for a typical x-height; the body font installed here (a book
        # font on Windows) may shift it, so the expectation uses the font measured.
        open_ = layout.leading_suggestions(10, ex.x_height, ex.geo.cpl)[0]["open"][2]
        assert body.attrs["PointSize"] == 10 and body.leading == open_
        if ex.x_height is None:
            assert open_ == 13
        assert doc.baseline_grid["division"] == open_
        assert doc.baseline_grid["start"] == doc.margins["top"]
        assert body.attrs["GridAlignment"] == "AlignBaseline"
        assert doc.resolved("Caption")[0]["GridAlignment"] == "None"
        assert doc.resolved("Body First")[0]["GridAlignment"] == "AlignBaseline"
        assert any(line.startswith("Body type: 10 pt on %g pt leading (open" % open_)
                   for line in ex.report)
        from idml_check import check
        from ectype_idml.idml.writer import write_idml
        assert not check(write_idml(doc, os.path.join(TMP, "grid.idml")))
    finally:
        ex.cleanup()
    prof["leading"].update(value=12, unit="pt")
    ex = Exporter(_files(), prof)
    try:
        assert ex.build().style("Body").leading == 12                 # an exact value wins
    finally:
        ex.cleanup()


def test_fonts_never_from_word():
    """The test manuscript's Word fonts are Calibri; the book's are book fonts."""
    from ectype_idml import fonts
    ex = Exporter(_files(), default_profile())
    try:
        doc = ex.build()
        assert doc.style("Body").font == fonts.book_font() != "Calibri"
        assert doc.style("Chapter Title").font in (None, doc.style("Body").font)
        assert any(line.startswith("Body font: %s (no font set in the profile"
                                   % fonts.book_font()) for line in ex.report)
        assert doc.style("Hebrew", "character").font == fonts.script_font("hebrew")
    finally:
        ex.cleanup()


def test_custom_style_look_from_style_map():
    prof = default_profile()
    prof["style_map"]["paragraph"]["Epigraph"] = {"idml": "Epigraph", "role": "body",
                                                  "look": "book"}
    ex = Exporter(_files(), prof)
    try:
        assert ex.build().style("Epigraph").attrs == {}       # the book style's look
    finally:
        ex.cleanup()
    # A custom style based on a heading follows the book's heading, unless set to Word's look.
    extra = ('<w:style w:type="paragraph" w:customStyle="1" w:styleId="SectHead">'
             '<w:name w:val="Sect Head"/><w:basedOn w:val="Heading2"/><w:pPr>'
             '<w:jc w:val="center"/></w:pPr></w:style>')
    path = make_docx(os.path.join(TMP, "sect.docx"), [para("Chapter", "Heading1"),
                                                       para("A Section", "SectHead"),
                                                       para("Text.")], extra_styles=[extra])
    ex = Exporter([path], default_profile())
    try:
        doc = ex.build()
        names = [p.style for st in doc.stories for p in st.paragraphs]
        assert "Heading A" in names and doc.style("Sect Head") is None
        assert "Justification" not in doc.style("Heading A").attrs or \
            doc.style("Heading A").attrs["Justification"] != "CenterAlign"
    finally:
        ex.cleanup()


def test_book_style_roles_are_book_styles():
    """Every style the mapping panel offers is one the export makes."""
    from ectype_idml.export import BOOK_STYLE_ROLES
    ex = Exporter(_files(), default_profile())
    try:
        ex.build()
        ex._book_styles()
        made = {s.name for s in ex.doc.paragraph_styles}
        para = set(BOOK_STYLE_ROLES) - {"Run-in Head"}    # a character style
        assert para <= made, para - made
    finally:
        ex.cleanup()


def test_two_papers_with_bibliographies():
    """Two articles not prepared as a book: each a Title, Heading 2 sections and a
    bibliography. Each paper is a unit of its own; bibliography styling stops at the end of
    its section, not at the end of the book."""
    long = "The prophets use the covenant formula in many settings and with many changes. " * 12
    a = make_docx(os.path.join(TMP, "Paper A.docx"), [
        para("Paper One", "Title"), para("Introduction", "Heading2"), para(long), para(long),
        para("Bibliography", "Heading1"), para("Author, A. A Book. 2020."),
        para("Writer, B. Another Book. 2018.")])
    b = make_docx(os.path.join(TMP, "Paper B.docx"), [
        para("Paper Two", "Title"), para("Introduction", "Heading2"), para(long),
        para("Works Cited", "Heading2"), para("Smith, C. A Third Book. 2019."),
        para("Afterword", "Heading2"), para("Text after the bibliography section.")])
    ex = Exporter([a, b], default_profile())
    try:
        ex.build()
        units = [(u.kind, u.title) for u in ex.outline.units]
        assert units == [("chapter", "Paper One"), ("back", "Bibliography"),
                         ("chapter", "Paper Two")], units
        styles = {}
        for st in ex.doc.stories[GENERATED:]:
            for p in st.paragraphs:
                styles.setdefault("".join(r.text for r in p.runs)[:20], p.style)
        assert styles["Paper One"] == "Chapter Title" and styles["Paper Two"] == "Chapter Title"
        assert styles["Author, A. A Book. 2"] == "Bibliography"
        assert styles["Smith, C. A Third Bo"] == "Bibliography"
        assert styles["Text after the bibli"] == "Body First"
        assert styles["The prophets use the"] == "Body First"
    finally:
        ex.cleanup()


def test_folio_places():
    """Page numbers at the foot centered (default), at the foot outside, or at the head
    outside on the running heads' line with a centered drop folio on openers; none on
    openers when asked. Each export validates."""
    from idml_check import check
    from ectype_idml.idml.writer import write_idml

    def folios(doc, name):
        m = [m for m in doc.masters if m.name == name][0]
        return {f.side: (f.bounds[0], f.paragraphs[0].attrs.get("Justification"))
                for f in m.frames if f.key == "folio"}
    for place, opener in (("foot_center", "drop"), ("foot_outside", "drop"),
                          ("head_outside", "drop"), ("foot_center", "none")):
        prof = default_profile()
        prof["running_heads"].update(folio=place, opener_folio=opener)
        ex = Exporter(_files(), prof)
        try:
            doc = ex.build()
            top, foot = doc.margins["top"], doc.height - doc.margins["bottom"]
            a, b = folios(doc, "A-Body"), folios(doc, "B-Opener")
            assert folios(doc, "C-Front") == a
            if place == "foot_center":
                assert a == {"verso": (foot + 14, None), "recto": (foot + 14, None)}
            elif place == "foot_outside":
                assert a == {"verso": (foot + 14, "LeftAlign"), "recto": (foot + 14, "RightAlign")}
            else:
                assert a == {"verso": (top - 27, "LeftAlign"), "recto": (top - 27, "RightAlign")}
            if opener == "none":
                assert b == {}
            elif place == "head_outside":
                assert b == {"verso": (foot + 14, None), "recto": (foot + 14, None)}
            else:
                assert b == a
            assert not folios(doc, "D-Display") and not folios(doc, "E-Blank")
            path = write_idml(doc, os.path.join(TMP, "folio-%s-%s.idml" % (place, opener)))
            assert not check(path)
        finally:
            ex.cleanup()


H5 = ('<w:style w:type="paragraph" w:styleId="Heading5"><w:name w:val="heading 5"/>'
      '<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="4"/></w:pPr></w:style>')
LONG = ("This paragraph is long enough to count as running text in the chapter, with more "
        "than twenty words in it so the outline treats it as body text.")


def test_bringhurst_styles():
    """1.1.0: sizes on the type scale, headings that change one thing (A larger roman, B
    spaced small caps, C italic), whole body lines for headings and quotations, a 1 em
    indent, lining figures in tables, three letters taken down at a hyphen, capitals and
    small caps letterspaced."""
    from idml_check import check
    from ectype_idml.idml.writer import write_idml
    ex = Exporter(_files(), default_profile())
    try:
        doc = ex.build()
        assert not check(write_idml(doc, os.path.join(TMP, "bringhurst.idml")))
        ex._book_styles()                    # all of them, not only those the book uses
        lead = ex.body_lead
        r = lambda n: doc.resolved(n)  # noqa: E731
        assert lead == 13                                  # 11/13, Bringhurst's routine
        assert r("Body")[0]["FirstLineIndent"] == 11 and r("Body")[0]["HyphenateBeforeLast"] == 3
        assert [r(n)[0]["PointSize"] for n in ("Chapter Title", "Heading A", "Footnote")] == \
            [18, 14, 9]
        b, c = r("Heading B")[0], r("Heading C")[0]
        assert "FontStyle" not in doc.style("Heading A").attrs          # text weight
        assert b["Capitalization"] == "SmallCaps" and b["Tracking"] == 50 and b["PointSize"] == 11
        assert c["FontStyle"] == "Italic" and c.get("Capitalization", "Normal") != "SmallCaps"
        for name in ("Chapter Title", "Heading A", "Heading B", "Heading C",
                     "Chapter Subtitle", "Block Quote First"):
            attrs, _f, own = r(name)
            total = attrs.get("SpaceBefore", 0) + own + attrs.get("SpaceAfter", 0)
            assert abs(total / lead - round(total / lead)) < 1e-6, (name, total)
        assert r("Block Quote")[2] == lead and r("Block Quote")[0]["PointSize"] == 10
        assert r("Table Body")[0]["OTFFigureStyle"] == "TabularLining"
        assert ex._char_style("Small Caps")["Tracking"] == 50
        assert any(line.startswith("For offset printing:") for line in ex.report)
    finally:
        ex.cleanup()


def test_block_quotes_and_run_in_heads():
    """A quotation of three paragraphs: the first in Block Quote First (flush), the others
    indented, no space between them. A heading 5 runs into the paragraph after it, in the
    Run-in Head style with a period; one with nothing after it stays a line and is reported."""
    path = make_docx(os.path.join(TMP, "quotes.docx"), [
        para("Chapter One", "Heading1"), para(LONG),
        para("First quoted paragraph.", "Quote"), para("Second quoted paragraph.", "Quote"),
        para("Third quoted paragraph.", "Quote"), para(LONG),
        para("A Minor Point", "Heading5"), para(LONG),
        para("Last Word", "Heading5")], extra_styles=[H5])
    for first, nxt in ((False, True), (True, False)):
        prof = default_profile()
        prof["block_quotes"] = {"indent_first": first, "indent_next": nxt}
        ex = Exporter([path], prof)
        try:
            doc = ex.build()
            paras = [p for st in doc.stories for p in st.paragraphs]
            quotes = [p for p in paras if p.style.startswith("Block Quote")]
            assert [p.style for p in quotes] == ["Block Quote First", "Block Quote",
                                                  "Block Quote"]
            assert [p.attrs.get("SpaceAfter") for p in quotes] == [0, 0, None]
            fi = lambda n: doc.resolved(n)[0]["FirstLineIndent"]  # noqa: E731
            assert (fi("Block Quote First") > 0) == first and (fi("Block Quote") > 0) == nxt
            run_in = [p for p in paras if p.runs and p.runs[0].style == "Run-in Head"]
            assert len(run_in) == 2
            text = "".join(x.text for x in run_in[0].runs)
            assert text.startswith("A Minor Point. This paragraph") and \
                run_in[0].style == "Body"
            assert "".join(x.text for x in run_in[1].runs).strip() == "Last Word"
            assert any("Last Word" in line and "run into" in line for line in ex.report)
            assert "Run-in Head" in {c.name for c in doc.character_styles}
            assert "Run-in Head" not in {s.name for s in doc.paragraph_styles}
        finally:
            ex.cleanup()


def test_no_running_heads_and_greek_size():
    """Running heads "none" on a side leave that side without a head frame. Greek is sized
    by the fonts' heights (as measured, here made up): its own style per size of text."""
    prof = default_profile()
    prof["running_heads"].update(verso="none", recto="none")
    ex = Exporter(_files(), prof)
    try:
        doc = ex.build()
        for m in doc.masters:
            assert not [f for f in m.frames if f.key in ("vhead", "rhead")], m.name
    finally:
        ex.cleanup()
    path = make_docx(os.path.join(TMP, "greek.docx"), [
        para("Chapter One", "Heading1"), para(LONG + " " + GRK),
        para("Note " + GRK, "Quote")])
    ex = Exporter([path], default_profile())
    ex._greek_ratio = 0.9
    try:
        doc = ex.build()
        styles = {c.name: c for c in doc.character_styles}
        assert styles["Greek"].attrs["PointSize"] == 9.9
        assert styles["Greek 10 pt"].attrs["PointSize"] == 9.0
        runs = [x for st in doc.stories for p in st.paragraphs for x in p.runs]
        assert all("PointSize" not in x.attrs for x in runs if x.style and
                   x.style.startswith("Greek"))
    finally:
        ex.cleanup()


def test_profile_upgrade_to_11():
    from ectype_idml import profile as profiles
    old = {"profile_version": 10, "running_heads": {"style": {"tracking": 20}},
           "page": {"trim": "6x9"}}
    up = profiles.upgrade(old) if hasattr(profiles, "upgrade") else profiles.migrate(old)
    assert up["running_heads"]["style"]["tracking"] == 75
    assert up["page"]["margin_scheme"] == "canon" and up["block_quotes"]["indent_next"]
    assert up["typography"]["paragraph_indent"] == 1 and up["running_heads"]["folio"] == \
        "foot_center"


if __name__ == "__main__":
    run_tests(globals())
