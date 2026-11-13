"""The .docx reader: styles, paragraphs, notes, sections, fields, scripts, unsupported items."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_builder import (endnote_ref, field, footnote_ref, image, make_docx, para, run,
                          run_tests, section_break, textbox)
from ectype_idml.docx_reader import DocxError, read_docx

TMP = tempfile.mkdtemp()


def build(name, body, **kw):
    return read_docx(make_docx(os.path.join(TMP, name), body, **kw))


def test_styles_and_paragraphs():
    doc = build("a.docx", [para("Chapter One", "Heading1"), para("Plain text here."),
                           para("A quote.", "Quote")])
    assert [p.text for p in doc.paragraphs] == ["Chapter One", "Plain text here.", "A quote."]
    assert doc.para_style(doc.paragraphs[1]) == "Normal"
    assert doc.styles["Heading1"].outline_level == 0
    assert doc.styles["Heading1Char"].linked == "Heading1"
    assert doc.style_chain("ChapterHead") == ["ChapterHead", "Heading1", "Normal"]
    assert doc.resolve_font("Normal") == "Calibri"
    assert doc.resolve_font("Heading1") == "Calibri Light"
    assert doc.resolve_size("Heading1") == 16
    assert doc.resolve_size("Normal") == 12


def test_notes_counted():
    doc = build("n.docx", [para(run("Text") + footnote_ref(1) + run(" more") + footnote_ref(2)),
                           para(run("End") + endnote_ref(1))],
                footnotes=["First note.", "Second note."], endnotes=["An endnote."])
    assert doc.footnote_count == 2 and doc.endnote_count == 1
    assert doc.paragraphs[0].footnotes == 2 and doc.paragraphs[1].endnotes == 1
    assert [p.text for p in doc.note_paragraphs] == ["First note.", "Second note.", "An endnote."]
    assert doc.note_paragraphs[0].where == "footnote"


def test_sections():
    doc = build("s.docx", [para("Front"), section_break("oddPage"), para("Chapter")])
    assert len(doc.sections) == 2
    # The first section ends at the break paragraph; the final one is the body's sectPr.
    assert doc.sections[0].page_width == 6.0 and doc.sections[1].page_width == 8.5
    assert doc.sections[1].margins["top"] == 1.0
    assert doc.paragraphs[1].ends_section and doc.paragraphs[2].section == 1


def test_fields():
    doc = build("f.docx", [para(field('TOC \\o "1-3" \\h', "Chapter One 1"), "TOC1"),
                           para(run("Grace") + field('XE "grace"')),
                           para(run("See ") + field("DOCPROPERTY Title", "My Book")),
                           para(field("PAGE", "3"))])
    codes = [f.code for f in doc.fields]
    assert codes == ["TOC", "XE", "DOCPROPERTY", "PAGE"]
    assert doc.paragraphs[0].in_toc_field
    kinds = [i.kind for i in doc.items]
    assert kinds == ["index entry (XE)", "field"], kinds
    assert doc.items[0].detail == '"grace"'
    # The displayed result of a field stays in the text.
    assert doc.paragraphs[2].text == "See My Book"


def test_text_box_not_in_body():
    doc = build("t.docx", [para(run("Before") + textbox("Boxed text")), para("After")])
    assert [p.text for p in doc.paragraphs] == ["Before", "After"]
    assert [(i.kind, i.snippet) for i in doc.items] == [("text box", "Before")]


def test_tracked_changes():
    ins = '<w:ins w:id="1" w:author="Ed">%s</w:ins>' % run(" added")
    dele = ('<w:del w:id="2" w:author="Ed"><w:r><w:delText>removed</w:delText></w:r></w:del>')
    doc = build("c.docx", [para(run("Kept") + ins + dele)])
    assert doc.paragraphs[0].text == "Kept added"
    assert sorted(i.detail for i in doc.items) == ["deletion", "insertion"]


def test_images_and_shapes():
    doc = build("i.docx", [para(image()), para(image(floating=True)),
                           para('<m:oMath><m:r><m:t>x</m:t></m:r></m:oMath>')])
    assert doc.images == 2
    assert [i.kind for i in doc.items] == ["floating image", "equation"]


def test_scripts():
    heb = run("בְּרֵאשִׁית", '<w:rFonts w:cs="SBL Hebrew"/><w:rtl/>')
    grk = run("ἐν ἀρχῇ", '<w:rFonts w:ascii="SBL Greek" w:hAnsi="SBL Greek"/>')
    doc = build("h.docx", [para(run("Genesis 1:1 ") + heb), para(run("John 1:1 ") + grk)])
    h, g = doc.scripts["hebrew"], doc.scripts["greek"]
    assert h.runs == 1 and h.points and h.rtl_marked == 1 and h.fonts["SBL Hebrew"] == 1
    assert g.runs == 1 and g.polytonic and g.fonts["SBL Greek"] == 1
    # A font set for Hebrew in the script slot is not a direct-formatting hotspot.
    assert doc.paragraphs[0].direct_font == []
    assert doc.paragraphs[1].direct_font == [["rFonts"]]


def test_direct_formatting():
    doc = build("d.docx", [para(run("Ital", "<w:i/>") + run("Big", '<w:sz w:val="40"/>')
                                + run("norm"), ppr='<w:jc w:val="center"/>')])
    p = doc.paragraphs[0]
    assert p.direct_emphasis == 1 and p.direct_font == [["sz"]]
    assert p.direct_layout == ["jc"] and p.run_count == 3


def test_header_styleref_and_props():
    hdr = para(field('STYLEREF "Chapter Head" \\* MERGEFORMAT', "Chapter"))
    doc = build("p.docx", [para("Text")], header=hdr,
                core={"title": "The Book", "creator": "Office User"}, app={"Pages": 12, "Words": 3456})
    assert doc.styleref == ["Chapter Head"]
    assert doc.core == {"title": "The Book", "creator": "Office User"}
    assert doc.app == {"pages": 12, "words": 3456}


def test_not_a_docx():
    bad = os.path.join(TMP, "bad.docx")
    with open(bad, "w") as f:
        f.write("not a zip")
    try:
        read_docx(bad)
    except DocxError as e:
        assert "bad.docx" in str(e)
    else:
        raise AssertionError("expected DocxError")


if __name__ == "__main__":
    run_tests(globals())
