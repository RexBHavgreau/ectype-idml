"""Write the generator's own versions of the reference files (build step 3).

    python tools/make_generated_files.py

Writes reference/generated/gNN-*.idml with ectype_idml.idml.writer, each built to match the
InDesign reference file of the same number (same pages, styles and text as
reference/make_reference_files.jsx makes), and checks each with tools/idml_check.py. Compare
with the reference using tools/idml_inspect.py; then open in InDesign and Affinity.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from ectype_idml.idml.model import (CellStyle, Document, Frame, Image, Master, Paragraph,
                                  PlacedImage, Run, Section, Story, Style, Table, TableStyle,
                                  TOCStyle)
from ectype_idml.idml.writer import write_idml
from ectype_idml.profile import default_profile

OUT = os.path.join(ROOT, "reference", "generated")

# The same sentences as the InDesign script, so the files can be compared page by page.
SENTENCES = [
    "The covenant formula recurs throughout the prophets with small but telling changes.",
    "Each change of wording marks a shift in the relationship the text describes.",
    "Readers in the early church heard these passages through the Greek translation.",
    "That translation smooths some difficulties of the Hebrew and sharpens others.",
    "A careful edition keeps both voices audible without forcing them into agreement.",
    "The apparatus at the foot of the page records where the witnesses part ways.",
    "Some of these differences are accidents of copying; others are deliberate.",
    "Distinguishing the two requires attention to the habits of each scribe.",
    "The argument of this chapter proceeds from the clearer cases to the harder ones.",
    "Office workers, affluent patrons and fifty-five official scribes all appear in the record.",
]


def filler(n_words, seed=0):
    out, count, i = [], 0, seed
    while count < n_words:
        s = SENTENCES[i % len(SENTENCES)]
        out.append(s)
        count += len(s.split())
        i += 1
    return " ".join(out)


def body_styles(font="Arno Pro"):
    """The styles the InDesign script's bodyStyles() makes."""
    return [
        Style("Body", font=font, leading=14,
              attrs={"FontStyle": "Regular", "PointSize": 11, "FirstLineIndent": 18,
                     "Justification": "LeftJustified", "Hyphenation": True,
                     "Composer": "HL Composer"}),
        Style("Body First", based_on="Body", attrs={"FirstLineIndent": 0}),
        Style("Chapter Title", based_on="Body", leading=24, next_style="Body First",
              attrs={"PointSize": 20, "FirstLineIndent": 0, "Justification": "CenterAlign",
                     "SpaceAfter": 28, "Hyphenation": False, "KeepWithNext": 2}),
        Style("Heading A", based_on="Body", leading=14, next_style="Body First",
              attrs={"PointSize": 12, "FontStyle": "Bold", "FirstLineIndent": 0,
                     "Justification": "LeftAlign", "SpaceBefore": 14, "Hyphenation": False,
                     "KeepWithNext": 2}),
        Style("Running Head", font=font, leading=11,
              attrs={"PointSize": 9, "FirstLineIndent": 0, "Hyphenation": False,
                     "Justification": "LeftAlign"}),
    ]


def note(*runs):
    return [Paragraph("Footnote", [r if isinstance(r, Run) else Run(r) for r in runs])]


def g01_footnotes():
    """Footnotes, as reference 01: two chapters (stories) of two pages, a section each,
    numbering restarting per section, a long note running over to the next page."""
    doc = Document(page_count=4, name="g01-footnotes")
    doc.paragraph_styles = body_styles() + [
        Style("Footnote", font="Arno Pro", leading=11,
              attrs={"PointSize": 9, "FirstLineIndent": 9, "Justification": "LeftJustified"})]
    doc.character_styles = [Style("Footnote Reference", attrs={"Position": "Superscript"}),
                            Style("Italic", attrs={"FontStyle": "Italic"})]
    doc.footnotes = dict(default_profile()["footnotes"])
    ch1 = [
        Paragraph("Chapter Title", [Run("First Chapter")]),
        Paragraph("Body First", [Run(filler(60, 0)), Run(footnote=note(
            "A short note with an ", Run("italic phrase", style="Italic"), " in it."))]),
        Paragraph("Body", [Run(filler(50, 2)), Run(footnote=note("Ibid.")),
                           Run(" " + filler(40, 3))]),
        Paragraph("Body", [Run(filler(70, 5)), Run(footnote=note(
            "This note is long enough to run onto the next page. " + filler(260, 4)))]),
        Paragraph("Body", [Run(filler(120, 6)), Run(footnote=note("A note on the second page."))]),
        Paragraph("Body", [Run(filler(160, 7))]),
    ]
    ch2 = [
        Paragraph("Chapter Title", [Run("Second Chapter")]),
        Paragraph("Body First", [Run(filler(60, 1)), Run(footnote=note(
            "Numbering restarts at 1 in a new section."))]),
        Paragraph("Body", [Run(filler(80, 2)), Run(footnote=note("Second note of chapter two."))]),
        Paragraph("Body", [Run(filler(200, 3))]),
    ]
    doc.stories = [Story(ch1, [0, 1], sink=72), Story(ch2, [2, 3], sink=72)]
    doc.sections = [Section(0, marker="First Chapter"), Section(2, marker="Second Chapter")]
    return doc


def area(doc, side):
    """The text area of a page, (top, left, bottom, right), in page coordinates. In facing
    documents the inside margin is on the right of a verso and the left of a recto."""
    m = doc.margins
    left = m["outside"] if side == "verso" else m["inside"]
    right = doc.width - (m["inside"] if side == "verso" else m["outside"])
    return m["top"], left, doc.height - m["bottom"], right


def head_frame(doc, side, runs, key="head", justification=None):
    """A running head 27-13 pt above the text area, text at its foot (as the script's
    headFrame)."""
    top, left, _bottom, right = area(doc, side)
    para = Paragraph("Running Head", runs,
                     attrs={"Justification": justification} if justification else {})
    return Frame(side, (top - 27, left, top - 13, right), [para], key=key, valign="BottomAlign")


def folio_frame(doc, side, key="folio"):
    """A folio 14-28 pt below the text area (as the script's folioFrame)."""
    _top, left, bottom, right = area(doc, side)
    return Frame(side, (bottom + 14, left, bottom + 28, right),
                 [Paragraph("Folio", [Run(special="page_number")])], key=key)


def g02_section_marker_heads():
    """Running heads from section markers, as reference 02: recto head = section marker and
    page number, verso head = page number and the book title; three sections."""
    doc = Document(page_count=7, name="g02-section-marker-heads")
    doc.paragraph_styles = body_styles()
    doc.character_styles = [Style("Italic", attrs={"FontStyle": "Italic"})]
    doc.footnotes = dict(default_profile()["footnotes"])
    doc.masters = [Master("A", "Body", frames=[
        head_frame(doc, "verso", [Run("  |  Reference Book", special="page_number")]),
        head_frame(doc, "recto", [Run("  |  ", special="section_marker"),
                                  Run(special="page_number")], justification="RightAlign")])]
    chapters = [("First Chapter", [0, 1]), ("Second Chapter", [2, 3]),
                ("A Third Chapter with a Much Longer Title Than the Others", [4, 5, 6])]
    doc.stories, doc.sections = [], []
    for i, (title, pages) in enumerate(chapters):
        doc.stories.append(Story([Paragraph("Chapter Title", [Run(title)]),
                                  Paragraph("Body First", [Run(filler(200 * len(pages), i))])],
                                 pages, sink=72))
        doc.sections.append(Section(pages[0], marker=title))
    return doc


def g03_section_numbering():
    """Roman front matter, arabic from chapter 1, as reference 03: display pages (D) and blank
    pages (E) with no folio; folios on A-Body and C-Front (based on A)."""
    doc = Document(page_count=9, name="g03-section-numbering")
    doc.paragraph_styles = body_styles() + [
        Style("Folio", based_on="Running Head", attrs={"Justification": "CenterAlign"})]
    doc.character_styles = [Style("Italic", attrs={"FontStyle": "Italic"})]
    doc.footnotes = dict(default_profile()["footnotes"])
    doc.masters = [Master("A", "Body", frames=[folio_frame(doc, "verso"),
                                               folio_frame(doc, "recto")]),
                   Master("C", "Front", based_on="A-Body"),
                   Master("D", "Display"), Master("E", "Blank")]
    plan = [("D-Display", "Reference Book"), ("E-Blank", ""),
            ("D-Display", "Reference Book\rA Subtitle\rAuthor Name"),
            ("D-Display", "Copyright \u00A9 2026 Author Name. All rights reserved."),
            ("C-Front", "Contents"), ("E-Blank", ""), ("C-Front", "Preface"),
            ("A-Body", "Chapter One"), ("A-Body", "")]
    doc.stories = []
    for i, (master, text) in enumerate(plan):
        doc.page_masters[i] = master
        if text:
            lines = text.split("\r")
            paras = [Paragraph("Chapter Title", [Run(lines[0])])]
            paras += [Paragraph("Body", [Run(line)]) for line in lines[1:]]
            if i >= 4:
                paras.append(Paragraph("Body First", [Run(filler(120, i))]))
            doc.stories.append(Story(paras, [i], sink=72))
    doc.sections = [Section(0, marker="Front matter", numbering="LowerRoman", start=1),
                    Section(7, marker="Chapter One", start=1)]
    return doc


def g04_parent_child_masters():
    """B-Opener based on A-Body, as reference 04: it removes A's running heads and has its own
    folio at the foot."""
    doc = Document(page_count=6, name="g04-parent-child-masters")
    doc.paragraph_styles = body_styles() + [
        Style("Folio", based_on="Running Head", attrs={"Justification": "CenterAlign"})]
    doc.character_styles = [Style("Italic", attrs={"FontStyle": "Italic"})]
    doc.footnotes = dict(default_profile()["footnotes"])
    a = Master("A", "Body", frames=[
        head_frame(doc, "verso", [Run("  |  Reference Book", special="page_number")]),
        head_frame(doc, "recto", [Run("Chapter Title  |  "), Run(special="page_number")],
                   justification="RightAlign")])
    b = Master("B", "Opener", based_on="A-Body", removes=["head"],
               frames=[folio_frame(doc, "verso"), folio_frame(doc, "recto")])
    doc.masters = [a, b]
    for i, m in enumerate(["B-Opener", "A-Body", "A-Body", "A-Body", "B-Opener", "A-Body"]):
        doc.page_masters[i] = m
    doc.stories = [
        Story([Paragraph("Chapter Title", [Run("Chapter Opener on B")]),
               Paragraph("Body First", [Run(filler(1000, 0))])], [0, 1, 2, 3], sink=108),
        Story([Paragraph("Chapter Title", [Run("Second Opener on B")]),
               Paragraph("Body First", [Run(filler(450, 3))])], [4, 5], sink=108)]
    doc.sections = [Section(0)]
    return doc


def base_doc(pages, name):
    doc = Document(page_count=pages, name=name)
    doc.paragraph_styles = body_styles()
    doc.character_styles = [Style("Italic", attrs={"FontStyle": "Italic"})]
    doc.footnotes = dict(default_profile()["footnotes"])
    return doc


def g05_primary_text_frame():
    """A primary text frame on A-Parent (verso and recto, threaded), page frames linked to it
    by OverrideList pairs, as reference 05 (version 3). Six pages are written, since Affinity
    adds none for overset text; InDesign reflows by itself."""
    doc = base_doc(6, "g05-primary-text-frame")
    a = Master("A", "Parent", frames=[Frame("verso", area(doc, "verso"), [], primary=True),
                                      Frame("recto", area(doc, "recto"), [], primary=True)])
    doc.masters = [a]
    doc.stories = [Story([Paragraph("Chapter Title", [Run("Text in the Primary Frame")]),
                          Paragraph("Body First", [Run(filler(2600, 0))])],
                         list(range(6)), linked=True)]
    return doc


def g06_toc():
    """The contents style of reference 06 (two levels, dot-leader tab, bold level 1). As decided
    after the Affinity tests, the contents page is reserved with its title only: no generated
    contents (InDesign users generate it from the style)."""
    doc = base_doc(7, "g06-toc")
    _t, left, _b, right = area(doc, "recto")
    tabs = [("RightAlign", right - left, ". ")]
    doc.paragraph_styles += [
        Style("Contents Title", based_on="Chapter Title"),
        Style("Contents 1", based_on="Body", tabs=tabs,
              attrs={"FontStyle": "Bold", "FirstLineIndent": 0, "Justification": "LeftAlign",
                     "SpaceBefore": 6}),
        Style("Contents 2", based_on="Body", tabs=tabs,
              attrs={"FirstLineIndent": 0, "LeftIndent": 18, "Justification": "LeftAlign"})]
    doc.toc_styles = [TOCStyle("Contents", "Contents", "Contents Title",
                               [("Chapter Title", 1, "Contents 1"), ("Heading A", 2, "Contents 2")])]
    doc.stories = [Story([Paragraph("Contents Title", [Run("Contents")])], [0], sink=0)]
    for i, title in enumerate(["Chapter One", "Chapter Two", "A Third Chapter"]):
        doc.stories.append(Story([
            Paragraph("Chapter Title", [Run(title)]),
            Paragraph("Body First", [Run(filler(150, i))]),
            Paragraph("Heading A", [Run("First Section of " + title)]),
            Paragraph("Body First", [Run(filler(200, i + 1))]),
            Paragraph("Heading A", [Run("Second Section")]),
            Paragraph("Body First", [Run(filler(150, i + 2))])], [1 + 2 * i, 2 + 2 * i], sink=72))
    return doc


def g07_table():
    """Table, cell and paragraph styles, 40 body rows with a header row, two merged cells, as
    reference 07."""
    doc = base_doc(3, "g07-table")
    doc.paragraph_styles += [
        Style("Table Body", based_on="Body", leading=12,
              attrs={"FirstLineIndent": 0, "PointSize": 9.5, "Justification": "LeftAlign",
                     "Hyphenation": False}),
        Style("Table Head", based_on="Table Body", attrs={"FontStyle": "Bold"})]
    doc.colors = [("Table Grey", (0, 0, 0, 12))]
    insets = {"TextTopInset": 3, "TextLeftInset": 4, "TextBottomInset": 3, "TextRightInset": 4,
              "TopInset": 3, "BottomInset": 3, "LeftInset": 4, "RightInset": 4}
    doc.cell_styles = [CellStyle("Head Cell", "Table Head", "Table Grey", dict(insets)),
                       CellStyle("Body Cell", "Table Body", None, dict(insets))]
    doc.table_styles = [TableStyle("Book Table", "Head Cell", "Body Cell",
                                   {"TopBorderStrokeWeight": 1, "BottomBorderStrokeWeight": 1,
                                    "LeftBorderStrokeWeight": 0, "RightBorderStrokeWeight": 0})]
    cell = lambda text, style="Table Body": [Paragraph(style, [Run(text)])]
    rows = [[cell(t, "Table Head") for t in ("Book", "Chapters", "Verses", "Notes")]]
    for r in range(1, 41):
        rows.append([cell("Book %d" % r), cell(str(r % 50 + 1)), cell(str(r * 31 % 900)),
                     cell("A longer note that wraps onto a second line in its cell."
                          if r % 7 == 0 else "")])
    rows[5][3] = None                     # merged into the cell to its left
    _t, left, _b, right = area(doc, "recto")
    width = (right - left) / 4
    table = Table(rows, [width] * 4, header_rows=1, style="Book Table", spans={(5, 2): 2})
    doc.stories = [Story([Paragraph("Chapter Title", [Run("Tables")]),
                          Paragraph("Body First", [Run(filler(150, 0))]),
                          Paragraph("Body", [Run(table=table)]),
                          Paragraph("Body", [Run(filler(200, 3))])], [0, 1, 2], sink=72)]
    return doc


def g08_opentype():
    """OpenType features, composers, hyphenation, optical margins and a balanced heading, as
    reference 08."""
    doc = base_doc(2, "g08-opentype")
    doc.paragraph_styles += [
        Style("Body OpenType", based_on="Body",
              attrs={"Ligatures": True, "OTFFigureStyle": "ProportionalOldstyle",
                     "KerningMethod": "$ID/Optical"}),
        Style("Body Lining", based_on="Body",
              attrs={"Ligatures": False, "OTFFigureStyle": "TabularLining",
                     "KerningMethod": "$ID/Metrics"}),
        Style("Body Single-line", based_on="Body", attrs={"Composer": "HL Single"}),
        Style("Body No Hyphenation", based_on="Body", attrs={"Hyphenation": False}),
        Style("Balanced Heading", based_on="Chapter Title",
              attrs={"Justification": "CenterAlign"},
              props={"BalanceRaggedLines": ("enumeration", "VeeShape")})]
    doc.character_styles += [Style("Small Caps", attrs={"Capitalization": "SmallCaps"}),
                             Style("All Small Caps", attrs={"Capitalization": "CapToSmallCap"}),
                             Style("Discretionary Ligatures",
                                   attrs={"OTFDiscretionaryLigature": True}),
                             Style("Fraction", attrs={"OTFFraction": True}),
                             Style("Ordinal", attrs={"OTFOrdinal": True})]
    paras = [
        Paragraph("Balanced Heading",
                  [Run("A Balanced Heading That Runs Long Enough to Take Two Lines")]),
        Paragraph("Body OpenType", [Run(
            "Ligatures: fi fl ff ffi ffl office affluent official. Old-style figures: "
            "1234567890, 1776, 2026. Kerning optical. \u201cQuoted lines\u201d hang into the "
            "margin with optical alignment. " + filler(80, 0))]),
        Paragraph("Body Lining", [Run("Lining figures: 1234567890, 1776, 2026. Ligatures off: "
                                      "fi fl ff office. Kerning metrics. " + filler(60, 1))]),
        Paragraph("Body", [Run("Small caps style: "), Run("Chapter and Verse", "Small Caps"),
                           Run(". All small caps: "), Run("UNESCO, NASB, LXX", "All Small Caps"),
                           Run(". Discretionary ligatures: "),
                           Run("ct st", "Discretionary Ligatures"), Run(". Fractions: "),
                           Run("1/2 3/4", "Fraction"), Run(". Ordinals: "),
                           Run("1st 2nd 3rd", "Ordinal"), Run(". " + filler(60, 2))]),
        Paragraph("Body Single-line", [Run("Single-line composer: " + filler(120, 3))]),
        Paragraph("Body", [Run("Paragraph composer: " + filler(120, 3))]),
        Paragraph("Body No Hyphenation", [Run("Hyphenation off: " + filler(120, 4))])]
    doc.stories = [Story(paras, [0, 1], sink=36, optical_margins=11)]
    return doc


def g09_baseline_grid():
    """Baseline grid from the top margin every 14 pt; body and headings aligned to it; a block
    quote off the grid, as reference 09."""
    doc = base_doc(2, "g09-baseline-grid")
    doc.baseline_grid = {"start": doc.margins["top"], "division": 14, "shown": True}
    for st in doc.paragraph_styles:
        if st.name in ("Body", "Body First", "Chapter Title", "Heading A"):
            st.attrs["GridAlignment"] = "AlignBaseline"
        if st.name == "Heading A":
            st.attrs["SpaceBefore"] = 7
    doc.paragraph_styles.append(
        Style("Block Quote", based_on="Body", leading=12,
              attrs={"PointSize": 10, "LeftIndent": 18, "FirstLineIndent": 0,
                     "GridAlignment": "None", "SpaceBefore": 7, "SpaceAfter": 7}))
    doc.stories = [Story([
        Paragraph("Chapter Title", [Run("On the Grid")]),
        Paragraph("Body First", [Run(filler(150, 0))]),
        Paragraph("Heading A", [Run("A Heading with Half a Line Before")]),
        Paragraph("Body First", [Run(filler(120, 1))]),
        Paragraph("Block Quote", [Run("A block quote set off the grid, at 10 on 12. "
                                      + filler(60, 2))]),
        Paragraph("Body", [Run(filler(250, 3))])], [0, 1], sink=72)]
    return doc


GEN = ("\u05D1\u05BC\u05B0\u05E8\u05B5\u05D0\u05E9\u05C1\u05B4\u0596\u05D9\u05EA "
       "\u05D1\u05BC\u05B8\u05E8\u05B8\u05A3\u05D0 \u05D0\u05B1\u05DC\u05B9\u05D4\u05B4\u0591\u05D9\u05DD "
       "\u05D0\u05B5\u05A5\u05EA \u05D4\u05B7\u05E9\u05BC\u05C1\u05B8\u05DE\u05B7\u0596\u05D9\u05B4\u05DD "
       "\u05D5\u05B0\u05D0\u05B5\u05A5\u05EA \u05D4\u05B8\u05D0\u05B8\u05BD\u05E8\u05B6\u05E5\u05C3")
GEN_PLAIN = "\u05D1\u05E8\u05D0\u05E9\u05D9\u05EA \u05D1\u05E8\u05D0 \u05D0\u05DC\u05D4\u05D9\u05DD"
JOHN = ("\u1F18\u03BD \u1F00\u03C1\u03C7\u1FC7 \u1F26\u03BD \u1F41 \u03BB\u03CC\u03B3\u03BF\u03C2, "
        "\u03BA\u03B1\u1F76 \u1F41 \u03BB\u03CC\u03B3\u03BF\u03C2 \u1F26\u03BD \u03C0\u03C1\u1F78\u03C2 "
        "\u03C4\u1F78\u03BD \u03B8\u03B5\u03CC\u03BD, \u03BA\u03B1\u1F76 \u03B8\u03B5\u1F78\u03C2 "
        "\u1F26\u03BD \u1F41 \u03BB\u03CC\u03B3\u03BF\u03C2.")
# The family name InDesign gave the Hebrew font on Beaux's machine (reference 10).
HEBREW_FONT = "Taamey David CLM (OTF)"


def g10_hebrew_greek():
    """Hebrew (pointed, cantillated) inline and as a right-to-left paragraph; polytonic Greek;
    direction and language in the styles, as reference 10."""
    doc = base_doc(2, "g10-hebrew-greek")
    doc.paragraph_styles += [
        Style("Body World-Ready", based_on="Body", attrs={"Composer": "HL Composer Optyca"}),
        Style("Hebrew Block", based_on="Body World-Ready", font=HEBREW_FONT, leading=18,
              attrs={"FontStyle": "Regular", "PointSize": 13, "FirstLineIndent": 0,
                     "AppliedLanguage": "$ID/Hebrew", "Justification": "RightAlign",
                     "CharacterDirection": "RightToLeftDirection",
                     "ParagraphDirection": "RightToLeftDirection"})]
    doc.character_styles += [
        Style("Hebrew", font=HEBREW_FONT, attrs={"FontStyle": "Regular",
                                                 "AppliedLanguage": "$ID/Hebrew",
                                                 "CharacterDirection": "RightToLeftDirection"}),
        Style("Greek", font="Arno Pro", attrs={"FontStyle": "Regular",
                                               "AppliedLanguage": "$ID/Greek"})]
    doc.stories = [Story([
        Paragraph("Chapter Title", [Run("Hebrew and Greek")]),
        Paragraph("Body World-Ready", [
            Run("World-Ready composer. Genesis 1:1 reads "), Run(GEN, "Hebrew"),
            Run(" and the phrase is long enough that it should wrap across a line when set in a "
                "paragraph of this width, which tests how the bidirectional run breaks. "
                "Unpointed: "), Run(GEN_PLAIN, "Hebrew"), Run(". John 1:1 reads "),
            Run(JOHN, "Greek"), Run(" " + filler(40, 0))]),
        Paragraph("Body", [Run("Paragraph composer (not World-Ready), same text: "),
                           Run(GEN, "Hebrew"), Run(" and then John: "), Run(JOHN, "Greek"),
                           Run(".")]),
        Paragraph("Hebrew Block", [Run(GEN + " " + GEN)]),
        Paragraph("Body World-Ready", [Run("Greek by language only, in the body font: "),
                                       Run(JOHN, "Greek")])], [0, 1], sink=72)]
    return doc


SAMPLE_IMAGE = os.path.join(ROOT, "tests", "data", "sample.jpg")


def g11_images():
    """An inline anchored image with a caption, and a free image with a text wrap on page 2, as
    reference 11. The image is copied to a Links folder beside the IDML."""
    doc = base_doc(2, "g11-images")
    doc.paragraph_styles += [
        Style("Caption", based_on="Body", leading=11,
              attrs={"PointSize": 9, "FirstLineIndent": 0, "FontStyle": "Italic",
                     "Justification": "CenterAlign", "SpaceAfter": 7}),
        Style("Figure", based_on="Body",
              attrs={"FirstLineIndent": 0, "Justification": "CenterAlign", "SpaceBefore": 7,
                     "SpaceAfter": 4})]
    doc.stories = [Story([
        Paragraph("Chapter Title", [Run("Images")]),
        Paragraph("Body First", [Run(filler(80, 0))]),
        Paragraph("Figure", [Run(image=Image(SAMPLE_IMAGE, width=162))]),
        Paragraph("Caption", [Run("Figure 1. An inline image, anchored in the text.")]),
        Paragraph("Body", [Run(filler(400, 1))])], [0, 1], sink=72)]
    top, left, _b, _r = area(doc, "verso")
    doc.images = [PlacedImage(1, top + 120, left, Image(SAMPLE_IMAGE, width=144),
                              wrap=(6, 6, 6, 9))]
    return doc


def g12_character_styles():
    """Character styles that set one thing each, inside different paragraph styles, and one
    local italic, as reference 12."""
    doc = base_doc(1, "g12-character-styles")
    doc.paragraph_styles += [
        Style("Block Quote", based_on="Body", leading=12,
              attrs={"PointSize": 9.5, "LeftIndent": 18, "FirstLineIndent": 0, "SpaceBefore": 6,
                     "SpaceAfter": 6}),
        Style("Sans Heading", based_on="Heading A", font="Myriad Pro",
              attrs={"FontStyle": "Bold"})]
    doc.character_styles += [Style("Bold", attrs={"FontStyle": "Bold"}),
                             Style("Bold Italic", attrs={"FontStyle": "Bold Italic"}),
                             Style("Small Caps", attrs={"Capitalization": "SmallCaps"}),
                             Style("Superscript", attrs={"Position": "Superscript"}),
                             Style("Underline", attrs={"Underline": True}),
                             Style("No Break", attrs={"NoBreak": True})]
    runs = lambda: [Run("Body text with "), Run("italic", "Italic"), Run(", "), Run("bold", "Bold"),
                    Run(", "), Run("bold italic", "Bold Italic"), Run(", "),
                    Run("Small Caps", "Small Caps"), Run(", a superscript"),
                    Run("12", "Superscript"), Run(", "), Run("underline", "Underline"),
                    Run(" and "), Run("a phrase that must not break", "No Break"), Run(". ")]
    doc.stories = [Story([
        Paragraph("Chapter Title", [Run("Character Styles")]),
        Paragraph("Body First", runs() + [Run(filler(50, 0))]),
        Paragraph("Block Quote", [Run("The same in a smaller paragraph style: ")] + runs()),
        Paragraph("Sans Heading", [Run("In a sans heading: "), Run("italic", "Italic"),
                                   Run(" and "), Run("Small Caps", "Small Caps")]),
        Paragraph("Body", [Run("Local "), Run("italic", attrs={"FontStyle": "Italic"}),
                           Run(" override (no character style) in this sentence.")])],
        [0], sink=72)]
    return doc


def g13_chapter_stories():
    """One story per chapter on B-Opener pages; chapter one overset; a blank verso with no
    master; chapter two on its own page, as reference 13."""
    doc = base_doc(6, "g13-chapter-stories")
    doc.masters = [Master("A", "Body"), Master("B", "Opener", based_on="A-Body")]
    doc.page_masters = {0: "B-Opener", 3: "", 4: "B-Opener"}
    doc.stories = [
        Story([Paragraph("Chapter Title", [Run("Chapter One (overset)")]),
               Paragraph("Body First", [Run(filler(1500, 0))])], [0, 1, 2], sink=144),
        Story([Paragraph("Chapter Title", [Run("Chapter Two")]),
               Paragraph("Body First", [Run(filler(500, 1))])], [4, 5], sink=144)]
    return doc


FILES = [("g01-footnotes", g01_footnotes), ("g02-section-marker-heads", g02_section_marker_heads),
         ("g03-section-numbering", g03_section_numbering),
         ("g04-parent-child-masters", g04_parent_child_masters),
         ("g05-primary-text-frame", g05_primary_text_frame), ("g06-toc", g06_toc),
         ("g07-table", g07_table), ("g08-opentype", g08_opentype),
         ("g09-baseline-grid", g09_baseline_grid), ("g10-hebrew-greek", g10_hebrew_greek),
         ("g11-images", g11_images), ("g12-character-styles", g12_character_styles),
         ("g13-chapter-stories", g13_chapter_stories)]


def main():
    from idml_check import check
    from ectype_idml.idml.writer import export_book
    os.makedirs(OUT, exist_ok=True)
    bad = 0
    jobs = [(name, build, None) for name, build in FILES if name != "g11-images"]
    # Images as an export folder of its own with a Links folder, linked relative to the IDML.
    jobs += [("g11-images", g11_images, True)]
    for name, build, relative in jobs:
        if relative is None:
            path = write_idml(build(), os.path.join(OUT, name + ".idml"))
        else:
            path = export_book(build(), OUT, name, relative_links=relative)
        probs = check(path)
        print("%s: %s" % (name, "OK" if not probs else "%d problem(s)" % len(probs)))
        for p in probs[:20]:
            print("  - " + p[:300])
        bad += bool(probs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
