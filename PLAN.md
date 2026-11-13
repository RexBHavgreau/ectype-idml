# Ectype IDML (DOCX → IDML book tool) — project brief

*Status: step 0 (reader and preflight) under way in this repository (October 21, 2026); see "Build order". Name: Ectype IDML (decided November 13, 2026; docx-to-idml until 0.8.0). This brief replaces the October 2026 version, which planned the exporter as a stage of a separate manuscript-prep tool. The earlier contents of this repository (a React/TypeScript concept test made with Qwen Code) were replaced; they remain in git history.*

## Goal

Take a Word book manuscript (one file or several) and produce an IDML file that opens in **InDesign**, **Affinity Publisher** or **DesignCraft** with most of the book already laid out: page geometry, masters, styles, front matter, running heads and pagination. The book should look like it does in Word, but better.

The main use is preparing books for **KDP print**, but the tool is not tied to one publisher or house style. All conventions are user settings saved in profiles.

## Core decisions

### Standalone tool
- The converter is its **own tool**, not part of the earlier manuscript-prep tool.
- Python; CLI first, then a **Tkinter** GUI (themed ttk widgets) built into a single EXE with PyInstaller.
- **Why Tkinter:** it keeps the EXE small (roughly 25–35 MB, against 100+ MB for PySide6/Qt, whose library is most of that size). The setup screens are forms and tables, which Tkinter handles well, and the rest of the plan is unchanged.
- **Considered and set aside:** a browser-based single HTML file (lightest, but limited access to installed fonts and fragile profile storage), Tauri (5–15 MB, but the tool's logic would move to JavaScript or Rust), and C# on .NET Framework (tiny, but a new language and no built-in RELAX NG validation).
- Runs fully offline; needs no Python, InDesign, Affinity or DesignCraft installed. Fonts are checked on the machine running the tool (system and per-user font folders). An unsigned EXE triggers a SmartScreen warning on first run; a Mac version would need a separate build made on a Mac.

### Updates (as with Indicat)
- **Versioned filename:** each release EXE carries its version, e.g. `IdmlWizard-0.3.0.exe` (working name). The version is also embedded in the EXE's file properties.
- **Releases on GitHub**, in a repository of its own on the same account as Indicat. The tool checks the latest release through GitHub's public releases API; no server of its own is needed. This is the same flow as Indicat's updater (check GitHub, alert the user, download to the same folder on yes), keeping it as easy as possible for the user. The checksum, open-new-version and old-copy cleanup steps below are additions beyond Indicat that run without extra effort from the user.
- **When it checks:** at every startup (can be turned off in settings), plus a "Check for updates" menu item. *(Changed in 0.4.0: "at most once a day" missed a release made after the day's check; a declined version isn't offered again at startup.)* With no connection, it fails silently on startup and says so only on a manual check.
- **When a newer version exists:** shows the version number and the release notes, and offers to download it.
- **Download:** to the **same folder as the running EXE**. Because the new file has a different name, nothing is overwritten and the running copy is untouched. The download goes to a temporary name first, is checked against the release's SHA-256 checksum, then renamed. The tool then offers to open the new version and close itself.
- **Old versions:** on first launch, a new version looks for older `IdmlWizard-*.exe` files in its folder and offers to delete them (a running EXE can't delete itself, so cleanup happens from the new one).
- **Folder not writable** (e.g. under Program Files): the tool says so and offers the Downloads folder instead.
- **Settings and profiles survive updates** because they live in the tool's settings folder, not beside the EXE.
- Each new unsigned EXE triggers Windows SmartScreen again on its first run.

### Reading Word
- Word is read by parsing its XML directly with lxml (python-docx doesn't expose sections, headers, footnotes or fields well enough).

### Cross-program rule
- **Nothing that works only in InDesign.** Every feature must work in InDesign, Affinity Publisher and DesignCraft, or have a fallback that does. No InDesign-only .jsx finisher, no InDesign-only text variables.
- **IDML is the single output.** InDesign opens it natively; Affinity imports it (one way, saved as .afpub); DesignCraft reads and writes it.
- **The IDML must be complete without any script:** page count, threading, masters and sections are all set in the file itself.

### Input: one file or several
- The user can select **one .docx or several** (for authors who send each chapter as its own document) and merge them into one IDML.
- **File order is the user's choice.** Selected files appear in a list, first sorted by natural filename order (so "Chapter 2" comes before "Chapter 10") as a starting point. The user then arranges them:
  - drag a file up or down in the list, or use **Move up / Move down** buttons (and Move to top / bottom)
  - **Add** more files or **Remove** one without starting over
  - a **Sort by filename** button to return to the natural order
  - each row shows the filename and the first heading detected in it (e.g. "Chapter 3: The Covenant"), so the order can be checked by content, not just by filename
- The outline, running-head table and page-count estimate update whenever the order changes.
- The chosen order is saved with the book's settings, so a re-export after corrections keeps it. If a file has been replaced by a corrected version with the same name, it keeps its place.
- **Drag and drop from File Explorer** (standard, not optional):
  - drop .docx files onto the list to add them, placed where they're dropped; dropping onto the empty window starts a new book with them
  - drop a **folder** to add all the .docx files in it, in natural filename order
  - other file types, Word's temporary lock files (`~$….docx`) and files already in the list are skipped, with a short note saying which and why
  - the Add button and file dialog remain for anyone who prefers them
- Reordering within the list uses Tkinter's own Treeview. Dropping from Explorer uses **tkinterdnd2** (the tkdnd extension, about 1 MB), which has to be bundled explicitly in the PyInstaller build (`--collect-all tkinterdnd2`).
- Each file can contain one or more chapters, or front/back matter (preface, bibliography). The outline is built across all files.
- **Style conflicts across files** (the same style name defined differently in two files) are reported in preflight. The style map applies by name, so one mapping covers every file.
- Images, footnotes and section settings are collected from every file. Footnote numbering restarts per chapter by default.

### Target programs (proposed October 21, 2026; not needed for now)
*Since fn-m works in both programs, one output serves all; the checkboxes are set aside unless a later finding needs a per-program difference. The report still gives program-specific advice (e.g. Hebrew: use InDesign).*

- The user ticks the programs the book is for: **InDesign, Affinity, DesignCraft** (Scribus only if wanted; it would need its own pass through the reference files). Each ticked program gets its own file (`Book (InDesign).idml`, `Book (Affinity).idml`); none ticked gives one "any program" file with every workaround on. The choice is saved in the profile.
- Differences come from one table of per-program workarounds, so each compatibility finding is one entry. Known so far: footnote formatting written directly on note text for Affinity and "any" (InDesign stays clean); the footnote number always in its own run; Hebrew warnings by program; fewer buffer pages for InDesign (smart text reflow adds pages), the full estimate plus buffer for the others; the TOC style written for InDesign and "any".
- The cross-program rule still holds: every output works in every program; targets only add workarounds, never InDesign-only features.

### Preflight, style map and profiles
- **Preflight** reads every input file and reports all paragraph and character styles in use, direct-formatting hotspots, and items version 1 doesn't carry over (text boxes, floating shapes, tracked changes, equations, unusual fields, XE index fields, endnotes). Nothing disappears silently.
- **Style map:** Word style → IDML style. Defaults cover Word's built-ins (Normal, Heading 1–3, Quote, Footnote Text, Caption, etc.). Unknown styles are mapped by the user or fall back to body text with a warning. All styles are shown together in a style mapping panel after the automatic mapping (0.4.0), where the user picks the IDML style, role and look for each.
- **Profiles** save everything the user sets (style map, trim, margins, fonts, leading, head pattern, notice library, front-matter defaults) so the next book in a series is one click.
  - Defaults are neutral, not tied to any one publisher.
  - Stored in the tool's settings folder, with Export/Import buttons for sharing or keeping a profile beside a series' manuscripts.
  - Each profile file carries a version number; newer releases of the tool upgrade old profiles instead of discarding them.

### Page geometry
- **Trim size:** pick from standard sizes (5×8, 5.25×8, 5.5×8.5, 6×9, 7×10, 8.5×11, A5) or enter a custom size.
- **Facing pages** with inside/outside margins.
- **Bleed off by default**; a toggle adds 0.125″ and applies KDP's with-bleed outside minimum.
- No printer selector. KDP's requirements are the built-in assumption, stored as editable data so other printers can be added later.

### Margins and measure
Calculated, then shown as editable values:
1. **Measure (changed in 0.5.0, Beaux):** about **30 times the type size** (Bringhurst: "usually around 30 times the size of the type", 20–40 expectable; profile `page.measure`), kept between 45 and 80 characters of the body font as measured from the font file with the manuscript's text (in effect his copyfitting table). At 11 pt that is 4.6″, about 71 characters; the old basis (65 characters) gave margins of about an inch, wider than trade books (Beaux measured a 6×9 at 74–76 characters, about 1″ inside, 0.6″ outside and top, 0.75″ bottom).
2. **Margins** take the remaining width and height: the outside 42% of the spare width, the inside the rest and **never less than the outside** by default (only a value the user types can make the outside wider); top and bottom 15% of the page height, 45/55, with room for running heads and folios.
3. **Floors:** every margin at least **0.5″**; the gutter also at least **KDP's minimum for the estimated page count**.
4. If the floors leave too little width, the measure gives way; under 45 characters the tool reports the problem and suggests a smaller size or a larger trim.
- **Page-count estimate:** words → characters per line → lines per page, plus pages added by structure (front matter, chapter openers, blank versos from recto rules). Pick the gutter band, recompute, repeat until stable. The report shows the estimated count, the KDP band, a warning near a band boundary, and a note for very short books (KDP minimum, even-page rounding).
- **User overrides:** any margin can be changed; the page count is re-estimated, with a warning (not a block) if the gutter drops below KDP's band minimum. Wider margins are always safe for printers with lower minimums.
- **Very large trims** with small type: the tool suggests a larger size or two columns.

### Leading
- Entered in **points by default**; the user can switch to a multiple or percent. Converted to points at export (IDML stores leading in points).
- From Word: "Exactly" carries over as-is; "Multiple" and "At least" are converted to points from the font size and shown in the box for rounding.
- Beside the box, **suggested tight / standard / open ranges** for the current size (at 11 pt, roughly 12.5–13 / 13.5–14 / 14.5–15), shifted for the font's x-height and the measure, with a one-line explanation when they shift.
- **Baseline grid off by default**; the user can turn it on (it uses the leading value as its increment).
- *(Built in 0.3.0: profile `body_size` and `leading.feel`; the suggested ranges shift by about the x-height's excess over 0.46 em times the size, and 0.2% per character of line length over 65; the window shows them and the leading the export will use. Taking the leading from Word isn't done: manuscripts are usually double-spaced.)*

### Fonts
- Chosen by **role**: Body, Headings, Notes, Display, and script fonts for **Hebrew** and **Greek**. Each style inherits its role's font; per-style overrides for exceptions.
- **Prefilled from Word.** If the body font looks like a template default (Calibri, Times New Roman), the tool notes it and offers the profile's house fonts.
- **Checks:** the font is installed; it has the faces the manuscript uses (italic, bold, bold italic); true OpenType small caps (otherwise scaled capitals, with a warning); Hebrew coverage including vowel points and cantillation, Greek polytonic coverage.
- **Hebrew needs InDesign.** Affinity does not support Hebrew (confirmed; in testing it set imported Hebrew left to right with letters reversed). When preflight finds Hebrew, the tool says plainly that the book must be laid out in InDesign, not Affinity. The Hebrew character style still carries font, language and right-to-left direction, so InDesign handles it correctly. Add a Hebrew test to the DesignCraft checks.
- **Hebrew and Greek runs** are detected by Unicode range (Word keeps right-to-left fonts in a separate slot) and wrapped in "Hebrew" and "Greek" character styles that set font, language and, for Hebrew, right-to-left direction.
- Changing the body font reruns the measure, margin and leading calculations.

### Masters
A standard set is **generated every time**, with settings taken from Word where present (`w:sectPr`, header/footer distances) and from the profile otherwise:

| Master | Use | Contents |
|---|---|---|
| A-Body (facing) | Regular text pages | Running heads, folios, primary text frame |
| B-Chapter opener | First page of each chapter | Based on A; no running head; drop folio; sunk text frame |
| C-Front matter | Contents, preface, etc. | Based on A; roman folios |
| D-Display | Half-title, title, copyright, dedication | No folio or heads |
| E-Blank | Intentional blank versos | Nothing |
| F-Back matter (optional) | Bibliography | As A, adjustable |

Masters are applied by rule: chapter starts get B, front-matter pages C, display pages D, inserted blanks E.

### Running heads
- **Detection** builds an outline from (in order of trust) the style map, Word section breaks and existing STYLEREF headers, then fallback cues (outline levels, a TOC field, known front/back-matter titles). Units are classified as front matter, part, chapter or back matter. The manuscript doesn't need running heads set up in Word.
- **Setup step:** a global pattern (verso: book title / part / chapter / author / custom; recto: chapter title / custom), toggles to suppress heads on openers, display pages and blanks, and a per-unit table with editable verso and recto fields prefilled from detected titles. **Titles too long for the measure are flagged** so short titles can be written.
- Choices save to the profile so a re-export after corrections doesn't ask again.
- **Mechanism (confirmed in Affinity 3.3.0, October 21, 2026; DesignCraft pending):** one IDML section per chapter (`ContinueNumbering="true"`) with the recto short title in the section **marker**; the A-Body recto head is the Section Marker character. If Affinity maps this to its Section Name field and DesignCraft keeps it, one master serves every chapter.
- **Fallback:** one child master per chapter (based on A-Body) carrying the heads as static text.
- Section-level recto heads (changing with H2s) are **out**: they require InDesign-only text variables.

### Front matter
A stage of its own: detect what's present, generate what's missing, order it and paginate it.
- **Order** (Chicago): half-title, (series page / frontispiece), title, copyright, dedication, epigraph, contents, foreword, preface, acknowledgments.
- **Half-title and title page:** generated if missing, prefilled from the detected title, subtitle and author; input fields when detection fails.
- **Copyright page:** generated if missing. Fields: copyright line (year, holder, all rights reserved), publisher name and address, edition/printing line, ISBNs (print, ebook), optional credits, country of printing, catalog data. A **notice library** (Bible versions, works quoted by permission) the user maintains in the profile and ticks per book; the tool ships no authoritative notice wording. English or Spanish boilerplate. Author detection: title page text first, user input with the detected name prefilled (`docProps/core.xml` creator is unreliable; it is usually whoever made the file).
- **Contents (decided October 21):** the tool sizes the reserved contents pages from the outline: entries (chapters, or chapters and first-level sections, plus parts and back matter), lines per entry (long titles wrapped at the measure less room for the page number) at the Contents style's leading, space above level-1 entries and the title, divided by lines per page and rounded up; then the recto rules (contents opens on a recto; a blank verso before the preface if the contents ends on a recto). The report gives the number; the user can change it. The contents itself is placed by hand from the Contents style (step 3: not generated in either program).
- **Contents:** offered when none is detected. Page numbers don't exist until layout, so the tool reserves the contents page(s) (estimated from entry count and lines per page) with a placeholder frame, and the user inserts the TOC with the layout program's own feature. Depth option: chapters only, or chapters plus first-level sections. An existing Word TOC field is replaced, not imported (its page numbers would be wrong). *Step 2 result:* a generated TOC does not survive in Affinity (formatting inconsistent, page numbers wrong or missing, no levels, can't be updated). So the tool writes **no generated contents**, only the reserved pages; it does write the TOC style (harmless in Affinity) so an InDesign user can generate the contents in one step.
- **Pagination:** front matter is one roman section starting at i. Display pages (half-title, title, copyright, dedication) are **counted but not folioed** (D/E masters), so the first visible folio falls on contents or preface. Chapter 1 starts a new section at arabic 1.
- **Page numbers (1.1.0):** placed at the foot centered (default), at the foot outside, or at the head outside on the running heads' line (a frame of its own, aligned to the outside); on chapter openers at the foot (a drop folio, centered when the others are at the head) or none. Profile `running_heads.folio` / `opener_folio`.
- **Recto rules:** title page, dedication, contents, preface and chapter 1 open on a recto. **Chapters open on a recto by default**; the profile can switch to "next page". Blank versos (E-Blank) are inserted as needed.

### Content carried over
- Paragraph and character styles with full settings and inheritance (fonts, sizes, spacing, indents, tabs, keep-with-next, widows/orphans).
- **Footnotes.** **Endnotes are not supported**; preflight flags them and offers to convert them to footnotes.
- Simple tables, images (extracted and linked), lists as auto-numbering.
- **No index.** XE fields are stripped from the text and listed in preflight; indexing in InDesign is handled by Indicat's .jsx (Affinity's IDML import doesn't carry indexes).
- **Left out in version 1** (and listed in preflight): text boxes and floating shapes, tracked changes, equations, unusual field codes.

### Threading
- **Each chapter is its own threaded story** starting on a B-Chapter opener page. Overflow stays in its chapter; a short chapter leaves at most a page or two to delete. InDesign adds pages for an overset story by itself (smart text reflow, reference file 05); **Affinity does not**, even in its own files (step 2), so the page-count estimate and buffer must leave every chapter fitting without help.
- Initial page counts come from the page-count estimate (or Word's `<Pages>` count in `docProps/app.xml`, scaled to the new trim), with a small buffer.

### Defaults the user can switch off
- Paragraph composer, optical margin alignment, hyphenation per language (InDesign has no Latin dictionary).
- OpenType small caps, ligatures, old-style figures where the font supports them; balanced ragged lines for headings.
- Footnote rule (default off), a rule above continued notes (default on), and the spaces above the notes, below a rule and between notes; widow/orphan control.
- Each depends on the target program keeping the setting; ones that don't survive are simply lost, never broken.

## Compatibility testing

**Affinity target: the current Affinity app (the Canva relaunch), not Affinity Publisher 1 or 2.** It imports IDML (and, since September 2026, INDD, though IDML is described as the more reliable route) but has no IDML export, so the path stays one-way.

The only published list of supported IDML features is for Affinity Publisher **V1**: facing spreads, master pages, automatic page numbering, bleed, grids and guides, frame properties, text styles, missing-resource warnings, tables and blend modes. Text variables other than page numbers are converted to static text. Footnotes, sections, section markers and TOC styles aren't mentioned. Treat the list as a hint only; the current app must be tested.

DesignCraft is pre-alpha (0.8.0), with IDML support checked against synthetic files only. The plan is a set of **small feature test files**, one feature each:

- footnotes
- section markers → running heads (Affinity's Section Name field)
- sections with roman → arabic numbering
- facing-page masters, **parent/child masters**, **primary text frames on masters**
- TOC style
- table style
- OpenType settings
- baseline grid
- Hebrew right-to-left run
- linked image

**How they get checked:**
- **InDesign and Affinity:** the user opens each file, records works / partly works / lost, notes the exact Affinity version, and exports a PDF of each file as Affinity opened it for comparison. Notes cover what a PDF can't show (live field vs static text, masters still linked).
- **DesignCraft:** automated. Its CLI can open an IDML and export each page as PNG, giving the headless check Scribus couldn't.

The results form a **compatibility table** that decides each fallback.

### Compatibility table (step 2, October 21, 2026)
The 13 reference files from InDesign, opened in the current Affinity app by Beaux (details in `reference/README.md`). DesignCraft still to check.

| Feature (file) | Affinity | Decision |
|---|---|---|
| Footnotes (01) | **Works**: at the page foot, numbering restarts per section, a long note splits. As InDesign writes them, notes lose their style or fall back to the root style's font and size | **Written as in fn-m** (see the decision below): works in both programs, and style edits reach every note |
| Section-marker running heads (02) | **Works** | Recto heads from section markers, one section per chapter, as planned |
| Roman/arabic sections, display pages without folio (03) | **Works**. The odd placing of pages in Affinity copies InDesign's own spreads: the front matter ended on vii, so InDesign put chapter 1 alone on a recto spread and page 2 alone on the next | As planned. The generator inserts a blank verso (E-Blank) before a recto opener, so spreads stay in pairs |
| Parent/child masters (04) | **Works**: B-Opener stays based on A-Body, heads removed, folio dropped | B-Opener based on A-Body; no per-chapter master fallback needed |
| Primary text frame, page added for overset (05) | **Pages and threading kept; Affinity adds no pages** (not even in native files) | Keep the primary frame (InDesign reflows), but write enough pages for each chapter from the estimate plus a buffer |
| Generated TOC (06) | **Lost in practice**: formatting inconsistent, page numbers wrong or missing, no levels, not updatable | No generated contents; reserved pages plus the TOC style |
| Table (07) | **Partly**: styles and merged cells kept; the header row is not repeated on the next page (InDesign repeats it) | Write header rows as InDesign does; nothing to fix for Affinity; long tables rare in Word books. *The generator's table (g07) doesn't break across pages in Affinity at all, though 07 does: parked.* |
| OpenType features, composers, hyphenation, optical margins (08) | **Works** | Write them as planned (user can switch off) |
| Baseline grid (09) | **Works** | As planned (off by default) |
| Hebrew (10) | **Fails** (reversed), as expected; style-level direction doesn't help. Greek, and the English around the Hebrew, are fine | Unchanged: books with Hebrew go to InDesign |
| Images, inline and with wrap (11) | **Works** | Inline anchored images for Word's inline pictures |
| Partly defined character styles (12) | **Works**: each keeps the paragraph's font and size | Character styles define only what they change |
| Story per chapter, overset, blank verso (13) | **Works** | As planned |

**Four files were faulty (found October 21):** the script typed text at the end of the story, so text after a styled run kept that run's character style. After the first footnote callout, the body text was in "Footnote Reference" (superscript, in InDesign's PDF too); in 08 the text after "UNESCO, NASB, LXX" stayed in All Small Caps; in 10 English after Hebrew stayed in "Hebrew"; in 12 text after "No Break" stayed in No Break. **The results for 01, 08, 10 and 12 are therefore provisional**; script version 4 rebuilds the four with every run's character style set explicitly. Affinity's PDF of the faulty 01 (3.3.1) still shows one thing worth retesting: in note 1 the Footnote formatting holds until the italic character style, then the text goes to [Basic Paragraph] size; notes 2 and 3 are [Basic Paragraph] throughout (those sat inside the stray "Footnote Reference" range, so the clean file may differ).

**Version 4 result (October 21):** 08, 10 and 12 are clean; 01 is clean in the IDML (body text after callouts in `[No character style]`, every note paragraph in Footnote), **but Affinity shows the same faults**: body text after the first callout in "Footnote Reference", note 1 losing its formatting at the italic, notes 2 and 3 losing the Footnote style. So Affinity's import mishandles InDesign's footnote structure: each `<Footnote>` sits inside a CharacterStyleRange in the marker style, and character style runs inside notes. The article's footnotes (callouts as local superscript, no marker style) came through, which points at the marker style. `tools/make_footnote_variants.py` makes six variants of 01 (`reference/variants/`), one change each, for Beaux to open in Affinity; the results choose how the generator writes footnotes. Footnotes are essential, so this is settled before the generator is written.

**Variant results so far (Beaux, October 21):** fn-c and fn-e (note text also formatted directly) keep the notes' look in Affinity; in both, only note 1 keeps the paragraph style name "Footnote", later notes show [Basic Paragraph]. So Affinity applies the note style to the first note only; direct formatting is the way to make every note look right there. Still to report: body text after callouts in fn-a and fn-b (plain, or "Footnote Reference"?), and whether the first note of chapter two (a second story) keeps the style.

Beaux confirmed the same footnote fault in an IDML exported from a real InDesign document, so it is Affinity's IDML reader, not the generator. Three more variants test the two file-side ideas left: a paragraph break ending each note (fn-f), and note styles renamed away from "Footnote" in case Affinity's own notes style takes over (fn-g, fn-h). If neither keeps the style, the pathway is direct formatting on note text for Affinity books (fn-c), plus re-applying the style in Affinity if it allows that in one step.

**Variants f, g and h changed nothing (Beaux, October 21).** Affinity has a document-wide footnote style setting. IDML has exactly one place for the footnote text style: `FootnoteOption FootnoteTextStyle` in Preferences.xml (the schema has no other footnote style setting; `TextFrameFootnoteOptionsObject` has none), and every file so far already sets it to Footnote. To check in Affinity: which style its footnote setting shows after opening fn-0 (does Affinity read `FootnoteTextStyle` at all?), and whether choosing Footnote there restyles all the notes. If it does, the clean pathway is one step after opening: set Affinity's footnote style to Footnote; the tool writes clean notes and says so in its report, and no direct formatting is needed.

**Cause found (October 21):** Affinity treats a note as a proper footnote only if the note's paragraph has **two or more CharacterStyleRanges**. In fn-0, note 1 (three runs: plain, Italic, plain) works and every single-run note is broken (settings greyed out, style lost), in both stories. In the Assumption article it's the other way round: note 1 is a single run and broken (it took Body Main), notes 2–6 have 4–16 runs and work (Beaux: changing the document-wide footnote style reaches all of them except note 1). Workaround to confirm: write the footnote number (`<?ACE 4?>` and the separator) in a run of its own, so every note has at least two (fn-i; fn-j adds plain callouts). If it works, the generator always writes notes that way; InDesign accepts it.

**fn-i and fn-j result (Beaux, October 21): the workaround works for the style.** Every note gets the Footnote style by name and responds to Affinity's document-wide footnote setting. Two things left: the notes don't look like the Footnote style on opening (the name is right, the formatting isn't), and choosing the style again in the document-wide setting strips italics (character style and local). The generator will put the footnote number in its own run either way; fn-i (callouts unchanged) is enough.

**fn-i details (Beaux):** editing the Footnote style reaches every note that really has it, italics kept. But on opening, note text after an Italic run (note 1's "in it") and all of note 2 onward show 12 pt Minion Pro with a "+": InDesign's built-in default font and size laid over the style as overrides, while the indent (a paragraph setting) comes from Footnote. Variants fn-k (no character style anywhere in the notes) and fn-l (italic as local formatting) test whether a character style in a note is what triggers it.

**fn-k and fn-l: both still wrong** (Beaux): with no character style at all in the notes, the text from "in it" on in note 1, and later notes, still show 12 pt Minion Pro "+". 12-character-styles (v4) is fine, so the fault is limited to footnotes. The 12 pt Minion Pro is not Affinity's own default: it is the file's root style, `[No paragraph style]` (Minion Pro, 12 pt, auto leading), which InDesign writes in Styles.xml and on which Footnote is based. The generator writes that root style itself. Two files: fn-n (diagnostic: root changed to Arno Pro 10 pt; if the faulty text turns Arno 10, Affinity is falling back to the root style) and fn-m (number in its own run plus the Footnote settings written directly on the note text: the fallback that should look right on opening).

**fn-m and fn-n result (Beaux, October 21):** **fn-m works perfectly in Affinity**: every note 9 pt Arno, Footnote style, no "+". fn-n confirms the cause: the faulty text (from "in it" in note 1 on) became Arno Pro 10 pt with a "+", i.e. Affinity lays the root style `[No paragraph style]` over that note text. Last check before deciding: editing the Footnote style (9 → 10 pt) in fn-m, in Affinity and in InDesign (does InDesign show a "+" on opening?). If notes follow the style in both, fn-m is how the generator writes every footnote and per-program outputs aren't needed for footnotes.

**Decided (October 21): footnotes are written as in fn-m, for every program.** Editing the Footnote style (9 → 10 pt) reached every note in both Affinity and InDesign, so the directly written settings don't block style changes. The generator writes each note as:
- the note paragraph in the Footnote style (`FootnoteOption FootnoteTextStyle` also set to it);
- the footnote number `<?ACE 4?>` and the separator in a run of their own (so every note has at least two runs; single-run notes are broken in Affinity);
- the Footnote style's font, size, leading, indent and alignment also written on every run of note text (Affinity otherwise lays the root style over note text);
- italic and other character formatting in notes as usual.

~~**Open: footnote text in Affinity.**~~ Settled by the decision above.

**Footnote rule and spacing (Beaux, October 21):** in 01 the note text sits right under the rule (all spacing at its minimum). Wanted: the rule switchable on or off; space above and below the rule; with no rule, only space between body text and notes; and optionally a rule only above notes continued from the previous page. IDML has each as its own setting in `FootnoteOption`: `RuleOn` (rule above the notes), `ContinuingRuleOn` (rule above continued notes, own width), `Spacer` (minimum space before the first note), `FootnoteFirstBaselineOffset` + `FootnoteMinimumFirstBaselineOffset` (rule to first baseline), `SpaceBetween`. Profile version 2 has a `footnotes` section: numbering, rule (default off), continuation_rule (default on), space_above (12 pt), space_below_rule (6 pt), space_between (3 pt). Variants fn-o (both rules, spaced), fn-p (space only) and fn-q (continuation rule only) test how InDesign and Affinity render these settings. **Result (Beaux): both programs show the spacing and the continuation rule as set.** Both rules default to 1 inch (`RuleWidth`, `ContinuingRuleWidth`; profile `rule_length`, 72 pt); the variants first had the continuation rule at the full text width, as InDesign does by default. Options: (a) also write the Footnote style's settings (font, size, leading, indent) directly on the footnote text, so it looks right in Affinity even without the style (InDesign would show the style with overrides); (b) leave it to the user to apply the Footnote style to the notes in Affinity in one step, if Affinity allows that; (c) (a) only when the profile says the book is for Affinity.

Beaux's reminders, already in the plan: chapter opener pages carry no running heads (02 had them only on the test's A master), and blank pages carry nothing, neither heads nor folio (E-Blank).

### Method: InDesign as the reference
Affinity is known to open InDesign-exported IDML (tested). But opening a file isn't the same as keeping every feature, and InDesign writes far more explicit IDML than a generator does, so Affinity may depend on attributes InDesign always writes but the schema treats as optional. Testing is therefore split into two questions:

1. **Does Affinity support the feature at all?** Build each feature by hand in InDesign, export it as IDML, and open that file in Affinity (and DesignCraft). This sets the ceiling, independent of the generator.
2. **Does the generator write it correctly?** Compare the generator's IDML for the same feature against InDesign's reference export. Also open the generated file in InDesign and re-export it: if InDesign's re-export works in Affinity but the generated file doesn't, the differences between the two files show what's missing.

The InDesign reference exports are kept with the project as the standard the generator is checked against.

### First reference document (October 21, 2026)
A real 34-page article exported from InDesign 2026 (21.6) — Daugereau, *Assumption Dogma*. Used for analysis only, not kept as a test file.

- **Validates cleanly** against the converted schema (confirms the schema conversion; only fix needed was letting the validator accept InDesign's `META-INF/metadata.xml`).
- **Page setup:** 6×9 in (432×648 pt), facing pages, no bleed.
- **Running heads use two mechanisms, one of each kind we need to test** (checked against the InDesign PDF):
  - **Verso = section marker**, the planned mechanism: one section per chapter, `ContinueNumbering="true"`, chapter title in `Marker`. Story: `<?ACE 18?> |  ` + `<?ACE 19?>` (Italic). **ACE 18 = page number, ACE 19 = section marker.** Prints e.g. "2 | *The Hermeneutics of the Assumption*".
  - **Recto = InDesign "Running Header" text variable** (MatchParagraphStyle type, picking up Heading 1): `<TextVariableInstance … AssociatedTextVariable="dTextVariablenRunning Header"/>` + `  | <?ACE 18?>`. Prints e.g. "*Introduction* | 3". This is the InDesign-only kind the plan rules out; Affinity's V1 docs say such variables become static text, so this file tests that directly.
- **Masters:** A-Parent (body), C-Parent (folio only), A-Title, A-Copyright, B-Contents. None is based on another master, and **none uses a primary text frame**. So parent/child masters and primary frames still need their own small test files.
- **Part and chapter openings follow the planned pattern:** page 11 = part title page (recto, C master, dropped folio), page 12 = intentional blank verso (C), page 13 = chapter opener (recto, C). The Chapter Title style uses `StartParagraph="NextOddPage"`. Section 2 starts on page 11 with the part title as its marker.
- **Threading:** the whole article is **one story** across all 34 pages (both chapters), not one story per chapter.
- **Footnotes:** 103. Structure: `<Footnote>` inside a `CharacterStyleRange`, containing a `ParagraphStyleRange` (style "Footnote") whose text starts `<?ACE 4?>` (the footnote number) followed by the separator. Footnote options sit in `Preferences.xml` (`FootnoteOption`, separator ". ", rule off). The reference marker's superscript is local formatting (`Position="Superscript"`) on every marker, not a character style; **the generator should use a character style instead.**
- **Direct formatting is common:** 135 local `FontStyle` overrides (italic) besides the Italic style. Preflight should expect this from Word-born text.
- **Greek:** 6 runs. Two are tagged **`AppliedLanguage="$ID/Arabic"`**, apparently left over from import, a concrete example of why the tool should set script languages itself.
- **Hebrew:** none in the text, though the document defines a Hebrew language and Taamey David CLM. Hebrew right-to-left still needs a test file.
- **Not covered here:** TOC style, title-page content, tables, linked images, baseline grid, parent/child masters, primary text frames, Hebrew.

**Opened in Affinity 3.3.0** (the current Canva app; PDF exported as spreads) and compared page by page with InDesign's PDF:

| Feature | Affinity result |
|---|---|
| Page size, facing pages, page count (34) | **Kept** |
| Section-marker running heads (verso) | **Kept, live:** change correctly from "The Hermeneutics of the Assumption" to "The Development of the Assumption Dogma" at section 2 |
| Page numbers, section numbering continuing | **Kept** |
| Masters, dropped folios on part page and opener, blank verso | **Kept:** pages 11–13 match InDesign |
| Running Header text variable (recto) | **Lost:** prints the literal placeholder **"&lt;Running Header&gt;"** on every recto, not even static text. Confirms: no InDesign text variables. |
| Paragraph and character styles (body, italic, small caps) | **Kept** for Arno Pro body text |
| Heading fonts (Source Sans *Variable*; Segoe UI) | **Substituted with Arial.** Affinity did not match the variable font. The tool should warn about variable fonts and prefer static font families. |
| Footnotes | **Kept**: placed at page foot with rule and numbering. But Affinity **kept each footnote whole** where InDesign split long ones across pages, which pushes text and changes page breaks. |
| GREP styles (8 rules in the Footnote style applying a "No Break" character style) | **Damaged:** text matched by the GREP rules printed at a larger size and different font, i.e. lost the paragraph style's settings. The generator writes no GREP styles (Word has none), so this doesn't affect the tool, but it shows that partially-defined character styles can pick up defaults in Affinity; worth a test file. |
| Line and page breaks | **Different on 28 of 34 pages.** Causes: the heading font substitution and unsplit footnotes; Affinity also has its own line breaker. *(Corrected October 21: "HL Composer Optyca" in the styles is not a plug-in. It is InDesign's internal name for its own Adobe World-Ready Paragraph Composer, as reference file 10 shows; see "Reference files from InDesign" below.)* |
| Text fit | **About 800 words didn't fit** on the 34 pages (most likely left as overset text at the end of the story, since it's one story with a fixed page count). InDesign's own copy ends mid-sentence too, so it was already slightly overset. This supports chapter-per-story threading plus a page buffer, and the instruction to check for overset text after opening in Affinity. |
| Greek | **Kept** where it fit (the two missing Greek words are in the text that didn't fit) |

### Second reference file (October 21, 2026): primary frame, parent master, TOC
A 7-page cut-down of the same article ("Untitled-1"), with a primary frame added to A-Parent and a generated TOC. Validates cleanly.

- **How InDesign records the primary frame:** on the master, `MasterSpread … PrimaryTextFrame="u155"`, pointing to the frame's `Self` ID. Here it points only to the **recto** frame of the facing A-Parent; the verso master frame (`u13e`) is neither primary nor threaded to it. Smart Text Reflow settings are in `Preferences.xml` → `TextPreference SmartTextReflow="true" AddPages="EndOfStory" LimitToMasterTextFrames="true" DeleteEmptyPages="false"`.
- **Why InDesign didn't add pages:** still open. *Correction (October 21, from `tools/idml_inspect.py`):* the page frames **are** overrides of the master frames. InDesign records the link on the `<Page>`, not the frame: `OverrideList="u13e u1a5"` lists pairs of master item and page item (master frame u13e → page frame u1a5). Every body page of both files carries one such pair, the original article included (its frames override A-Parent's non-primary frames u13e/u155). So "local frames" was wrong; the likelier reason no pages were added is that the story wasn't overset. In Untitled-1, pages 2 and 3 override the opposite-side master frame (verso page ← recto frame u155), so InDesign doesn't require the frame to come from the same side. Reference file 05 (fresh document with a primary text frame, more text than fits) settles it.
- **Parent/child master:** A-Title's page has `AppliedMaster="ud8"` (based on A-Parent), which shows how a master based on another is written. Affinity result pending.
- **Revised version (same day):** the A-Parent master frames are now threaded verso → recto, with `PrimaryTextFrame` pointing to the verso frame (`u13e`). The page frames override them (see the correction above), but InDesign still added no pages. The revision also added test content: Hebrew (character style "Hebrew Regular", Taamey David CLM), polytonic Greek, a linked image with bounding-box text wrap, a 4×4 table and a Heading 3. 7 pages in both programs.
- **Affinity 3.3.1 results for the revised file:**
  - **Hebrew: letters reversed.** InDesign sets the Hebrew right to left; Affinity sets the same letters left to right (word order and letter order both mirrored; vowel points not tested). In the IDML, direction is a local override on the run (`CharacterDirection="RightToLeftDirection"`), not part of the "Hebrew Regular" style, and Affinity ignored it. **Confirmed (Beaux, independently of this test): Affinity does not support Hebrew at all.** So books with Hebrew must be laid out in InDesign (DesignCraft's right-to-left support is untested). Pre-reversing Hebrew for Affinity is rejected: it breaks copy and search, and fails whenever a Hebrew phrase wraps across lines.
  - **Greek (polytonic):** kept.
  - **Linked image with text wrap:** kept, wrap included. InDesign writes the link as an absolute `file:` URI (`file:D:/Downloads/images.jpg`), and Affinity found the image.
  - **Table:** kept.
  - **TOC:** came across with the right entries, but the entry lost its bold and the page number sits right after the text instead of at the tab position. Whether it stays updatable in Affinity is still to be checked in Affinity itself.
  - **Footnotes:** again kept whole in Affinity where InDesign splits them.
- **TOC:** a generated table of contents on page 1. The `TOCStyle` (in Styles.xml) lists Heading 1 at level 1, tab before the page number, title "Contents". The TOC text is an ordinary story marked `AppliedTOCStyle="TOCStyle/$ID/DefaultTOCStyleName"`, with hyperlinks to the headings. Affinity result pending (whether the TOC stays updatable or becomes plain text).

### Reference files from InDesign (October 21, 2026)
`reference/make_reference_files.jsx` (version 1) ran in InDesign 21.6.0.57 with Arno Pro, Myriad Pro and Taamey David CLM. 12 of 13 files were made and are in `reference/idml/`; **all 12 validate** (structure and schema). 05 (primary text frame) came out without a primary frame and 06 (TOC) failed. Version 2 rebuilt both; both validate. 06 is right: a TOC style "Contents" with two levels (Chapter Title → Contents 1, Heading A → Contents 2, tab before the page number) and the generated story marked `AppliedTOCStyle`. 05 v2 showed that **smart text reflow works once the page frame is linked to the primary frame**: InDesign added pages by itself (4 → 6) and left nothing overset. But the file is muddled (InDesign had already linked empty frames on pages 2–4, and the script added local frames over them), so version 3 rebuilt 05 from one page, using only the frame InDesign links, and letting reflow add the rest. **Version 3 result (clean, validates): InDesign went from 1 page to 6, nothing overset, one story threaded through six page frames.** Each page frame overrides the master frame for its own side (recto ← u118, verso ← u101; the master frames are threaded verso → recto, `PrimaryTextFrame` = the verso one). The page frames are ordinary `TextFrame`s, identical to local frames apart from their ids: the only link to the master is the `<Page>`'s `OverrideList` pair. The story is a new one, not the master frames' story. So the generator writes: master frames threaded with `PrimaryTextFrame` set, each page's frame as a plain threaded frame, and an `OverrideList` pair on its page. InDesign then reflows such a story by itself; whether Affinity and DesignCraft do is a step 2 question.

What InDesign writes, for the generator to copy:
- **Composers** are stored under internal names: Adobe Paragraph Composer = `HL Composer`, Adobe Single-line Composer = `HL Single`, Adobe World-Ready Paragraph Composer = `HL Composer Optyca`. This InDesign's default (`[No paragraph style]`) is World-Ready.
- **Footnotes:** the marker character style goes in `FootnoteOption FootnoteMarkerStyle` (01: "Footnote Reference", which defines only `Position`). `RestartNumbering="SectionRestart"` restarts at each section.
- **Sections:** `PageNumberStyle` is a child property (`LowerRoman`, `Arabic`); a restart is `ContinueNumbering="false"` with `PageNumberStart="1"`. The section marker is `Marker`.
- **Masters:** a master based on another has `AppliedMaster="<parent id>"` on each of its `<Page>`s. A parent item removed on the child is a pair with `n` in the child page's `OverrideList` (`"u117 n"`). A page with no master has `AppliedMaster="n"` (13, the blank verso).
- **Page frames from master frames:** `OverrideList="<master item> <page item>"` pairs on the `<Page>`.
- **Character styles** define only what they set (12: Italic defines `FontStyle` only; Small Caps `Capitalization`; No Break `NoBreak`).
- **Hebrew (10):** direction and language now sit in the styles (`CharacterDirection`, `ParagraphDirection`, `AppliedLanguage` on "Hebrew" and "Hebrew Block"). Whether Affinity honors them there is the step 2 question.
- **Images (11):** links are absolute `file:` URIs (`file:D:/Downloads/images/sample.jpg`); the inline image is an anchored `Rectangle` inside the story.

### Schema validation
- Every IDML the tool writes (feature test files included) is **validated against Adobe's IDML schema** before it's handed over, catching structural errors without opening any outside program.
- The schema (RELAX NG) can be generated once from InDesign through its scripting API (`generateIDMLSchema`) and shipped with the tool as a data file.
- No built-in page previewer: the user reviews the layout in their own program.
- **Schema in hand (October 21, 2026), complete:** generated from **InDesign 2026 (21.6.0.57)**; requires **`DOMVersion="21.5"`** in every part, so the tool writes that version. Kept in `idml-schema/` with the original .rnc files and the converted .rng files. *(In this repository since October 21, 2026: `idml-schema/rnc/` as InDesign wrote it, `idml-schema/rng/` converted by `tools/prepare_schema.py`; `tools/idml_check.py` runs the structural checks and jing. Both InDesign reference files validate cleanly, about 4 s each.)*
- **What the validator checks:** zip structure (`mimetype` first and uncompressed), `container.xml`, every XML part against its schema, and that designmap.xml's references and the package's files match both ways.
- **Validation is a development and test-suite step, not done inside the shipped EXE.** lxml (libxml2) turned out to be far too slow on this schema's interleave patterns: `Styles.xml` didn't finish in 60 s even when valid. **jing** validates the same file in about a second, with clearer messages, but needs Java. So jing (via the `jingtrang` package) runs on every test file and sample book during development; users never need Java. The tool's own correctness comes from writing only structures the test suite has validated.
- **Conversion notes:** Adobe's `datatype.rnc` has a documentation comment written without `#` marks (the "Schema for packaged folios" table, 18 lines), which breaks every parser; `prepare_schema.py` comments it out. `rnc2rng` mis-converts the included grammar; trang converts correctly.
- **First result, `build_idml.py`:** its output fails in three ways, each fixed and confirmed (with the fixes, the package validates):
  1. `DOMVersion="13.0"` in every part (must be 21.5)
  2. `PageNumberStyle` written as an attribute on `Section`; it must be a child element: `<Properties><PageNumberStyle type="enumeration">Arabic</PageNumberStyle></Properties>`
  3. `InsetSpacing` written as an attribute on `TextFramePreference`; it must be a child element: `<Properties><InsetSpacing type="list"><ListItem type="unit">0</ListItem>…(×4)</InsetSpacing></Properties>`
  InDesign opened the file anyway, but Affinity and DesignCraft may be less forgiving, which is the reason for validating.

## Lessons from the first IDML experiment

A hand-built IDML was generated for a bilingual Latin/Spanish edition (Augustine, *De Genesi ad litteram* I–IV), with each book as a 2-column table in one threaded story (`build_idml.py`).

- **It opened in InDesign.** The hand-written package structure works: mimetype stored uncompressed first, `META-INF/container.xml`, `designmap.xml`, `Resources/{Graphic,Fonts,Styles,Preferences}.xml`, a master spread, spreads, stories.
- **Many blank pages at the start had to be deleted.** The page count was guessed (104 pre-threaded pages in one story); a table row taller than a frame likely left frames empty. Chapter-per-story threading and the page-count estimate are the fixes.
- **InDesign table rows can't break across frames.** Long rows must be split (the 14 longest sections were split at matching sentences).
- Geometry used and accepted: non-facing pages centered on the spread origin (`Page ItemTransform="1 0 0 1 -306 -396"` for US Letter), text-frame path points in spread coordinates.
- No language was set in the styles; the real tool must set hyphenation languages.
- `build_idml.py` is a useful reference for package structure, styles, cell and table styles, master page and footer, threaded frames, and the (empty) `Section` marker and `TOCStyle` elements.

## Build order

0. **Reader and preflight:** parse one or several .docx files, build the outline, report styles and unsupported items; style map and profile format. *(Under way, October 21, 2026: `python -m ectype_idml preflight`. Not yet tried on a real manuscript from Word.)*
1. **Schema and reference files:** ~~obtain the IDML schema and set up validation~~ (done October 21, 2026); make the InDesign reference export for each feature (list above), and validate those too, as a check on the validator itself. *(October 21, 2026: `tools/idml_check.py` checks a package's structure (zip, container, DOMVersion, designmap references both ways, StoryList, threading, masters, overrides, sections) and passes both InDesign files; `tools/idml_inspect.py` summarizes a package for comparing generated files with references. `reference/make_reference_files.jsx` builds all 13 reference files in InDesign and exports IDML, PDF and INDD; `reference/README.md` has the list and the Affinity checklist for step 2. The schema is in the repository and validation works. **Step 1 done (October 21): all 13 reference files made in InDesign and validated.**)*
2. **Check the reference files** in Affinity (user) and DesignCraft (CLI); record the compatibility table and choose fallbacks. *(Affinity done October 21; see the compatibility table. DesignCraft pending.)*
3. **Generated test files:** build each feature with the generator, validate it, compare it against the reference, and confirm it in Affinity. *(Started October 21: `ectype_idml/idml/` writes IDML from a model of the book, starting from a base made of InDesign's own settings and root styles (`tools/make_base.py`), cloning InDesign's elements for spreads, pages, frames, stories and sections. g01 (footnotes, as decided) validates and matches reference 01. Affinity: opens and looks right. InDesign: the first version would not open, though it validated; compared element by element with reference 01, it had every section claiming the alternate layout, the wrong binding on the lone last verso, and no page descriptors. Fixed to match InDesign. InDesign still refused it ("may not support the file format"): the real cause was that the writer dropped the `<?aid ... type="document" ...?>` line InDesign puts before designmap.xml's root, by which it recognises the package. Fixed, and `tools/idml_check.py` now requires it. **g01 then opened in InDesign and looks right in Affinity**, but InDesign added pages at the start: the writer had set `PagesPerDocument` to the real page count, where InDesign writes 1 (the new-document default). Fixed: **g01 confirmed in InDesign and Affinity.** g02 (section-marker running heads), g03 (roman/arabic sections, display and blank masters) and g04 (B-Opener based on A-Body, removing its heads) validate and match references 02–04 in the inspector (pages, sides, spreads, masters, sections, special characters); the writer now gives pages their side from the page number, as InDesign does. **g02–g04 confirmed in InDesign and Affinity.** Then g05 (primary text frame with linked page frames; six pages written, since Affinity adds none), g06 (contents style and a reserved contents page, no generated contents), g07 (table, cell and table styles, merged cells, a swatch), g08 (OpenType, composers, optical margins, balanced heading), g09 (baseline grid), g10 (Hebrew and Greek, direction and language in the styles), g12 (character styles) and g13 (chapter stories, blank verso with no master): all validate and match their references in the inspector. g11 (images) waits on where linked images go. Beaux: all look right in InDesign. The contents isn't generated in either program, but places from its style by hand (as intended). In Affinity g07's table didn't break across pages and ran off the page: the writer gave rows no `SingleRowHeight`, which InDesign always writes. Rows now get an estimated height (within a point of InDesign's for all 41 rows of 07; InDesign grows a short row) and InDesign's insets on rows, columns and cells **Still doesn't break across pages in Affinity** (Beaux: left for now, tables will be uncommon; to look at later against reference 07, which does break). **All other files look right in Affinity** (g10's Hebrew reversed, as expected). g11 (images): an inline anchored image with a caption and a placed image with a text wrap, frames cloned from reference 11, sizes and scaling as InDesign's; images copied to a `Links` folder beside the IDML and linked by full path. **g11 looks right in both programs.** With the link's path not found, both InDesign and Affinity find the image when it's in the same folder as the file; without it, both warn that it's missing and leave a placeholder. **Step 3 done** (g07's table breaking in Affinity parked). **Decided (Beaux):** every export is a folder of its own holding the IDML and a `Links` folder with the images, linked there, even for one image. The programs found the image only loose beside the IDML, not in `Links/`, after the link's path broke, so a relative link (`file:Links/sample.jpg`) was tried: **both InDesign and Affinity find relative-linked images, so the tool links images relative to the IDML** and an export folder can be moved or sent on without relinking.)*
4. **Exporter core:** styles, content, footnotes, Hebrew/Greek character styles. *(Started October 21, 2026: `python -m ectype_idml export`. `ectype_idml/content.py` reads the text; `ectype_idml/export.py` builds the model: a book style set with the profile's fonts (else Word's), custom Word styles kept under their own names with Word's alignment, indents, spacing, face and relative size; direct emphasis as character styles; Word character styles by the style map; Hebrew and Greek character styles; footnotes as decided, endnotes converted; tables in the Book Table style; JPEG and PNG images linked in the export folder (other formats reported, a placeholder line left); list and heading numbers as static text. One story and one section per unit, on new pages, with a rough page estimate and a page to spare per chapter, until step 5. Sample: `tools/make_sample_book.py` writes `reference/generated/e01-sample-book/`; validates, not yet opened in InDesign or Affinity.)*
5. **Geometry and pagination:** trim, margin and measure calculation, page-count estimate, masters, sections, chapter-per-story threading, recto rules. *(Step 4's e01 opened and looked right in InDesign and Affinity (October 21); front matter in arabic, a folio on the title page and no copyright page were expected then. Step 5 started October 21: `ectype_idml/layout.py` and `ectype_idml/fonts.py`. The measure is 65 characters of the body font, its average width measured with fontTools from the manuscript's own text (0.42 em when the font isn't installed); the margins take the rest: inside 40% of the spare width, at least KDP's gutter for the estimated count and 0.5 in; top and bottom 19% of the page height, 45/55, with the text a whole number of lines; profile overrides win, with a warning below KDP's gutter. The count is re-estimated until it stays in the same KDP step. Masters A-Body, B-Opener, C-Front (each its own primary text frames, not parent/child, so linked page frames point at their own master), D-Display, E-Blank. Display and front matter in one roman run from i, the first chapter or part at arabic 1; title page, front matter, parts and chapter 1 on a recto, later chapters as the profile says; blank versos E-Blank; parts on D-Display. Bleed (0.125 in, top, bottom, outside) from the profile. Not yet opened in InDesign or Affinity.)* *(Beaux, October 21: e01 flows right in both programs, text width fine. Outside margin wider than inside is the plan's proportion; to revisit in the GUI if wanted. Keeps added: widow/orphan control (2 lines, with KeepLinesTogether, which InDesign needs), headings kept whole and with the next paragraph, no hyphen in a last word or at a page's foot, and runt control without GREP styles (Affinity has none): the last words of each running-text paragraph go in a No Break character style so the last line has at least 10 characters (profile `typography.last_line_min_chars`, profile version 3). Whether Affinity honours these is to check in e01.)*
6. **Running-head setup and front-matter stage** (half-title, title, copyright, contents placeholder). *(Done October 21 for the export: `ectype_idml/frontmatter.py`. Half-title, title page and copyright page generated in Chicago order (half-title i, blank, title iii, copyright iv on the verso at the foot, dedication/epigraph, contents on a recto, then the other front matter); details from the book settings, else detected, else a bracketed placeholder that the report names; notices from the profile's library; English or Spanish boilerplate. The manuscript's own title page is replaced (its copyright lines move to the copyright page) and a typed contents dropped. Contents pages reserved by the decided estimate (or set), with the TOC style for InDesign. Running heads by section marker (recto) and static verso text, per the profile; per-part copies of A-Body for part verso heads; long heads flagged for a short title. The per-unit table is the GUI's (step 7). Not yet opened in InDesign or Affinity.)*
7. **Tkinter GUI, EXE (versioned filename) and update checker.** *(Started October 21: `ectype_idml/gui.py` (tabs for files, book details, running heads with the per-unit short-title table, layout profile, style map, report; drag and drop with tkinterdnd2; book files keep the order and book details), `ectype_idml/updates.py` (Indicat's updater, with the SHA-256 digest GitHub gives each release file), `build_exe.bat` and `.github/workflows/build.yml` (version 0.1.0, not tagged). Tested under Xvfb on Linux; not yet on Windows.)*

## Still open

- Results of the compatibility tests (decides the running-head mechanism, the TOC approach, and parent masters).
- ~~The tool's name~~: **Ectype IDML** (decided November 13, released as 1.0.0). The GitHub
  repository can be renamed to match (GitHub redirects the old address, so installed copies keep
  finding updates).

## Use by other programs (decided October 24)

Ectype OCR (and other programs) need the conversion. Beaux's engine-split plan (a separate
`idml_engine` package with its own document model, src/ layout and versioning) was assessed
against the app: the engine already has no window code, and the cheapest robust way is to use
docx-to-idml as a **separate installed tool**: the caller writes a .docx (character styles
such as "Check OCR" or "Page Marker" carry over by name), runs the .exe's `convert` command,
and reads a JSON result; the .exe records its location in `program.json`; the first call of
the day starts a silent update. So callers always use the latest version, and the two
programs share only files (no license ties). Golden files guard the output. A DOCX-free
input model is deferred until the .docx route proves too limiting. Contract: docs/ENGINE.md
(API version 1).

## Separate project (tabled)

A **page-layout engine** that can build and edit IDML itself, assembled from existing open-source components (text shaping, line breaking, hyphenation, rendering). It's a separate tool and project, not part of this converter, and isn't planned yet. The converter's plan doesn't depend on it.

## Needed to restart

- A representative book manuscript, ideally one sent as **separate chapter files**, with sections, footnotes and some Hebrew or Greek, plus the PDF Word makes from it for comparison.
- Access to Affinity Publisher (and InDesign if possible) for the test checks.
- `idml-schema.zip` (schema for InDesign 2026 21.6.0.57 / DOM 21.5, converted, with the validator). Regenerate with `generate_idml_schema.jsx` and `prepare_schema.py` after a major InDesign update.

## Reference

- Affinity Publisher V1 Help, "Importing documents" (supported IDML features list): https://affinity.help/publisher/en-US.lproj/pages/GetStarted/importDocument.html
- Affinity Publisher 2 Help, "Importing InDesign documents": https://affinity.help/publisher2/en-US.lproj/pages/GetStarted/importInDesign.html
- KDP, "Set Trim Size, Bleed, and Margins" (gutter minimums by page count): https://kdp.amazon.com/help/topic/G201857950
- DesignCraft (open-source page layout with IDML import/export and a CLI): https://sourceforge.net/projects/designcraft.mirror/

## Scribus (tried October 23)

Scribus 1.6.1 opens the exports with their pages, masters, running heads, folios, sections,
images and tables, but its IDML import applies no fonts (everything in its default font, so
italic and bold are lost) and drops footnotes entirely. It does the same with InDesign's own
reference files, so the losses are Scribus's import, not the exports. Not a target for now.

