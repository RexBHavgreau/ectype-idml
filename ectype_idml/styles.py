"""The book's styles (moved out of export.py, 1.1.0): `StylesMixin` of the Exporter makes the
paragraph and character styles (the book set, Word styles kept by name with their look in
book terms, a style template's), and the helpers they share with the exporter.
"""

import os

from . import fonts, layout
from .idml.model import CellStyle, Style, TableStyle
from .stylemap import norm
from .template import apply_template

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
ROLE_BASE = {"body": "Body", "quote": "Block Quote", "verse": "Verse", "list": "List",
             "caption": "Caption", "note": "Footnote", "chapter": "Chapter Title",
             "part": "Part Title", "book_title": "Book Title", "subtitle": "Book Subtitle",
             "author": "Author"}


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



class StylesMixin:
    """Styles of the Exporter (export.py): the book set, Word and template styles."""

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
