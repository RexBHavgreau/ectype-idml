"""Golden files: two exports compared part by part with saved copies (tests/golden/), so a
change to the output never goes unnoticed (other programs, Ectype OCR, rely on it).

The exports don't depend on the machine: every font is named one that isn't installed
anywhere (the estimates then use the average book font's width), the copyright year is set,
and the images' link times are blanked. When a change to the output is intended, run

    python tests/test_golden.py --update

and say so in the commit message; the diff of tests/golden/ shows what changed.
"""

import os
import re
import shutil
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

TMP = tempfile.mkdtemp()
os.environ["APPDATA"] = os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")

from docx_builder import footnote_ref, make_docx, para, run, run_tests  # noqa: E402
from ectype_idml.export import export  # noqa: E402
from ectype_idml.profile import default_profile  # noqa: E402

GOLDEN = os.path.join(ROOT, "tests", "golden")
MS = os.path.join(ROOT, "reference", "manuscript")
NO_FONT = "Golden Test Font"            # installed nowhere
HEB = "\u05e0\u05e9\u05c2\u05d9\u05d0"
GRK = "\u03bb\u03cc\u03b3\u03bf\u03c2"
VOLATILE = re.compile(r' (LinkImportStamp|LinkImportModificationTime|LinkImportTime)="[^"]*"')


def _profile():
    prof = default_profile()
    for key in prof["fonts"]:
        prof["fonts"][key] = NO_FONT
    return prof


def _settings():
    return {"front": {"year": "2026", "half_title": True, "contents": True}}


def _scholarly():
    """A paper without heading styles: headings by formatting, Hebrew in a chapter head
    (its own master), Greek, footnotes with a long web address."""
    text = ("The prince of Ezekiel 40\u201348 is set over the land, and the text returns to "
            "him as the vision unfolds. ")
    bold = lambda t: para('<w:r><w:rPr><w:b/></w:rPr><w:t>%s</w:t></w:r>' % t)  # noqa: E731
    body = [para("A Study of the Prince", "Title"), para("Beaux Hargrove", "Author")]
    titles = ("Introduction", HEB + " in Ezekiel 40\u201348", "Conclusion")
    for n, title in enumerate(titles, 1):
        body.append(para(title, "Heading1"))
        body.append(bold("The Setting of the Vision"))
        body.append(para(run(text * 4) + footnote_ref(n)))
        body += [para(text * 6)] * 8
        body.append(bold("The Word " + GRK))
        body += [para(text * 6)] * 8
    notes = ["See https://search.ebscohost.com/login.aspx?direct=true&db=rfh&AN=ATLA0001234567"
             "&site=ehost-live and www.jstor.org/stable/1234567.",
             "On " + HEB + " see the lexicons.", "A note in the conclusion."]
    return make_docx(os.path.join(TMP, "scholarly.docx"), body, footnotes=notes)


BOOKS = {"e01-sample-book": lambda: sorted(os.path.join(MS, f) for f in os.listdir(MS)
                                           if f.endswith(".docx")),
         "g02-scholarly-paper": lambda: [_scholarly()]}


def _parts(name, files):
    """The export's parts as {path: normalized text}."""
    out = os.path.join(TMP, "out", name)
    idml, _report = export(files, out, _profile(), name, _settings())
    from idml_check import check
    assert check(idml) == [], "%s doesn't validate" % name
    parts = {}
    with zipfile.ZipFile(idml) as z:
        for n in z.namelist():
            text = z.read(n).decode("utf-8")
            parts[n] = VOLATILE.sub(r' \1=""', text).replace("><", ">\n<")
    return parts


def _check(name):
    parts = _parts(name, BOOKS[name]())
    folder = os.path.join(GOLDEN, name)
    if "--update" in sys.argv:
        shutil.rmtree(folder, ignore_errors=True)
        for n, text in parts.items():
            p = os.path.join(folder, n)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        return
    saved = {}
    for base, _dirs, files in os.walk(folder):
        for f in files:
            p = os.path.join(base, f)
            with open(p, encoding="utf-8", newline="") as fh:
                saved[os.path.relpath(p, folder).replace(os.sep, "/")] = fh.read()
    assert saved, "No golden files for %s: run python tests/test_golden.py --update" % name
    assert sorted(parts) == sorted(saved), "parts differ: %s" % sorted(
        set(parts) ^ set(saved))
    for n in sorted(parts):
        if parts[n] != saved[n]:
            a, b = saved[n].splitlines(), parts[n].splitlines()
            k = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            raise AssertionError("%s/%s differs from the golden copy at line %d:\n  was: %s\n"
                                 "  now: %s\n(If the change is intended: python "
                                 "tests/test_golden.py --update)" % (
                                     name, n, k + 1, (a[k] if k < len(a) else "")[:300],
                                     (b[k] if k < len(b) else "")[:300]))


def test_sample_book():
    _check("e01-sample-book")


def test_scholarly_paper():
    _check("g02-scholarly-paper")


if __name__ == "__main__":
    run_tests({k: v for k, v in globals().items() if k.startswith("test_")})
