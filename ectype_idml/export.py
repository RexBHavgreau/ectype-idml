"""The exporter core (build step 4): Word manuscript -> the IDML model -> an export folder.

    files -> docx_reader (styles, outline) + content (text) -> Document -> writer.export_book

What it does:
- Styles: a book set (Body, Body First, Chapter Title, Heading A-C, Block Quote, Footnote...)
  with the profile's fonts, else installed book fonts (never Word's). Word's paragraph styles
  give names and roles only; a custom style with no book counterpart is kept under its own
  name with its distinct look in book terms (_word_look), unless the style map says "book".
- Text: italic, bold, small caps, capitals, superscript, subscript, underline and strikethrough
  become character styles (Italic, Bold, Small Caps...), so they survive a change of font;
  Word's own character styles are mapped by the style map. Other direct formatting (fonts,
  sizes, colours) gives way to the book's styles; preflight lists it.
- Hebrew and Greek runs are found by Unicode range and put in "Hebrew" and "Greek" character
  styles (font, language, right-to-left for Hebrew); paragraphs with Hebrew get the World-Ready
  composer.
- Footnotes as decided (fn-m, in the writer); endnotes are converted to footnotes.
- Tables (Book Table style; header rows; merged cells across), images (JPEG, PNG; others are
  listed and left as a placeholder line), list and heading numbers as static text.
- One story per unit of the outline, each on new pages, in one section per unit so footnote
  numbers restart per chapter. Pages are estimated (spare pages as the profile says); the
  geometry comes from layout.py, front matter and running heads from frontmatter.py and
  _front_matter / _masters here. Hebrew and Greek in generated text get their styles too
  (_generated_scripts).
"""

import math
import re
from dataclasses import dataclass, replace
import os
import shutil
import tempfile

from . import fonts, frontmatter, layout
from . import profile as profiles
from .content import read_content, save_image
from .docx_reader import is_greek, is_hebrew, read_docx
from .idml.images import image_info
from .idml.model import CellStyle, Document, Image, Paragraph, Run, Style, Table, TableStyle
from .pagination import PaginationMixin
from .outline import _BACK, _FRONT, Unit, apply_kinds, build_outline, title_key
from .stylemap import StyleMap, norm
from .template import TemplateError, apply_template, read_template

BLEED = 9                   # 0.125 in, KDP's bleed
TRIMS = {"5x8": (5, 8), "5.25x8": (5.25, 8), "5.5x8.5": (5.5, 8.5), "6x9": (6, 9),
         "7x10": (7, 10), "8.5x11": (8.5, 11), "A5": (5.83, 8.27)}
SLACK = 0.03         # of the text estimated per page, for lines lost at page feet
LANGUAGES = {"en": "$ID/English: USA", "es": "$ID/Spanish: Castilian"}
FONT_STYLES = {(False, False): "Regular", (False, True): "Italic", (True, False): "Bold",
               (True, True): "Bold Italic"}
# Character styles the exporter makes from Word's formatting.
CHAR_STYLES = {
    "Italic": {"FontStyle": "Italic"}, "Bold": {"FontStyle": "Bold"},
    "Bold Italic": {"FontStyle": "Bold Italic"}, "Small Caps": {"Capitalization": "SmallCaps"},
    "All Caps": {"Capitalization": "AllCaps"}, "Superscript": {"Position": "Superscript"},
    "Subscript": {"Position": "Subscript"}, "Underline": {"Underline": True},
    "Strikethrough": {"StrikeThru": True}, "Footnote Reference": {"Position": "Superscript"},
    "Hyperlink": {}, "No Break": {"NoBreak": True},
}
RESET = {"FontStyle": None, "Capitalization": "Normal", "Position": "Normal",
         "Underline": False, "StrikeThru": False}
# Roles whose paragraphs are followed by an unindented first paragraph.
# Styles whose paragraphs are not running text (no runt control), with those based on them.
NO_RUNT_SKIP = {"Chapter Title", "Part Title", "Heading A", "Heading B", "Heading C",
                "Book Title", "Book Subtitle", "Author", "Verse", "Figure", "Table", "Caption",
                "Table Body", "Table Head", "Folio"}
# The book styles a Word paragraph style can be mapped to, with the role (and heading level)
# each implies; the window's style mapping panel offers these.
BOOK_STYLE_ROLES = {
    "Body": ("body", 0), "Body First": ("body", 0), "Chapter Title": ("chapter", 0),
    "Chapter Subtitle": ("body", 0), "Chapter Author": ("body", 0), "Part Title": ("part", 0),
    "Heading A": ("heading", 1), "Heading B": ("heading", 2), "Heading C": ("heading", 3),
    "Book Title": ("book_title", 0), "Book Subtitle": ("subtitle", 0), "Author": ("author", 0),
    "Block Quote": ("quote", 0), "Verse": ("verse", 0), "List": ("list", 0),
    "List Bullet": ("list", 0), "List Number": ("list", 0), "Bibliography": ("body", 0),
    "Footnote": ("note", 0), "Caption": ("caption", 0), "Copyright": ("body", 0),
}
HEAD_ROLES = {"chapter", "part", "heading", "book_title", "subtitle", "author", "toc_title",
              "centered"}
ROLE_BASE = {"body": "Body", "quote": "Block Quote", "verse": "Verse", "list": "List",
             "caption": "Caption", "note": "Footnote", "chapter": "Chapter Title",
             "part": "Part Title", "book_title": "Book Title", "subtitle": "Book Subtitle",
             "author": "Author"}


@dataclass
class Block:
    """One story of the book: a unit of the manuscript or a generated page."""
    unit: object
    paras: list
    opens: str = None             # "recto", "next", or None for the rule by kind
    spare: int = None             # spare pages; None = by kind
    sink: float = None            # None = by kind
    pages: int = None             # fixed page count (reserved contents), else estimated
    valign: str = None            # e.g. "BottomAlign" (copyright page)
    est: int = None               # pages estimated for the text (set when paginating)
    fill: float = None            # how full the estimate leaves its last page (0-1)

    @property
    def kind(self):
        return self.unit.kind if self.unit else "chapter"

    @property
    def title(self):
        return self.unit.title if self.unit else ""


BODY_SIZE = 11


def body_size(profile):
    try:
        size = float(profile.get("body_size") or BODY_SIZE)
    except (TypeError, ValueError):
        return BODY_SIZE
    return size if 6 <= size <= 24 else BODY_SIZE


def leading_for(profile, size=None, x_height=None, cpl=layout.TARGET_CPL):
    """The body leading in points: the profile's value (points, a multiple or a percent), else
    the middle of the suggested range for its feel (tight, standard, open), shifted for the
    font's x-height and the line length."""
    size = size or body_size(profile)
    lead = profile.get("leading") or {}
    v, unit = lead.get("value"), lead.get("unit", "pt")
    if not v:
        feel = lead.get("feel") if lead.get("feel") in layout.LEADING_RATIOS else "standard"
        return layout.leading_suggestions(size, x_height, cpl)[0][feel][2]
    if unit == "multiple":
        return _half(size * v)
    if unit == "percent":
        return _half(size * v / 100)
    return v


def calculated_margins(profile, pages=200, text=None):
    """The margins the export would calculate (before any set in the profile), for showing
    the user: (layout.Geometry, body font found installed?)."""
    page = profile["page"]
    if page.get("trim") == "custom" and page.get("custom_width") and page.get("custom_height"):
        w, h = page["custom_width"], page["custom_height"]
    else:
        w, h = TRIMS.get(page.get("trim"), TRIMS["6x9"])
    found = fonts.find_font((profile.get("fonts") or {}).get("body") or fonts.book_font())
    avg, xh = fonts.FALLBACK_WIDTH, None
    if found:
        try:
            avg = fonts.average_width(found, text)
            xh = fonts.x_height(found)
        except Exception:
            found = None
    size = body_size(profile)
    return layout.geometry(_half(w * 72), _half(h * 72), size,
                           leading_for(profile, size, xh), avg, pages,
                           measure_ems=page.get("measure")), bool(found)


class ExportError(Exception):
    """Something that stops the export. The message is shown to the user."""


def _half(v):
    return round(v * 2) / 2


def _twips(props, key):
    """A value in points from a summarized Word property ("left=720 firstLine=360")."""
    for part in (props or "").split():
        k, _, v = part.partition("=")
        if k == key and v.lstrip("-").isdigit():
            return int(v) / 20
    return None


def _prop(props, key):
    for part in (props or "").split():
        k, _, v = part.partition("=")
        if k == key:
            return v
    return None


def _toggle(props):
    return props is not None and (props == "on" or _prop(props, "val") not in
                                  ("0", "false", "off", "none"))


def segments(text):
    """Split text into (script, part): script is "hebrew", "greek" or None. Spaces and
    punctuation between two words of the same script stay with them; combining marks go with
    the letter before."""
    out = []
    pending = ""
    for ch in text:
        o = ord(ch)
        if is_hebrew(ch):
            script = "hebrew"
        elif is_greek(ch):
            script = "greek"
        elif 0x0300 <= o <= 0x036F and out and not pending:
            script = out[-1][0]
        elif not ch.isalpha():
            pending += ch
            continue
        else:
            script = None
        if out and out[-1][0] == script:
            out[-1][1] += pending + ch
        else:
            if pending:
                if out and out[-1][0] is None:
                    out[-1][1] += pending
                else:
                    out.append([None, pending])
            if out and out[-1][0] == script:
                out[-1][1] += ch
            else:
                out.append([script, ch])
        pending = ""
    if pending:
        if out and out[-1][0] is None:
            out[-1][1] += pending
        else:
            out.append([None, pending])
    return [tuple(s) for s in out]


class Exporter(PaginationMixin):
    def __init__(self, paths, profile=None, settings=None):
        """settings: the book's own settings (Book.settings): "front" (book details, see
        frontmatter) and "short_titles" ({unit title: running head})."""
        self.paths = [str(p) for p in paths]
        self.profile = profile or profiles.default_profile()
        self.settings = settings or {}
        self.x_height = None
        self.tpl = None
        path = self.profile.get("styles_template")
        if path:
            try:
                self.tpl = read_template(path)
            except TemplateError as e:
                raise ExportError(str(e)) from None
        self.sm = StyleMap.from_profile(self.profile, self.settings)
        self.report = []
        self.tmp = None

    # ---- the whole export ----

    def build(self):
        if not self.paths:
            raise ExportError("No .docx files to export.")
        self.docs = [read_docx(p) for p in self.paths]
        self.outline = apply_kinds(build_outline(self.docs, self.sm),
                                   self.settings.get("unit_kinds"))
        self.doc = Document(name=self.outline.title or os.path.splitext(
            os.path.basename(self.paths[0]))[0])
        self.tmp = tempfile.mkdtemp(prefix="ectype_idml-")
        self._fonts()
        self._page()
        self._book_styles()
        self._measure_font()
        # Geometry depends on the page count (KDP's gutter steps) and the page count on the
        # geometry: repeat until the count stays in the same step.
        base_report = list(self.report)
        pages = self._first_guess()
        for _ in range(4):
            self.report = list(base_report)
            self._geometry(pages)
            self.used_char, self.custom = {}, {}
            self._book_styles()
            stories = self._stories()
            new = self._paginate(self._front_matter(stories))
            if layout.kdp_band(new) == layout.kdp_band(pages):
                break
            pages = new
        self._generated_scripts()
        missing = sorted(getattr(self, "hebrew_faces_missing", ()))
        if missing:
            self.report.append(
                "The Hebrew font (%s) has no %s face, so Hebrew in %s text is set upright. "
                "Choose a Hebrew font with that face in Layout Profile > Type if it should "
                "match." % (self.fonts["hebrew"], " or ".join(m.lower() for m in missing),
                            " or ".join(m.lower() for m in missing)))
        self.report += self.geo.notes + layout.page_count_notes(self.doc.page_count)
        self._finish_styles()
        return self.doc

    def cleanup(self):
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None

    # ---- page and fonts ----

    def _page(self):
        page = self.profile["page"]
        if page.get("trim") == "custom" and page.get("custom_width") and page.get("custom_height"):
            w, h = page["custom_width"], page["custom_height"]
        else:
            w, h = TRIMS.get(page.get("trim"), TRIMS["6x9"])
        doc = self.doc
        doc.width, doc.height = _half(w * 72), _half(h * 72)
        doc.facing = page.get("facing", True)
        doc.bleed = BLEED if page.get("bleed") else 0
        doc.footnotes = dict(self.profile["footnotes"])
        # Until the geometry is worked out (the styles need a measure for nothing yet).
        self.measure, self.text_height = doc.width - 108, doc.height - 117

    def _measure_font(self):
        """The body font's average character width, from the manuscript's own text."""
        text = []
        n = 0
        for d in self.docs:
            for p in d.paragraphs:
                if n > 20000:
                    break
                text.append(p.text)
                n += len(p.text)
        found = fonts.find_font(self.fonts["body"])
        self.x_height = None
        if found:
            try:
                self.avg_width = fonts.average_width(found, " ".join(text))
                self.x_height = fonts.x_height(found)
                return
            except Exception:
                pass
        self.avg_width = fonts.FALLBACK_WIDTH
        self.report.append("%s isn't installed on this computer, so the text width was worked out "
                           "for an average book font. Install the font, or check the line length "
                           "in InDesign or Affinity." % self.fonts["body"])

    def _first_guess(self):
        """Page count from the words, for the first geometry."""
        chars = sum(len(p.text) for d in self.docs for p in d.paragraphs)
        notes = sum(len(p.text) for d in self.docs for p in d.note_paragraphs)
        g = layout.geometry(self.doc.width, self.doc.height, self.body_size, self.body_lead,
                            self.avg_width, 100,
                            measure_ems=self.profile["page"].get("measure"))
        per_page = g.cpl * g.lines
        return int((chars + notes * 0.8) / per_page) + 2 * len(self.outline.units) + 4

    def _geometry(self, pages):
        doc = self.doc
        g = layout.geometry(doc.width, doc.height, self.body_size, self.body_lead,
                            self.avg_width, pages, self.profile["page"].get("margins"),
                            self.profile["page"].get("measure"))
        self.geo = g
        doc.margins = g.margins
        self.measure, self.text_height = g.measure, g.text_height

    def _fonts(self):
        pf = dict(self.profile["fonts"])
        # A style template's fonts count as chosen (the profile's own still win).
        for role, style in (("body", "Body"), ("headings", "Chapter Title"),
                            ("notes", "Footnote")):
            if not pf.get(role) and self._template_font(style):
                pf[role] = self._template_font(style)
        # Fonts not set in the profile (or a template) are book fonts installed here, never
        # Word's: a manuscript's fonts are its author's or its template's, not the book's.
        body = pf.get("body")
        if not body:
            body = fonts.book_font()
            self.report.append("Body font: %s (no font set in the profile; a book font "
                               "installed on this computer). Choose another in Layout Profile "
                               "> Type." % body)
        heads = pf.get("headings") or body
        notes = pf.get("notes") or body
        display = pf.get("display") or heads
        heb = pf.get("hebrew")
        if not heb:
            heb = fonts.script_font("hebrew")
            if any(d.scripts["hebrew"].chars for d in self.docs):
                self.report.append("Hebrew font: %s (none set in the profile)." % heb)
        grk = pf.get("greek")
        if not grk and any(d.scripts["greek"].chars for d in self.docs):
            # The body font if it has Greek letters (polytonic too), else a Greek font.
            found = fonts.find_font(body)
            if not (found and fonts.has_char(found, 0x1F00)):
                grk = fonts.script_font("greek")
                self.report.append("Greek font: %s (the body font has no polytonic Greek; "
                                   "none set in the profile)." % grk)
        self.fonts = {"body": body, "headings": heads, "notes": notes, "display": display,
                      "hebrew": heb, "greek": grk}

    # ---- styles ----

    def _composer(self, typo):
        """The World-Ready composer (InDesign's "HL Composer Optyca") by default: the paragraph
        composer with right-to-left support, so Hebrew is set right in every style, including
        Hebrew added later in InDesign; Latin and Greek text set the same. Single-line only if
        the profile asks for it and the book has no Hebrew."""
        if typo["paragraph_composer"]:
            return "HL Composer Optyca"
        if any(d.scripts["hebrew"].chars for d in self.docs):
            if not getattr(self, "_composer_noted", False):
                self.report.append("The book has Hebrew, so the World-Ready composer is used "
                                   "although the profile asks for the single-line composer "
                                   "(Hebrew needs it).")
                self._composer_noted = True
            return "HL Composer Optyca"
        return "HL Single"

    def _leading(self, size):
        cpl = self.geo.cpl if getattr(self, "geo", None) else layout.TARGET_CPL
        return leading_for(self.profile, size, self.x_height, cpl)

    def _book_styles(self):
        typo = self.profile["typography"]
        f = self.fonts
        size = body_size(self.profile)
        lead = self._leading(size)
        self.body_size, self.body_lead = size, lead
        indent = _half(size * 1.5)
        lang = LANGUAGES.get(self.profile["front_matter"].get("language"), LANGUAGES["en"])
        body = {"FontStyle": fonts.regular_face(f["body"]), "PointSize": size,
                "FirstLineIndent": indent,
                "Justification": "LeftJustified", "Hyphenation": bool(typo["hyphenation"]),
                "Composer": self._composer(typo),
                "AppliedLanguage": lang, "Ligatures": bool(typo["ligatures"])}
        if typo["oldstyle_figures"]:
            body["OTFFigureStyle"] = "ProportionalOldstyle"
        # Widows and orphans: InDesign applies KeepFirstLines/KeepLastLines only with
        # KeepLinesTogether on (and KeepAllLinesTogether off).
        if typo["widow_orphan_control"]:
            body.update({"KeepLinesTogether": True, "KeepFirstLines": 2, "KeepLastLines": 2})
        else:
            body.update({"KeepLinesTogether": False, "KeepFirstLines": 1, "KeepLastLines": 1})
        # No hyphen in a paragraph's last word, nor at the foot of a page or column.
        body.update({"HyphenateLastWord": False, "HyphenateAcrossColumns": False})
        balance = {"BalanceRaggedLines": ("enumeration", "VeeShape")} \
            if typo["balance_ragged_headings"] else {}
        head = {"FirstLineIndent": 0, "Hyphenation": False, "KeepWithNext": 2,
                "KeepLinesTogether": True, "KeepAllLinesTogether": True}
        note_size, note_lead = size - 2, _half((size - 2) * 1.22)
        # Chapter titles start a page: the next odd page when chapters open on a recto. Each
        # chapter is a story of its own on its recto already; this keeps the rule if chapters
        # are joined into one story in InDesign.
        start = "NextOddPage" if self.profile.get("chapters_open", "recto") == "recto" \
            else "NextPage"
        hang = [("LeftAlign", 18, "")]
        S = Style
        self.doc.paragraph_styles = [
            S("Body", font=f["body"], leading=lead, attrs=body),
            S("Body First", "Body", {"FirstLineIndent": 0}),
            S("Chapter Title", "Body", dict(head, PointSize=_half(size * 1.8),
                                             Justification="CenterAlign", SpaceAfter=lead * 2,
                                             StartParagraph=start),
              font=f["headings"], leading=_half(size * 2.2), next_style="Body First", props=balance),
            S("Part Title", "Chapter Title", {"PointSize": _half(size * 2.2)},
              leading=_half(size * 2.6), next_style="Body First"),
            S("Heading A", "Body", dict(head, PointSize=size + 1, FontStyle="Bold",
                                         Justification="LeftAlign", SpaceBefore=lead,
                                         SpaceAfter=_half(lead / 2)),
              font=f["headings"], leading=lead, next_style="Body First", props=balance),
            S("Heading B", "Heading A", {"PointSize": size, "FontStyle": "Bold Italic"},
              next_style="Body First"),
            S("Heading C", "Heading A", {"PointSize": size, "FontStyle": "Italic"},
              next_style="Body First"),
            S("Book Title", "Body", dict(head, PointSize=_half(size * 2.4),
                                          Justification="CenterAlign", SpaceAfter=lead),
              font=f["display"], leading=_half(size * 2.8), props=balance),
            S("Chapter Subtitle", "Chapter Title", {"PointSize": _half(size * 1.3),
                                                    "FontStyle": "Italic",
                                                    "StartParagraph": "Anywhere",
                                                    "SpaceAfter": lead * 2},
              leading=_half(size * 1.7), next_style="Body First"),
            S("Chapter Author", "Chapter Subtitle", {"FontStyle": "Regular",
                                                     "PointSize": size + 1},
              leading=_half(size * 1.5), next_style="Body First"),
            S("Book Subtitle", "Book Title", {"PointSize": _half(size * 1.4),
                                              "FontStyle": "Italic"}, leading=_half(size * 1.8)),
            S("Author", "Book Title", {"PointSize": _half(size * 1.3), "SpaceBefore": lead * 2},
              leading=_half(size * 1.7)),
            S("Block Quote", "Body", {"PointSize": size - 1, "FirstLineIndent": 0,
                                      "LeftIndent": indent, "SpaceBefore": _half(lead / 2),
                                      "SpaceAfter": _half(lead / 2)}, leading=lead - 1),
            S("Verse", "Block Quote", {"Justification": "LeftAlign", "Hyphenation": False}),
            S("List", "Body", {"FirstLineIndent": -18, "LeftIndent": 18,
                               "Justification": "LeftAlign"}, tabs=hang),
            S("List Bullet", "List"),
            S("List Number", "List"),
            S("Bibliography", "Body", {"FirstLineIndent": -indent, "LeftIndent": indent,
                                       "Justification": "LeftAlign"}),
            S("Footnote", font=f["notes"], leading=note_lead,
              attrs={"FontStyle": fonts.regular_face(f["notes"]), "PointSize": note_size, "FirstLineIndent": size - 2,
                     "Justification": "LeftJustified", "AppliedLanguage": lang,
                     "Hyphenation": bool(typo["hyphenation"]),
                     "Composer": body["Composer"], "HyphenateLastWord": False,
                     **{k: body[k] for k in ("KeepLinesTogether", "KeepFirstLines",
                                             "KeepLastLines")}}),
            S("Caption", "Body", {"PointSize": size - 2, "FirstLineIndent": 0,
                                  "FontStyle": "Italic", "Justification": "CenterAlign",
                                  "SpaceAfter": _half(lead / 2)}, leading=note_lead),
            S("Figure", "Body", {"FirstLineIndent": 0, "Justification": "CenterAlign",
                                 "SpaceBefore": _half(lead / 2), "SpaceAfter": 4}),
            S("Table", "Body", {"FirstLineIndent": 0, "SpaceBefore": _half(lead / 2),
                                "SpaceAfter": _half(lead / 2)}),
            S("Table Body", "Body", {"FirstLineIndent": 0, "PointSize": size - 1.5,
                                     "Justification": "LeftAlign", "Hyphenation": False},
              leading=_half((size - 1.5) * 1.26)),
            S("Table Head", "Table Body", {"FontStyle": "Bold"}),
            S("Folio", font=f["body"], leading=lead,
              attrs={"PointSize": size - 2, "Justification": "CenterAlign"}),
            self._running_head_style(size, lead),
            S("Half Title", "Book Title", {"PointSize": _half(size * 1.6)},
              leading=_half(size * 2)),
            S("Publisher", "Book Title", {"PointSize": size, "SpaceBefore": lead * 6},
              leading=lead),
            S("Series", "Half Title", {"PointSize": size, "SpaceBefore": lead * 2,
                                       "FontStyle": "Italic"}, leading=lead),
            S("Volume", "Book Subtitle", {"SpaceBefore": lead}),
            S("Copyright", "Body", {"PointSize": size - 2, "FirstLineIndent": 0,
                                    "Justification": "LeftAlign", "Hyphenation": False,
                                    "SpaceAfter": _half(lead / 2)}, leading=note_lead),
            S("Copyright Title", "Copyright", {"FontStyle": "Italic"}),
            S("Contents Title", "Chapter Title", next_style="Contents 1"),
            S("Contents 1", "Body", {"FirstLineIndent": 0, "Justification": "LeftAlign",
                                     "SpaceBefore": 6, "Hyphenation": False},
              tabs=[("RightAlign", self.measure, ". ")]),
            S("Contents 2", "Contents 1", {"LeftIndent": 18, "SpaceBefore": 0}),
        ]
        self.doc.colors = [("Table Grey", (0, 0, 0, 12))]
        insets = {"TextTopInset": 3, "TextLeftInset": 4, "TextBottomInset": 3,
                  "TextRightInset": 4, "TopInset": 3, "BottomInset": 3, "LeftInset": 4,
                  "RightInset": 4}
        self.doc.cell_styles = [CellStyle("Head Cell", "Table Head", "Table Grey", dict(insets)),
                                CellStyle("Body Cell", "Table Body", None, dict(insets))]
        self.doc.table_styles = [TableStyle("Book Table", "Head Cell", "Body Cell",
                                            {"TopBorderStrokeWeight": 1,
                                             "BottomBorderStrokeWeight": 1,
                                             "LeftBorderStrokeWeight": 0,
                                             "RightBorderStrokeWeight": 0})]
        self.builtin = {s.name for s in self.doc.paragraph_styles}
        if self.tpl:
            apply_template(self.doc.paragraph_styles, self.tpl[0])
            self._keep_world_ready()
            attrs, _font, leading = self.doc.resolved("Body")
            self.body_size = attrs.get("PointSize", self.body_size)
            if isinstance(leading, (int, float)):
                self.body_lead = leading

    def _resolved_attrs(self, name):
        attrs, _font, _lead = self.doc.resolved(name)
        return attrs

    def _custom_paragraph_style(self, mapping, docx, style_id):
        """A Word style kept under its own name, based on its parent's IDML style (or its
        role's book style)."""
        name = mapping.idml
        if name in self.builtin or name in self.custom:
            return
        st = docx.styles.get(style_id)
        base = ROLE_BASE.get(mapping.role, "Body")
        if mapping.role == "heading":
            base = "Heading " + "ABC"[max(1, min(mapping.level, 3)) - 1]
        if st and st.based_on and st.based_on in docx.styles:
            pm = self.sm.paragraph_style(docx, st.based_on)
            if pm.idml and pm.idml not in self.builtin and pm.idml != name:
                self._custom_paragraph_style(pm, docx, st.based_on)
                base = pm.idml
            elif pm.idml in self.builtin:
                base = pm.idml if pm.role == mapping.role else base
        # The name and the place in the book come from Word; the look is the book style's
        # it is based on (Word's alignment, indents, spacing and sizes are a manuscript's).
        # A style with no book counterpart (a special paragraph the author set up, based on
        # Normal) keeps what makes it distinct, in book terms; never Word's fonts. The style
        # map's "look" setting overrides either way.
        attrs, leading = {}, None
        if self._look(mapping) == "word" and st is not None:
            attrs, leading = self._word_look(docx, style_id, st, base)
        self.custom[name] = Style(name, base, attrs, leading=leading)
        self.doc.paragraph_styles.append(self.custom[name])

    def _look(self, mapping):
        """"word" to keep a custom style's distinct look, "book" for the book style's. By
        default only styles with no book counterpart (role body, kept under their own name)
        keep their look."""
        entry = self.sm.paragraph.get(norm(mapping.word))
        if isinstance(entry, dict) and entry.get("look") in ("word", "book"):
            return entry["look"]
        return "word" if mapping.role == "body" and mapping.idml == mapping.word else "book"

    def _word_look(self, docx, style_id, st, base):
        """What a Word style sets on itself, in book terms: alignment; indents in proportion
        to the book's line against Word's; italic, bold, capitals; size and space in
        proportion to the body size. (attrs, leading)."""
        attrs, props = {}, st.props
        jc = _prop(props.get("jc"), "val")
        just = {"center": "CenterAlign", "right": "RightAlign", "end": "RightAlign",
                "both": "LeftJustified", "left": "LeftAlign", "start": "LeftAlign"}.get(jc)
        if just:
            attrs["Justification"] = just
            if just in ("CenterAlign", "RightAlign"):
                attrs["FirstLineIndent"] = 0
        sec = docx.sections[0] if docx.sections else None
        word_measure = None
        if sec and sec.page_width:
            m = sec.margins
            word_measure = (sec.page_width - m.get("left", 1) - m.get("right", 1)) * 72
        scale = min(1.0, self.measure / word_measure) if word_measure else 1.0
        ind = props.get("ind")
        if ind:
            for key, attr in (("left", "LeftIndent"), ("start", "LeftIndent"),
                              ("right", "RightIndent"), ("end", "RightIndent"),
                              ("firstLine", "FirstLineIndent")):
                v = _twips(ind, key)
                if v is not None:
                    attrs[attr] = _half(v * scale)
            hanging = _twips(ind, "hanging")
            if hanging is not None:
                attrs["FirstLineIndent"] = -_half(hanging * scale)
        normal = docx.resolve_size(docx.default_style.get("paragraph")) or 12
        size_scale = self.body_size / normal
        sp = props.get("spacing")
        if sp:
            for key, attr in (("before", "SpaceBefore"), ("after", "SpaceAfter")):
                v = _twips(sp, key)
                if v is not None:
                    attrs[attr] = _half(min(v * size_scale, 2 * self.body_lead))
        bold, italic = props.get("b"), props.get("i")
        if bold is not None or italic is not None:
            base_fs = self._resolved_attrs(base).get("FontStyle", "Regular")
            b = _toggle(bold) if bold is not None else "Bold" in base_fs
            i = _toggle(italic) if italic is not None else "Italic" in base_fs
            attrs["FontStyle"] = FONT_STYLES[(b, i)]
        if _toggle(props.get("caps")):
            attrs["Capitalization"] = "AllCaps"
        elif _toggle(props.get("smallCaps")):
            attrs["Capitalization"] = "SmallCaps"
        if "keepNext" in props and _toggle(props["keepNext"]):
            attrs["KeepWithNext"] = 2
        leading = None
        if "sz" in props:
            ratio = docx.resolve_size(style_id) / normal
            if abs(ratio - 1) > 0.01:
                attrs["PointSize"] = _half(self.body_size * ratio)
                leading = _half(self.body_lead * ratio)
        return attrs, leading

    def _char_style(self, name, docx=None, style_id=None):
        """Make sure a character style exists; returns its attributes."""
        if name in self.used_char:
            return self.used_char[name].attrs
        if name in CHAR_STYLES:
            st = Style(name, attrs=dict(CHAR_STYLES[name]))
        elif name == "Hebrew":
            # No face: Hebrew takes the face of the text around it (italic in italic text);
            # _script_runs gives the Hebrew font's own name for that face where it differs.
            st = Style(name, font=self.fonts["hebrew"],
                       attrs={"AppliedLanguage": "$ID/Hebrew",
                              "CharacterDirection": "RightToLeftDirection"})
        elif name == "Greek":
            st = Style(name, font=self.fonts["greek"], attrs={"AppliedLanguage": "$ID/Greek"})
        else:
            attrs, font = {}, None
            if docx is not None and style_id in docx.styles:
                ws = docx.styles[style_id]
                p = ws.props
                b, i = _toggle(p.get("b")), _toggle(p.get("i"))
                if b or i:
                    attrs["FontStyle"] = FONT_STYLES[(b, i)]
                if _toggle(p.get("caps")):
                    attrs["Capitalization"] = "AllCaps"
                elif _toggle(p.get("smallCaps")):
                    attrs["Capitalization"] = "SmallCaps"
                va = _prop(p.get("vertAlign"), "val")
                if va in ("superscript", "subscript"):
                    attrs["Position"] = va.capitalize()
                if p.get("u") and _prop(p["u"], "val") != "none":
                    attrs["Underline"] = True
                if _toggle(p.get("strike")):
                    attrs["StrikeThru"] = True
                font = ws.fonts.get("ascii") or ws.fonts.get("hAnsi")
            st = Style(name, attrs=attrs, font=font)
        self.used_char[name] = st
        return st.attrs

    def _template_font(self, name):
        """The font a template style ends up with (through its based-on styles), or None."""
        if not self.tpl:
            return None
        seen = set()
        st = self.tpl[0].get(name)
        while st is not None and st.name not in seen:
            seen.add(st.name)
            if st.font:
                return st.font
            st = self.tpl[0].get(st.based_on) if st.based_on else None
        return None

    def _keep_world_ready(self):
        """A template's composer gives way to World-Ready when the book has Hebrew."""
        if not any(d.scripts["hebrew"].chars for d in self.docs):
            return
        changed = False
        for s in self.doc.paragraph_styles:
            if s.attrs.get("Composer") not in (None, "HL Composer Optyca"):
                s.attrs["Composer"] = "HL Composer Optyca"
                changed = True
        if changed and not getattr(self, "_tpl_composer_noted", False):
            self.report.append("The template's styles use another composer; the book has "
                               "Hebrew, so they use the World-Ready composer instead (Hebrew "
                               "needs it).")
            self._tpl_composer_noted = True

    def _template_styles(self):
        """The template's styles over the book's (custom ones too), and its other styles
        added for use by hand. Reported."""
        tp, tc, notes = self.tpl
        replaced = set(apply_template(self.doc.paragraph_styles, tp))
        self._keep_world_ready()
        chars = list(self.doc.character_styles)
        replaced |= set(apply_template(chars, tc))
        self.doc.character_styles = chars
        have_p = {s.name for s in self.doc.paragraph_styles}
        have_c = {s.name for s in chars}
        added = [n for n in tp if n not in have_p] + [n for n in tc if n not in have_c]
        for n in tp:
            if n not in have_p:
                self.doc.paragraph_styles.append(tp[n])
        for n in tc:
            if n not in have_c:
                self.doc.character_styles.append(tc[n])
        own = sorted((have_p | have_c) - replaced)
        self.report.append("Styles from %s: %d of the book's styles taken from it; %d more "
                           "added for use by hand; the tool's own kept for %s." % (
                               os.path.basename(self.profile["styles_template"]), len(replaced),
                               len(added), ", ".join(own) if own else "none"))
        self.report += notes
        return set(tp)

    def _baseline_grid(self):
        """Body text on a baseline grid of the body leading, from the top margin (as g09);
        styles with other leading (block quotes, notes, captions, headings) stay off it."""
        m = self.doc.margins
        self.doc.baseline_grid = {"start": m["top"], "division": self.body_lead, "shown": False}
        body = self.doc.style("Body")
        if body is not None:
            body.attrs["GridAlignment"] = "AlignBaseline"
        for s in self.doc.paragraph_styles:
            attrs, _font, lead = self.doc.resolved(s.name)
            if attrs.get("GridAlignment") == "AlignBaseline" and lead != self.body_lead:
                s.attrs["GridAlignment"] = "None"

    def _finish_styles(self):
        self._char_style("Footnote Reference")
        order = list(CHAR_STYLES) + ["Hebrew", "Greek"]
        self.doc.character_styles = sorted(
            self.used_char.values(),
            key=lambda s: (order.index(s.name) if s.name in order else len(order), s.name))
        tpl_names = self._template_styles() if self.tpl else set()
        if self.profile.get("baseline_grid"):
            self._baseline_grid()
        # Only the styles the book uses, plus the ones every book has (and the template's).
        used = set(self.para_used) | {"Body", "Body First", "Footnote", "Folio", "Running Head"}
        used |= tpl_names
        for st in self.doc.stories:
            used |= {p.style for p in st.paragraphs}
        if self.doc.toc_styles:
            used |= {"Contents Title", "Contents 1", "Contents 2"}
        keep, changed = [], True
        styles = {s.name: s for s in self.doc.paragraph_styles}
        while changed:
            changed = False
            for name in list(used):
                s = styles.get(name)
                for dep in (s.based_on, s.next_style) if s else ():
                    if dep and dep not in used:
                        used.add(dep)
                        changed = True
        for cs in self.doc.cell_styles:
            if self.tables_used:
                used.add(cs.paragraph_style)
        keep = [s for s in self.doc.paragraph_styles if s.name in used]
        self.doc.paragraph_styles = keep
        if not self.tables_used:
            self.doc.cell_styles, self.doc.table_styles, self.doc.colors = [], [], []

    # ---- text ----

    def _run_attrs(self, crun, para_style, docx, note):
        """(character style, local attributes) for a run's features in a paragraph style."""
        pattrs = self._resolved_attrs(para_style)
        pfs = pattrs.get("FontStyle", "Regular")
        p_bold, p_italic = "Bold" in pfs, "Italic" in pfs
        cs_feats = {}
        mapped = None
        if crun.char_style and crun.char_style in docx.styles:
            m = self.sm.character_style(docx, crun.char_style)
            if m.role != "skip":
                mapped = m.idml
            for sid in reversed(docx.style_chain(crun.char_style)):
                p = docx.styles[sid].props
                for key, feat in (("i", "italic"), ("b", "bold")):
                    if key in p:
                        cs_feats[feat] = _toggle(p[key])
        f = crun.feats

        def eff(feat, para_on):
            if feat in f:
                return f[feat]
            if feat in cs_feats:
                return para_on != cs_feats[feat] if cs_feats[feat] else para_on
            return para_on
        fs = FONT_STYLES[(eff("bold", p_bold), eff("italic", p_italic))]
        want = {}
        if fs != pfs:
            want["FontStyle"] = fs
        if f.get("caps"):
            want["Capitalization"] = "AllCaps"
        elif f.get("smallcaps"):
            want["Capitalization"] = "SmallCaps"
        if f.get("position"):
            want["Position"] = f["position"].capitalize()
        if f.get("underline"):
            want["Underline"] = True
        if f.get("strike"):
            want["StrikeThru"] = True
        if mapped:
            sattrs = self._char_style(mapped, docx, crun.char_style)
            if "FontStyle" in sattrs and "FontStyle" not in want and fs == pfs:
                want["FontStyle"] = fs        # the style's face is right for this run
            return mapped, self._local(want, sattrs, pfs)
        style = None
        if want.get("FontStyle") in ("Italic", "Bold", "Bold Italic"):
            style = want["FontStyle"]
        elif "Capitalization" in want:
            style = {"SmallCaps": "Small Caps", "AllCaps": "All Caps"}[want["Capitalization"]]
        elif "Position" in want:
            style = want["Position"]
        elif "Underline" in want:
            style = "Underline"
        elif "StrikeThru" in want:
            style = "Strikethrough"
        if style is None:
            return None, want
        return style, self._local(want, self._char_style(style), pfs)

    @staticmethod
    def _local(want, sattrs, pfs):
        local = {k: v for k, v in want.items() if sattrs.get(k) != v}
        for k, v in sattrs.items():
            if k in RESET and k not in want:
                local[k] = RESET[k] if RESET[k] is not None else pfs
        return local

    def _runs(self, cruns, para_style, docx, note=False):
        out = []
        for cr in cruns:
            if cr.footnote is not None:
                out.append(Run(footnote=self._note(cr.footnote, docx)))
                continue
            if cr.image is not None or not cr.text:
                continue
            style, local = self._run_attrs(cr, para_style, docx, note)
            out += self._script_runs(cr.text, style, local, para_style)
        out = _merge_runs(out)
        for r in out:
            if r.text and ("//" in r.text or "www." in r.text):
                r.text = url_breaks(r.text)
        return out

    def _script_runs(self, text, style, local, para_style=None):
        """A run's text split into runs: Hebrew and Greek in their character styles, keeping
        the run's own style's settings (italic...) as local ones. Hebrew takes the face of
        the text around it, by the Hebrew font's own name for that face."""
        out = []
        for script, part in segments(text):
            if script:
                name = "Hebrew" if script == "hebrew" else "Greek"
                sattrs = self._char_style(name)
                want = dict(local)
                if style and style in self.used_char:
                    for k, v in self.used_char[style].attrs.items():
                        want.setdefault(k, v)
                if script == "hebrew":
                    self._hebrew_face(want, para_style)
                out.append(Run(part, name, {k: v for k, v in want.items()
                                            if sattrs.get(k) != v}))
            else:
                out.append(Run(part, style, dict(local)))
        return out

    def _hebrew_face(self, want, para_style):
        """Set want["FontStyle"] to the Hebrew font's name for the face the Hebrew sits in (the
        run's, else the paragraph's) when that name differs; note a face the font lacks."""
        face = want.get("FontStyle") or \
            (self._resolved_attrs(para_style).get("FontStyle") if para_style else None) or \
            "Regular"
        heb = self.fonts["hebrew"]
        name, exact = fonts.matching_face(heb, face)
        if name and name != face:
            want["FontStyle"] = name
        if not exact:
            missing = getattr(self, "hebrew_faces_missing", set())
            missing.add(face)
            self.hebrew_faces_missing = missing

    def _generated_scripts(self):
        """Hebrew and Greek in text the program wrote itself (half-title, title and copyright
        pages, running heads) set as in the manuscript's text: in the Hebrew and Greek
        styles, and a Hebrew line with the World-Ready composer, right to left when mostly
        Hebrew. The manuscript's runs are split already and pass through unchanged."""
        paras = [p for st in self.doc.stories for p in st.paragraphs]
        paras += [p for m in self.doc.masters for f in m.frames for p in f.paragraphs]
        for p in paras:
            if not any(r.text and r.style not in ("Hebrew", "Greek") and
                       any(is_hebrew(c) or is_greek(c) for c in r.text) for r in p.runs):
                continue
            runs = []
            for r in p.runs:
                if r.text and r.style not in ("Hebrew", "Greek") and r.footnote is None:
                    runs += self._script_runs(r.text, r.style, r.attrs, p.style)
                else:
                    runs.append(r)
            p.runs = _merge_runs(runs)
            text = "".join(r.text for r in p.runs if r.text)
            heb = sum(1 for c in text if is_hebrew(c))
            if heb:
                p.attrs["Composer"] = "HL Composer Optyca"
                if heb > sum(1 for c in text if c.isalpha() and not is_hebrew(c)):
                    p.attrs["ParagraphDirection"] = "RightToLeftDirection"

    def _runt_style(self, name):
        """Paragraphs of running text (Body, notes, quotations...), not headings or display."""
        seen = set()
        while name and name not in seen:
            seen.add(name)
            if name in NO_RUNT_SKIP:
                return False
            if name in ("Body", "Footnote"):
                return True
            s = self.doc.style(name)
            name = s.based_on if s else None
        return False

    def _no_runt(self, para, min_chars):
        """Keep the last words of a paragraph together (No Break), so its last line has at
        least min_chars characters: no short word alone on the last line. Works in every
        program, unlike a GREP style."""
        if not min_chars or not self._runt_style(para.style):
            return
        texts = [(i, r) for i, r in enumerate(para.runs)
                 if r.footnote is None and r.table is None and r.image is None and not r.special]
        full = "".join(r.text for _i, r in texts)
        end = len(full.rstrip())
        if end < 4 * min_chars:
            return                      # a line or so: nothing to gain
        start = full.rfind(" ", 0, end) + 1
        if not start or end - start >= min_chars:
            return                      # a long last word is not a runt
        while end - start < min_chars:
            space = full.rfind(" ", 0, start - 1)
            if space < 0 or "\t" in full[space:end] or "\n" in full[space:end]:
                return
            start = space + 1
        if end - start > 3 * min_chars:
            return
        # Split the runs at start; mark everything from there on.
        pos, out = 0, []
        text_ids = {i for i, _r in texts}
        for i, r in enumerate(para.runs):
            if i not in text_ids:
                out.append(r)
                continue
            a, b = pos, pos + len(r.text)
            pos = b
            if b <= start:
                out.append(r)
                continue
            if a < start:
                out.append(Run(r.text[:start - a], r.style, dict(r.attrs)))
                r = Run(r.text[start - a:], r.style, dict(r.attrs))
            if r.style is None:
                r.style = "No Break"
                self._char_style("No Break")
            else:
                r.attrs["NoBreak"] = True
            out.append(r)
        para.runs = out

    def _note(self, cparas, docx):
        paras = []
        for cp in cparas:
            if cp.empty:
                continue
            paras.append(Paragraph("Footnote", self._runs(cp.runs, "Footnote", docx, True),
                                   self._para_attrs(cp, "Footnote")))
        return paras or [Paragraph("Footnote", [])]

    def _para_attrs(self, cp, style):
        attrs = {}
        text = cp.text
        if cp.align in ("center", "right"):
            attrs["Justification"] = "CenterAlign" if cp.align == "center" else "RightAlign"
            if cp.align == "center":
                attrs["FirstLineIndent"] = 0
        heb = sum(1 for c in text if is_hebrew(c))
        if heb:
            attrs["Composer"] = "HL Composer Optyca"
            latin = sum(1 for c in text if c.isalpha() and not is_hebrew(c))
            if cp.bidi or heb > latin:
                attrs["ParagraphDirection"] = "RightToLeftDirection"
                just = attrs.get("Justification") or \
                    self._resolved_attrs(style).get("Justification", "LeftAlign")
                attrs["Justification"] = {"LeftJustified": "RightJustified",
                                          "LeftAlign": "RightAlign"}.get(just, just)
        return attrs

    def _mapping(self, docx, style_id, index=None):
        """The mapping for a paragraph of style style_id; index (a body paragraph's) lets a
        heading found by formatting map by its look."""
        sid = style_id if style_id in docx.styles else docx.default_style.get("paragraph")
        if index is not None and (index in self.sm.format_groups(docx)[1] or
                                  self.sm.repeated_title(docx, docx.paragraphs[index])):
            return self.sm.paragraph_mapping(docx, docx.paragraphs[index])
        m = self.sm.paragraph_style(docx, sid)
        if m.idml and m.idml not in self.builtin and m.role not in ("skip", "toc", "toc_title"):
            self._custom_paragraph_style(m, docx, sid)
        return m

    def _bibliography_state(self, cp, docx, bib):
        """Bibliography styling runs from a heading titled Bibliography (Works Cited,
        References...) at any level to the next heading of the same or a higher level, so a
        bibliography ending a chapter doesn't spill into what follows."""
        if cp.table is not None:
            return bib
        m = self._mapping(docx, cp.style_id, cp.index)
        if m.role in ("chapter", "part", "book_title"):
            level = 0
        elif m.role == "heading":
            level = max(1, m.level)
        else:
            return bib
        if _BACK.get(title_key(cp.text)) == "bibliography":
            return level
        return bib if bib is not None and level > bib else None

    def _paragraphs(self, cp, docx, unit, prev_role, first, bib=False, body_seen=True):
        """Model paragraphs for one content paragraph (an image splits it), with its role.
        bib: the paragraph is in a bibliography section (body text set as entries).
        body_seen: the unit already has body text (the first text paragraph of a unit, after
        an epigraph say, is set flush: Body First)."""
        if cp.table is not None:
            return [Paragraph("Table", [Run(table=self._table(cp.table, docx))])], "table"
        m = self._mapping(docx, cp.style_id, cp.index)
        if m.role in ("skip", "toc", "toc_title") or cp.empty:
            return [], prev_role
        style = m.idml or "Body"
        runs = list(cp.runs)
        if m.feats:
            # A heading found by its look: the bold, italic or capitals that made it one are
            # the heading style's business now, not character styles on its text.
            runs = [replace(r, feats={k: v for k, v in r.feats.items() if k not in m.feats})
                    for r in runs]
        if m.role == "part" or (unit is not None and unit.kind == "part" and first and
                                m.role == "chapter"):
            style = "Part Title"
        elif unit is not None and unit.kind != "display" and \
                m.role in ("book_title", "subtitle", "author"):
            # A title line opening a chapter (an article's title, say) titles that chapter,
            # not the book's title page.
            style = {"book_title": "Chapter Title", "subtitle": "Chapter Subtitle",
                     "author": "Chapter Author"}[m.role]
        if cp.label:
            if m.role in ("chapter", "part", "heading"):
                runs.insert(0, _label_run(cp.label + " "))
            else:
                if style in ("Body", "List"):
                    style = "List Bullet" if cp.list_format == "bullet" else "List Number"
                runs.insert(0, _label_run(cp.label + (cp.label_suffix or "\t")))
        if style == "Body" and bib:
            style = "Bibliography"
        if style == "Body" and (first or prev_role in HEAD_ROLES or not body_seen):
            style = "Body First"
        attrs = self._para_attrs(cp, style)
        role = m.role
        if attrs.get("Justification", self._resolved_attrs(style).get("Justification")) == \
                "CenterAlign" and role not in HEAD_ROLES:
            role = "centered"      # an epigraph, a centered line: the text after starts flush
        if cp.label and cp.list_level and style.startswith("List"):
            attrs["LeftIndent"] = 18 * (cp.list_level + 1)
        if cp.page_break_before and not first:
            attrs["StartParagraph"] = "NextPage"
        # Images go in paragraphs of their own, in order with the text around them.
        out, chunk = [], []
        for r in runs:
            if r.image is not None:
                if any(x.text.strip() or x.footnote is not None for x in chunk):
                    out.append(Paragraph(style, self._runs(chunk, style, docx), dict(attrs)))
                chunk = []
                out.append(self._figure(r.image, docx))
            else:
                chunk.append(r)
        if any(x.text.strip() or x.footnote is not None for x in chunk) or not out:
            out.append(Paragraph(style, self._runs(chunk, style, docx), attrs))
        return out, role

    def _figure(self, img, docx):
        prefix = os.path.splitext(docx.name)[0]
        path = save_image(img, self.tmp, prefix)
        if path is None:
            self.report.append("Image %s in %s is not JPEG or PNG; it was left out (a line marks "
                               "its place). Save it as PNG or JPEG and place it by hand."
                               % (img.name, docx.name))
            return Paragraph("Figure", [Run("[Image not carried over: %s]" % img.name)])
        width = min(img.width or self.measure, self.measure)
        return Paragraph("Figure", [Run(image=Image(path, width=_half(width)))])

    def _table(self, ct, docx):
        self.tables_used = True
        rows = []
        for r, row in enumerate(ct.rows):
            out_row = []
            for cell in row:
                if cell is None:
                    out_row.append(None)
                    continue
                paras = []
                for cp in cell:
                    if cp.table is not None or cp.empty:
                        continue
                    m = self._mapping(docx, cp.style_id)
                    style = m.idml if m.idml and m.role not in ("body", "skip") else "Table Body"
                    if r < ct.header_rows and style == "Table Body":
                        style = "Table Head"
                    self.para_used.add(style)
                    paras.append(Paragraph(style, self._runs(cp.runs, style, docx),
                                           self._para_attrs(cp, style)))
                out_row.append(paras or [Paragraph("Table Body", [])])
            rows.append(out_row)
        n = len(rows[0]) if rows else 1
        widths = ct.widths
        if not widths or None in widths:
            widths = [self.measure / n] * n
        total = sum(widths)
        if total > self.measure:
            widths = [w * self.measure / total for w in widths]
        return Table(rows, [_half(w) for w in widths], ct.header_rows, "Book Table",
                     dict(ct.spans))

    # ---- units and stories ----

    def _stories(self):
        """[(unit, paragraphs)] in book order."""
        self.para_used = set()
        self.tables_used = False
        units_by_file = {}
        for u in self.outline.units:
            units_by_file.setdefault(u.file, []).append(u)
        stories = []
        current = None
        for docx in self.docs:
            content = read_content(docx)
            starts = {u.start: u for u in units_by_file.get(docx.name, [])}
            prev_role, first = None, True
            bib = None              # level of the bibliography heading we're under, if any
            for cp in content:
                if cp.index in starts:
                    unit = starts.pop(cp.index)
                    current = [unit, []]
                    stories.append(current)
                    prev_role, first, bib = None, True, None
                if current is None:
                    # Text before the first unit (the outline found none for it).
                    current = [None, []]
                    stories.append(current)
                if cp.index >= 0 and cp.index < len(docx.paragraphs) and \
                        docx.paragraphs[cp.index].in_toc_field and cp.table is None:
                    continue
                bib = self._bibliography_state(cp, docx, bib)
                body_seen = any(p.style in ("Body", "Body First") for p in current[1])
                paras, role = self._paragraphs(cp, docx, current[0], prev_role, first,
                                               bib is not None, body_seen)
                if paras:
                    current[1].extend(paras)
                    prev_role, first = role, False
        min_chars = self.profile["typography"].get("last_line_min_chars") or 0
        for _unit, paras in stories:
            for p in paras:
                self.para_used.add(p.style)
                self._no_runt(p, min_chars)
                for r in p.runs:
                    for n in r.footnote or ():
                        self.para_used.add(n.style)
                        self._no_runt(n, min_chars)
        n_end = sum(d.endnote_count for d in self.docs)
        if n_end:
            self.report.append("%d endnote%s converted to footnotes." %
                               (n_end, "" if n_end == 1 else "s"))
        return [(u, p) for u, p in stories if p]

    def _estimate(self, paras, sink, raw=False):
        """Pages a story needs: lines of text at the styles' sizes, notes, tables, images.
        raw: the estimate as a fraction of pages, before the slack and rounding up."""
        def lines(p, measure):
            attrs, _font, leading = self.doc.resolved(p.style)
            size = attrs.get("PointSize", self.body_size)
            lead = leading if isinstance(leading, (int, float)) else size * 1.2
            text = "".join(r.text for r in p.runs)
            cpl = max(10, (measure - attrs.get("LeftIndent", 0)) / (size * self.avg_width))
            n = max(1, math.ceil(len(text) / cpl))
            return n * lead + attrs.get("SpaceBefore", 0) + attrs.get("SpaceAfter", 0)
        height = sink
        notes = 0
        for p in paras:
            for r in p.runs:
                if r.table is not None:
                    for row in r.table.rows:
                        cells = [c for c in row if c]
                        height += max([sum(lines(q, self.measure / len(row)) for q in c)
                                       for c in cells] + [12]) + 6
                    continue
                if r.image is not None:
                    w, h, *_ = image_info(r.image.path)
                    height += r.image.width * h / w + 12
                for n in r.footnote or ():
                    height += lines(n, self.measure) + 3
                notes += bool(r.footnote)
            if not any(r.table is not None or r.image is not None for r in p.runs):
                height += lines(p, self.measure)
        # Each page with notes also gives up the space above them (and the rule).
        fn = self.profile.get("footnotes") or {}
        per_page = (fn.get("space_above") or 0) + \
            ((fn.get("space_below_rule") or 0) + 0.5 if fn.get("rule") else 0)
        height += min(notes, math.ceil(height / self.text_height)) * per_page
        if raw:
            return height / self.text_height
        # Lines lost at page feet (keeps, widows, notes that can't split) grow with the
        # length: SLACK of each page. A story whose text runs past its pages makes InDesign's
        # Smart Text Reflow add a page, out of place among the chapters' spreads.
        return max(1, math.ceil(height * (1 + SLACK) / self.text_height))

    # ---- front matter (step 6) ----

    def _front_matter(self, stories):
        """The book's blocks in order: generated half-title, title and copyright pages, the
        manuscript's display pages, the reserved contents, then front matter, text and back
        matter. Returns [Block]."""
        front = self.settings.get("front", {})
        lang = self.profile["front_matter"].get("language", "en")
        info, notes = frontmatter.book_info(self.outline, front, lang)
        self.info = info
        self.report += notes
        display, front_units, rest, praise = [], [], [], []
        ms_copyright, extras = [], []
        for unit, paras in stories:
            kind = unit.kind if unit else "chapter"
            if kind == "display" and unit.type in ("title page", "opening"):
                cp, ex = self._split_opening(paras)
                ms_copyright += cp
                extras += ex
            elif kind == "display" and unit.type == "copyright":
                # Replaced by the page made from Book Details (its details were read into
                # them: outline.details).
                ms_copyright.append(unit.title)
            elif kind == "display" and unit.type == "endorsements":
                praise.append(Block(unit, paras))
            elif kind == "display":
                display.append(Block(unit, paras))
            elif kind == "front" and unit.type == "contents":
                self.report.append('The manuscript\'s own contents ("%s") was left out: its '
                                   "page numbers would be wrong. Pages are reserved for the "
                                   "contents instead." % unit.title)
            elif kind == "front" and not rest:
                front_units.append(Block(unit, paras))
            else:
                rest.append(Block(unit, paras))
        # Endorsements come first, before the half-title (Chicago).
        blocks = list(praise)
        g = lambda kind, title, typ: Unit(kind, typ, title, "", -1, "generated")  # noqa: E731
        if info["half_title"]:
            blocks.append(Block(g("display", "Half title", "half title"),
                                frontmatter.half_title(info, lang), sink=_half(self.text_height / 4)))
        blocks.append(Block(g("display", "Title page", "title page"), frontmatter.title_page(info, lang),
                            sink=_half(self.text_height / 5)))
        paras, cnotes = frontmatter.copyright_page(info, lang, self.profile.get("notices"))
        self.report += cnotes
        if ms_copyright:
            left = (self.outline.details or {}).get("leftover") or []
            self.report.append(
                "The manuscript's copyright page was replaced by one made from Book Details "
                "(its details and notices were read into them)." + (
                    " Lines that fit no field, left out: %s. Add any that belong in Credits "
                    "or as a notice." % "; ".join("\u201c%s\u201d" % x for x in left)
                    if left else ""))
        blocks.append(Block(g("display", "Copyright", "copyright"), paras, opens="next",
                            valign="BottomAlign"))
        if extras:
            # Other lines of the manuscript's title page (a school, a place, a date) are left
            # out (Beaux): the generated pages hold what a book needs. Listed, so nothing is
            # lost unseen.
            lines = ["".join(r.text for r in p.runs).strip() for p in extras]
            self.report.append(
                "Left out from the manuscript's title page: %s. If any belongs in the book "
                "(the publisher, say), enter it in Book Details."
                % "; ".join("\u201c%s\u201d" % t for t in lines if t))
        blocks += display
        if info["contents"]:
            depth = self.profile["front_matter"].get("contents_depth", "chapters")
            entries = frontmatter.contents_entries(self.outline, depth)
            sink = self._opener_drop()
            pages = info["contents_pages"] or frontmatter.contents_pages(
                entries, self.geo.cpl, self.body_lead, self.text_height, sink)
            blocks.append(Block(g("front", frontmatter.texts(lang)["contents"], "contents"),
                                frontmatter.contents_page(lang), pages=pages, spare=0))
            self.report.append("Contents: %d page%s reserved for %d entries (change it in the "
                               "book settings). Place the contents from the Contents style."
                               % (pages, "" if pages == 1 else "s", len(entries)))
            self.contents_depth = depth
        else:
            self.contents_depth = None
        return blocks + front_units + rest

    def _split_opening(self, paras):
        """The manuscript's own title page: title, subtitle and author lines are replaced by
        the generated title page; from a copyright line on, the text goes on the copyright
        page; anything else is left out (and reported)."""
        copyright_, extras = [], []
        author = (self.outline.author or "").casefold()
        for p in paras:
            text = " ".join("".join(r.text for r in p.runs).split())
            low = text.casefold()
            if copyright_ or "\u00a9" in text or low.startswith("copyright") or \
                    "derechos reservados" in low:
                copyright_.append(p)
            elif p.style in ("Book Title", "Book Subtitle", "Author") or \
                    (author and author in low and len(text) < 80) or \
                    low in ("by", "por") or \
                    _FRONT.get(title_key(text)) == ("front", "contents"):
                continue        # replaced by the generated pages (the contents has its own)
            else:
                extras.append(p)
        return copyright_, extras

    def _leading_note(self):
        sug, why = layout.leading_suggestions(self.body_size, self.x_height, self.geo.cpl,
                                              self.fonts["body"])
        lead = self.profile.get("leading") or {}
        if self.tpl and self.tpl[0].get("Body"):
            source = "from the style template"
        elif lead.get("value"):
            source = "as set in the profile"
        else:
            source = "%s, the middle of its range" % (lead.get("feel") or "standard")
        return ("Body type: %g pt on %g pt leading (%s). Suggested for %g pt: tight %g\u2013%g, "
                "standard %g\u2013%g, open %g\u2013%g%s." % (
                    self.body_size, self.body_lead, source, self.body_size,
                    sug["tight"][0], sug["tight"][1], sug["standard"][0], sug["standard"][1],
                    sug["open"][0], sug["open"][1], (" (%s)" % why) if why else ""))

    def _running_head_style(self, size, lead):
        """The Running Head style as the profile sets it (capitals, italic, bold, underline,
        size, letter-spacing, font). Title and sentence case change the text instead
        (`_head_text`)."""
        rs = (self.profile.get("running_heads") or {}).get("style") or {}
        attrs = {"PointSize": rs.get("size") or size - 2, "Justification": "CenterAlign",
                 "Tracking": rs.get("tracking") if rs.get("tracking") is not None else 20,
                 "Hyphenation": False}
        caps = rs.get("caps")
        if caps in ("small_caps", "all_caps"):
            attrs["Capitalization"] = "SmallCaps" if caps == "small_caps" else "AllCaps"
        face = FONT_STYLES[(bool(rs.get("bold")), bool(rs.get("italic")))]
        if face != "Regular":
            attrs["FontStyle"] = face
        if rs.get("underline"):
            attrs["Underline"] = True
        return Style("Running Head", font=rs.get("font") or self.fonts["body"], leading=lead,
                     attrs=attrs)

_URL = re.compile(r"(?:https?://|www\.|doi\.org/)[^\s<>\"\u201c\u201d]+", re.I)
ZWSP = "\u200b"


def url_breaks(text):
    """Web addresses with places to break a line (a zero-width space, no hyphen), as Chicago
    6.8 has them: after a colon or a double slash; before a single slash, a period, a comma,
    a hyphen, an underscore, a tilde, a question mark, a number sign or a percent sign; before
    or after an equals sign or an ampersand. Without them a long address in justified text
    (a footnote's database link) is spaced out letter by letter. A closing period or comma
    stays outside the address."""
    def breaks(m):
        url = m.group(0)
        tail = ""
        while url and url[-1] in ".,;:)":
            url, tail = url[:-1], url[-1] + tail
        out, i = [], 0
        while i < len(url):
            c = url[i]
            if url.startswith("//", i):
                out.append("//" + ZWSP)
                i += 2
                continue
            if c in "/.,-_~?#%" and i > 0 and out and not out[-1].endswith(ZWSP):
                out.append(ZWSP + c)
            elif c in "=&":
                out.append((ZWSP if out and not out[-1].endswith(ZWSP) else "") + c + ZWSP)
            elif c == ":" and not url.startswith("//", i + 1):
                out.append(c + ZWSP)
            else:
                out.append(c)
            i += 1
        return "".join(out).replace(ZWSP + ZWSP, ZWSP) + tail
    return _URL.sub(breaks, text)


def _merge_runs(out):
    """Neighbouring text runs with the same style and settings as one."""
    merged = []
    for r in out:
        prev = merged[-1] if merged else None
        if prev and not any((r.footnote, prev.footnote, r.special, prev.special, r.table,
                             prev.table, r.image, prev.image)) and \
                prev.style == r.style and prev.attrs == r.attrs:
            prev.text += r.text
        else:
            merged.append(r)
    return merged


def _label_run(text):
    from .content import CRun
    return CRun(text)


def export(paths, out_dir, profile=None, name=None, settings=None):
    """Export the manuscript to an export folder (IDML and Links). settings: the book's own
    settings. Returns (IDML path, report lines)."""
    from .idml.writer import export_book
    ex = Exporter(paths, profile, settings)
    try:
        doc = ex.build()
        info = getattr(ex, "info", None) or {}
        path = export_book(doc, out_dir, file_name(name) if name else file_name(
            info.get("title") or doc.name, info.get("short_title")))
    finally:
        ex.cleanup()
    return path, ex.report


_RESERVED = {"con", "prn", "aux", "nul"} | {"com%d" % n for n in range(1, 10)} | \
    {"lpt%d" % n for n in range(1, 10)}


def file_name(title, short_title=None, limit=60):
    """A name for the export folder and IDML that Windows accepts as it is: the short title if
    there is one, else the title before a colon (its subtitle left off); characters Windows
    forbids replaced, cut at a word to `limit` characters, no space or dot at the end (Windows
    drops them from a folder's name, so the path written would not be the one made), and not
    a reserved device name."""
    name = (short_title or "").strip() or re.split(r"\s*:\s+|\s+[\u2013\u2014]\s+",
                                                   title or "")[0]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", name)
    name = " ".join(name.split())
    if len(name) > limit:
        cut = name[:limit + 1].rsplit(" ", 1)[0]
        name = cut if len(cut) >= limit // 2 else name[:limit]
    name = name.rstrip(" .").lstrip(" ")
    if name.split(".")[0].lower() in _RESERVED:
        name += " book"
    return name or "Book"