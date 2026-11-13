# docx-to-idml (working name)

Turns a Word book manuscript (one .docx or several) into an IDML file that opens in InDesign,
Affinity or DesignCraft with most of the book already laid out: page geometry, masters, styles,
front matter, running heads and pagination. The plan is in [PLAN.md](PLAN.md).

## Versions

Download the program (`docx-to-idml-X.Y.Z.exe`) from
[Releases](https://github.com/RexBHavgreau/docx-to-idml/releases); once installed, it offers
new versions itself. The full list of changes is in [CHANGELOG.md](CHANGELOG.md).

- **0.8.1** (in progress): exports of books with long titles no longer fail; the export is
  named after the short title, or the title before a colon.
- **0.8.0** (October 24, 2026, latest release): Hebrew or Greek in running heads gets masters of its own by
  default when the head font lacks it, with a pop-up saying so; the "Open the export folder"
  button is back after an export; long web addresses (in footnotes) break at Chicago's break
  points instead of being spaced out; the report names the last pages to check; other
  programs can run the converter (`convert` command, docs/ENGINE.md).
- **0.7.0** (October 23, 2026): chapter openings lowered by their style
  (the drop moves with the title; adjustable), full-height text frames; running heads in
  title or sentence case, with boldface and underline; the title on the copyright page; a
  preview of the generated front pages; margins and spacing shown as points with inches.
  Fixes: a note-heavy chapter running past its pages in InDesign; the window opening too short.
- **0.6.0** (October 23, 2026): Book Details as a bibliographic record
  (contributors in title-page order with bylines, series, volume, call number); the
  manuscript's copyright page read into Book Details and replaced by the generated one, with a
  window to compare them; headings found by their formatting in manuscripts without heading
  styles; front-matter files (copyright, foreword, contributors) recognized; Hebrew follows
  italic and bold text; running heads with Hebrew flagged when their font lacks it.
- **0.5.0** (October 23, 2026): the Style Map tab shows every style in one
  view; narrower default margins (line length about 30 times the type size, outside never
  wider than inside); running-head style settings; Page Layout in three sections. Fixes: Hebrew in the title
  pages and running heads, chapter openers kept on right-hand pages when InDesign adds pages,
  a paper's cover page read better.
- **0.4.0** (October 22, 2026): style mapping in one window; after an
  update, shortcuts and taskbar pins point at the new version; the update check runs at
  every start.
- **0.3.0** (October 22, 2026): endorsements recognized and set first; no Word formatting in
  the book's styles; body size, leading choices and baseline grid; calculated margins shown.
- **0.2.0** (October 21, 2026): font dropdowns; styles from an IDML template; spare pages;
  World-Ready composer for Hebrew; bibliography and footnote-italics fixes.

**Status:** all seven steps of the build order are in place (preflight, export with styles,
footnotes, Hebrew and Greek, tables and images, layout and pagination, front matter and
running heads, the window, the .exe and the updater). Being tried on real manuscripts.

## Which programs open the files

What has been tried with the exported IDML, so you can decide whether it fits your program.

| Program | Result | What to know |
|---|---|---|
| **Adobe InDesign** (2026) | **Works** (tested) | The recommended program, and the only one for books with Hebrew. Text, styles, footnotes, masters, running heads, page numbers, images and tables come through. The contents is placed by hand from the Contents style. When a chapter runs long, InDesign adds pages itself. |
| **Affinity** | **Works**, with limits (tested) | Hebrew is reversed (Affinity can't set it right to left), so use InDesign for Hebrew. Tables don't break across pages. Affinity doesn't add pages when a chapter runs long; add them by hand. The contents is placed by hand from the Contents style. |
| **DesignCraft** (0.12.0) | **Works** (tested on a 0.6.0 export) | Pages, footnotes, chapters on right-hand pages, front matter and page numbers come through, and Hebrew in the text reads right to left. A running head can use only one font, so since 0.8.0 a chapter whose head has Hebrew the head font lacks gets a master of its own with the head as text. Like Affinity, DesignCraft doesn't add pages when a chapter runs long; add them by hand. |
| **Scribus** (1.6.1) | **Not recommended** (tested) | The pages, masters, running heads, page numbers, images and tables come through, but every font is replaced by Scribus's default (so italic and bold are lost too) and the **footnotes are dropped entirely**. Scribus does the same with files InDesign itself writes, so this is a limit of Scribus's IDML import. |

## Use from other programs

Other programs (such as Ectype OCR) run the installed .exe with the `convert` command and read
the result from a JSON file; the converter keeps updating itself, so they always use the latest
version. See [docs/ENGINE.md](docs/ENGINE.md).

## The window

```
pip install -r requirements.txt
python run_app.py            # or: python -m ectype_idml
```

Add the .docx files (or drop them, with tkinterdnd2 installed), put them in order, fill in the
book details and running heads, choose or adjust the layout profile, then Export IDML. File >
Save book keeps all of it for a re-export after corrections. `build_exe.bat` builds the
Windows program (`dist\docx-to-idml-X.Y.Z.exe`).

## Export

```
python -m ectype_idml export "Chapter 1.docx" "Chapter 2.docx" --out books
python -m ectype_idml export manuscript-folder --out books --profile "Series A"
```

Each export is a folder of its own (named after the book title, or `--name`) holding the IDML
and a `Links` folder with the images, linked relative to the IDML, so the folder can be moved
or sent on.

## Preflight

```
pip install -r requirements.txt
python -m ectype_idml preflight "Chapter 1.docx" "Chapter 2.docx"   # files in book order
python -m ectype_idml preflight manuscript-folder                   # a folder, natural name order
python -m ectype_idml preflight manuscript-folder --save-book book.json
python -m ectype_idml preflight --book book.json --json --out report.json
```

The report covers:

- the files in book order
- the outline (front matter, parts, chapters, back matter) and how each unit was found
- the title, subtitle and author it detected
- the paragraph and character styles in use, and the IDML style each one maps to
- direct formatting, with the hotspots listed
- fonts
- Hebrew and Greek
- style conflicts between files
- everything version 1 doesn't carry over: text boxes, shapes, equations, comments, XE fields
  and endnotes

Tracked changes and unusual fields are also listed.

## Profiles

```
python -m ectype_idml profile new "Series A"
python -m ectype_idml profile show "Series A"
python -m ectype_idml profile export "Series A" "Series A.json"
python -m ectype_idml profile import "Series A.json"
python -m ectype_idml preflight ms-folder --profile "Series A"
```

Profiles are saved in `%APPDATA%\docx-to-idml\profiles` (on Linux and Mac,
`~/.config/docx-to-idml/profiles`).

## Tests

```
python tests/test_reader.py
python tests/test_outline.py
python tests/test_preflight.py    # includes a LibreOffice round trip when soffice is installed
python tests/test_idml_tools.py
python tests/test_writer.py
python tests/test_export.py
python tests/test_layout.py
python tests/test_updates.py
python tests/test_service.py  # the convert command for other programs
python tests/test_golden.py   # the output against tests/golden/ (--update after an intended change)
python tests/test_gui.py      # needs a display (xvfb-run on Linux)
```

## Development tools

```
pip install -r requirements-dev.txt      # jing and trang for schema validation (needs Java)
python tools/idml_check.py file.idml      # structure, then Adobe's schema (jing)
python tools/idml_inspect.py file.idml    # masters, pages, overrides, sections, stories, styles
python tools/prepare_schema.py            # rebuild idml-schema/rng after an InDesign update
python tools/make_base.py                 # rebuild the writer's base from reference 01
python tools/make_generated_files.py      # the generator's feature files, reference/generated/
```
