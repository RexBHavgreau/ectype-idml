# Changelog

## 1.1.0 (not yet released)

The book's defaults now follow Bringhurst's *Elements of Typographic Style* (Beaux, from his
digest of book-layout principles). The output changes; saved profiles are upgraded (profile
version 11) and take the new defaults where they held the old ones.

- **Margins:** a choice of proportions (Layout Profile > Page Margins): the classical canon
  2:3:4:6 (inside : top : outside : bottom, the new default), Gress's 1:1:1.5:2, the margins
  as before ("Economical": inside at least the outside), or schemes of your own (New...,
  Edit..., Delete; kept in the profile). The line length still sets the inside and outside
  together; the inside is never less than KDP's gutter for the page count.
- **Leading:** Bringhurst's routine settings: standard 11 on 13 (was about 11 on 13.75);
  tight and open move with it. **Preview the leading** (Layout Profile > Type) shows two
  paragraphs in the body font at the size, leading and line length set, with buttons for
  tight, standard and open; it closes when you click elsewhere.
- **Type sizes** come from the traditional scale (9, 10, 11, 12, 14, 18, 21, 24...): chapter
  titles 18 pt, part titles 21, the book title 24, notes 9 (for 11 pt text).
- **Headings** change one thing at a time and are never bold: Heading A a larger size at text
  weight, B spaced small caps, C italic. A heading below C (Word's heading 5 and below) is
  run into the start of its paragraph in italic (the Run-in Head character style), with a
  period.
- **Vertical rhythm:** a one-line heading, title or block quotation with its space above and
  below takes a whole number of body lines, so the text after it stays on the page's lines.
  Block quotations are a size smaller on the body's leading.
- **Block quotations:** the first paragraph flush left, the later ones indented, no space
  between them (both indents can be set in Layout Profile > Type).
- **Paragraph indent** one em (was 1.5), settable (Layout Profile > Type).
- **Page numbers** at the text size (settable), and placed as you choose (Running Heads > Page
  Numbers): at the foot, centered (the default); at the foot, outside; or at the head,
  outside, on the running heads' line. On chapter openers: at the foot (centered when the
  others are at the head) or none.
- **Running heads:** small caps at the text size (was 2 pt smaller), letterspaced 7.5% (was
  2%); either head can be "none".
- Capitals and small caps in the text letterspaced 5%; capitals and tables use lining figures
  (tables of one width, so columns of numbers line up); a hyphen takes at least three letters
  to the next line.
- Greek is sized to match the Latin around it (by the height of its lowercase), when both
  fonts are installed.
- The report says when pages have fewer than 30 or more than 45 lines, and how the page count
  fills 16-page signatures for offset printing.
- Inside the program: the book's styles moved to styles.py, and the Running Heads and Layout
  Profile tabs to modules of their own.

## 1.0.0 (November 13, 2026)

- The tool is named **Ectype IDML** (Beaux), in the family of Ectype OCR. The program is
  `Ectype-IDML-X.Y.Z.exe`, the window's title Ectype IDML, the settings folder
  `%APPDATA%\Ectype IDML`. At its first start, 1.0.0 copies the old `docx-to-idml` settings
  folder (profiles, settings) to the new one. Copies of docx-to-idml (0.8.0 and earlier) update
  to it as usual: each release also carries the program under its old name, which is all they
  look for; from 1.0.0 the updater recognizes both names, and older copies under either name
  are offered for deletion. `program.json`, which other programs read to find the converter,
  is written in both settings folders while the old one exists. The repository is now
  github.com/RexBHavgreau/ectype-idml (the old address forwards to it).
- 1.0.0: Beaux's call that the tool is ready for real books (see CLAUDE.md, Progress).
- Fixed: an export could fail with "No such file or directory" when the book's title was
  long. The export folder's name was the title cut at 80 characters, and when the cut fell
  after a space, Windows made the folder without it, so the IDML's path didn't exist (Beaux,
  "The Broken Heart: or, David's Penance..."). The name is now the short title from Book
  Details, else the title before a colon ("The Broken Heart"), cut at a word to 60
  characters, never ending in a space or dot, and never a name Windows reserves (CON, NUL...).

## 0.8.0 (October 24, 2026)

- Other programs (Ectype OCR first) can use the converter: the .exe takes a `convert` command
  (no window), writes the result as JSON (the IDML's path, the report, pop-up alerts, or a
  plain error), and records its own location in `program.json` in the settings folder at
  every start, so callers find the current version. The first `convert` of each day starts a
  silent update check in a separate copy of the program; a newer release is downloaded beside
  it and becomes the one callers use. An `update` command does the same on demand. Described
  in docs/ENGINE.md. The build checks the .exe's `convert` on Windows.
- Golden tests (tests/golden/): two exports (the sample book and a paper with Hebrew heads,
  Greek, footnotes and headings by formatting) compared part by part, so no change to the
  output goes unnoticed.
- The export report names the chapters (and other units) whose last page the estimate
  leaves nearly full (over 80%: they may run past it in Affinity and DesignCraft, which
  don't add pages) or nearly empty (under 20%: the page may be left blank), with the page,
  and says what to do. The estimate can't know each program's line breaks or a font
  substituted on another computer, so these are the pages to look at first.
- Running heads with Hebrew or Greek the running-head font lacks now get separate masters by
  default (Beaux): each such chapter has a master of its own with its head written as text,
  so the Hebrew and Greek are set in their fonts in every program instead of printing as
  empty boxes (DesignCraft). A pop-up after the export says what was done and why, and how
  to keep one master instead. When the head font has the letters, nothing changes. Profile
  version 10 turns the option on in saved profiles too (off had only been the default).
- Fixed: the "Open the export folder" button didn't appear after an export (0.7.0 gave the
  tabs all the room it was placed in). It now appears in the export row, beside Export IDML.
- Fixed: a long web address in justified text (a footnote's EBSCO or JSTOR link) had no
  place to break, so its line was spaced out letter by letter (found in DesignCraft). Web
  addresses now carry invisible break points (zero-width spaces) where Chicago 6.8 allows a
  break: after a colon or double slash; before a single slash, period, comma, hyphen,
  underscore, tilde, question mark, number or percent sign; before or after = and &.

## 0.7.0 (October 23, 2026)

- Running Head Style is in two parts. Case: As typed, Title Case (Chicago: articles,
  prepositions and "and, but, for, or, nor" lower case unless first or last) or Sentence case
  (names the manuscript capitalizes in its running text, such as God or Ezekiel, keep their
  capital). Font: Italic, Boldface, Underlined, All Caps or Small Caps (one or the other, or
  neither), size, letter-spacing and font. Title and sentence case change the heads' letters;
  the capitals set the type, so title case in small caps works. Profile version 8: saved
  profiles keep their capitals setting.
- Book Details: "Title on the copyright page" puts the title (and subtitle) at the top of the
  copyright page, in italics. Ticked by "Fill from the manuscript" when the manuscript's
  copyright page starts with the title.
- Preview pages (Book Details, was "Compare copyright pages"): the half-title, title page and
  copyright page as the export will set them, drawn at the book's trim and margins; the
  copyright page beside the manuscript's.
- Chapter openings (and the half-title, title page and contents) are lowered by their
  paragraph style instead of a shorter text frame, so the drop moves with the title when
  pages are added or removed, and every text frame is full height (Beaux, tested in both
  programs). The style has Space Before (Affinity: set it to apply "Only at column top") and
  an invisible rule above kept in the frame, which is how InDesign lowers a paragraph at the
  top of a frame. The report says what to set in Affinity, and to re-apply B-Opener if a
  chapter moves to another page.
- Layout Profile > Page Organization: "Chapter titles lowered by" sets the drop (blank = six
  body lines, as before). It shows points with their inches, 72 pt (1"); the arrows step
  6 pt; points or inches can be typed (72, 1", 1 in). Profile version 9.
- The margin and footnote spacing fields work the same way: points with their inches
  (margins step 9 pt, an eighth of an inch; note spacing 1 pt; rule length 9 pt), and the
  calculated margins and line length are shown in the same form. A plain number is points
  (typing 1 in a margin field now means 1 pt; type 1" for an inch). Margins are still saved
  in inches, so saved profiles are unchanged.
- Fixed: in InDesign, a chapter with many footnotes could run past its last page, and Smart
  Text Reflow then added a page out of place (an unthreaded page before the chapter's last
  one; Beaux's Ezekiel paper, 40 notes in one chapter). Affinity fitted the same text. The
  page estimate now counts the space above the notes on each page (and the rule) and leaves
  3% for lines lost at page feet, so such a chapter gets one more page instead.
- Fixed: the window opened too short on Windows, hiding the export folder and the Export
  button until it was made taller. It now opens tall enough (within the screen), and the
  export row stays visible however small the window is made.

## 0.6.0 (October 23, 2026)

- Book Details is now a bibliographic record for the book (modelled on Zotero's Book item):
  title, subtitle, short title; contributors; series and number in the series, volume and
  number of volumes, edition, publisher, place, copyright year and holder, ISBNs, call number
  (blank: no line), credits, printed in. Contributors are a list in title-page order, each an
  author, editor, translator, writer of the foreword, afterword, preface or introduction,
  contributor or series editor (Add, Change, Remove, Move up, Move down). The title page has
  a byline per role in that order: the authors' names, "Edited by ...", "Translated by ...",
  "With a foreword by ..." (afterword, preface, introduction likewise; Chicago style: "A, B,
  and C"); a unit titled "Foreword by ..." in the manuscript fills that role; the wording comes from the
  book's language (English, and Spanish, so other languages can be added). The copyright
  holder and the "author" running head use the authors, else the editors. The series goes on
  the half-title, the volume ("Volume 2 of 3") on the title page, the call number on the
  copyright page. "Fill from the manuscript" fills the contributors (editors from a copyright
  page's "Edited by" line). Saved books are upgraded: the old Author field becomes an author.
  The tab is in sections: Title, Contributors, Pages, Publication.
- Headings set by formatting: a manuscript without heading styles (headings made bigger,
  bold, centered or in capitals by hand) has its headings found by their look. Paragraphs
  that look alike form a group ("[16 pt bold centered]", "[bold]"...), ranked by prominence:
  the strongest becomes chapter titles, the next Heading A, and so on. Groups show in the
  Style Map tab, marked as guessed, to confirm or change; changes are saved with the book.
  The bold or size that made a paragraph a heading is left to the heading style. Bold lines
  in the text, italic titles of works, title-page lines and a typed contents' title are not
  taken for headings. Only what the styles don't give is guessed: a manuscript with heading
  styles is read by its styles as before. Preflight says when headings were found this way.
  Levels are ranked across the whole book, so a look means the same level in every file. In a
  book sent as several files, each file's most prominent opening line is its title (PREFACE,
  Contributors, Foreword by...), and a line of names under a chapter title is its author line.
- Front matter sent as files: a file of copyright lines (a copyright notice, "All rights
  reserved", an ISBN) is used as the book's copyright page instead of a generated one, so its
  information isn't duplicated; its "Edited by ..." line gives the editors, and its other
  lines fill the empty Book Details fields: copyright year and holder, a rights statement
  (new field, blank: "All rights reserved."), publisher, web address, ISBNs (print and ebook
  by their labels), "Printed in ...", the edition line. Permissions (for Bible versions and
  the like) go into the notice library under a short name (ESV, NKJV...) and are ticked for
  the book. The export then replaces the manuscript's copyright page with one made from Book
  Details, so nothing is duplicated; lines that fit no field are listed in the report.
  Copyright lines on a manuscript's title page are read and replaced the same way.
  "Compare copyright pages..." (Book Details) shows the manuscript's page beside the new one
  as plain text, with the lines that fit no field.
  The book's title, when it opens several files, is taken as the title and left out where it
  repeats at the top of a file. A file whose first line isn't a title (an abbreviations
  list) is titled from its file name ("00.5 Abbreviations" -> Abbreviations). "Foreword by
  ..." and "Contributors" are recognized as front matter.
- Fixed: Hebrew inside italic text was set upright: the Hebrew style fixed the face. It now
  takes the face of the text around it (italic in italic text, bold in a bold heading), by the
  Hebrew font's own name for that face (the Culmus fonts call theirs "Medium" and "Medium
  Oblique"). If the Hebrew font has no such face, the Hebrew is set upright and the report
  says so.
- Running heads with Hebrew or Greek: a running head taken from the chapter title can use
  only one font. When a head has Hebrew or Greek and the running-head font lacks those
  letters (or isn't installed, so it can't be checked), the report says so: choose a font that
  has them, or turn on the new "Separate masters for heads with Hebrew or Greek" (Running
  Heads > Running Head Style), which gives each such chapter a master of its own (R1-Body...)
  with the head as text in the Hebrew or Greek font. Off by default. Profile version 7.
- Page Margins: the line length field says it's a multiple of the type size, and shows what
  that comes to in inches and picas (30 at 11 pt: 4.58 in, 27.5 picas); the note under the
  margins gives it too, with the characters per line.

## 0.5.0 (October 23, 2026)

- The Style Map tab is now the one view of every style found in the manuscript, with the
  IDML style, role and look of each as dropdowns (it replaces the list with a dialog per
  style and the separate window). "Apply the mapping" reads the manuscript again with it;
  changes not yet applied are still used by the export. The tab is shown after the
  manuscript is first read. The manuscript's own contents (Word's TOC styles) isn't listed:
  a new contents replaces it.
- Tabs are in title case (Book Details, Running Heads, Layout Profile, Style Map; Page
  Layout, Notes and Contents).
- The Page Layout tab (was Page) is in three sections: Page Size, Page Organization and Page
  Margins.
- Narrower default margins: the line length is now about 30 times the type size (Bringhurst;
  a setting in Page Margins, 20–40), kept between 45 and 80 characters, instead of 65
  characters. At 11 pt on 6 x 9 the margins are about 0.82 in inside, 0.6 in outside and top,
  0.76 in bottom, and lines run about 71 characters. The outside margin is never wider than
  the inside unless you set it so.
- The running heads' style can be set in the Running Heads tab: small caps, all caps or as
  typed; italic; size; letter-spacing; font.
- Profile version 6 (line length, running-head style); saved profiles are upgraded. Two
  settings that did nothing are dropped (OpenType small caps; endnotes: "ask").
- Preflight reports tables inside tables: their text is kept in the outer table's cell, but
  the inner table's rows and columns are not (they went unreported before).
- Housekeeping: unused code removed; the reference folder keeps only what the tests and tools
  use (the InDesign files, PDFs and footnote experiments are in the history).
- Fixed: when a chapter ran longer than estimated, InDesign added one page, which pushed
  the next chapter's opening page (B-Opener) onto a left-hand page; the chapter title then
  jumped to the following right-hand page, which had the A-Body master. InDesign now adds
  pages two at a time (Smart Text Reflow's "Preserve Facing-Page Spreads"), so openers stay
  on right-hand pages with their master.
- Fixed: Hebrew and Greek in text the program writes itself (the book's title on the
  half-title and title pages, the title or author in a running head, a part's title) were set
  in the style's own font. They now get the Hebrew and Greek styles and fonts, as in the
  manuscript's text, and a line with Hebrew uses the World-Ready composer. Running heads taken
  from the chapter title can't change font partway; when one has Hebrew or Greek, the report
  says so (give the chapter a short title in the Running heads tab).
- Fonts whose normal face isn't called "Regular" (the Culmus Hebrew fonts such as Taamey
  David CLM call it "Medium") are asked for by the face's own name, so InDesign doesn't report
  a missing font.
- A paper's cover page (from a real manuscript): a line or two above the title, such as a
  school's name, is now part of the title page rather than a page of endorsements (text above
  the title still counts as endorsements when it runs to sentences or is a quotation); a Word
  style named "Author" (or "Autor") gives the author; a bare "by" line and the title of a
  typed contents are left out with the contents. Other lines of the manuscript's title page
  (a school, a place, a date) are left out too, and listed in the report; anything that
  belongs in the book goes in Book details.

## 0.4.0 (October 22, 2026)

- Style mapping in one window (as InDesign's style mapping when placing a Word file): after
  the automatic mapping, every paragraph and character style found in the manuscript is
  listed with how often it's used and the IDML style it becomes. Choose another book style,
  keep the style under its own name, or leave its paragraphs out; for paragraph styles also
  the role (heading, quotation, note...) and the look. Styles the program had to guess are
  marked ⚠. It opens the first time a set of files is read, and from "Map styles..." (Files
  tab) or the Style map tab. "Back to the automatic mapping" forgets the choices. Choices
  are saved in the profile.
- After an update, the new version offers to delete the old copy and to point desktop and
  Start-menu shortcuts and taskbar pins that opened it at itself (as Indicat does). A copy
  you choose to keep isn't asked about again.
- Fixed: the update check at startup ran at most once a day, so a release made after the
  day's check wasn't noticed until the next day (0.2.0 missed 0.3.0). It now checks at every
  start, quietly unless there's a newer version. If you decline a version, the startup check
  doesn't ask about it again; Help > Check for updates always does.

## 0.3.0 (October 22, 2026)

- Endorsements ("Endorsements", "Praise for...", "Advance Praise", "What Others Are Saying",
  and the Spanish "Elogios", "Recomendaciones") are recognized and set first, before the
  half-title, as display pages without folios or running heads.
- Nothing of Word's formatting is carried into the book's styles. Word's paragraph styles
  still say which styles the book needs and what each is (heading, quotation, note...), but
  a custom Word style is now based on the book style for its role without Word's alignment,
  indents, spacing or sizes; change its look in InDesign or with a style template. Fonts not
  set in the profile are book fonts installed on the computer (Minion, Arno, Garamond,
  Caslon, Palatino, Georgia...), never Word's; Hebrew and Greek fonts likewise (SBL Hebrew,
  SBL Greek, Gentium...), when the body font lacks the letters. Italic, bold, small caps
  and Word's character styles in the text are kept, as are centered lines (scene breaks).
- A custom Word style with no book counterpart (a special paragraph the author set up, based
  on Normal) keeps what makes it distinct, in book terms: alignment, indents in proportion
  to the book's line, italic or bold, capitals, and size and spacing in proportion to the
  body size; never Word's fonts. Custom styles based on a heading, quotation or the like
  follow the book style. The Style map tab shows each style's look and can switch it.
- The first text paragraph of a chapter is set flush (Body First) after an epigraph or any
  other opening matter, not only after a heading.
- Body size and leading (Layout profile > Type): a body size (11 pt by default) and leading
  chosen as tight, standard or open, with the suggested range for each shown for the size
  (at 11 pt about 12.5-13, 13.5-14, 14.5-15), shifted for the body font's x-height and the
  line length; an exact leading still wins. The export report says what it used.
- Baseline grid (Layout profile > Type): body text on a grid of the body leading; block
  quotes, notes and captions stay off it.
- The Type tab reads down each column: fonts, size and leading on the left, typographic
  switches on the right.
- Text before the title page (endorsements, which seldom have a heading) is set as
  endorsements, before the half-title; so is a file of it placed before the title-page file.
- Layout profile > Page: each margin field shows the margin the export would calculate (for
  the trim, the body font and the book's page count, once preflight has run), with a button
  to fill them in. Blank fields keep following the page count; typed values are fixed. The
  Page tab is now one column, so the margins read together.
- Running heads tab: double-click a unit's kind to change what it is (chapter, part, front
  matter, back matter, display page, endorsements); the choice is saved with the book.
- Book details: "Fill from the manuscript" is at the top of the tab, and after filling it says
  where each value was found (which style in which file, or the title page's "by" line), or
  that it wasn't found.

## 0.2.0 (October 21, 2026)

- Fonts are chosen from dropdowns of the fonts installed on the computer (you can still type a
  name, or leave the box blank to use Word's). The Hebrew and Greek lists show only fonts that
  have Hebrew or Greek letters.
- Styles from an IDML file (Layout profile > Type): the template's paragraph and character
  styles replace the tool's of the same name, and its other styles are added. Settings that
  point at things the export doesn't carry (most colour swatches, lists, nested and GREP
  styles) are left out and listed in the report.
- Spare pages after each chapter are a setting: none (the default), one, or two.
- Chapter titles are set to start on the next odd page (the next page when chapters open on
  the next page), so the rule holds if chapters are joined into one story in InDesign.
- Fixed: Hebrew could come out reversed in InDesign: the styles used the Adobe Paragraph
  Composer. They now use the World-Ready Composer (the same paragraph composer, with
  right-to-left support), so Hebrew sets right everywhere, including Hebrew added later in
  InDesign. The profile's single-line option is ignored when the book has Hebrew.
- Fixed: after a bibliography, the rest of the book was set in the Bibliography style.
  Bibliography styling now runs from a heading titled Bibliography (Works Cited, References...)
  at any level to the next heading of the same or higher level, so a bibliography can end a
  chapter. A file whose text starts before its first chapter heading (an article with a title
  line, headings or a page or more of text) is a unit of its own, not added to the previous
  file's last unit; a title line opening a chapter is set as its Chapter Title.
- Fixed: italics in footnotes were lost (the footnote settings written on each note run
  overrode the Italic style), and so were the Greek and Hebrew fonts inside notes.

## 0.1.0 (October 21, 2026)

First version with a window and an .exe.

- The window: files in book order (add, drop, move, sort), book details for the title and
  copyright pages, running heads with short titles, the layout profile, the style map,
  preflight and export.
- Export to IDML (InDesign, Affinity): styles, character formatting, footnotes, Hebrew and
  Greek, tables, images, margins and measure, masters, roman and arabic page numbers, recto
  rules, half-title, title, copyright and reserved contents pages, running heads, widow,
  orphan and short-last-line control.
- Update check at startup (once a day, can be turned off) and in the Help menu; the new
  version is saved beside the running one.
