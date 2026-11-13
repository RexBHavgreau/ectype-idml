"""The IDML writer: the generator's feature files validate and match the InDesign references."""

import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lxml import etree

from docx_builder import run_tests
from ectype_idml.idml.model import Document, Paragraph, Run, Section, Story, Style
from ectype_idml.idml.writer import Writer, export_book, roman, write_idml
from idml_check import check, schema_available
from idml_inspect import inspect
import make_generated_files as gen
from make_generated_files import (g01_footnotes, g02_section_marker_heads,
                                  g03_section_numbering, g04_parent_child_masters)

TMP = tempfile.mkdtemp()


def test_roman_and_page_names():
    assert [roman(n) for n in (1, 4, 9, 14, 40, 1999)] == ["i", "iv", "ix", "xiv", "xl", "mcmxcix"]
    doc = Document(page_count=9, sections=[Section(0, numbering="LowerRoman", start=1),
                                           Section(7, start=1)])
    assert Writer(doc)._page_names() == ["i", "ii", "iii", "iv", "v", "vi", "vii", "1", "2"]
    doc = Document(page_count=5, sections=[Section(0), Section(3, marker="Two")])
    assert Writer(doc)._page_names() == ["1", "2", "3", "4", "5"]


def test_spreads():
    assert Writer(Document(page_count=5))._spreads() == [[0], [1, 2], [3, 4]]
    assert Writer(Document(page_count=4))._spreads() == [[0], [1, 2], [3]]
    assert Writer(Document(page_count=2, facing=False))._spreads() == [[0], [1]]
    # As InDesign does it (reference 03): front matter ends on vii (recto), chapter 1 restarts
    # at 1, also a recto, so it stands alone and page 2 starts the next spread.
    doc = Document(page_count=9, sections=[Section(0, numbering="LowerRoman", start=1),
                                           Section(7, start=1)])
    assert Writer(doc)._spreads() == [[0], [1, 2], [3, 4], [5, 6], [7], [8]]


def test_sections_and_spreads_as_indesign_writes_them():
    """Rules read from reference files 02, 03 and 13 (g01's first version broke them and
    InDesign wouldn't open it)."""
    doc = Document(page_count=7, sections=[Section(0, marker="One"), Section(2, marker="Two"),
                                           Section(4, marker="Three")])
    doc.stories = [Story([Paragraph("Body", [Run("x")])], [0])]
    doc.paragraph_styles = [Style("Body")]
    path = write_idml(doc, os.path.join(TMP, "sections.idml"))
    z = zipfile.ZipFile(path)
    dm = etree.fromstring(z.read("designmap.xml"))
    secs = [(s.get("Length"), s.get("AlternateLayoutLength"), s.get("AlternateLayout"))
            for s in dm.iter("Section")]
    assert secs == [("2", "7", "Custom V"), ("2", "5", ""), ("3", "3", "")], secs
    spreads = sorted((etree.fromstring(z.read(n)).find("Spread") for n in z.namelist()
                      if n.startswith("Spreads/")),
                     key=lambda sp: float(sp.get("ItemTransform").split()[5]))
    assert [(sp.get("PageCount"), sp.get("BindingLocation")) for sp in spreads] == \
        [("1", "0"), ("2", "1"), ("2", "1"), ("2", "1")]
    doc.page_count = 6
    doc.sections = [Section(0)]
    z = zipfile.ZipFile(write_idml(doc, os.path.join(TMP, "lone-verso.idml")))
    spreads = sorted((etree.fromstring(z.read(n)).find("Spread") for n in z.namelist()
                      if n.startswith("Spreads/")),
                     key=lambda sp: float(sp.get("ItemTransform").split()[5]))
    assert (spreads[-1].get("PageCount"), spreads[-1].get("BindingLocation")) == ("1", "1")


def test_designmap_keeps_aid_instruction():
    path = write_idml(g01_footnotes(), os.path.join(TMP, "aid.idml"))
    head = zipfile.ZipFile(path).read("designmap.xml")[:200]
    assert head.startswith(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    assert b'<?aid style="50" type="document"' in head


def test_pages_per_document_stays_one():
    """InDesign added pages at the start when PagesPerDocument was the real page count."""
    path = write_idml(g01_footnotes(), os.path.join(TMP, "ppd.idml"))
    prefs = etree.fromstring(zipfile.ZipFile(path).read("Resources/Preferences.xml"))
    assert prefs.find("DocumentPreference").get("PagesPerDocument") == "1"
    # Pages added by Smart Text Reflow come two at a time: rectos (and openers) stay rectos.
    tp = prefs.find("TextPreference")
    assert tp.get("PreserveFacingPageSpreads") == "true" and tp.get("SmartTextReflow") == "true"


def test_g01_validates():
    path = write_idml(g01_footnotes(), os.path.join(TMP, "g01.idml"))
    why = schema_available()
    assert check(path, schema=why is None) == []
    if why:
        print("     (structure only: %s)" % why)


def test_g01_matches_reference():
    path = write_idml(g01_footnotes(), os.path.join(TMP, "g01b.idml"))
    info = inspect(path)
    assert [(p["name"], p["side"], p["master"]) for p in info["pages"]] == [
        ("1", "recto", "A-Body"), ("2", "verso", "A-Body"), ("3", "recto", "A-Body"),
        ("4", "verso", "A-Body")]
    assert [(s["start_page"], s["marker"], s["continue_numbering"]) for s in info["sections"]] == \
        [("1", "First Chapter", "true"), ("3", "Second Chapter", "true")]
    stories = [s for s in info["stories"] if s.get("footnotes")]
    assert sorted(s["footnotes"] for s in stories) == [2, 4]
    assert all(s["special_characters"] == {"footnote number": s["footnotes"]} for s in stories)
    first = [s for s in stories if s["footnotes"] == 4][0]
    assert [(f["page"]) for f in first["frames"]] == ["1", "2"]
    assert first["character_styles"] == {"Footnote Reference": 4, "Italic": 1}
    fo = info["preferences"]["FootnoteOption"]
    assert fo["FootnoteTextStyle"] == "Footnote" and fo["FootnoteMarkerStyle"] == "Footnote Reference"
    assert fo["RestartNumbering"] == "SectionRestart" and fo["RuleOn"] == "false"


def test_footnote_structure():
    """As decided (PLAN.md): number in its own run; Footnote settings on every note run."""
    path = write_idml(g01_footnotes(), os.path.join(TMP, "g01c.idml"))
    z = zipfile.ZipFile(path)
    notes = []
    for n in z.namelist():
        if n.startswith("Stories/"):
            notes += list(etree.fromstring(z.read(n)).iter("Footnote"))
    assert len(notes) == 6
    for fn in notes:
        psr = fn.find("ParagraphStyleRange")
        assert psr.get("AppliedParagraphStyle") == "ParagraphStyle/Footnote"
        runs = psr.findall("CharacterStyleRange")
        assert len(runs) >= 2
        first = runs[0].find("Content")
        assert isinstance(first[0], etree._ProcessingInstruction) and first[0].text == "4"
        assert first[0].tail == ". "
        for r in runs:
            assert r.get("PointSize") == "9" and r.get("FirstLineIndent") == "9"
            assert r.find("Properties/AppliedFont").text == "Arno Pro"
            assert r.find("Properties/Leading").text == "11"
    italic = [r for fn in notes for r in fn.iter("CharacterStyleRange")
              if r.get("AppliedCharacterStyle") == "CharacterStyle/Italic"]
    assert len(italic) == 1
    assert italic[0].get("FontStyle") is None      # the Italic style's own face shows


def test_note_runs_keep_character_style_settings():
    """The Footnote style's settings go on note runs, but not those the run's character style
    sets: written locally they would override it (italic lost in notes)."""
    doc = g01_footnotes()
    doc.style("Footnote").attrs["FontStyle"] = "Regular"     # as the exporter's Footnote
    doc.character_styles.append(Style("Greek", font="SBL Greek",
                                      attrs={"AppliedLanguage": "$ID/Greek"}))
    doc.stories[0].paragraphs[1].runs[1].footnote[0].runs.append(Run(" \u03bb\u03cc\u03b3\u03bf\u03c2", "Greek"))
    path = write_idml(doc, os.path.join(TMP, "g01n.idml"))
    z = zipfile.ZipFile(path)
    runs = [r for n in z.namelist() if n.startswith("Stories/")
            for fn in etree.fromstring(z.read(n)).iter("Footnote")
            for r in fn.iter("CharacterStyleRange")]
    by = {r.get("AppliedCharacterStyle"): r for r in runs}
    italic, greek = by["CharacterStyle/Italic"], by["CharacterStyle/Greek"]
    assert italic.get("FontStyle") is None and italic.get("PointSize") == "9"
    assert greek.find("Properties/AppliedFont") is None and greek.get("FontStyle") == "Regular"
    plain = [r for r in runs if r.get("AppliedCharacterStyle") == "CharacterStyle/$ID/[No character style]"]
    assert all(r.get("FontStyle") == "Regular" for r in plain)


def test_footnote_options_from_profile():
    doc = g01_footnotes()
    doc.footnotes.update(rule=True, continuation_rule=False, space_above=18, rule_length=50,
                         numbering="continuous")
    w = Writer(doc)
    w.prefs = etree.parse(os.path.join(ROOT, "ectype_idml", "idml", "base", "Resources",
                                       "Preferences.xml")).getroot()
    w._write_preferences()
    fo = w.prefs.find("FootnoteOption")
    assert (fo.get("RuleOn"), fo.get("ContinuingRuleOn"), fo.get("Spacer"), fo.get("RuleWidth"),
            fo.get("FootnoteMinimumFirstBaselineOffset")) == ("true", "false", "18", "50", "17")
    assert fo.find("Properties/RestartNumbering").text == "DontRestart"


def test_g02_g03_g04_validate():
    why = schema_available()
    for build in (g02_section_marker_heads, g03_section_numbering, g04_parent_child_masters):
        path = write_idml(build(), os.path.join(TMP, build.__name__ + ".idml"))
        assert check(path, schema=why is None) == [], build.__name__


def test_running_heads():
    """g02: master frames carry the page number and section marker, as reference 02."""
    info = inspect(write_idml(g02_section_marker_heads(), os.path.join(TMP, "g02.idml")))
    assert [(m["name"], len(m["text_frames"])) for m in info["masters"]] == [("A-Body", 2)]
    heads = [s["special_characters"] for s in info["stories"] if s.get("special_characters")]
    assert sorted(heads, key=len) == [{"current page number": 1},
                                      {"current page number": 1, "section marker": 1}]
    assert [s["marker"] for s in info["sections"]] == [
        "First Chapter", "Second Chapter", "A Third Chapter with a Much Longer Title Than the Others"]


def test_masters_based_on_and_removed_items():
    """g04: B-Opener based on A-Body removes A's heads (OverrideList "<id> n"), as reference 04;
    master frames allow overrides."""
    path = write_idml(g04_parent_child_masters(), os.path.join(TMP, "g04.idml"))
    info = inspect(path)
    ms = {m["name"]: m for m in info["masters"]}
    assert ms["B-Opener"]["based_on"] == ["A-Body"]
    a_ids = {f["id"] for f in ms["A-Body"]["text_frames"]}
    assert set(ms["B-Opener"]["parent_items_removed"]) == a_ids and len(a_ids) == 2
    assert [p["master"] for p in info["pages"]] == ["B-Opener", "A-Body", "A-Body", "A-Body",
                                                    "B-Opener", "A-Body"]
    z = zipfile.ZipFile(path)
    for n in z.namelist():
        if n.startswith("MasterSpreads/"):
            for tf in etree.fromstring(z.read(n)).iter("TextFrame"):
                assert tf.get("AllowOverrides") == "true"


def test_no_master_and_roman_pages():
    """g03: display and blank masters, roman front matter, chapter 1 alone on a recto."""
    info = inspect(write_idml(g03_section_numbering(), os.path.join(TMP, "g03.idml")))
    assert [(p["name"], p["side"]) for p in info["pages"]][5:] == [
        ("vi", "verso"), ("vii", "recto"), ("1", "recto"), ("2", "verso")]
    assert [(m["name"], m["based_on"]) for m in info["masters"]] == [
        ("A-Body", None), ("C-Front", ["A-Body"]), ("D-Display", None), ("E-Blank", None)]


def test_all_generated_files_validate():
    why = schema_available()
    for name, build in gen.FILES:
        path = write_idml(build(), os.path.join(TMP, name + ".idml"))
        assert check(path, schema=why is None) == [], name


def _parts(doc, name):
    z = zipfile.ZipFile(write_idml(doc, os.path.join(TMP, name)))
    return z, {n: etree.fromstring(z.read(n)) for n in z.namelist() if n.endswith(".xml")}


def test_primary_frame_and_linked_pages():
    """g05: master frames threaded verso -> recto, the verso primary; every page frame linked to
    the master frame of its side by an OverrideList pair (reference 05, version 3)."""
    _z, parts = _parts(gen.g05_primary_text_frame(), "g05.idml")
    ms = [r.find("MasterSpread") for n, r in parts.items() if n.startswith("MasterSpreads/")][0]
    verso, recto = ms.findall("TextFrame")
    assert ms.get("PrimaryTextFrame") == verso.get("Self")
    assert verso.get("NextTextFrame") == recto.get("Self")
    assert recto.get("PreviousTextFrame") == verso.get("Self")
    info = inspect(_z.filename)
    for p in info["pages"]:
        assert [o["master_item"] for o in p["overrides"]] == [
            recto.get("Self") if p["side"] == "recto" else verso.get("Self")]
    story = [s for s in info["stories"] if s["start"]][0]
    assert [f["id"] for f in story["frames"]] == [o["page_item"] for p in info["pages"]
                                                  for o in p["overrides"]]


def test_table():
    """g07: 41 rows, 4 columns, cells named column:row, one cell spanning two columns (the cell
    it covers left out), header row, table and cell styles, the grey swatch."""
    _z, parts = _parts(gen.g07_table(), "g07.idml")
    table = [t for n, r in parts.items() if n.startswith("Stories/") for t in r.iter("Table")][0]
    assert (table.get("HeaderRowCount"), table.get("BodyRowCount"), table.get("ColumnCount")) == \
        ("1", "40", "4")
    cells = table.findall("Cell")
    assert len(cells) == 41 * 4 - 1
    assert cells[0].get("Name") == "0:0" and cells[1].get("Name") == "1:0"
    merged = [c for c in cells if c.get("ColumnSpan") == "2"]
    assert [c.get("Name") for c in merged] == ["2:5"]
    assert "3:5" not in [c.get("Name") for c in cells]
    assert table.get("AppliedTableStyle") == "TableStyle/Book Table"
    # Row heights, which Affinity needs to break a table across frames (it ran off the page
    # without them); estimated within a point of InDesign's for reference 07.
    heights = [float(r.get("SingleRowHeight")) for r in table.findall("Row")]
    assert abs(heights[0] - 12.44) < 1 and abs(heights[7] - 48.44) < 1
    assert abs(sum(heights) - 690.1) < 10
    graphic = parts["Resources/Graphic.xml"]
    grey = [c for c in graphic.iter("Color") if c.get("Name") == "Table Grey"][0]
    assert grey.get("ColorValue") == "0 0 0 12"
    refs = [s.get("SwatchItemRef") for s in parts["designmap.xml"].iter("ColorGroupSwatch")]
    assert "Color/Table Grey" in refs


def test_toc_grid_language_and_optical_margins():
    _z, parts = _parts(gen.g06_toc(), "g06.idml")
    toc = [t for t in parts["Resources/Styles.xml"].iter("TOCStyle") if t.get("Name") == "Contents"][0]
    assert [(e.get("Name"), e.get("Level")) for e in toc.findall("TOCStyleEntry")] == [
        ("Chapter Title", "1"), ("Heading A", "2")]
    _z, parts = _parts(gen.g09_baseline_grid(), "g09.idml")
    gp = parts["Resources/Preferences.xml"].find("GridPreference")
    assert (gp.get("BaselineStart"), gp.get("BaselineDivision"), gp.get("BaselineGridShown")) == \
        ("54", "14", "true")
    _z, parts = _parts(gen.g10_hebrew_greek(), "g10.idml")
    heb = [s for s in parts["Resources/Styles.xml"].iter("CharacterStyle") if s.get("Name") == "Hebrew"][0]
    assert heb.get("AppliedLanguage") == "$ID/Hebrew"
    assert heb.get("CharacterDirection") == "RightToLeftDirection"
    _z, parts = _parts(gen.g08_opentype(), "g08.idml")
    prefs = [r.find("Story/StoryPreference") for n, r in parts.items() if n.startswith("Stories/")]
    assert any(p.get("OpticalMarginAlignment") == "true" and p.get("OpticalMarginSize") == "11"
               for p in prefs)


def test_image_info():
    import struct, zlib
    from ectype_idml.idml.images import image_info
    assert image_info(gen.SAMPLE_IMAGE) == (450, 300, 150.0, 150.0, "JPEG")
    # A 3 x 2 px PNG at 300 ppi (11811 px per metre), built by hand.
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 3, 2, 8, 2, 0, 0, 0))
           + chunk(b"pHYs", struct.pack(">IIB", 11811, 11811, 1))
           + chunk(b"IDAT", zlib.compress(b"\x00" + b"\x00" * 9 + b"\x00" + b"\x00" * 9))
           + chunk(b"IEND", b""))
    path = os.path.join(TMP, "t.png")
    with open(path, "wb") as f:
        f.write(png)
    w, h, x, y, fmt = image_info(path)
    assert (w, h, fmt) == (3, 2, "PNG") and abs(x - 300) < 0.1


def test_images():
    """g11: an anchored image in the text and a placed one with a text wrap, sized and scaled as
    in reference 11; the image copied to Links/ beside the IDML and linked there."""
    out = os.path.join(TMP, "g11dir")
    os.makedirs(out, exist_ok=True)
    path = write_idml(gen.g11_images(), os.path.join(out, "g11.idml"))
    assert os.path.exists(os.path.join(out, "Links", "sample.jpg"))
    z = zipfile.ZipFile(path)
    roots = {n: etree.fromstring(z.read(n)) for n in z.namelist() if n.endswith(".xml")}
    anchored = [r for n, root in roots.items() if n.startswith("Stories/") for r in root.iter("Rectangle")]
    placed = [r for n, root in roots.items() if n.startswith("Spreads/") for r in root.iter("Rectangle")]
    assert len(anchored) == 1 and len(placed) == 1
    assert anchored[0].find("AnchoredObjectSetting").get("AnchoredPosition") == "InlinePosition"
    assert placed[0].find("TextWrapPreference").get("TextWrapMode") == "BoundingBoxTextWrap"
    for rect, scale in ((anchored[0], "0.75"), (placed[0], "0.6667")):
        img = rect.find("Image")
        assert img.get("ItemTransform").startswith(scale + " 0 0 " + scale)
        assert img.find("Properties/GraphicBounds").get("Right") == "216"
        uri = img.find("Link").get("LinkResourceURI")
        assert uri == "file:Links/sample.jpg"
    assert check(path, schema=schema_available() is None) == []


def test_export_folder():
    """An export is a folder of its own: the IDML and a Links folder with the images, linked
    relative to the IDML (decided October 21); full paths as an option."""
    path = export_book(gen.g11_images(), TMP, "My Book")
    folder = os.path.join(TMP, "My Book")
    assert path == os.path.join(folder, "My Book.idml")
    assert sorted(os.listdir(folder)) == ["Links", "My Book.idml"]
    assert os.listdir(os.path.join(folder, "Links")) == ["sample.jpg"]
    full = export_book(gen.g11_images(), TMP, "Full", relative_links=False)
    uris = {l.get("LinkResourceURI") for n in zipfile.ZipFile(full).namelist() if n.endswith(".xml")
            for l in etree.fromstring(zipfile.ZipFile(full).read(n)).iter("Link")}
    assert len(uris) == 1 and uris.pop().endswith("/Full/Links/sample.jpg")


def test_text_details():
    doc = Document(page_count=1)
    doc.paragraph_styles = [Style("Body", font="Arno Pro", leading=14, attrs={"PointSize": 11})]
    doc.stories = [Story([Paragraph("Body", [Run("Line one\nline two\tand <tab> & more")]),
                          Paragraph("Body", [Run("Last", attrs={"FontStyle": "Italic"})])], [0])]
    path = write_idml(doc, os.path.join(TMP, "text.idml"))
    assert check(path, schema=schema_available() is None) == []
    z = zipfile.ZipFile(path)
    story = [etree.fromstring(z.read(n)) for n in z.namelist() if n.startswith("Stories/")][0]
    contents = [c.text for c in story.iter("Content")]
    assert contents == ["Line one line two\tand <tab> & more", "Last"]
    assert len(list(story.iter("Br"))) == 1
    assert [c.get("FontStyle") for c in story.iter("CharacterStyleRange")] == [None, "Italic"]


if __name__ == "__main__":
    run_tests(globals())
