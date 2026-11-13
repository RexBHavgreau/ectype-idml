"""The Layout Profile tab of the window (moved out of gui.py, 1.1.0): page, type, footnote
and typography forms, the calculated margins and the leading note."""

import copy
import tkinter as tk
from tkinter import ttk

from .export import TRIMS
from .gui_forms import Form, _num, format_points

PROFILE_FIELDS = {
    # The Page Layout tab in three sections.
    "Page Layout": {
        "Page Size": [
            (("page", "trim"), "Trim size", "choice", list(TRIMS) + ["custom"]),
            (("page", "custom_width"), "Custom width (in)", "number", None),
            (("page", "custom_height"), "Custom height (in)", "number", None),
            (("page", "bleed"), "Bleed (0.125 in)", "bool", None),
        ],
        "Page Organization": [
            (("page", "facing"), "Facing pages", "bool", None),
            (("chapters_open",), "Chapters open on", "choice", ["recto", "next_page"]),
            (("page", "spare_pages"), "Spare pages after each chapter", "int_choice",
             ["0", "1", "2"]),
            (("page", "opener_drop"), "Chapter titles lowered by (blank = 6 body lines)",
             "points", (6, "pt")),
        ],
        "Page Margins": [
            (("page", "measure"), "Line length (a multiple of the type size; 30 usual, "
             "20\u201340)", "number", None),
            (("page", "margins", "top"), "Top margin", "points", (9, "in")),
            (("page", "margins", "bottom"), "Bottom margin", "points", (9, "in")),
            (("page", "margins", "inside"), "Inside margin", "points", (9, "in")),
            (("page", "margins", "outside"), "Outside margin", "points", (9, "in")),
        ],
    },
    "Type": [
        (("styles_template",), "Styles from an IDML file (optional)", "file", None),
        (("fonts", "body"), "Body font (blank = an installed book font)", "font", None),
        (("fonts", "headings"), "Headings font", "font", None),
        (("fonts", "notes"), "Notes font", "font", None),
        (("fonts", "display"), "Display font", "font", None),
        (("fonts", "hebrew"), "Hebrew font", "font", "hebrew"),
        (("fonts", "greek"), "Greek font", "font", "greek"),
        (("body_size",), "Body size (pt)", "size", ["9", "9.5", "10", "10.5", "11", "11.5", "12",
                                                     "12.5", "13"]),
        (("leading", "feel"), "Leading", "choice", ["tight", "standard", "open"]),
        (("leading", "value"), "Exact leading (blank = from the choice above)", "number", None),
        (("leading", "unit"), "Leading unit", "choice", ["pt", "multiple", "percent"]),
        (("front_matter", "language"), "Language", "choice", ["en", "es"]),
        (("baseline_grid",), "Baseline grid (body text on the leading)", "bool", None),
        (("typography", "paragraph_composer"), "World-Ready composer (off = single-line)",
         "bool", None),
        (("typography", "optical_margins"), "Optical margin alignment", "bool", None),
        (("typography", "hyphenation"), "Hyphenation", "bool", None),
        (("typography", "ligatures"), "Ligatures", "bool", None),
        (("typography", "oldstyle_figures"), "Old-style figures", "bool", None),
        (("typography", "balance_ragged_headings"), "Balance ragged headings", "bool", None),
        (("typography", "widow_orphan_control"), "Widow and orphan control", "bool", None),
        (("typography", "last_line_min_chars"), "Shortest last line (characters, 0 = off)",
         "int", None),
    ],
    "Notes and Contents": [
        (("footnotes", "numbering"), "Footnote numbering", "choice", ["per_chapter", "continuous"]),
        (("footnotes", "rule"), "Rule above the notes", "bool", None),
        (("footnotes", "continuation_rule"), "Rule above continued notes", "bool", None),
        (("footnotes", "space_above"), "Space above the notes", "points", (1, "pt")),
        (("footnotes", "space_below_rule"), "Space below a rule", "points", (1, "pt")),
        (("footnotes", "space_between"), "Space between notes", "points", (1, "pt")),
        (("footnotes", "rule_length"), "Rule length", "points", (9, "pt")),
        (("front_matter", "contents_depth"), "Contents lists", "choice", ["chapters", "sections"]),
    ],
}


class LayoutTabMixin:
    """The Layout Profile tab of the App."""

    def _auto_drop(self):
        """The automatic opener drop (six body lines) for the profile as the forms set it."""
        from .export import body_size, leading_for
        prof = copy.deepcopy(self.profile)
        for form in self.profile_forms:
            form.save(prof)
        return round(leading_for(prof, body_size(prof)) * 6 * 2) / 2

    def _layout_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Layout Profile")
        inner = ttk.Notebook(tab)
        inner.pack(fill="both", expand=True)
        self.profile_forms = []
        for name, fields in PROFILE_FIELDS.items():
            f = ttk.Frame(inner, padding=8)
            inner.add(f, text=name)
            if isinstance(fields, dict):         # sections, one above the other
                for title, section in fields.items():
                    box = ttk.LabelFrame(f, text=title, padding=6)
                    box.pack(fill="x", pady=(0, 6))
                    self.profile_forms.append(Form(box, section, columns=1))
                    if title == "Page Margins":
                        margins = box
            else:
                self.profile_forms.append(Form(f, fields, columns=2, by_column=True))
                if name == "Type":
                    typetab, ntype = f, len(fields)
        for form in self.profile_forms:
            form.points_start = {("page", "opener_drop"): self._auto_drop}
            form.points_start.update({("page", "margins", side): (
                lambda side=side: self.calculated()[0].margins[side]) for side in self.MARGINS})
        # The suggested leading for the size and font, under the Type fields.
        self.leading_note = tk.StringVar()
        ttk.Label(typetab, textvariable=self.leading_note, wraplength=820, justify="left").grid(
            row=-(-ntype // 2) + 1, column=0, columnspan=4, sticky="w", padx=6, pady=(10, 4))
        # The margins the export would calculate, under the margin fields.
        row = len(PROFILE_FIELDS["Page Layout"]["Page Margins"]) + 1
        self.margin_note = tk.StringVar()
        ttk.Label(margins, textvariable=self.margin_note, wraplength=820, justify="left").grid(
            row=row, column=0, columnspan=4, sticky="w", padx=6, pady=(10, 4))
        ttk.Button(margins, text="Fill in the calculated margins",
                   command=self.fill_margins).grid(row=row + 1, column=0, columnspan=2,
                                                   sticky="w", padx=6)
        watched = [self.pvar(p) for p in (("page", "trim"), ("page", "custom_width"),
                                          ("page", "custom_height"), ("page", "measure"),
                                          ("fonts", "body"), ("leading", "value"),
                                          ("leading", "unit"), ("leading", "feel"),
                                          ("body_size",))]
        for var in watched:
            var.trace_add("write", lambda *_: self._margins_later())
        ttk.Label(tab, text="Changes apply to the next export. Profile > Save profile keeps them "
                            "for the next book in the series.").pack(anchor="w", pady=(6, 0))

    def pvar(self, path):
        """The variable of a profile field, whichever form it is in."""
        for form in self.profile_forms:
            if path in form.vars:
                return form.vars[path][0]
        raise KeyError(path)

    def _form_of(self, path):
        return next(f for f in self.profile_forms if path in f.vars)

    def _margins_later(self):
        """Recalculate the shown margins shortly after a change (not on every keystroke)."""
        if getattr(self, "_margin_job", None):
            self.root.after_cancel(self._margin_job)
        self._margin_job = self.root.after(400, self.update_margins)

    def calculated(self):
        """The margins the export would calculate now: (Geometry, pages, font found)."""
        from .export import calculated_margins
        prof = copy.deepcopy(self.profile)
        for form in self.profile_forms:
            form.save(prof)
        pages = 200
        if self.report and self.report.outline:
            # A rough count from the words, as the export starts from.
            g, _found = calculated_margins(prof)
            words = self.report.outline.words
            pages = int(words * 6.2 / (g.cpl * g.lines)) + 2 * len(self.report.outline.units) + 6
        g, found = calculated_margins(prof, pages)
        return g, pages, found

    def update_margins(self):
        self._margin_job = None
        try:
            g, pages, found = self.calculated()
        except Exception:
            return
        self._update_leading_note(g)
        form = self._form_of(("page", "margins", "top"))
        for side in self.MARGINS:
            lab, text = form.labels[("page", "margins", side)]
            lab.configure(text="%s (calculated %s)" % (text, format_points(g.margins[side])))
        # What the multiple comes to: 30 x 11 pt = 330 pt = 27.5 picas = 4.58 in.
        lab, text = form.labels[("page", "measure")]
        lab.configure(text="%s: %s, %g picas" % (text, format_points(g.measure),
                                                   round(g.measure / 12, 1)))
        from . import fonts
        font = (self.pvar(("fonts", "body")).get() or "").strip() or \
            fonts.book_font()
        basis = ("%s, measured" % font) if found else \
            "%s isn't installed: an average book font" % font
        self.margin_note.set(
            "Calculated margins: top %s, bottom %s, inside %s, outside %s, for "
            "about %d pages (%s). Line length %s, %g picas, %d characters per line at "
            "%g pt. Blank margin fields use "
            "the calculated values, which follow the page count (KDP's inside minimum grows "
            "with it); a value typed in is used as it is."
            % (format_points(g.margins["top"]), format_points(g.margins["bottom"]),
               format_points(g.margins["inside"]), format_points(g.margins["outside"]),
               pages, basis, format_points(g.measure), round(g.measure / 12, 1),
               round(g.cpl),
               _num(self.pvar(("body_size",)).get(), "number") or 11))

    def _update_leading_note(self, g):
        """The suggested leading ranges for the size and font, and the leading the export
        will use."""
        from . import fonts, layout
        from .export import body_size, leading_for
        prof = copy.deepcopy(self.profile)
        for form in self.profile_forms:
            form.save(prof)
        size = body_size(prof)
        font = (prof.get("fonts") or {}).get("body") or fonts.book_font()
        found = fonts.find_font(font)
        xh = fonts.x_height(found) if found else None
        sug, why = layout.leading_suggestions(size, xh, g.cpl, font)
        lead = leading_for(prof, size, xh, g.cpl)
        feel = (prof.get("leading") or {}).get("feel") or "standard"
        used = "as typed" if (prof.get("leading") or {}).get("value") else feel
        self.leading_note.set(
            "Suggested for %g pt%s: tight %g\u2013%g, standard %g\u2013%g, open %g\u2013%g "
            "points%s. The export will use %g on %g (%s)." % (
                size, (" " + font) if font and found else "",
                sug["tight"][0], sug["tight"][1], sug["standard"][0], sug["standard"][1],
                sug["open"][0], sug["open"][1], ("; " + why) if why else "", size, lead, used))

    def fill_margins(self):
        g, _pages, _found = self.calculated()
        for side in self.MARGINS:
            var = self.pvar(("page", "margins", side))
            if not var.get().strip():
                var.set(format_points(g.margins[side]))
        self.status.set("Calculated margins filled in; they are now fixed for this profile "
                        "(clear a field to let it follow the page count again).")
