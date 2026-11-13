"""The outline across several files, and the style map."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_builder import field, footnote_ref, make_docx, para, run, run_tests, section_break
from ectype_idml.docx_reader import read_docx
from ectype_idml.outline import build_outline, classify
from ectype_idml.stylemap import StyleMap, display_name

TMP = tempfile.mkdtemp()


def doc(name, body, **kw):
    return read_docx(make_docx(os.path.join(TMP, name), body, **kw))


def book():
    front = doc("00 Front.docx", [
        para("The Covenant", "Title"), para("A Study", "Subtitle"), para("by Jane Smith"),
        para("© 2026 Jane Smith. All rights reserved."),
        para("Preface", "Heading1"), para("Why this book. " * 10)])
    ch1 = doc("Chapter 1.docx", [
        para("Part One", "Heading1"),
        para("Beginnings", "ChapterHead"), para("Some text" + "", None),
        para(run("Noted") + footnote_ref(1)), para("First section", "Heading2"),
        para("More text."), para("Second section", "Heading2")], footnotes=["A note."])
    ch2 = doc("Chapter 2.docx", [
        para("A stray opening line."),
        para("Endings", "Heading1"), para("Text.")])
    back = doc("Back.docx", [para("Bibliography", "Heading1"), para("Smith, J. 2020.")])
    return [front, ch1, ch2, back]


def test_outline_across_files():
    out = build_outline(book())
    got = [(u.kind, u.type, u.title, u.file) for u in out.units]
    assert got == [
        ("display", "title page", "(title page)", "00 Front.docx"),
        ("front", "preface", "Preface", "00 Front.docx"),
        ("part", "part", "Part One", "Chapter 1.docx"),
        ("chapter", "chapter", "Beginnings", "Chapter 1.docx"),
        ("chapter", "chapter", "Endings", "Chapter 2.docx"),
        ("back", "bibliography", "Bibliography", "Back.docx"),
    ], got
    ch = out.units[3]
    assert ch.subheads == ["First section", "Second section"]
    assert ch.note_refs == 1
    assert "style Chapter Head (based on Heading 1)" == ch.detected_by
    assert out.title == "The Covenant" and out.subtitle == "A Study"
    assert out.author == "Jane Smith" and out.author_source == "title page text"
    assert out.copyright_found
    assert out.first_heading == {"00 Front.docx": "Preface", "Chapter 1.docx": "Part One",
                                 "Chapter 2.docx": "Endings", "Back.docx": "Bibliography"}
    # Text before the first heading of a later file stays with the previous unit, with a note.
    assert any("Chapter 2.docx starts with 1 paragraph of" in n for n in out.notes), out.notes
    assert out.present() >= {"title page", "copyright", "preface"}


def test_classify():
    assert classify("PREFACE", False) == ("front", "preface")
    assert classify("Preface", True) == ("chapter", "chapter")      # front names only up front
    assert classify("Notes:", True) == ("back", "notes")
    assert classify("Appendix B: Tables", True) == ("back", "appendix")
    assert classify("Part II", False) == ("part", "part")
    assert classify("Parte primera", False) == ("part", "part")
    assert classify("Party Politics", False) == ("chapter", "chapter")
    assert classify("Índice", False) == ("front", "contents")
    assert classify("Índice", True) == ("back", "index")
    assert classify("Agradecimientos", False) == ("front", "acknowledgments")


def test_profile_map_overrides():
    # A manuscript using Heading 1 for parts and Heading 2 for chapters.
    d = doc("h.docx", [para("Part One", "Heading1"), para("Chapter A", "Heading2"),
                       para("Text"), para("Chapter B", "Heading2")])
    sm = StyleMap({"Heading 1": {"idml": "Part Title", "role": "part"},
                   "heading 2": {"idml": "Chapter Title", "role": "chapter"}})
    out = build_outline([d], sm)
    assert [(u.kind, u.title) for u in out.units] == [
        ("part", "Part One"), ("chapter", "Chapter A"), ("chapter", "Chapter B")]


def test_fallback_styleref():
    hdr = para(field('STYLEREF "Fancy Para"', "x"))
    d = doc("r.docx", [para("Opening", "Fancy"), para("Text"), para("Second", "Fancy")], header=hdr)
    out = build_outline([d])
    assert [u.title for u in out.units] == ["Opening", "Second"]
    assert out.units[0].detected_by == 'Word running head (STYLEREF "Fancy Para")'


def test_fallback_outline_level():
    d = doc("o.docx", [para("Intro text"), para("Real Chapter", ppr='<w:outlineLvl w:val="0"/>'),
                       para("Text")])
    out = build_outline([d])
    assert [(u.kind, u.title) for u in out.units] == [
        ("display", "(text before the first heading)"), ("chapter", "Real Chapter")]
    assert out.units[1].detected_by == "outline level 1"


def test_fallback_section_breaks_and_whole_file():
    # A section's w:type says how that section starts: the second section starts on a new
    # page, the third runs on (its type is on the body's final sectPr).
    d = doc("s.docx", [para("First Title"), para("text"), section_break("nextPage"),
                       para(""), para("Second Title"), para("text"),
                       section_break("nextPage"), para("Not a title")],
            sect='<w:sectPr><w:type w:val="continuous"/></w:sectPr>')
    w = doc("w.docx", [para(""), para("Lonely Chapter"), para("text")])
    out = build_outline([d, w])
    assert [(u.title, u.detected_by) for u in out.units] == [
        ("First Title", "section break (start of file)"), ("Second Title", "section break"),
        ("Lonely Chapter", "whole file")], [(u.title, u.detected_by) for u in out.units]
    assert any("no recognized headings" in n for n in out.notes)


def test_toc_paragraphs_ignored():
    d = doc("t.docx", [para("Contents", "Heading1"), para(field("TOC \\o", "Chapter One\t1"), "TOC1"),
                       para("Chapter One", "Heading1"), para("Text")])
    out = build_outline([d])
    assert [(u.kind, u.type, u.title) for u in out.units] == [
        ("front", "contents", "Contents"), ("chapter", "chapter", "Chapter One")]
    assert out.toc_field and out.units[0].words == 1


def test_stylemap_mappings():
    d = doc("m.docx", [para("x")])
    sm = StyleMap()
    m = sm.paragraph_style(d, "Fancy")
    assert (m.idml, m.role, m.source, m.warning) == ("Fancy Para", "body", "based on Normal", True)
    m = sm.paragraph_style(d, "PartTitle")
    assert (m.role, m.source) == ("chapter", "outline level 1")
    m = sm.paragraph_style(d, "Heading2")
    assert (m.idml, m.role, m.level) == ("Heading A", "heading", 1)
    m = sm.paragraph_style(d, "TOC1")
    assert m.role == "toc" and m.word == "TOC 1"
    assert sm.character_style(d, "Heading1Char").role == "skip"
    assert sm.character_style(d, "Emphasis").idml == "Italic"
    assert sm.character_style(d, "FootnoteReference").idml == "Footnote Reference"
    assert display_name("footnote text") == "Footnote Text"
    assert display_name("My Style") == "My Style"


def test_endorsements_and_kinds_set_by_user():
    from ectype_idml.outline import KINDS, apply_kinds, classify, kind_key
    for title in ("Endorsements", "Praise for The Covenant Formula", "Advance Praise",
                  "What Others Are Saying", "Elogios"):
        assert classify(title, False) == ("display", "endorsements"), title
    assert classify("Praise for The Covenant Formula", True) == ("chapter", "chapter")
    doc = read_docx(make_docx(os.path.join(TMP, "e.docx"), [para("Praise for This Book", "Heading1"), para("A fine book. -- A."),
                           para("Kind Words", "Heading1"), para("Also fine."),
                           para("Chapter One", "Heading1"), para("Text.")]))
    out = build_outline([doc])
    assert [(u.title, kind_key(u)) for u in out.units] == [
        ("Praise for This Book", "endorsements"), ("Kind Words", "chapter"),
        ("Chapter One", "chapter")]
    apply_kinds(out, {"Kind Words": "endorsements", "Chapter One": "chapter", "x": "bogus"})
    assert (out.units[1].kind, out.units[1].type) == KINDS["endorsements"]
    assert "set in the book settings" in out.units[1].detected_by
    assert "set in the book settings" not in out.units[2].detected_by


def test_text_before_the_title_page_is_endorsements():
    from ectype_idml.outline import kind_key
    # One file: endorsements with no heading, then the title page, then chapters.
    one = read_docx(make_docx(os.path.join(TMP, "pre.docx"), [
        para("\u201cA wonderful book.\u201d \u2014 A. Reader"),
        para("\u201cRead it twice.\u201d \u2014 B. Critic"),
        para("The Covenant Formula", "Title"), para("Studies", "Subtitle"),
        para("by A. N. Author"),
        para("Preface", "Heading1"), para("Text."),
        para("Chapter One", "Heading1"), para("Text.")]))
    out = build_outline([one])
    assert [(u.title, kind_key(u), u.type) for u in out.units] == [
        ("(endorsements)", "endorsements", "endorsements"),
        ("(title page)", "display", "title page"), ("Preface", "front", "preface"),
        ("Chapter One", "chapter", "chapter")]
    assert out.title == "The Covenant Formula" and out.author == "A. N. Author"
    # Two files: a file of endorsements with no headings, then the title page and chapters.
    praise = read_docx(make_docx(os.path.join(TMP, "00 Praise.docx"), [
        para("\u201cA wonderful book.\u201d \u2014 A. Reader"), para("\u201cRead it.\u201d")]))
    book = read_docx(make_docx(os.path.join(TMP, "01 Book.docx"), [
        para("The Covenant Formula", "Title"), para("Preface", "Heading1"), para("Text."),
        para("Chapter One", "Heading1"), para("Text.")]))
    out = build_outline([praise, book])
    assert [(kind_key(u), u.type) for u in out.units] == [
        ("endorsements", "endorsements"), ("display", "title page"), ("front", "preface"),
        ("chapter", "chapter")], [(u.title, u.kind, u.type) for u in out.units]


BODY = "Text of the chapter goes on for a while, and more words follow it here. " * 4


def unstyled_book(name="unstyled.docx"):
    """A manuscript with no heading styles: chapter titles 16 pt bold centered on new pages,
    subheads bold; traps: a bold one-line paragraph, an italic title of a work, and cover
    lines in centered capitals."""
    def chap(t, first=False):
        return para(run(t, '<w:b/><w:sz w:val="32"/>'),
                    ppr='<w:jc w:val="center"/>' + ("" if first else "<w:pageBreakBefore/>"))

    def sub(t):
        return para(run(t, "<w:b/>"))

    def cover(t):
        return para(run(t, "<w:caps/>"), ppr='<w:jc w:val="center"/>')
    body = [cover("A Seminary"), cover("by"), cover("July 2026"),
            chap("Introduction", True), para(BODY), sub("The First Question"), para(BODY),
            para(run("Note well.", "<w:b/>")), para(BODY), sub("A Second Question"), para(BODY),
            chap("The Middle Chapter"), para(BODY), para(run("Biblia Hebraica", "<w:i/>")),
            para(BODY), sub("Another Section"), para(BODY), chap("Conclusion"), para(BODY)]
    return make_docx(os.path.join(TMP, name), body)


def test_headings_found_by_formatting():
    doc = read_docx(unstyled_book())
    sm = StyleMap()
    groups, by_para = sm.format_groups(doc)
    # A single file: the first heading is just the first chapter (no file title line).
    assert [(g.name, g.role, g.level, len(g.paragraphs)) for g in groups] == [
        ("[16 pt bold centered]", "chapter", 0, 3), ("[bold]", "heading", 1, 3)]
    texts = {doc.paragraphs[i].text for i in by_para}
    assert "Note well." not in texts and "Biblia Hebraica" not in texts       # traps
    assert not texts & {"A Seminary", "by", "July 2026"}                       # cover lines
    out = build_outline([doc], sm)
    assert [u.title for u in out.units if u.kind == "chapter"] == [
        "Introduction", "The Middle Chapter", "Conclusion"]
    assert out.units[-1].detected_by == "formatting [16 pt bold centered]"
    assert [u.subheads for u in out.units if u.kind == "chapter"][0] == [
        "The First Question", "A Second Question"]
    # The book's own choice for a group wins.
    sm = StyleMap(formats={"[bold]": {"idml": "Heading B", "role": "heading", "level": 2}})
    p = [p for p in doc.paragraphs if p.text == "Another Section"][0]
    m = sm.paragraph_mapping(doc, p)
    assert (m.idml, m.level, m.source) == ("Heading B", 2, "book")


LONG = ("Over fifty years have now elapsed since the movement began, and the work has grown "
        "in many churches and schools across the country. ")


def front_matter_book():
    """Like a real edited volume sent as files: endorsements, a copyright file, a foreword
    whose first line repeats the book title, a preface with bold subheads, an abbreviations
    list without a title line, and a chapter titled 16 pt bold centered with an author line,
    bold sections and italic subsections. No heading styles anywhere."""
    def bold(t, center=False):
        return para(run(t, "<w:b/>"), ppr='<w:jc w:val="center"/>' if center else "")

    def italic(t):
        return para(run(t, "<w:i/>"))
    title = "A Theology of Soul Care: Essays in Biblical Counseling"
    files = [
        ("00.0 Endorsements - BH.docx", [bold("Endorsements"), para("\u201c" + LONG),
                                          para("\u2014A. Reader, Pastor")]),
        ("00.1 Copyright Information_rk.docx", [
            italic(title), para("Copyright \u00a9 2026 by A Seminary"),
            para("Edited by Nicolas Ellen and Josh Stephens"),
            para("All rights reserved. No part of this publication may be reproduced, stored "
                 "in a retrieval system, or transmitted in any form or by any means."),
            para("ISBN: 978-1-934952-94-8"),
            para("Scripture quotations marked ESV are from the ESV\u00ae Bible, \u00a9 2001 by "
                 "Crossway. Used by permission.")]),
        ("00.2 Foreword by Lance Quinn - BH.docx", [bold(title, True),
                                                    bold("Foreword by Lance Quinn", True),
                                                    para(LONG), para(LONG)]),
        ("00.3 Preface - BH.docx", [bold("PREFACE"), para(LONG), bold("Objectives of This Book"),
                                    para(LONG), bold("Our Prayer"), para(LONG)]),
        ("00.5 Abbreviations.docx", [para("BDAG\tWalter Bauer, A Greek-English Lexicon of the "
                                          "New Testament and Other Early Christian Literature, "
                                          "third edition, Chicago, 2000, and so on."),
                                     para("JETS\tJournal of the Evangelical Theological Society")]),
        ("01 A Biblical Philosophy of Soul Care.docx", [
            para(run("A Biblical Philosophy of Soul Care", '<w:b/><w:sz w:val="32"/>'),
                 ppr='<w:jc w:val="center"/>'),
            para("Nicolas Ellen and Josh Stephens", ppr='<w:jc w:val="center"/>'),
            bold("The Definition of Soul Care"), para(LONG), italic("In the Torah"), para(LONG),
            bold("The Objectives of Soul Care"), para(LONG), italic("In the Prophets"),
            para(LONG)]),
    ]
    return [doc(name, body) for name, body in files]


def test_front_matter_files_by_formatting():
    from ectype_idml.stylemap import StyleMap
    docs = front_matter_book()
    sm = StyleMap()
    out = build_outline(docs, sm)
    got = [(u.kind, u.type, u.title) for u in out.units]
    assert got == [
        ("display", "endorsements", "Endorsements"),
        ("display", "copyright", "A Theology of Soul Care: Essays in Biblical Counseling"),
        ("front", "foreword", "Foreword by Lance Quinn"),
        ("front", "preface", "PREFACE"),
        ("front", "abbreviations", "Abbreviations"),           # from the file's name
        ("chapter", "chapter", "A Biblical Philosophy of Soul Care"),
    ], got
    # Levels across the book: bold is Heading A in the preface and the chapter alike.
    assert out.units[3].subheads == ["Objectives of This Book", "Our Prayer"]
    assert out.units[5].subheads == ["The Definition of Soul Care", "The Objectives of Soul Care"]
    ch = docs[-1]
    m = {p.text: sm.paragraph_mapping(ch, p) for p in ch.paragraphs if p.text.strip()}
    assert (m["In the Torah"].idml, m["Nicolas Ellen and Josh Stephens"].role) == (
        "Heading B", "author")
    # The book: its title opens two files; the editors come from the copyright page; the
    # title repeated at the top of the foreword is left out there.
    assert out.title == "A Theology of Soul Care: Essays in Biblical Counseling"
    assert out.author == "Nicolas Ellen and Josh Stephens"
    assert out.creators == [{"role": "editor", "name": "Nicolas Ellen"},
                            {"role": "editor", "name": "Josh Stephens"},
                            {"role": "foreword", "name": "Lance Quinn"}]   # "Foreword by ..."
    fw = docs[2]
    assert sm.paragraph_mapping(fw, fw.paragraphs[0]).role == "skip"
    assert out.copyright_found
    # The copyright page's details, for Book Details (notices for Bible versions passed over).
    assert out.details == {"year": "2026", "holder": "A Seminary", "notices": [
        "Scripture quotations marked ESV are from the ESV\u00ae Bible, \u00a9 2001 by Crossway. "
        "Used by permission."],
                           "leftover": [], "isbn_print": "978-1-934952-94-8",
                           "rights": "All rights reserved. No part of this publication may be "
                                     "reproduced, stored in a retrieval system, or transmitted "
                                     "in any form or by any means."}


def test_copyright_lines_read():
    from ectype_idml.frontmatter import parse_copyright
    got = parse_copyright([
        "A Theology of Soul Care", "Copyright \u00a9 2026 by Central Baptist Seminary",
        "Published by Kress Biblical Resources", "www.kressbiblical.com",
        "All rights reserved.", "ISBN: 978-1-934952-94-8 (paperback)",
        "ISBN 978-1-934952-95-5 (ebook)",
        "Scripture quotations marked NKJV are taken from the New King James Version\u00ae. "
        "Copyright \u00a9 1982 by Thomas Nelson. Used by permission.",
        "Printed in the United States of America", "First edition"])
    notices = got.pop("notices")
    assert len(notices) == 1 and notices[0].startswith("Scripture quotations marked NKJV")
    assert got == {"year": "2026", "holder": "Central Baptist Seminary",
                   "publisher": "Kress Biblical Resources",
                   "publisher_address": "www.kressbiblical.com",
                   "isbn_print": "978-1-934952-94-8", "isbn_ebook": "978-1-934952-95-5",
                   "printed_in": "the United States of America", "edition": "First edition",
                   "leftover": ["A Theology of Soul Care"]}       # the title (outline drops it)
    # Given the book's title, a line with the title (and subtitle) ticks the copyright title.
    got = parse_copyright(["A Theology of Soul Care: Essays in Biblical Counseling",
                           "\u00a9 2026 A Seminary"],
                          known=("A Theology of Soul Care", "Essays in Biblical Counseling"))
    assert got["copyright_title"] is True and got["leftover"] == []
    assert parse_copyright(["\u00a9 2019 Jane Smith. All rights reserved."]) == {
        "year": "2019", "holder": "Jane Smith", "notices": [], "leftover": []}
    from ectype_idml.frontmatter import notice_name
    assert notice_name(notices[0]) == "NKJV"


def test_styled_manuscript_not_guessed():
    """Headings in styles: nothing is guessed, whatever the formatting."""
    d = doc("styled.docx", [para("One", "Heading1"), para(run("Bold line", "<w:b/>")),
                             para(BODY), para("Two", "Heading2"), para(BODY),
                             para(run("Bold line", "<w:b/>")), para(BODY)])
    assert StyleMap().format_groups(d) == ([], {})


if __name__ == "__main__":
    run_tests(globals())
