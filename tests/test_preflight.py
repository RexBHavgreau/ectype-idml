"""Preflight report, profiles, book file order and the command line."""

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_builder import (table, endnote_ref, field, footnote_ref, make_docx, para, run, run_tests,
                          textbox)
from ectype_idml import profile as profiles
from ectype_idml.book import Book, apply_saved_order, collect, natural_sort
from ectype_idml.cli import main
from ectype_idml.preflight import preflight, render_text

TMP = tempfile.mkdtemp()
os.environ["APPDATA"] = os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "settings")

ORPHAN = ('<w:style w:type="paragraph" w:customStyle="1" w:styleId="Orphan">'
          '<w:name w:val="Orphan"/></w:style>')


def manuscript(folder):
    os.makedirs(folder, exist_ok=True)
    a = make_docx(os.path.join(folder, "Chapter 10.docx"), [
        para("Later Chapter", "Heading1"), para(run("Text") + endnote_ref(1)),
        para("Odd one", "Orphan"), para(run("Grace") + field('XE "grace"'))],
        endnotes=["An endnote."], extra_styles=[ORPHAN])
    b = make_docx(os.path.join(folder, "Chapter 2.docx"), [
        para("Early Chapter", "Heading1"),
        para(run("In the beginning ") + run("בְּרֵאשִׁית", '<w:rFonts w:cs="SBL Hebrew"/><w:rtl/>')
             + footnote_ref(1)),
        para(run("Loud", '<w:rFonts w:ascii="Comic Sans MS" w:hAnsi="Comic Sans MS"/><w:sz w:val="40"/>')),
        para("A quote.", "Quote"), para(run("Box") + textbox("inside"))],
        footnotes=["See ἐν ἀρχῇ."],
        styles={"Quote": '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/>'
                         '<w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'})
    return a, b


def test_report():
    a, b = manuscript(os.path.join(TMP, "ms"))
    rep = preflight([b, a])
    assert [f.name for f in rep.files] == ["Chapter 2.docx", "Chapter 10.docx"]
    assert rep.files[0].first_heading == "Early Chapter" and rep.files[0].footnotes == 1
    styles = {u.word: u for u in rep.paragraph_styles}
    assert styles["Heading 1"].count == 2 and styles["Heading 1"].role == "chapter"
    assert styles["Orphan"].source == "fallback" and styles["Orphan"].warning
    assert styles["Footnote Text"].count == 2       # the footnote and the endnote
    chars = {u.word: u for u in rep.character_styles}
    assert chars["Footnote Reference"].count == 1
    assert rep.direct["hotspot_paragraphs"] == 1
    assert rep.direct["hotspots"][0]["props"] == ["font", "size"]
    assert rep.fonts["body"] == "Calibri" and rep.fonts["template_default"]
    assert rep.fonts["direct"] == {"Comic Sans MS": 1}
    assert rep.scripts["hebrew"]["runs"] == 1 and rep.scripts["greek"]["polytonic"]
    assert set(rep.items) == {"text box", "index entry (XE)", "endnotes"}
    assert [c["style"] for c in rep.conflicts] == ["Quote"]
    diffs = {d["property"]: d["values"] for d in rep.conflicts[0]["differences"]}
    assert diffs["sz"] == {"Chapter 2.docx": "val=20", "Chapter 10.docx": "val=22"}
    assert "ind" in diffs
    w = rep.warnings
    assert w[0].startswith("This book has Hebrew")
    assert w[1].startswith("1 endnote.")
    assert any('Style "Orphan"' in x and "body text" in x for x in w)
    assert any('Style "Quote" is defined differently' in x for x in w)
    assert any(x.startswith("1 text box:") for x in w)
    assert any("Indicat" in x for x in w)
    text = render_text(rep)
    assert "Early Chapter" in text and "Needs attention" in text and "Hebrew:" in text
    data = json.loads(rep.to_json())
    assert data["outline"]["units"][0]["title"] == "Early Chapter"


def test_headings_by_formatting_reported():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_outline import unstyled_book
    rep = preflight([unstyled_book("unstyled-preflight.docx")])
    assert any("Headings set by formatting" in w and "[16 pt bold centered]" in w
               for w in rep.warnings)
    rows = {s.word: s for s in rep.paragraph_styles}
    assert rows["[bold]"].idml == "Heading A" and rows["[bold]"].source == "formatting"
    assert not any("change font, size" in w for w in rep.warnings)   # the headings are expected
    # The sample manuscript has styles: nothing guessed.
    ms = os.path.join(ROOT, "reference", "manuscript")
    rep = preflight(sorted(os.path.join(ms, f) for f in os.listdir(ms)))
    assert rep.guessed_heads == {}


def test_nested_table_reported():
    """A table inside a table keeps its text in the outer cell; preflight says the inner
    table's rows and columns are lost (nothing disappears silently)."""
    inner = table([["inner a", "inner b"]])
    path = make_docx(os.path.join(TMP, "nested.docx"), [
        para("Chapter", "Heading1"),
        table([["outer", inner + para("")]])])
    rep = preflight([path])
    assert any("1 table inside other tables" in w for w in rep.warnings), rep.warnings


def test_bad_file_reported():
    bad = os.path.join(TMP, "broken.docx")
    with open(bad, "w") as f:
        f.write("x")
    rep = preflight([bad])
    assert rep.errors and "broken.docx" in rep.warnings[0]


def test_collect_and_order():
    folder = os.path.join(TMP, "drop")
    manuscript(folder)
    for name in ("~$apter 2.docx", "notes.txt", "old.doc"):
        open(os.path.join(folder, name), "w").close()
    files, skipped = collect([folder])
    assert [os.path.basename(f) for f in files] == ["Chapter 2.docx", "Chapter 10.docx"]
    reasons = {os.path.basename(p): r for p, r in skipped}
    assert reasons == {"~$apter 2.docx": "Word's temporary lock file, not a document",
                       "notes.txt": "not a .docx file",
                       "old.doc": "an older Word file: save it as .docx from Word"}
    again, skipped = collect([files[0]], existing=files)
    assert again == [] and skipped[0][1] == "already in the list"
    assert natural_sort(["c10.docx", "c2.docx", "C1.docx"]) == ["C1.docx", "c2.docx", "c10.docx"]

    bk = Book()
    bk.add([folder])
    bk.move(1, 0)
    path = os.path.join(TMP, "book.json")
    bk.save(path)
    loaded = Book.load(path)
    assert [os.path.basename(f) for f in loaded.files] == ["Chapter 10.docx", "Chapter 2.docx"]
    # A corrected file with the same name keeps its place; a new file goes at the end.
    found = [os.path.join(TMP, "new", n) for n in ("Chapter 2.docx", "Epilogue.docx",
                                                   "Chapter 10.docx")]
    order = apply_saved_order(loaded.files, found)
    assert [os.path.basename(f) for f in order] == ["Chapter 10.docx", "Chapter 2.docx",
                                                    "Epilogue.docx"]


def test_profiles():
    p = profiles.default_profile()
    p["name"] = "Series A"
    p["style_map"]["paragraph"]["Chapter Head"] = {"idml": "Chapter Title", "role": "chapter"}
    profiles.save(p)
    assert profiles.list_profiles() == ["Series A"]
    assert profiles.load("Series A")["style_map"]["paragraph"]["Chapter Head"]["role"] == "chapter"
    # An old profile (no version, flat style map, missing settings) is upgraded, not lost.
    old = os.path.join(TMP, "old.json")
    with open(old, "w") as f:
        json.dump({"name": "Old", "style_map": {"Verse": "Poetry"}, "page": {"trim": "5.5x8.5"}}, f)
    up = profiles.load(old)
    assert up["profile_version"] == profiles.PROFILE_VERSION
    assert up["style_map"] == {"paragraph": {"Verse": "Poetry"}, "character": {}}
    assert up["page"]["trim"] == "5.5x8.5" and up["page"]["facing"] is True
    assert up["typography"]["optical_margins"] is True
    # Version 1: footnote numbering and rule elsewhere; moved into "footnotes".
    v1 = os.path.join(TMP, "v1.json")
    with open(v1, "w") as f:
        json.dump({"profile_version": 1, "name": "V1", "footnote_numbering": "continuous",
                   "typography": {"footnote_rule": True, "ligatures": False}}, f)
    up1 = profiles.load(v1)
    assert up1["footnotes"]["numbering"] == "continuous" and up1["footnotes"]["rule"] is True
    assert up1["footnotes"]["continuation_rule"] is True and up1["footnotes"]["space_above"] == 12
    assert "footnote_numbering" not in up1 and "footnote_rule" not in up1["typography"]
    assert up1["typography"]["ligatures"] is False
    assert up1["typography"]["last_line_min_chars"] == 10 and up1["profile_version"] == profiles.PROFILE_VERSION
    assert up1["page"]["spare_pages"] == 0 and up1["styles_template"] is None
    assert up1["body_size"] == 11 and up1["leading"]["feel"] == "standard"
    assert up1["page"]["measure"] == 30
    assert up1["running_heads"]["style"]["case"] == "as_typed"
    assert up1["running_heads"]["style"]["caps"] == "small_caps"
    assert up1["running_heads"]["style"]["bold"] is False
    assert up1["running_heads"]["script_masters"] is True      # turned on in version 10
    assert up1["page"]["opener_drop"] is None
    # Version 7: "case" was the type (all_caps); now the letters, with caps the type.
    v7 = os.path.join(TMP, "v7.json")
    with open(v7, "w") as f:
        json.dump({"profile_version": 7, "name": "V7",
                   "running_heads": {"style": {"case": "all_caps", "italic": True}}}, f)
    rs = profiles.load(v7)["running_heads"]["style"]
    assert (rs["case"], rs["caps"], rs["italic"], rs["underline"]) == \
        ("as_typed", "all_caps", True, False)
    newer = os.path.join(TMP, "newer.json")
    with open(newer, "w") as f:
        json.dump({"profile_version": 999}, f)
    try:
        profiles.load(newer)
    except profiles.ProfileError as e:
        assert "newer version" in str(e)
    else:
        raise AssertionError("expected ProfileError")
    dest = os.path.join(TMP, "export", "Series A.json")
    profiles.export_profile("Series A", dest)
    assert profiles.import_profile(old) == "Old"
    assert sorted(profiles.list_profiles()) == ["Old", "Series A"]


def test_profile_changes_map():
    a, b = manuscript(os.path.join(TMP, "ms2"))
    prof = profiles.default_profile()
    prof["style_map"]["paragraph"]["Orphan"] = {"idml": "Epigraph", "role": "quote"}
    rep = preflight([b, a], prof)
    u = {u.word: u for u in rep.paragraph_styles}["Orphan"]
    assert (u.idml, u.role, u.source, u.warning) == ("Epigraph", "quote", "profile", False)


def test_cli():
    folder = os.path.join(TMP, "cli")
    manuscript(folder)
    out = os.path.join(TMP, "report.txt")
    bookfile = os.path.join(TMP, "cli.book.json")
    assert main(["preflight", folder, "--out", out, "--save-book", bookfile]) == 0
    assert "Early Chapter" in open(out, encoding="utf-8").read()
    js = os.path.join(TMP, "report.json")
    assert main(["preflight", "--book", bookfile, "--json", "--out", js]) == 0
    assert json.load(open(js, encoding="utf-8"))["files"][0]["name"] == "Chapter 2.docx"
    assert main(["preflight", os.path.join(TMP, "nothing-here.txt")]) == 2
    # As a module, the way users run it.
    r = subprocess.run([sys.executable, "-m", "ectype_idml", "preflight", folder], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "PREFLIGHT" in r.stdout, r.stderr


def test_libreoffice_roundtrip():
    """A file saved again by a real word processor still reads the same (skipped without
    LibreOffice)."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        print("     (LibreOffice not found; skipped)")
        return
    a, b = manuscript(os.path.join(TMP, "lo-in"))
    outdir = os.path.join(TMP, "lo-out")
    r = subprocess.run([soffice, "--headless", "--convert-to", "docx:MS Word 2007 XML",
                        "--outdir", outdir, b], capture_output=True, text=True, timeout=180,
                       env=dict(os.environ, HOME=os.path.join(TMP, "lo-home")))
    resaved = os.path.join(outdir, "Chapter 2.docx")
    assert os.path.exists(resaved), r.stderr
    rep = preflight([resaved])
    assert [u.title for u in rep.outline.units] == ["Early Chapter"], rep.outline.units
    assert rep.files[0].footnotes == 1
    assert rep.scripts["hebrew"]["runs"] >= 1 and rep.scripts["greek"]["runs"] >= 1
    assert "text box" in rep.items


if __name__ == "__main__":
    run_tests(globals())
