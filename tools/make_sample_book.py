"""Write a small sample manuscript as Word files and export it (build step 4).

    python tools/make_sample_book.py

Writes reference/manuscript/*.docx (three files, as an author might send chapters) and
exports them with ectype_idml.export to reference/generated/e01-sample-book/ (IDML and Links),
then checks the IDML with tools/idml_check.py. Open the IDML in InDesign and Affinity.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from docx_builder import (NUMBERING, footnote_ref, image, make_docx, numbered, para, run,
                          section_break, table)
from make_generated_files import GEN, GEN_PLAIN, HEBREW_FONT, JOHN, filler
from ectype_idml.export import export
from ectype_idml.profile import default_profile

MS = os.path.join(ROOT, "reference", "manuscript")
OUT = os.path.join(ROOT, "reference", "generated")
SAMPLE_IMAGE = os.path.join(ROOT, "tests", "data", "sample.jpg")

STYLES = [
    '<w:style w:type="paragraph" w:customStyle="1" w:styleId="Epigraph"><w:name w:val="Epigraph"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/><w:ind w:left="1440" w:right="1440"/>'
    '</w:pPr><w:rPr><w:i/><w:sz w:val="20"/></w:rPr></w:style>',
    '<w:style w:type="character" w:customStyle="1" w:styleId="ScriptureRef">'
    '<w:name w:val="Scripture Ref"/><w:rPr><w:smallCaps/></w:rPr></w:style>',
    '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/></w:pPr></w:style>',
    '<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/>'
    '<w:basedOn w:val="Normal"/><w:rPr><w:i/><w:sz w:val="18"/></w:rPr></w:style>',
    '<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="2"/></w:pPr></w:style>',
]


def i(text):
    return run(text, "<w:i/>")


def front():
    body = [para("The Covenant Formula", "Title"),
            para("Studies in the Prophets", "Subtitle"),
            para("by A. N. Author"),
            section_break("nextPage"),
            para("Preface", "Heading1"),
            para(run(filler(120, 0) + " This book uses ") + i("italic") + run(" for titles such as ")
                 + i("Biblia Hebraica Stuttgartensia") + run(".") + footnote_ref(1)),
            para(filler(150, 3))]
    return make_docx(os.path.join(MS, "00 Front.docx"), body, extra_styles=STYLES,
                     footnotes=["Abbreviations follow the SBL Handbook of Style."])


def chapter_one():
    with open(SAMPLE_IMAGE, "rb") as f:
        jpg = f.read()
    body = [
        para("The Formula in the Prophets", "Heading1"),
        para("I will be their God, and they shall be my people.", "Epigraph"),
        para(run(filler(90, 0) + " The formula first appears in ") + run(
            "Lev 26:12", '<w:rStyle w:val="ScriptureRef"/>') + run(".") + footnote_ref(1)
            + run(" " + filler(60, 1))),
        para(run("Genesis 1:1 reads ") + run(GEN, "<w:rtl/>") + run(" (unpointed: ")
             + run(GEN_PLAIN, "<w:rtl/>") + run("), and John 1:1 reads ") + run(JOHN)
             + run(" " + filler(40, 2)) + footnote_ref(2)),
        para("Jeremiah", "Heading2"),
        para(run(filler(120, 3) + " Some words are ") + run("bold", "<w:b/>") + run(", some ")
             + run("small capitals", "<w:smallCaps/>") + run(", and a superscript")
             + run("2", '<w:vertAlign w:val="superscript"/>') + run(".") + footnote_ref(3)),
        para("Three points follow:"),
        numbered("The formula is covenantal.", 2, style="ListParagraph"),
        numbered("It has two halves.", 2, style="ListParagraph"),
        numbered("God speaks first.", 2, 1, style="ListParagraph"),
        numbered("The people answer.", 2, 1, style="ListParagraph"),
        numbered("It recurs in Ezekiel.", 2, style="ListParagraph"),
        para("Ezekiel", "Heading2"),
        para(filler(160, 4)),
        table([["Book", "Occurrences", "Form"], ["Jeremiah", "7", "Full"],
               ["Ezekiel", "6", "Full"], ["Hosea", "1", "Reversed"],
               ["A note spanning the whole table"]], header=1, widths=[3000, 2000, 2500],
              spans={(4, 0): 3}),
        para(filler(80, 5)),
        para(image(rid="rIdImg1")),
        para("Figure 1. A sample image.", "Caption"),
        para("Later Echoes", "Heading3"),
        para(run(filler(200, 6)) + footnote_ref(4)),
        para("* * *", ppr='<w:jc w:val="center"/>'),
        para(filler(150, 7)),
    ]
    notes = [run("See the commentary on Leviticus in ") + i("The Anchor Bible")
             + run(" for the priestly setting."),
             run("On the Greek of John's prologue (") + run(JOHN[:20]) + run("), see ")
             + i("A Grammar of New Testament Greek") + run("."),
             "This note is long enough to run onto a second page if it falls near the foot. "
             + filler(120, 8),
             "Ibid."]
    return make_docx(os.path.join(MS, "01 Chapter One.docx"), body, extra_styles=STYLES,
                     footnotes=notes, numbering=NUMBERING,
                     media={"rIdImg1": ("image1.jpeg", jpg)})


def chapter_two():
    body = [para("Covenant and Community", "Heading1"),
            para(run(filler(300, 2)) + footnote_ref(1)),
            para("A block quotation set off from the text, as a reader would expect in a book "
                 "of this kind. " + filler(50, 3), "Quote"),
            para(run(filler(250, 4)) + footnote_ref(2)),
            para("Bibliography", "Heading1"),
            para(run("Author, A. N. ") + i("The Covenant in the Prophets") + run(". City: Press, 2020.")),
            para(run("Writer, B. ") + i("Greek and Hebrew Together") + run(". City: Press, 2018."))]
    return make_docx(os.path.join(MS, "02 Chapter Two.docx"), body, extra_styles=STYLES,
                     footnotes=["Numbering restarts in each chapter.", "A second note."])


def main():
    from idml_check import check
    os.makedirs(MS, exist_ok=True)
    files = [front(), chapter_one(), chapter_two()]
    # The fonts of the reference files (on Beaux's machine); Word's own are Calibri.
    prof = default_profile()
    prof["fonts"].update({"body": "Arno Pro", "hebrew": HEBREW_FONT})
    prof["notices"] = [{"name": "Sample Bible", "text": "Scripture quotations are the author's "
                                                        "own translation."}]
    # Sample book details (a placeholder ISBN), as the GUI's book settings would hold them.
    settings = {"front": {"publisher": "Sample Press", "publisher_address": "City, State",
                          "isbn_print": "978-0-000-00000-0", "notices": ["Sample Bible"],
                          "printed_in": "the United States of America",
                          "edition": "First edition"},
                "short_titles": {"The Formula in the Prophets": "The Formula"}}
    path, report = export(files, OUT, prof, "e01-sample-book", settings)
    print("Wrote %s" % path)
    for line in report:
        print("- " + line)
    probs = check(path)
    print("check: %s" % ("OK" if not probs else "%d problem(s)" % len(probs)))
    for p in probs[:20]:
        print("  - " + p[:300])
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
