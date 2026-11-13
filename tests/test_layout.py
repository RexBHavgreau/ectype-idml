"""Page geometry, pagination and the font measure (build step 5)."""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_builder import run_tests
from ectype_idml import fonts, layout


def test_kdp_gutter():
    assert layout.kdp_gutter(100) == 27 and layout.kdp_gutter(150) == 27
    assert layout.kdp_gutter(151) == 36 and layout.kdp_gutter(450) == 45
    assert layout.kdp_gutter(828) == 63
    assert layout.kdp_band(150) != layout.kdp_band(151)


def test_geometry_6x9():
    g = layout.geometry(432, 648, 11, 14, 0.42, 200)
    m = g.margins
    # The measure about 30 times the type size (Bringhurst): 4.6 in, about 71 characters.
    assert abs(g.measure - 330) <= 1 and round(g.cpl) == 71
    # Never the outside wider than the inside by default; margins near a trade 6x9's
    # (Beaux: about 0.6 in outside and top, 0.75 in bottom).
    assert m["inside"] >= m["outside"] and m["top"] < m["bottom"]
    assert 0.55 <= m["outside"] / 72 <= 0.65 and 0.55 <= m["top"] / 72 <= 0.65
    assert min(m.values()) >= 36
    assert m["top"] + m["bottom"] + g.lines * 14 == 648      # whole lines
    assert g.measure == 432 - m["inside"] - m["outside"]
    assert not g.notes


def test_geometry_floors():
    # A long book on a small trim: KDP's gutter (0.875 in) wins and the measure gives way.
    g = layout.geometry(360, 576, 12, 15, 0.5, 800)
    assert g.margins["inside"] >= 63 and g.margins["outside"] >= 36
    assert g.cpl < 45
    assert any("under 45 characters" in n for n in g.notes)


def test_geometry_wide_trim_and_overrides():
    g = layout.geometry(612, 792, 10, 12.5, 0.42, 200)
    assert any("two columns" in n for n in g.notes)
    g = layout.geometry(432, 648, 11, 14, 0.42, 400, {"inside": 0.5, "top": 1})
    assert g.margins["inside"] == 36 and g.margins["top"] == 72
    assert any("below KDP's minimum" in n for n in g.notes)


def test_measure_setting_and_limits():
    # A shorter line by choice (25 times the type size); a very narrow font is held at 80
    # characters, a very wide one at 45.
    g = layout.geometry(432, 648, 11, 14, 0.42, 200, measure_ems=25)
    assert abs(g.measure - 275) <= 1
    assert round(layout.geometry(432, 648, 11, 14, 0.3, 200).cpl) == 80
    g = layout.geometry(504, 720, 11, 14, 0.8, 200)          # 7 x 10
    assert round(g.cpl) == 45 and g.margins["inside"] >= g.margins["outside"]


def test_plan_pages_recto_rules():
    units = [("display", 1, 0), ("front", 2, 1), ("chapter", 4, 1), ("chapter", 2, 1),
             ("part", 1, 0), ("chapter", 3, 1), ("back", 1, 1)]
    placed, count, masters, first = layout.plan_pages(units)
    starts = [p.start for p in placed]
    assert first == 2
    assert all(s % 2 == 0 for s in starts)           # every unit on a recto (even index)
    assert starts == [0, 2, 6, 12, 16, 18, 22]
    assert masters[1] == "E-Blank" and placed[1].blank_before
    assert masters[0] == "D-Display" and masters[2] == "B-Opener" and masters[3] == "C-Front"
    assert masters[6] == "B-Opener" and masters[7] == "A-Body" and masters[16] == "D-Display"
    assert count == 24
    # Chapters on the next page: only the first chapter and parts need a recto.
    placed, count, masters, first = layout.plan_pages(units, "next_page")
    assert [p.start for p in placed][2:4] == [6, 11]


def test_page_count_notes():
    assert any("minimum" in n for n in layout.page_count_notes(20))
    assert any("near KDP's 150-page step" in n for n in layout.page_count_notes(147))
    assert not layout.page_count_notes(220)


def test_font_measure():
    index = fonts.font_index()
    if not index:
        print("  (no fonts installed here; skipped)")
        return
    family = sorted(index)[0]
    found = fonts.find_font(family)
    w = fonts.average_width(found, "the quick brown fox jumps over the lazy dog")
    assert 0.2 < w < 0.8
    assert fonts.find_font("No Such Font Family") is None
    assert fonts.font_index([tempfile.mkdtemp()]) == {}


def test_book_and_script_fonts():
    fake = {"georgia": {"regular": ("/x/georgia.ttf", 0)},
            "palatino linotype": {"regular": ("/x/pala.ttf", 0)}}
    assert fonts.book_font(fake) == "Palatino Linotype"      # earlier in the list
    assert fonts.book_font({}) == "Minion Pro"               # none installed: the first
    assert fonts.script_font("hebrew", {}) == "SBL Hebrew"
    assert fonts.script_font("greek", {}) == "SBL Greek"


def test_leading_suggestions():
    sug, why = layout.leading_suggestions(11)
    assert sug["tight"][:2] == (12.5, 13) and sug["standard"][:2] == (13.5, 14)
    assert sug["open"][:2] == (14.5, 15) and not why
    assert sug["standard"][2] == 14
    big, why = layout.leading_suggestions(11, x_height=0.53, font="Big Font")
    assert big["standard"][2] > sug["standard"][2] and "Big Font has a large x-height" in why
    small, why = layout.leading_suggestions(11, x_height=0.40)
    assert small["standard"][2] < sug["standard"][2] and "small x-height" in why
    long, why = layout.leading_suggestions(11, cpl=80)
    assert long["open"][1] >= sug["open"][1] and "long lines" in why
    assert layout.leading_suggestions(10)[0]["standard"][:2] == (12.5, 12.5)


if __name__ == "__main__":
    run_tests(globals())
