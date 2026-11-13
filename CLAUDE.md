# Ectype IDML: notes for Claude

Ectype IDML (named November 13, 2026; "docx-to-idml" until 0.8.0) converts a Word book
manuscript (one .docx or several) into IDML for InDesign, Affinity and DesignCraft, with the
book laid out: page geometry, masters, styles, front matter, running heads, pagination. It is
one of Beaux's Ectype programs (Ectype OCR calls it, docs/ENGINE.md). Python; the package is
`ectype_idml`; a Tkinter window built into one .exe with PyInstaller; a command line for
scripts and other programs. The plan is in `PLAN.md`; keep it up to date when decisions change.

## Progress

Keep this section current: update it with every batch of work (what was done, what was
checked and where, what's next), so a new session knows where the tool stands.

**Version:** 1.0.0 (November 13: the name Ectype IDML, the long-title fix), merged; its
release is published by Beaux from the tag. Earlier releases: 0.2.0 (Oct 21, first .exe),
0.3.0, 0.4.0 (Oct 22), 0.5.0, 0.6.0, 0.7.0 (Oct 23), 0.8.0 (Oct 24). Details in CHANGELOG.md.

| Area | State | Checked in |
|---|---|---|
| Reading Word (styles, notes, sections, fields, Hebrew/Greek) | Done | Tests; real manuscripts (Beaux's Ezekiel paper, an edited volume, The Broken Heart) |
| Outline (chapters, parts, front/back matter, headings by formatting) | Done | Tests; Beaux's manuscripts |
| Styles, character styles, footnotes (fn-m) | Done | InDesign, Affinity; DesignCraft (0.6.0 export) |
| Page geometry, masters, sections, folios, recto openers | Done | InDesign, Affinity, DesignCraft |
| Front matter (half-title, title, copyright, contents reserved), Book Details | Done | Tests; the window's preview; not yet a full export opened since 0.7.0 |
| Running heads (case, style, Hebrew masters) | Done | Tests; the Hebrew masters not yet opened in a program |
| Opener drop in the style (0.7.0) | Done | o01 test file in InDesign and Affinity; not yet a full export |
| Page estimate, last pages to check | Done | Beaux's Ezekiel paper (InDesign); DesignCraft with substituted fonts runs over |
| Window (tabs, forms, preview, points fields) | Done | Xvfb here, GitHub's Windows runner; Beaux on Windows up to 0.7.0 |
| Updater (check, download, digest, old copies, shortcuts, pins) | Done | Real updates 0.2.0 -> 0.3.0, 0.4.0 -> 0.5.0 (Start pin); the rename's transition not yet |
| Use by other programs (`convert`, program.json, daily update) | Done | The .exe's convert on GitHub's Windows runner; not yet called by Ectype OCR; the silent update not yet with a real release |
| Golden files (tests/golden) | Done | Windows and Linux CI |

**In progress (1.1.0, branch):** page-number placing (Running Heads > Page Numbers: foot
centered / foot outside / head outside; openers at the foot or none; profile version 11).
Tests and schema check here; not yet opened in InDesign, Affinity or DesignCraft.

**Next / open:**
- Convert The Broken Heart again with 1.0.0 (its export failed in 0.8.0 on the long title).
- After 1.0.0 is released: check that a 0.8.0 copy updates to it (under the old name), that the
  settings folder is carried over, and that the Start pin follows. (The GitHub repository was
  renamed to ectype-idml on November 13; GitHub forwards the old address, which copies before
  1.0.0 use to check for updates.)
- Open a full 0.7.0+ export in InDesign and Affinity: opener drop (does the rule's offset
  match the old position?), title/sentence-case heads, Hebrew head masters.
- Ectype OCR: write its side of docs/ENGINE.md; the first real call; the silent daily update
  with a real release.
- Parked: tables breaking across pages in Affinity (g07); generating Fonts.xml from the fonts
  used; IDML auto-numbering for lists; a DOCX-free input model for Ectype (only if the .docx
  route proves too limiting).

## Working with Beaux

- Keep reports short and plain: what changed, what was tested, what wasn't.
- He works on Windows. Build for Windows.
- Ask before merging to `main` or tagging a release. Work on a branch and push it; Beaux merges.
- He is an editor and Hebrew/OT scholar; conventions follow the Chicago Manual of Style. When an
  editorial choice is unclear, ask rather than guess.
- **Future-proofing (Beaux, October 23):** when he asks for something, point out its
  implications for the future in a line or two: what it would make harder later (another
  program, a Mac version, other languages, saved profiles and books), a simpler way that
  keeps options open, and anything that should be decided now rather than patched later.
- Keep the code clean as it grows: remove what a change makes unused, keep descriptions
  current, and keep only what the tests and tools use in `reference/`. `export.py` and
  `gui.py` are large: when a change mostly touches one part of them, move that part into a
  module of its own first (export: styles, pagination and masters, front-matter assembly;
  gui: one module per tab), tests passing before and after, in a commit of its own.

## Rules from the plan

- **Nothing that works only in InDesign.** Every feature must work in InDesign, Affinity and
  DesignCraft, or have a fallback that does. IDML is the only output, complete without scripts.
- Hebrew needs InDesign (Affinity reverses it); preflight says so whenever Hebrew is found.
- Word is read with lxml directly; python-docx is not used.
- Every IDML the tool writes must validate against Adobe's schema (jing, during development
  and tests only; the shipped .exe doesn't validate). Write `DOMVersion="21.5"`.
- Nothing disappears silently: whatever isn't carried over is listed in preflight.
- The user's files are never modified.
- User-facing text is plain and specific: say what to do.

## Layout

| Path | What it is |
|---|---|
| `ectype_idml/docx_reader.py` | Reads a .docx: styles, paragraphs, notes, sections, fields, scripts, unsupported items |
| `ectype_idml/stylemap.py` | Word style -> IDML style and role; defaults for Word's built-ins |
| `ectype_idml/formatheads.py` | Headings set by direct formatting (0.6.0): groups of paragraphs by look (size, bold, italic, caps, centered), ranked; `StyleMap.format_groups` / `paragraph_mapping` feed them to the outline, preflight and export |
| `ectype_idml/outline.py` | Units across files (front, part, chapter, back); title/author detection |
| `ectype_idml/preflight.py` | The preflight report (text and JSON) |
| `ectype_idml/profile.py` | Profiles: defaults, save/load, export/import, `PROFILE_VERSION` + `MIGRATIONS` |
| `ectype_idml/book.py` | Input files: drop/folder collection, natural order, saved order |
| `ectype_idml/content.py` | The text of a .docx for the exporter: runs with formatting features, notes, tables, images, list numbers; paragraph indexes match `docx_reader`'s |
| `ectype_idml/export.py` | Step 4, the exporter core: book styles, Word styles kept by name, runs to character styles, Hebrew/Greek, one story and section per outline unit, page estimate; `export()` writes the export folder |
| `ectype_idml/styles.py` | `StylesMixin` of the Exporter (moved out of export.py, 1.1.0): the book's paragraph and character styles, Word styles kept by name, a style template's; `body_size`, `leading_for` |
| `ectype_idml/pagination.py` | `PaginationMixin` of the Exporter (moved out of export.py, 0.6.0): pages, stories, sections and markers, masters and running-head frames |
| `ectype_idml/layout.py` | Step 5: margins and measure (30 times the type size within 45-80 characters, floors, KDP gutter by page count), pagination (roman front matter, recto rules, masters per page) |
| `ectype_idml/frontmatter.py` | Step 6: book details (settings, then detected, else bracketed placeholders), half-title, title, copyright (English/Spanish, notices from the profile's library), contents entries and reserved pages |
| `ectype_idml/textcase.py`, `preview.py` | Title and sentence case for running heads (Chicago); the generated front pages as lines with sizes, for the window's preview (0.7.0) |
| `ectype_idml/fonts.py` | Installed fonts (system and user folders) and a font's average character width (fontTools), for the measure |
| `ectype_idml/cli.py` | `python -m ectype_idml preflight / export / profile / convert / update` (the .exe takes the same; no arguments opens the window) |
| `ectype_idml/gui.py` | Step 7, the window (ttk): Files, Book Details, Running Heads, Layout Profile, Style Map, Report tabs; forms declared as field tables bound to the profile and book settings; work in threads, results through a queue polled by the window |
| `ectype_idml/gui_forms.py`, `gui_heads.py`, `gui_layout.py` | Moved out of gui.py (1.1.0): `Form` and the points helpers; `HeadsTabMixin` (Running Heads tab); `LayoutTabMixin` (Layout Profile tab, calculated margins, leading note) |
| `ectype_idml/gui_book.py` | `BookTabMixin` of the window (moved out of gui.py, 0.6.0): the Book Details tab, filling from the manuscript, the notice library |
| `ectype_idml/service.py`, `docs/ENGINE.md` | The converter as a tool for other programs (0.8.0): `convert` (JSON result), `program.json` (the .exe's location, rewritten at every start by `cli.main`), the silent daily update (`daily_check` starts a detached `update --quiet`); the contract for callers, API version 1 |
| `ectype_idml/updates.py`, `appsettings.py` | Update check and install (as Indicat's: versioned .exe beside the running one, SHA-256 digest, Downloads fallback, older copies offered for deletion); the program's own settings.json |
| `run_app.py`, `build_exe.bat`, `.github/workflows/build.yml` | The .exe (PyInstaller, one file, "Ectype-IDML-X.Y.Z.exe", with `ectype_idml/idml/base`); the workflow builds and releases on a `vX.Y.Z` tag (the release also carries a copy named "docx-to-idml-X.Y.Z.exe" for copies before 1.0.0), or by hand |
| `ectype_idml/idml/` | The IDML writer: `model.py` (the book as pages, styles, stories, sections), `writer.py`, `images.py` (image size and resolution from file headers), `base/` (InDesign's own settings and root styles, made by `tools/make_base.py` from reference 01; `snippets.xml` holds elements the writer clones) |
| `reference/` | `idml/` (the 13 InDesign reference IDMLs, used by tests and `tools/make_base.py`), `manuscript/` (the sample manuscript), `make_reference_files.jsx` (rebuilds the references in InDesign), README (what was checked, footnote findings). No .indd, PDFs or generated files (removed October 23) |
| `idml-schema/` | Adobe's IDML schema for InDesign 2026 (21.6.0.57, DOM 21.5): `rnc/` as InDesign wrote it, `rng/` converted by `tools/prepare_schema.py` |
| `tools/make_generated_files.py` | Step 3: the generator's versions of the reference files, in `reference/generated/` (ignored by git; tests build them in a temp folder) |
| `tools/idml_check.py`, `tools/idml_inspect.py` | Development tools: structural check of an IDML package plus jing against the schema; summary of a package (masters, pages, overrides, sections, stories, styles) for comparing with references |
| `tools/make_sample_book.py` | Step 4: a sample manuscript (`reference/manuscript/`, three .docx) exported to `reference/generated/e01-sample-book/` |
| `tests/docx_builder.py` | Builds test .docx files from raw WordprocessingML (images, tables, numbering too); the test runner |

## Conventions

- When the profile layout changes, bump `PROFILE_VERSION` and add a step to `MIGRATIONS` in
  `profile.py`, so saved profiles are upgraded, not lost.
- In Word, a section's `w:type` says how *that* section starts; it sits in the sectPr that ends
  the section.
- The schema is strict about element order (e.g. in designmap.xml, idPkg:Styles comes before
  idPkg:Preferences, and many settings are child `<Properties>` elements, not attributes).
  Check the generator's output with `tools/idml_check.py`; jing needs Java and
  `pip install -r requirements-dev.txt`.
- IDML composer names: `HL Composer` (Adobe Paragraph Composer), `HL Single` (Single-line),
  `HL Composer Optyca` (World-Ready). They are InDesign's own, not plug-ins.
- IDML: a parent-master item removed on a child master, or a master item removed on a page,
  is an `OverrideList` pair with `n` as the page item.
- Footnotes are written as the footnote variant "fn-m" (decided after Affinity tests; the
  variants are gone, the findings are in reference/README.md and PLAN.md): Footnote paragraph style; the number `<?ACE 4?>` and separator in
  a run of their own (Affinity breaks single-run notes); the Footnote style's font, size,
  leading, indent and alignment also on every note run (Affinity otherwise lays the root style
  `[No paragraph style]` over note text). Style edits still reach every note in both programs.
  Settings the run's own character style sets (Italic's face, Greek/Hebrew fonts) are left off
  the run, or the local copy overrides the style (italics in notes were lost until 0.2.0).
- designmap.xml must start with InDesign's `<?aid style="50" type="document" ...?>` line before
  `<Document>`; without it InDesign says it "may not support the file format". The schema
  doesn't require it; `idml_check.py` does. Write parts with `writer.serialize()` (whole
  document, double-quoted XML declaration), never `tostring(root)`, which drops the line.
- `TextPreference PreserveFacingPageSpreads="true"` in facing documents (0.5.0): Smart Text
  Reflow adding one page shifted every later opener onto a verso (Beaux, a real paper).
  DeleteEmptyPages stays false, so spare pages survive.
- `DocumentPreference PagesPerDocument` stays 1 (the new-document default InDesign writes); set
  to the real page count, InDesign adds that many pages at the start when opening the file.
- In facing documents a page's side follows its number (odd = recto), as in InDesign; a recto
  after a recto stands alone on its spread (reference 03). The writer works out spreads that way.
- IDML sections, as InDesign writes them (g01's first version broke these and wouldn't open
  in InDesign, though it validated and opened in Affinity): the alternate layout's name
  (`AlternateLayout="Custom V"`) on the first section only, `""` on the others;
  `AlternateLayoutLength` = pages from the section's start to the end; pages'
  `AppliedAlternateLayout` = the first section's id. A spread's `BindingLocation` is 0 when it
  starts with a recto, 1 when it starts with a verso (a lone last verso too). Each page carries a
  `Descriptor` (prefix, numbering style, continue numbering, include prefix, number, number,
  marker). Validating against the schema is not enough: compare with the reference files.
- Tables: write every row's `SingleRowHeight` (an estimate; InDesign grows a short row).
  Without it Affinity can't break a table across frames and runs it off the page (g07).
- An export is a folder of its own (`writer.export_book`): `<name>/<name>.idml` and
  `<name>/Links/` with the images, linked relative to the IDML (`file:Links/x.jpg`), so the
  folder can be moved or sent on: both InDesign and Affinity find them (decided October 21).
  Full paths (InDesign's own way) broke when the folder moved. Frames are cloned from reference 11.
  `tests/data/sample.jpg` is the test image (450 x 300 px, 150 ppi).
- IDML: a page frame made from a master frame is linked on the `<Page>` element,
  `OverrideList="<master item> <page item> ..."` (pairs), not on the frame; the frame itself is
  an ordinary `TextFrame` (reference file 05).
- The two InDesign files from the brief (the Assumption article and its cut-down) are a real
  article: use them for analysis only; don't commit them.
- Nothing from Word's formatting goes into the styles (Beaux, 0.3.0): Word paragraph styles
  give names and roles only. A custom style kept under its own name with role body (no book
  counterpart) keeps its distinct look in book terms (`Exporter._word_look`: alignment,
  indents scaled by book/Word measure, face, caps, size/space scaled by book/Word body size;
  no fonts); others are `Style(name, base)` with no attributes. Style map entries may carry
  "look": "word" or "book" to override. Fonts
  not set (profile or template) are `fonts.book_font()` / `fonts.script_font()` (installed
  book fonts in order), never Word's. Kept from Word: emphasis and character styles in the
  text, direct center/right alignment of a line. Body First = a unit's first body paragraph.
- Export (step 4): direct italic, bold, small caps, capitals, super/subscript, underline and
  strikethrough become character styles (Italic, Bold, Bold Italic, Small Caps...), worked out
  against the paragraph style (italic in a bold heading is Bold Italic; Word's toggle rule for
  a character style inside an italic paragraph is kept). Other direct formatting gives way to
  the book's styles. Body after a heading, a centered line or at a story's start is Body First.
  List and heading numbers are static text for now (IDML auto-numbering not yet tested in
  Affinity). Images that aren't JPEG or PNG are left out with a placeholder line and reported.
- Layout (step 5): masters A-Body, B-Opener, C-Front each have their own primary text frames
  (and a folio for now); D-Display and E-Blank are empty. Each unit is a story and a section;
  display and front units are LowerRoman from i, the first chapter or part restarts Arabic 1.
  Spare pages per chapter as the profile says (default none); blank versos before recto
  openers get E-Blank.
- Keeps (October 21): widow/orphan control is KeepLinesTogether="true" with KeepFirstLines and
  KeepLastLines 2 (InDesign ignores the line counts without KeepLinesTogether); headings keep
  all their lines together and with the next paragraph; no hyphen in a paragraph's last word
  or at the foot of a page. Short last lines (runts) are prevented without GREP styles, which
  Affinity lacks: the exporter puts the last words of each running-text paragraph in the
  "No Break" character style (or NoBreak="true" on a run that has a style already) so the last
  line has at least `typography.last_line_min_chars` (10) characters.
- Front matter and heads (step 6): the book is a list of `export.Block`s: generated half-title
  (i), title (recto), copyright (the verso after it, set at the foot), the manuscript's display
  pages, reserved contents (recto; its page count estimated or set), then front matter, text,
  back matter. The manuscript's title page is replaced (copyright lines from it go on the
  copyright page; other lines left out and listed in the report, Beaux 0.5.0); its typed
  contents is dropped.
  Running heads: recto = section marker (short title from `settings["short_titles"]`), verso =
  book title / author / chapter / custom on A-Body; C-Front shows the marker both sides; B, D, E
  none unless the profile's suppress toggles are off. Verso "part": one copy of A-Body per part
  (P1-Body...), not a child master, so linked page frames point at its own primary frames. Book
  settings (`Book.settings`): "front" (see frontmatter.py) and "short_titles".
- Bibliographies (0.2.0): Body paragraphs are set in Bibliography from a heading whose title is
  a bibliography title (outline `_BACK`) at any level until the next heading of the same or a
  higher level, a new unit or a new file. Outline: text before a file's first chapter heading
  is a unit of its own (titled by a Title-style line, else its first line) when it has a title
  line, headings or more than 150 words; in the first file, a short opening without headings
  is the title page; a stray line or two in a later file stays with the previous unit. In a
  chapter, Title/Subtitle/Author lines are set as Chapter Title, Chapter Subtitle, Chapter Author.
- Composer (0.2.0): the book's styles use the World-Ready composer (`HL Composer Optyca`) by
  default; the Adobe Paragraph Composer (`HL Composer`) reversed Hebrew in InDesign (Beaux).
  Profile `paragraph_composer` off = single-line (`HL Single`), unless the book has Hebrew.
- Style template (0.2.0, `ectype_idml/template.py`, profile `styles_template`): an IDML's
  paragraph and character styles replace the tool's by name (model level, so note runs and
  estimates use them); its other styles are added; attributes referring to swatches beyond
  InDesign's standard ones, lists, styles, and nested/GREP styles are dropped and reported.
  Its Body/Chapter Title/Footnote fonts count as chosen fonts; World-Ready kept if Hebrew.
- Spare pages: profile `page.spare_pages` 0 (default, Beaux), 1 or 2. Chapter Title has
  StartParagraph NextOddPage (NextPage for chapters on the next page); Chapter Subtitle resets
  it to Anywhere. Profile version 4.
- Unit kinds (0.3.0): the user can set a unit's kind (outline `KINDS`: chapter, part, front,
  back, display, endorsements) in the Running heads tab; saved as book settings
  `unit_kinds` {unit title: key}, applied by `outline.apply_kinds` after the outline is built.
  Endorsements (display, type "endorsements") are detected by title and placed before the
  half-title; so is text before the title line (outline: the title page is found by its
  Title-style line when no style-detected unit came before; units before it become
  endorsements). The window shows the calculated margins beside the margin fields
  (`export.calculated_margins`), with a button to fill them in.
- Size and leading (0.3.0): profile `body_size` (11) and `leading.feel` (tight/standard/open;
  version 5). `layout.leading_suggestions` gives the ranges (11 pt: 12.5-13 / 13.5-14 /
  14.5-15) shifted by x-height (`fonts.x_height`, OS/2) and line length; `export.leading_for`
  uses an exact value if set, else the middle of the feel's range. Baseline grid (profile
  `baseline_grid`): Body GridAlignment AlignBaseline, grid = body leading from the top margin;
  styles with other leading set to None (as g09).
- Updates (0.4.0): the startup check runs at every start (`updates.due`: only the on/off
  setting), as Indicat's; once a day missed same-day releases. A version declined at the
  prompt is saved as `declined_version` and not offered again at startup (`should_offer`).
  After an update the new copy offers to delete older copies and retarget shortcuts and pins
  (`gui.offer_cleanup`, `updates.retarget_shortcuts`); declined copies are saved as
  `kept_old_versions` and not asked about again. pywin32 is a Windows-only requirement.
- Font fields in the window are editable dropdowns of the installed families
  (`fonts.families()`; Hebrew and Greek lists filtered by a look at each regular font's
  character map, once, cached); read in a background thread at startup.
- Style mapping (0.4.0, a tab since 0.5.0; `gui.StyleMappingPanel`): only rows changed from
  the automatic mapping are saved, as profile `style_map` entries ({"idml", "role", "level",
  "look"}; a character entry is a name or None for no style); choices are
  `export.BOOK_STYLE_ROLES` plus a style template's styles. Preflight runs again after Apply,
  since the outline depends on the map.
- Hebrew/Greek in generated text (0.5.0): `Exporter._generated_scripts` runs after the
  build over every story and master frame, splitting runs not yet in the Hebrew/Greek styles
  (`_script_runs`, the same split as the manuscript's runs). Section markers can't carry a
  character style. Since 0.8.0 (Beaux, after DesignCraft printed boxes): when a head has
  Hebrew/Greek the running-head font lacks or can't be checked (`_script_head_lack`), the
  unit gets a copy of its master (R1-Body, R1-Front...) with the head as text
  (`_script_head_masters`, profile `running_heads.script_masters`, on by default, version
  10), and the report line is a `pagination.Alert` (a str), which the window also shows in a
  pop-up after the export. Off: a warning only.
- Faces (0.5.0): FontStyle for the body and notes styles is `fonts.regular_face()`, the
  installed face's own name (Culmus fonts: "Medium"); "Regular" when not installed here. The
  Hebrew style sets no face (0.6.0, Beaux): Hebrew takes the face around it, and
  `Exporter._hebrew_face` puts the Hebrew font's own name for it on the run
  (`fonts.matching_face`); a face the font lacks falls back to upright and is reported.
- Title page (0.5.0): text above the Title line is endorsements only when
  `outline._endorsement_like` (25+ words, or a quotation/attribution); otherwise it belongs
  to the title page. "author"/"autor" are default style names for the author role.
- 0.5.0 window: the Style Map tab is `gui.StyleMappingPanel(app, tab)` (no Toplevel, no
  per-style dialog); `refresh()` after each preflight, `save()` (changed rows into the
  profile, also from `_forms_to_profile`), `apply()` (save and read again), `reset()`. TOC
  and TOC Heading styles aren't listed. Profile fields are found with `App.pvar(path)` /
  `_form_of(path)` (the Page Layout tab has three forms in LabelFrames). Running-head style
  (0.7.0, profile version 8): `running_heads.style` case (as_typed/title/sentence: the
  letters, `textcase.py`, applied to every head's text by `PaginationMixin._head_text`;
  sentence case keeps `textcase.proper_nouns` of the running text) and caps (None,
  small_caps, all_caps: the type), italic, bold, underline, size, tracking, font ->
  `Exporter._running_head_style`; forms `head_case_form` and `head_style_form` (Form kinds
  "radio" and "one_of": at most one of its check boxes).
- Front-page preview (0.7.0): `preview.front_pages` gives the half-title, title and copyright
  pages as lines with sizes (its STYLES table follows the exporter's styles; keep them in
  step), drawn on canvases by `gui_book._draw_page`; the copyright tab shows the manuscript's
  page beside it. Book setting `front.copyright_title` (Copyright Title style, italic).
- Opener drop (0.7.0, Beaux's tests o01): `PaginationMixin._sinks` puts each block's sink
  into its first paragraph's style (SINK_STYLES: Chapter Title, Contents Title, Book Title,
  Half Title; styles based on them reset RuleAbove and SpaceBefore), else locally: Space
  Before (Affinity honours it at the frame top only with "Only at column top", set by hand)
  plus RuleAbove weight 0, tint 0, offset sink + 0.75 x size, KeepRuleAboveInFrame (InDesign
  ignores Space Before at the top of a frame; Affinity ignores the rule). Text frames are full
  height; `Story.sink` (a shorter first frame) is left for the reference-file generator only.
  The chapter drop is profile `page.opener_drop` (points; None = six body lines,
  `_opener_drop`; profile version 9), a Form "points" field (`gui.parse_points` /
  `format_points`: 72 pt (1"); choices (arrow step, unit saved "pt"/"in"); blank arrows
  start at `Form.points_start[path]`, `App._auto_drop` or the calculated margin). Margins
  (saved in inches) and the footnote spacing use it too.
- Page numbers (1.1.0): profile `running_heads.folio` (foot_center, foot_outside,
  head_outside) and `opener_folio` (drop, none), version 11; `PaginationMixin._master_frames`
  (folio "book" = the profile's place, a place, or None) writes the folio frame with a local
  Justification for outside; at the head it is a frame of its own on the running heads' line;
  `_opener_folio` gives B-Opener's (foot, centered after a head place). The window's
  `folio_form` (Running Heads tab, "Page Numbers" box); like `heads_form`, not in `pvar`.
- The main window packs the status line and export row first (side bottom) and sizes itself
  to its requested height within the screen (`App._fit_window`).
- Margins (0.5.0): measure = `page.measure` (30) x type size within 45-80 characters;
  outside 42% of the rest, inside never less than the outside (`layout.geometry`).
- Headings by formatting (Beaux, 0.6.0; `formatheads.py`): the reader records each body
  paragraph's dominant look (`Paragraph.look`, align, space_before, page_break_before).
  Candidates: body-role paragraphs of at most 15 words, no closing period unless numbered,
  looking different from the body text (the look of most of the text in 20+-word paragraphs),
  with a 20+-word non-centered paragraph under them before the next of the same look (so
  title-page lines and a contents title drop out); a group needs 2 members unless larger or
  starting a page; italic-only groups only below a stronger one. Ranked by prominence; only
  levels the styles don't provide (no chapter styles in use -> top group = chapters; no
  heading styles -> the rest = Heading A-C). Mappings are per paragraph
  (`StyleMap.paragraph_mapping`, used by outline, preflight, `Exporter._mapping(..., index)`);
  the group's bold/italic/caps are dropped from its runs. Group names ("[16 pt bold
  centered]") are keys of book settings `format_map` (not the profile), edited in the Style Map
  tab. Tried on Beaux's Ezekiel paper with its heading styles stripped: same outline as styled.
  Book-wide (`formatheads.plan(docs)`, `StyleMap.prepare` from `build_outline`): looks ranked
  over all files; in a book of several files each file's most prominent line before its first
  text is its title ("[title line of a file]"), lines of names under it "[author line under a
  file title]" (Chapter Author), else "[subtitle ...]"; a first line opening 2+ files is the
  book title (`StyleMap.book_title_line`), left out (role skip) where a file title follows it.
  Not in single-file books (there the first heading is the first chapter).
- Front matter files (0.6.0, Beaux's edited volume): `outline._copyright_file` makes a short
  file with 2+ copyright marks (©, all rights reserved, ISBN) a display/copyright unit (read,
  then replaced by the generated page); "Edited by ..." gives the editors; `frontmatter.
  parse_copyright` reads year/holder, publisher, web address, ISBNs, printed in, edition into
  `outline.details` (also from title-page copyright lines), used by `book_info` for empty
  fields and by "Fill from the manuscript"; permissions in details["notices"] (into the
  profile's notice library via `gui_book._take_notices`, or printed directly when the book
  has none ticked), unmatched lines in details["leftover"] (reported). Beaux: the
  manuscript's copyright page is always replaced by the generated one (export._front_matter). A whole-file unit whose
  first line isn't a title gets `outline.file_title(name)`. classify reads "Foreword by X" as a
  foreword; "contributors" is front matter.
- Book details (Beaux, 0.6.0): `front` is a bibliographic record (Zotero's Book fields, our
  own code: Zotero is AGPL and none of it is copied): `creators` [{"role", "name"}] in
  title-page order (roles `frontmatter.ROLES`; bylines for author/editor/translator and the
  foreword/afterword/preface/introduction writers ("With a foreword by"; `outline._by_lines`
  fills them from unit titles like "Foreword by X") via
  `frontmatter.bylines`, wording in `frontmatter.TEXT[lang]`, the profile's
  `front_matter.language`); `info["author"]` = authors else editors else translators (holder,
  verso head). series/series_number (half-title, Series style), volume/volumes (title page,
  Volume style), call_number (copyright page; blank = none). `book.BOOK_VERSION` 2:
  `book.migrate_settings` turns the old "author" into creators. GUI: `gui_book.BookTabMixin`
  (`app.creators`, `add/change/remove/move_creator`).
- Last pages to check (0.8.0): `_paginate` keeps each estimated block's `Block.est` and
  `fill` (raw estimate, `_estimate(..., raw=True)`, minus the full pages);
  `PaginationMixin._fit_note` reports fill > FULL (0.8) or < EMPTY (0.2) with the folio
  (`writer.page_names(doc)`).
- Other programs (0.8.0, Beaux: a separate tool, not a library): `run_app.py` calls
  `cli.main` (no arguments = the window). Keep `convert`'s arguments and the result's fields
  working within API version 1 (`service.API_VERSION`); raise it only for breaking changes and
  update docs/ENGINE.md. `program.json` is also written in the old settings folder
  (`OLD_APP_NAME`, docx-to-idml) while it exists.
- The rename (1.0.0): `APP_NAME` "Ectype IDML" (settings folder), `EXE_BASE` "Ectype-IDML";
  `OLD_APP_NAME`/`OLD_EXE_BASE` "docx-to-idml": `profile.carry_over_old_settings` (called by
  `cli.main`) copies the old folder once; `updates.EXE_RE` matches both names, `_pick_asset`
  prefers the current one; the build adds a copy under the old name to each release (copies
  before 1.0.0 look only for that). Keep both until no copies before 1.0.0 are in use. Golden files (`tests/golden/`,
  LF line endings by .gitattributes) use fonts installed nowhere and a fixed year; any change
  to the output shows there.
- Web addresses (0.8.0): `export.url_breaks` puts zero-width spaces at Chicago 6.8's break
  points in every run's text (after `_merge_runs`), so justified lines with long links
  don't letter-space.
- Styles are matched by name (Word writes built-in names in English, lower case, in the file);
  `stylemap.display_name` gives the name as Word shows it.

## Releases

- **Version numbers.** From 1.0.0 (Beaux, November 13), X.Y.Z means:
  - **Patch (Z):** bug fixes only; the same settings give the same output except where the
    fix corrects it.
  - **Minor (Y):** any new feature, a changed default or a change in the output (margins,
    styles, layout), or a profile version change that upgrades saved profiles. A batch with
    both fixes and features is minor.
  - **Major (X):** a change that callers or users must act on: the `convert` command or its
    result changing incompatibly (API version raised), or saved profiles or books that can't be
    upgraded. Ask Beaux first.
  - Label work on the branch with the version it will ship as (in CHANGELOG's "not yet
    released" heading); change the label if the batch grows.
  (Before 1.0: the same, with minor for features and patch for fixes; 1.0.0 was Beaux's call.)
- **README:** the top of README.md lists the latest release and the few before it (one or
  two lines each, the version in progress first). Update it with every release. Its "Which
  programs open the files" table says what each program does with the IDML (tested or not);
  keep it current when a program is tried or a limit changes.
- Version in `ectype_idml/__init__.py` (`EXE_BASE` and `REPO` there too); a dated entry at the
  top of `CHANGELOG.md`. Pushing a tag `vX.Y.Z` (matching `__version__`) runs
  `.github/workflows/build.yml` on Windows: tests, the .exe, a check that it carries the IDML
  base files, and a GitHub Release with the .exe (its SHA-256 digest is what the updater
  checks). **Ask Beaux before tagging.** Tag the merge commit on `main` (after the branch is
  merged): v0.1.0 was put on an older commit without the workflow, so nothing was built.

## Tests

```
python tests/test_reader.py
python tests/test_outline.py
python tests/test_preflight.py
python tests/test_idml_tools.py
python tests/test_writer.py
python tests/test_export.py
python tests/test_layout.py
python tests/test_updates.py
python tests/test_service.py
python tests/test_golden.py          # --update after an intended change to the output (say so in the commit)
python tests/test_gui.py             # needs a display: on Linux, xvfb-run (and python3-tk)
```

Run them all before pushing; CI (`.github/workflows/tests.yml`) runs them on Windows and Linux.
On Windows set `PYTHONUTF8=1`. Tests must not depend on which fonts are installed: CI's
Windows has book fonts (Palatino, Georgia) that this Linux machine lacks, and their x-height
and widths change leading and estimates (0.3.0's leading test failed there for that reason). `test_preflight` includes a LibreOffice round trip when
`soffice` is installed; LibreOffice refuses a theme without a color scheme, so the test builder
writes one.

## Checks so far (detail)
- Step 2: Affinity done (all files; footnotes settled as fn-m, rule and spacing as fn-o/p/q).
  DesignCraft 0.12.0 (a friend of Beaux's, October 23, the Ezekiel paper's 0.6.0 export,
  fonts substituted): all pages and footnotes, recto openers, front matter, folios, Hebrew
  right to left in the text; Hebrew in a section-marker head shows boxes (head font lacks
  it); no page added for a chapter that runs long (as Affinity).
- Step 3: g01 (footnotes) opens in Affinity and looks right; confirmed in InDesign and Affinity.
  g02-g04 confirmed in both programs. g05-g10, g12, g13 (primary text frame, contents style,
  table, OpenType, baseline grid, Hebrew/Greek, character styles, chapter stories) validate and
  match their references in the inspector (masters named A-Body where InDesign defaults to
  A-Parent; g06 writes the contents style and a reserved page, no generated contents, as
  decided). Beaux: all right in InDesign; contents placed by hand from the style in both programs
  (as intended); all right in Affinity except g07's table, which doesn't break across pages
  even with row heights (parked: tables uncommon; reference 07 does break, so compare again
  later). g11 (images) right in both; with the linked path missing, both programs find the image
  in the file's folder, else warn and leave a placeholder. Step 3 done. The base's Fonts.xml is InDesign's from reference 01 (Minion, Myriad,
  Kozuka, Arno); generating it from the fonts used is still to do. `reference/make_reference_files.jsx` v3 made the last file (05); all 13
  are in `reference/idml/` and validate. ExtendScript is
  ES3: no let/const, arrow functions, forEach/indexOf/map, trim. The file is saved as UTF-8
  with a byte-order mark.

- Step 4: e01 (sample book) opens in InDesign and Affinity and looks right (Beaux). Not yet run
  on a real manuscript.
- Step 5: e01 with the layout: text flows right, text width fine, folios right (Beaux). Spare
  pages the text doesn't reach keep their folio (they are text pages). Bleed not yet checked.
- Step 6: e01 with front matter and running heads: validates, not yet opened.
- Step 7: the window tested under Xvfb here and by its tests on GitHub's Windows runner.
  Released: v0.2.0 (October 21, the first release with the .exe), v0.3.0 and v0.4.0 (October 22),
  v0.5.0 (October 23),
  each built by the tag's workflow from main. The updater's real run worked (Beaux, October
  22): 0.2.0 found 0.3.0 by Help > Check for updates (the startup check didn't, fixed in
  0.4.0), downloaded it, opened it, and 0.3.0 offered to delete 0.2.0. 0.4.0 -> 0.5.0
  (Beaux, October 23): the startup check found it, and the Start pin was retargeted to the new
  version. Desktop shortcuts and taskbar pins use the same code but weren't there to test.
- Keeps and runts in e01: does Affinity keep KeepLinesTogether/KeepFirstLines/KeepLastLines,
  the No Break style and the local NoBreak attribute?
- 0.2.0 additions not yet opened: StartParagraph NextOddPage on Chapter Title (does Affinity
  keep it, and does InDesign leave a title already at the top of a recto where it is?); a
  style template's styles in InDesign and Affinity.
- 0.7.0: the opener drop tested in both programs by o01 (rule in InDesign; Space Before in
  Affinity with "Only at column top"); not yet a full export opened in either, nor the
  rule's offset matching the old position. Title/sentence case heads, the front-page
  preview, the points fields and the window height not yet seen on Windows.
- Preflight on a real manuscript from Word (only generated files and a LibreOffice re-save so far).
- Scribus 1.6.1 (tried here October 23, headless, `apt install scribus`): opens our IDML with
  pages, masters, running heads, folios, sections, images, tables and justification; but every
  font becomes its default (so italic and bold go too), and footnotes are dropped entirely.
  InDesign's own reference files (01, 12) lose fonts and footnotes the same way, so it's
  Scribus's IDML import, not our files. Not a target (Beaux to decide).
