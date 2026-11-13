"""The Layout Profile tab of the window (moved out of gui.py, 1.1.0): page, type, footnote
and typography forms, the calculated margins and the leading note."""

import copy
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from . import layout
from .export import TRIMS
from .gui_forms import TITLE, Form, _num, format_points

# The leading preview's text (the tool's own words, about the setting it shows).
SAMPLE = [
    "Leading is the space from one line of type to the next. Too little and the lines crowd "
    "each other, so the eye slips to the wrong line on its way back to the left; too much and "
    "the page turns grey and loose, the lines drifting apart like boats that have slipped "
    "their moorings.",
    "Bringhurst's routine settings add two points or so to the type: 10 on 12, 11 on 13. A "
    "font with a large x-height, a long line, or text thick with capitals and accents wants a "
    "little more. Read a few lines at each setting and choose the one that reads most easily.",
]
PREVIEW_WIDTH = 640           # pixels: wider measures are shown reduced

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
        (("typography", "paragraph_indent"), "Paragraph indent (ems of the body size; 1 usual)",
         "number", None),
        (("block_quotes", "indent_first"), "Indent a block quotation's first paragraph",
         "bool", None),
        (("block_quotes", "indent_next"), "Indent a block quotation's later paragraphs",
         "bool", None),
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
        self.leading_button = ttk.Button(typetab, text="Preview the leading",
                                         command=self.preview_leading)
        self.leading_button.grid(row=-(-ntype // 2) + 2, column=0, columnspan=2, sticky="w",
                                 padx=6)
        self.leading_popup = None
        # The margins the export would calculate, under the margin fields.
        row = len(PROFILE_FIELDS["Page Layout"]["Page Margins"]) + 1
        # The margin scheme: proportions for the calculated margins.
        schemes = ttk.Frame(margins)
        schemes.grid(row=row, column=0, columnspan=4, sticky="w", padx=6, pady=(8, 0))
        ttk.Label(schemes, text="Margin proportions (inside : top : outside : bottom)").pack(
            side="left", padx=(0, 6))
        self.scheme_var = tk.StringVar()
        self.scheme_box = ttk.Combobox(schemes, textvariable=self.scheme_var, state="readonly",
                                       width=34)
        self.scheme_box.pack(side="left")
        self.scheme_box.bind("<<ComboboxSelected>>", self._scheme_chosen)
        for text, cmd in (("New...", self.new_scheme), ("Edit...", self.edit_scheme),
                          ("Delete", self.delete_scheme)):
            ttk.Button(schemes, text=text, command=cmd).pack(side="left", padx=(6, 0))
        self.margin_note = tk.StringVar()
        ttk.Label(margins, textvariable=self.margin_note, wraplength=820, justify="left").grid(
            row=row + 1, column=0, columnspan=4, sticky="w", padx=6, pady=(10, 4))
        ttk.Button(margins, text="Fill in the calculated margins",
                   command=self.fill_margins).grid(row=row + 2, column=0, columnspan=2,
                                                   sticky="w", padx=6)
        self._refresh_schemes()
        watched = [self.pvar(p) for p in (("page", "trim"), ("page", "custom_width"),
                                          ("page", "custom_height"), ("page", "measure"),
                                          ("fonts", "body"), ("leading", "value"),
                                          ("leading", "unit"), ("leading", "feel"),
                                          ("body_size",))]
        for var in watched:
            var.trace_add("write", lambda *_: self._margins_later())
        ttk.Label(tab, text="Changes apply to the next export. Profile > Save profile keeps them "
                            "for the next book in the series.").pack(anchor="w", pady=(6, 0))

    # ---- margin schemes ----

    def _schemes(self):
        """[(key, label)]: the presets, then the profile's own schemes."""
        out = [(k, s["name"]) for k, s in layout.MARGIN_SCHEMES.items()]
        for s in self.profile["page"].get("margin_schemes") or []:
            out.append((s["name"], "%s (%s)" % (s["name"], ":".join(
                "%g" % float(s[k]) for k in layout.SCHEME_SIDES))))
        return out

    def _refresh_schemes(self):
        if not hasattr(self, "scheme_box"):
            return
        schemes = self._schemes()
        self.scheme_box["values"] = [label for _k, label in schemes]
        key = self.profile["page"].get("margin_scheme") or layout.DEFAULT_SCHEME
        label = dict(schemes).get(key) or dict(schemes)[layout.DEFAULT_SCHEME]
        self.scheme_var.set(label)

    def _scheme_key(self):
        labels = {label: k for k, label in self._schemes()}
        return labels.get(self.scheme_var.get(), layout.DEFAULT_SCHEME)

    def _scheme_chosen(self, _event=None):
        self.profile["page"]["margin_scheme"] = self._scheme_key()
        self._margins_later()

    def new_scheme(self):
        self._scheme_dialog(None)

    def edit_scheme(self):
        key = self._scheme_key()
        if key in layout.MARGIN_SCHEMES:
            base = layout.MARGIN_SCHEMES[key]
            if base.get("economical"):
                messagebox.showinfo(TITLE, "The economical margins aren't proportions, so they "
                                    "can't be edited. Choose New... for a scheme of your own.",
                                    parent=self.root)
                return
            # A preset is copied, not changed.
            self._scheme_dialog(dict(base, name=base["name"].split(" (")[0] + " (mine)"),
                                new=True)
            return
        own = next(s for s in self.profile["page"]["margin_schemes"] if s["name"] == key)
        self._scheme_dialog(own)

    def delete_scheme(self):
        key = self._scheme_key()
        if key in layout.MARGIN_SCHEMES:
            messagebox.showinfo(TITLE, "The built-in schemes can't be deleted.",
                                parent=self.root)
            return
        page = self.profile["page"]
        page["margin_schemes"] = [s for s in page["margin_schemes"] if s["name"] != key]
        page["margin_scheme"] = layout.DEFAULT_SCHEME
        self._refresh_schemes()
        self._margins_later()

    def save_scheme(self, scheme, old_name=None):
        """Add or replace one of the profile's own schemes and choose it. Returns an error
        message, or None."""
        name = (scheme.get("name") or "").strip()
        if not name:
            return "Give the scheme a name."
        if name in layout.MARGIN_SCHEMES or any(
                label == name for _k, label in self._schemes()[:len(layout.MARGIN_SCHEMES)]):
            return "That name belongs to a built-in scheme. Choose another."
        if not layout.valid_scheme(scheme):
            return "Each proportion must be a number above 0."
        page = self.profile["page"]
        own = [s for s in page.get("margin_schemes") or [] if s["name"] not in (old_name, name)]
        own.append({"name": name, **{k: float(scheme[k]) for k in layout.SCHEME_SIDES}})
        page["margin_schemes"] = own
        page["margin_scheme"] = name
        self._refresh_schemes()
        self._margins_later()
        return None

    def _scheme_dialog(self, scheme, new=False):
        """A small dialog for a scheme's name and four proportions."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Margin scheme")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        body = ttk.Frame(dlg, padding=10)
        body.pack(fill="both")
        ttk.Label(body, text="Proportions of the four margins, e.g. 2, 3, 4, 6 for the "
                             "classical canon. The line length sets the inside and outside "
                             "together; the same unit gives the top and bottom.",
                  wraplength=360, justify="left").grid(row=0, column=0, columnspan=2,
                                                       sticky="w", pady=(0, 8))
        vars_ = {"name": tk.StringVar(value=(scheme or {}).get("name", ""))}
        rows = [("name", "Name")] + [(k, k.capitalize()) for k in layout.SCHEME_SIDES]
        for n, (k, label) in enumerate(rows, 1):
            if k != "name":
                vars_[k] = tk.StringVar(value="%g" % float((scheme or {}).get(k, 1)))
            ttk.Label(body, text=label).grid(row=n, column=0, sticky="w", pady=2)
            ttk.Entry(body, textvariable=vars_[k], width=24 if k == "name" else 8).grid(
                row=n, column=1, sticky="w", pady=2)
        old = None if (scheme is None or new) else scheme["name"]

        def ok():
            data = {k: v.get().strip() for k, v in vars_.items()}
            err = self.save_scheme(data, old)
            if err:
                messagebox.showerror(TITLE, err, parent=dlg)
                return
            dlg.destroy()
        btns = ttk.Frame(body)
        btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="OK", command=ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="left")
        dlg.bind("<Return>", lambda _e: ok())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        self.scheme_dialog = dlg
        return dlg

    # ---- leading preview ----

    def preview_leading(self):
        """A panel laid over the window under the button (not a window of its own, which
        Windows could open behind the main window), showing two paragraphs in the body font
        at the size, leading and line length the forms give. Its buttons try tight, standard
        and open; a click anywhere outside it, or Esc, closes it."""
        self.close_leading_preview()
        panel = tk.Frame(self.root, relief="solid", borderwidth=1)
        frame = ttk.Frame(panel, padding=8)
        frame.pack(fill="both", expand=True)
        self.leading_caption = tk.StringVar()
        ttk.Label(frame, textvariable=self.leading_caption, wraplength=PREVIEW_WIDTH,
                  justify="left").pack(anchor="w")
        self.leading_canvas = tk.Canvas(frame, background="white", highlightthickness=0,
                                        width=PREVIEW_WIDTH + 24, height=200)
        self.leading_canvas.pack(anchor="w", pady=(6, 6))
        btns = ttk.Frame(frame)
        btns.pack(anchor="w")
        for feel in ("tight", "standard", "open"):
            ttk.Button(btns, text=feel.capitalize(),
                       command=lambda f=feel: self._try_feel(f)).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Close", command=self.close_leading_preview).pack(
            side="left", padx=(0, 6))
        ttk.Label(btns, text="Or click anywhere else.", foreground="#555").pack(
            side="left", padx=(8, 0))
        self.leading_popup = panel
        self._draw_leading()
        # Under the button, within the window (above the button if there's no room below).
        root, b = self.root, self.leading_button
        root.update_idletasks()
        w, h = panel.winfo_reqwidth(), panel.winfo_reqheight()
        x = b.winfo_rootx() - root.winfo_rootx()
        y = b.winfo_rooty() - root.winfo_rooty() + b.winfo_height() + 2
        rw, rh = max(root.winfo_width(), w), max(root.winfo_height(), h)
        x = max(0, min(x, rw - w))
        if y + h > rh:
            y = max(0, b.winfo_rooty() - root.winfo_rooty() - h - 2)
        panel.place(x=x, y=y)
        panel.lift()
        if not getattr(self, "_leading_bound", False):
            # Once: every click and Esc in the window come here while the panel is open.
            root.bind_all("<ButtonPress>", self._leading_click, add="+")
            root.bind_all("<Escape>", lambda _e: self.close_leading_preview(), add="+")
            self._leading_bound = True

    def _leading_click(self, event):
        """A click outside the open panel closes it (the click still does its own work)."""
        panel = getattr(self, "leading_popup", None)
        if panel is None:
            return
        w = event.widget
        while w is not None:
            if w is panel:
                return
            w = getattr(w, "master", None)
        self.close_leading_preview()

    def close_leading_preview(self):
        panel, self.leading_popup = getattr(self, "leading_popup", None), None
        if panel is not None:
            try:
                panel.destroy()
            except tk.TclError:
                pass

    def _try_feel(self, feel):
        """Use one of the leading choices (clearing an exact leading) and show it."""
        self.pvar(("leading", "value")).set("")
        self.pvar(("leading", "feel")).set(feel)
        self._draw_leading()

    def leading_sample(self):
        """(font family, size, leading, measure, indent) in points, from the forms."""
        from . import fonts
        from .export import body_size, leading_for
        from .styles import paragraph_indent
        g, _pages, _found = self.calculated()
        prof = copy.deepcopy(self.profile)
        for form in self.profile_forms:
            form.save(prof)
        size = body_size(prof)
        font = (prof.get("fonts") or {}).get("body") or fonts.book_font()
        found = fonts.find_font(font)
        xh = fonts.x_height(found) if found else None
        return (font, size, leading_for(prof, size, xh, g.cpl), g.measure,
                paragraph_indent(prof, size), bool(found))

    def _draw_leading(self):
        c = self.leading_canvas
        c.delete("all")
        font, size, lead, measure, indent, found = self.leading_sample()
        ppp = self.root.winfo_fpixels("1p")            # pixels per point
        scale = min(1.0, PREVIEW_WIDTH / (measure * ppp))
        px = lambda pt: pt * ppp * scale  # noqa: E731
        f = tkfont.Font(root=self.root, family=font, size=-max(1, round(px(size))))
        ascent = f.metrics("ascent")
        x0, y = 12, 12 + ascent
        width = px(measure)
        lines = 0
        for k, para in enumerate(SAMPLE):
            words, line, first = para.split(), "", True
            start = px(indent) if k else 0              # the first paragraph flush left
            for word in words + [None]:
                trial = (line + " " + word).strip() if word else line
                room = width - (start if first else 0)
                if word is not None and f.measure(trial) <= room:
                    line = trial
                    continue
                c.create_text(x0 + (start if first else 0), y - ascent, text=line, font=f,
                              anchor="nw")
                lines += 1
                y += px(lead)
                first, line = False, word or ""
        c.configure(height=int(y - px(lead) + f.metrics("descent") + 14),
                    width=int(width + 24))
        shown = font if found else "%s isn't installed here, so another font stands in" % font
        self.leading_caption.set(
            "%g pt on %g pt leading, %g picas wide: %s%s. Lines are ragged here; the book "
            "justifies them." % (size, lead, round(measure / 12, 1), shown,
                                 "" if scale == 1 else ", shown at %d%%" % round(scale * 100)))
        self.leading_lines = lines

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
