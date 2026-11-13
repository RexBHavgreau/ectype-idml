"""The window (build step 7): files, book details, running heads, layout profile, preflight
and export, in themed Tkinter (ttk).

Everything the user sets lands in two places: the profile (layout, fonts, style map, running
head pattern: shared by a series) and the book settings (files in order, title and copyright
details, short running heads: this book only), saved as a book file (.json). Dropping files
from Explorer works when tkinterdnd2 is installed (it is bundled in the .exe).
"""

import copy
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__, appsettings, updates
from . import profile as profiles
from .book import Book
from .gui_book import BookTabMixin
from .export import TRIMS, ExportError, export
from .outline import KIND_LABELS, KINDS, kind_key
from .stylemap import ROLES

TITLE = "docx-to-idml"     # working name
LOOKS = {"book": "the book style's", "word": "Word's, in book terms"}

# Profile fields: (path in the profile, label, kind, choices). Kinds: bool, text, number
# (blank allowed = automatic), int, choice, int_choice (a choice saved as a number), file (an
# IDML file, with Browse), points (a measure shown as points with its inches, 72 pt (1"),
# with arrows; inches may be typed: 1"; choices: (arrow step in points, unit saved: "pt" or
# "in")), font (a dropdown of installed fonts that can also
# be typed in; its choices name a script, "hebrew" or "greek", to list only fonts that have it).
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
HEAD_FIELDS = [
    (("running_heads", "verso"), "Verso head", "choice",
     ["book_title", "part", "chapter", "author", "custom"]),
    (("running_heads", "verso_custom"), "Verso text (custom)", "text", None),
    (("running_heads", "recto"), "Recto head", "choice", ["chapter_title", "custom"]),
    (("running_heads", "recto_custom"), "Recto text (custom)", "text", None),
    (("running_heads", "suppress_on_openers"), "No heads on chapter openers", "bool", None),
    (("running_heads", "suppress_on_display"), "No heads on display pages", "bool", None),
    (("running_heads", "suppress_on_blanks"), "No heads on blank pages", "bool", None),
    (("running_heads", "script_masters"),
     "Separate masters for heads with Hebrew or Greek the head font lacks", "bool", None),
]
HEAD_CASE_FIELDS = [
    (("running_heads", "style", "case"), "", "radio",
     [("as_typed", "As typed"), ("title", "Title Case"), ("sentence", "Sentence case")]),
]
HEAD_FONT_FIELDS = [
    (("running_heads", "style", "italic"), "Italic", "bool", None),
    (("running_heads", "style", "bold"), "Boldface", "bool", None),
    (("running_heads", "style", "underline"), "Underlined", "bool", None),
    (("running_heads", "style", "caps"), "", "one_of",
     [("all_caps", "All Caps"), ("small_caps", "Small Caps")]),
    (("running_heads", "style", "size"), "Size (pt; blank = 2 pt below the body)", "number",
     None),
    (("running_heads", "style", "tracking"), "Letter-spacing (thousandths of an em)", "int",
     None),
    (("running_heads", "style", "font"), "Font (blank = the body font)", "font", None),
]
def _get(d, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _set(d, path, value):
    for k in path[:-1]:
        d = d.setdefault(k, {})
    d[path[-1]] = value


def parse_points(text):
    """Points from what was typed: "72", "72 pt", "72 pt (1\")", or inches: "1\"", "1 in".
    None when blank or not a measure."""
    text = (text or "").strip().lower().replace("\u2033", '"')
    m = re.match(r'^(\d+(?:\.\d*)?|\.\d+)\s*(pt|p|"|in|inch|inches)?', text)
    if not m:
        return None
    value = float(m.group(1))
    return value * 72 if m.group(2) in ('"', "in", "inch", "inches") else value


def format_points(value):
    """72 -> '72 pt (1")'; 84 -> '84 pt (1.17")'."""
    if value is None:
        return ""
    inches = ("%.2f" % (value / 72)).rstrip("0").rstrip(".")
    return '%g pt (%s")' % (round(value * 2) / 2, inches)


def _num(text, kind):
    text = (text or "").strip()
    if not text:
        return None
    try:
        v = float(text)
    except ValueError:
        return None
    return int(v) if kind == "int" else v


class Form:
    """Widgets for a list of fields, bound to a dict (read with load(), written with save())."""

    def __init__(self, parent, fields, columns=1, by_column=False):
        """by_column: fill each column top to bottom (fields listed in reading order down the
        first column, then the second), instead of row by row."""
        self.fields, self.vars, self.font_boxes, self.labels = fields, {}, [], {}
        self.points_start = {}      # path -> function: a blank points field's arrows start there
        for n, (path, label, kind, choices) in enumerate(fields):
            rows = -(-len(fields) // columns)
            if by_column:
                row, col = n % rows, (n // rows) * 2
            else:
                row, col = n // columns, (n % columns) * 2
            if kind == "bool":
                var = tk.BooleanVar()
                ttk.Checkbutton(parent, text=label, variable=var).grid(
                    row=row, column=col, columnspan=2, sticky="w", padx=6, pady=2)
            elif kind in ("radio", "one_of"):
                # radio: one of the choices [(value, label)]; one_of: check boxes of which at
                # most one is on (the value is None when none is).
                var = tk.StringVar()
                box = ttk.Frame(parent)
                box.grid(row=row, column=col, columnspan=2, sticky="w", padx=6, pady=2)
                if label:
                    ttk.Label(box, text=label).pack(side="left", padx=(0, 6))
                for value, text in choices:
                    if kind == "radio":
                        ttk.Radiobutton(box, text=text, value=value, variable=var).pack(
                            side="left", padx=(0, 8))
                        continue
                    check = tk.BooleanVar()

                    def toggled(var=var, check=check, value=value):
                        var.set(value if check.get() else "")
                    ttk.Checkbutton(box, text=text, variable=check, command=toggled).pack(
                        side="left", padx=(0, 8))

                    def follow(*_a, var=var, check=check, value=value):
                        check.set(var.get() == value)
                    var.trace_add("write", follow)
            else:
                var = tk.StringVar()
                lab = ttk.Label(parent, text=label)
                lab.grid(row=row, column=col, sticky="w", padx=6, pady=2)
                self.labels[path] = (lab, label)
                if kind == "size":
                    w = ttk.Combobox(parent, textvariable=var, values=choices, width=24)
                elif kind in ("choice", "int_choice"):
                    w = ttk.Combobox(parent, textvariable=var, values=choices, state="readonly",
                                     width=24)
                elif kind == "file":
                    w = ttk.Frame(parent)
                    ttk.Entry(w, textvariable=var, width=14).pack(side="left", fill="x",
                                                                   expand=True)

                    def browse(var=var):
                        path = filedialog.askopenfilename(
                            title="IDML file whose styles the book should use",
                            filetypes=[("InDesign Markup", "*.idml")])
                        if path:
                            var.set(path)
                    ttk.Button(w, text="Browse...", command=browse).pack(side="left", padx=2)
                elif kind == "points":
                    w = ttk.Spinbox(parent, textvariable=var, width=24)

                    def step(direction, var=var, path=path, size=choices[0]):
                        value = parse_points(var.get())
                        if value is None:
                            start = self.points_start.get(path)
                            value = start() if start else 72
                        else:
                            value = max(0, value + direction * size)
                        var.set(format_points(value))
                        return "break"

                    def tidy(_e=None, var=var):
                        if var.get().strip():
                            var.set(format_points(parse_points(var.get())))
                    w.bind("<<Increment>>", lambda e, s=step: s(1))
                    w.bind("<<Decrement>>", lambda e, s=step: s(-1))
                    w.bind("<FocusOut>", tidy)
                    w.bind("<Return>", tidy)
                elif kind == "font":
                    w = ttk.Combobox(parent, textvariable=var, width=24, height=20,
                                     values=["(reading the installed fonts...)"])
                    self.font_boxes.append((w, choices))
                else:
                    w = ttk.Entry(parent, textvariable=var, width=26)
                w.grid(row=row, column=col + 1, sticky="we", padx=6, pady=2)
            self.vars[path] = (var, kind)

    def _unit(self, path):
        """The unit a points field is saved in ("pt" or "in")."""
        for p, _label, kind, choices in self.fields:
            if p == path and kind == "points":
                return (choices or (6, "pt"))[1]
        return "pt"

    def set_fonts(self, lists):
        """Fill the font dropdowns: lists = {None: all families, "hebrew": [...], ...}."""
        for box, script in self.font_boxes:
            box["values"] = lists.get(script) or lists.get(None) or []

    def load(self, data):
        for path, (var, kind) in self.vars.items():
            v = _get(data, path)
            if kind == "bool":
                var.set(bool(v))
            elif kind == "points":
                scale = 72 if self._unit(path) == "in" else 1
                var.set(format_points(None if v is None else v * scale))
            else:
                var.set("" if v is None else (("%g" % v) if isinstance(v, float) else str(v)))

    def save(self, data):
        for path, (var, kind) in self.vars.items():
            if kind == "bool":
                value = bool(var.get())
            elif kind == "size":
                value = _num(var.get(), "number") or 11
            elif kind == "int_choice":
                value = _num(var.get(), "int") or 0
            elif kind == "one_of":
                value = var.get() or None
            elif kind == "points":
                value = parse_points(var.get())
                if value is not None and self._unit(path) == "in":
                    value = round(value / 72, 4)
            elif kind in ("number", "int"):
                value = _num(var.get(), kind)
                if value is None and kind == "int":
                    value = 0
            else:
                value = var.get().strip() or None
                if kind == "font" and value and value.startswith("("):
                    value = None          # the placeholder shown while fonts are read
                if kind == "choice" and value is None:
                    continue
            _set(data, path, value)


OWN, LEAVE_OUT, NONE = "(its own name)", "(leave out)", "(no character style)"


class StyleMappingPanel:
    """The Style Map tab: all the manuscript's styles in one view, with the IDML style each
    becomes (as InDesign's Place > Style Mapping): the automatic mapping first, the user's
    choices over it, saved in the profile's style map. The manuscript's own contents (Word's
    TOC styles) isn't mapped: a new contents replaces it."""

    def __init__(self, app, parent):
        self.app = app
        self.rows, self.char_rows = [], []
        ttk.Label(parent, wraplength=960, justify="left", text=(
            "The styles found in the manuscript and the IDML style each becomes, as the tool "
            "mapped them. Change any of them: choose a book style, a style from your "
            "template, or \u201c%s\u201d to keep the Word style under its own name. Choosing "
            "a book style sets the role to match. Rows marked \u26a0 were guessed; check "
            "them. The mapping is kept in the profile (Profile > Save profile keeps it for "
            "the series)." % OWN)).pack(fill="x", pady=(0, 6))
        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True)
        canvas = self.canvas = tk.Canvas(outer, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.grid = ttk.Frame(canvas)
        self.grid.bind("<Configure>",
                       lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.grid, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        buttons = ttk.Frame(parent, padding=(0, 8, 0, 0))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Back to the automatic mapping",
                   command=self.reset).pack(side="left")
        ttk.Button(buttons, text="Apply the mapping", command=self.apply).pack(side="right")
        self.refresh()

    def _choices(self):
        from .export import BOOK_STYLE_ROLES, CHAR_STYLES
        tpl_para, tpl_char = [], []
        path = self.app.profile.get("styles_template")
        if path:
            try:
                from .template import read_template
                tp, tc, _notes = read_template(path)
                tpl_para, tpl_char = sorted(tp), sorted(tc)
            except Exception:
                pass
        para = [OWN] + list(BOOK_STYLE_ROLES) + \
            [n for n in tpl_para if n not in BOOK_STYLE_ROLES] + [LEAVE_OUT]
        char = [OWN, NONE] + [n for n in CHAR_STYLES if n != "No Break"] + \
            [n for n in tpl_char if n not in CHAR_STYLES]
        return para, char

    def refresh(self):
        """The rows for the current preflight report (or how to get one)."""
        from .export import BOOK_STYLE_ROLES
        self.roles = BOOK_STYLE_ROLES
        grid, app, rep = self.grid, self.app, self.app.report
        for w in grid.winfo_children():
            w.destroy()
        self.rows, self.char_rows = [], []
        if rep is None:
            ttk.Label(grid, text="Add the manuscript's files, then read them to list their "
                                 "styles.").grid(row=0, column=0, sticky="w", pady=4)
            ttk.Button(grid, text="Read the manuscript", command=app.run_preflight).grid(
                row=1, column=0, sticky="w")
            return
        para_choices, char_choices = self._choices()
        heads = ("", "Word style", "Paragraphs", "IDML style", "Role", "Look", "Mapped by")
        for c, h in enumerate(heads):
            ttk.Label(grid, text=h, font=("TkDefaultFont", 9, "bold")).grid(
                row=0, column=c, sticky="w", padx=4, pady=(0, 4))
        r = 1
        tocs = []
        for s in rep.paragraph_styles:
            if s.role in ("toc", "toc_title"):
                tocs.append(s.word)          # replaced by a new contents, not mapped
                continue
            idml = s.word if s.idml == s.word and s.idml not in BOOK_STYLE_ROLES else s.idml
            shown = OWN if idml == s.word and s.word not in BOOK_STYLE_ROLES else \
                (idml or LEAVE_OUT)
            look = app._look(s.word, s.idml, s.role)
            iv, rv, lv = tk.StringVar(value=shown), tk.StringVar(value=s.role), \
                tk.StringVar(value=LOOKS[look])
            ttk.Label(grid, text="\u26a0" if s.warning else "").grid(row=r, column=0)
            ttk.Label(grid, text=s.word).grid(row=r, column=1, sticky="w", padx=4)
            ttk.Label(grid, text=str(s.count)).grid(row=r, column=2, sticky="e", padx=4)
            box = ttk.Combobox(grid, textvariable=iv, values=para_choices, width=24)
            box.grid(row=r, column=3, padx=4, pady=1)
            ttk.Combobox(grid, textvariable=rv, values=[x for x in ROLES
                                                        if x not in ("toc", "toc_title")],
                         state="readonly", width=11).grid(row=r, column=4, padx=4)
            ttk.Combobox(grid, textvariable=lv, values=list(LOOKS.values()), state="readonly",
                         width=20).grid(row=r, column=5, padx=4)
            ttk.Label(grid, text=s.source).grid(row=r, column=6, sticky="w", padx=4)
            box.bind("<<ComboboxSelected>>", lambda e, iv=iv, rv=rv: self._role_for(iv, rv))
            self.rows.append((s.word, iv, rv, lv, (shown, s.role, LOOKS[look])))
            r += 1
        if tocs:
            ttk.Label(grid, wraplength=700, justify="left", text=(
                "The manuscript's own contents (%s) is replaced by a new contents, so its "
                "styles aren't mapped." % ", ".join(tocs))).grid(
                row=r, column=1, columnspan=6, sticky="w", padx=4, pady=(6, 0))
            r += 1
        chars = [c for c in rep.character_styles if c.role != "skip"]
        if chars:
            ttk.Label(grid, text="Character styles", font=("TkDefaultFont", 9, "bold")).grid(
                row=r, column=1, sticky="w", padx=4, pady=(12, 4))
            r += 1
            for c in chars:
                shown = OWN if c.idml == c.word else (c.idml or NONE)
                cv = tk.StringVar(value=shown)
                ttk.Label(grid, text="\u26a0" if c.warning else "").grid(row=r, column=0)
                ttk.Label(grid, text=c.word).grid(row=r, column=1, sticky="w", padx=4)
                ttk.Label(grid, text=str(c.count)).grid(row=r, column=2, sticky="e", padx=4)
                ttk.Combobox(grid, textvariable=cv, values=char_choices, width=24).grid(
                    row=r, column=3, padx=4, pady=1)
                ttk.Label(grid, text=c.source).grid(row=r, column=6, sticky="w", padx=4)
                self.char_rows.append((c.word, cv, shown))
                r += 1
        self.canvas.yview_moveto(0)

    def _role_for(self, iv, rv):
        """A book style sets its role (Heading B: a heading at level 2...)."""
        if iv.get() in self.roles:
            rv.set(self.roles[iv.get()][0])

    def save(self):
        """Put the rows changed from the automatic mapping into the profile (earlier choices
        are kept). Returns how many changed."""
        sm = self.app.profile.setdefault("style_map", {})
        para, char = sm.setdefault("paragraph", {}), sm.setdefault("character", {})
        formats = self.app.book.settings.setdefault("format_map", {})
        changed = 0
        for word, iv, rv, lv, initial in self.rows:
            now = (iv.get().strip(), rv.get(), lv.get())
            if now == initial:
                continue
            idml = word if now[0] == OWN else (None if now[0] == LEAVE_OUT else now[0])
            role = "skip" if now[0] == LEAVE_OUT else now[1]
            level = self.roles.get(now[0], (None, 0))[1] if role == "heading" else 0
            if role == "heading" and not level:
                level = 1
            look = [k for k, v in LOOKS.items() if v == now[2]] or ["book"]
            entry = {"idml": idml, "role": role, "level": level, "look": look[0]}
            if word.startswith("["):
                # A heading group found by formatting belongs to this manuscript: the book.
                formats[word] = entry
                self.app.dirty = True
            else:
                para[word] = entry
            changed += 1
        for word, cv, initial in self.char_rows:
            now = cv.get().strip()
            if now == initial:
                continue
            char[word] = word if now == OWN else (None if now == NONE else now)
            changed += 1
        return changed

    def apply(self):
        """Save the changes and read the manuscript again with them (the outline depends on
        the mapping)."""
        changed = self.save()
        if changed:
            self.app.mapping_changed(changed)
        else:
            self.app.status.set("No changes to the mapping.")

    def reset(self):
        """Forget the choices made for these styles; the automatic mapping comes back."""
        sm = self.app.profile.setdefault("style_map", {})
        from .stylemap import norm
        names = {norm(w) for w, *_ in self.rows} | {norm(w) for w, *_ in self.char_rows}
        for kind in ("paragraph", "character"):
            m = sm.get(kind) or {}
            for k in [k for k in m if norm(k) in names]:
                del m[k]
        formats = self.app.book.settings.get("format_map") or {}
        for k in [k for k in formats if norm(k) in names]:
            del formats[k]
            self.app.dirty = True
        self.rows, self.char_rows = [], []      # nothing left to save over the reset
        self.app.mapping_changed(0)


class App(BookTabMixin):
    def __init__(self, root, dnd=False):
        self.root = root
        self.settings = appsettings.load()
        self.book = Book()
        self.book_path = None
        self.dirty = False
        self.busy = False
        self.report = None           # last preflight report
        self.units = []              # (title, kind) from the last outline
        self.results = queue.Queue() # callbacks from worker threads
        self.font_lists = None       # installed fonts, once read
        self.profile_name = self.settings.get("profile")
        try:
            self.profile = profiles.load(self.profile_name)
        except profiles.ProfileError:
            self.profile_name, self.profile = None, profiles.default_profile()
        root.title("%s %s" % (TITLE, __version__))
        root.minsize(760, 520)
        self._menus()
        self._build(dnd)
        self._load_profile_into_forms()
        self._load_book_into_forms()
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self._poll()
        self._read_fonts()

    # ---- layout of the window ----

    def _menus(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=False)
        f.add_command(label="New book", command=self.new_book)
        f.add_command(label="Open book...", command=self.open_book)
        f.add_command(label="Save book", command=self.save_book)
        f.add_command(label="Save book as...", command=lambda: self.save_book(True))
        f.add_separator()
        f.add_command(label="Quit", command=self.quit)
        m.add_cascade(label="File", menu=f)
        p = tk.Menu(m, tearoff=False)
        p.add_command(label="New profile...", command=self.new_profile)
        p.add_command(label="Save profile", command=self.save_profile)
        p.add_command(label="Save profile as...", command=lambda: self.save_profile(True))
        p.add_command(label="Import profile...", command=self.import_profile)
        p.add_command(label="Export profile...", command=self.export_profile)
        m.add_cascade(label="Profile", menu=p)
        h = tk.Menu(m, tearoff=False)
        h.add_command(label="Check for updates", command=lambda: self.check_updates(manual=True))
        self.auto_check = tk.BooleanVar(value=self.settings.get("check_updates", True))
        h.add_checkbutton(label="Check for updates at startup", variable=self.auto_check,
                          command=self._auto_check_changed)
        h.add_command(label="About", command=self.about)
        m.add_cascade(label="Help", menu=h)
        self.root.config(menu=m)

    def _build(self, dnd):
        top = ttk.Frame(self.root, padding=(8, 8, 8, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Profile:").pack(side="left")
        self.profile_var = tk.StringVar()
        self.profile_box = ttk.Combobox(top, textvariable=self.profile_var, state="readonly",
                                        width=30)
        self.profile_box.pack(side="left", padx=6)
        self.profile_box.bind("<<ComboboxSelected>>", self._profile_chosen)
        self._refresh_profile_list()

        # The status line and the export row are packed before the tabs, at the bottom, so a
        # short window shrinks the tabs, not them.
        self.status = tk.StringVar(value="Add the manuscript's .docx files to begin.")
        ttk.Label(self.root, textvariable=self.status, padding=(10, 0, 10, 6)).pack(
            side="bottom", fill="x")
        bottom = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        bottom.pack(side="bottom", fill="x")
        ttk.Label(bottom, text="Save the export in:").pack(side="left")
        self.out_var = tk.StringVar(value=self.settings.get("out_dir") or str(Path.home()))
        ttk.Entry(bottom, textvariable=self.out_var, width=50).pack(side="left", padx=6,
                                                                    fill="x", expand=True)
        ttk.Button(bottom, text="Browse...", command=self._choose_out).pack(side="left")
        self.export_btn = ttk.Button(bottom, text="Export IDML", command=self.export)
        self.export_btn.pack(side="left", padx=(12, 0))
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=120)
        self.progress.pack(side="left", padx=6)
        # Shown in the export row after an export (packed then, so it never lacks room).
        self.open_btn = ttk.Button(bottom, text="Open the export folder",
                                   command=self.open_export)

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self._files_tab(dnd)
        self._book_tab()
        self._heads_tab()
        self._layout_tab()
        self._styles_tab()
        self._report_tab()
        self._fit_window()

    def _fit_window(self):
        """Open large enough for the tallest tab and the export row (Windows scales text,
        so a fixed size cut off the bottom), within the screen."""
        self.root.update_idletasks()
        w = max(1040, self.root.winfo_reqwidth())
        h = max(720, self.root.winfo_reqheight())
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = min(w, sw - 40), min(h, sh - 80)
        self.root.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 3)))

    def _files_tab(self, dnd):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Files")
        cols = ("file", "heading")
        self.tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("file", text="File (in book order)")
        self.tree.heading("heading", text="First heading")
        self.tree.column("file", width=330)
        self.tree.column("heading", width=420)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(tab, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        btns = ttk.Frame(tab)
        btns.grid(row=0, column=2, sticky="n", padx=(8, 0))
        for text, cmd in (("Add files...", self.add_files), ("Add folder...", self.add_folder),
                          ("Remove", self.remove_files), (None, None),
                          ("Move up", lambda: self.move(-1)), ("Move down", lambda: self.move(1)),
                          ("Move to top", lambda: self.move("top")),
                          ("Move to bottom", lambda: self.move("bottom")), (None, None),
                          ("Sort by filename", self.sort_files),
                          ("Run preflight", self.run_preflight)):
            if text is None:
                ttk.Separator(btns).pack(fill="x", pady=6)
            else:
                ttk.Button(btns, text=text, command=cmd, width=18).pack(pady=2)
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)
        hint = "Drop .docx files or folders here, or use Add." if dnd else \
            "Use Add files or Add folder. The order here is the book's order."
        ttk.Label(tab, text=hint).grid(row=1, column=0, sticky="w", pady=(6, 0))
        if dnd:
            try:
                from tkinterdnd2 import DND_FILES
                self.tree.drop_target_register(DND_FILES)
                self.tree.dnd_bind("<<Drop>>", self._dropped)
            except Exception:
                pass

    def _heads_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Running Heads")
        form = ttk.Frame(tab)
        form.pack(fill="x")
        self.heads_form = Form(form, HEAD_FIELDS, columns=2)
        box = ttk.LabelFrame(tab, text="Running Head Style", padding=6)
        box.pack(fill="x", pady=(8, 0))
        case = ttk.LabelFrame(box, text="Case", padding=4)
        case.pack(fill="x")
        self.head_case_form = Form(case, HEAD_CASE_FIELDS)
        ttk.Label(case, foreground="#555", text=(
            "Title and sentence case change the letters of every head (sentence case keeps the "
            "names the manuscript capitalizes); the capitals below set the type.")).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=6)
        font = ttk.LabelFrame(box, text="Font", padding=4)
        font.pack(fill="x", pady=(6, 0))
        self.head_style_form = Form(font, HEAD_FONT_FIELDS, columns=2)
        ttk.Label(tab, text="Units of the book (double-click a running head to give a short "
                            "title, or a kind to change what the unit is; \"too long\" means "
                            "the head won't fit the page):").pack(anchor="w", pady=(10, 2))
        self.heads = ttk.Treeview(tab, columns=("unit", "kind", "head", "note"), show="headings")
        for c, t, w in (("unit", "Title in the manuscript", 330), ("kind", "Kind (double-click)", 160),
                        ("head", "Running head", 280), ("note", "", 80)):
            self.heads.heading(c, text=t)
            self.heads.column(c, width=w)
        self.heads.pack(fill="both", expand=True)
        self.heads.bind("<Double-1>", self._edit_head)

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

    def _styles_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Style Map")
        self.styles_tab = tab
        self.mapping = StyleMappingPanel(self, tab)

    def _report_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Report")
        self.text = tk.Text(tab, wrap="word", height=10)
        sb = ttk.Scrollbar(tab, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.last_export = None

    # ---- profile ----

    def _refresh_profile_list(self):
        names = profiles.list_profiles()
        self.profile_box["values"] = ["(defaults)"] + names
        self.profile_var.set(self.profile_name or "(defaults)")

    def _load_profile_into_forms(self):
        for form in self.profile_forms:
            form.load(self.profile)
        self.heads_form.load(self.profile)
        self.head_case_form.load(self.profile)
        self.head_style_form.load(self.profile)
        self._margins_later()
        self.notice_list.delete(0, "end")
        chosen = set((self.book.settings.get("front") or {}).get("notices") or [])
        for n, item in enumerate(self.profile.get("notices") or []):
            self.notice_list.insert("end", item.get("name", ""))
            if item.get("name") in chosen:
                self.notice_list.selection_set(n)

    def _read_fonts(self):
        """List the installed fonts in the background (a few seconds with many fonts), then
        fill the font dropdowns."""
        def work():
            from . import fonts
            return {None: fonts.families(), "hebrew": fonts.families("hebrew"),
                    "greek": fonts.families("greek")}

        def target():
            try:
                lists = work()
            except Exception:
                lists = {}
            self.results.put(lambda: self._fonts_read(lists))
        threading.Thread(target=target, daemon=True).start()

    def _fonts_read(self, lists):
        self.font_lists = lists
        for form in self.profile_forms + [self.head_style_form]:
            form.set_fonts(lists)

    MARGINS = ("top", "bottom", "inside", "outside")

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

    def _forms_to_profile(self):
        for form in self.profile_forms:
            form.save(self.profile)
        if getattr(self, "mapping", None) is not None:
            self.mapping.save()          # mapping changes not yet applied
        self.heads_form.save(self.profile)
        self.head_case_form.save(self.profile)
        self.head_style_form.save(self.profile)

    def _profile_chosen(self, _event=None):
        name = self.profile_var.get()
        name = None if name == "(defaults)" else name
        try:
            self.profile = profiles.load(name)
        except profiles.ProfileError as e:
            messagebox.showerror(TITLE, str(e))
            return
        self.profile_name = name
        self.settings["profile"] = name
        self._load_profile_into_forms()
        self.book.profile = name

    def new_profile(self):
        name = simpledialog.askstring(TITLE, "Name of the new profile (it starts from the "
                                             "settings shown now):", parent=self.root)
        if name:
            self._forms_to_profile()
            self.profile = copy.deepcopy(self.profile)
            self.profile["name"] = name
            self.profile_name = name
            profiles.save(self.profile)
            self._refresh_profile_list()
            self.status.set('Profile "%s" saved.' % name)

    def save_profile(self, as_new=False):
        if as_new or not self.profile_name:
            return self.new_profile()
        self._forms_to_profile()
        self.profile["name"] = self.profile_name
        profiles.save(self.profile)
        self.status.set('Profile "%s" saved.' % self.profile_name)

    def import_profile(self):
        path = filedialog.askopenfilename(title="Import a profile",
                                          filetypes=[("Profile", "*.json")])
        if path:
            try:
                name = profiles.import_profile(path)
            except profiles.ProfileError as e:
                messagebox.showerror(TITLE, str(e))
                return
            self._refresh_profile_list()
            self.profile_var.set(name)
            self._profile_chosen()

    def export_profile(self):
        path = filedialog.asksaveasfilename(title="Export the profile", defaultextension=".json",
                                            initialfile=(self.profile_name or "Profile") + ".json",
                                            filetypes=[("Profile", "*.json")])
        if path:
            self._forms_to_profile()
            profiles.save_file(self.profile, path)
            self.status.set("Profile exported to %s." % path)

    # ---- book ----

    def _refresh_files(self):
        self.tree.delete(*self.tree.get_children())
        headings = (self.report.outline.first_heading if self.report and self.report.outline
                    else {})
        for f in self.book.files:
            name = os.path.basename(f)
            self.tree.insert("", "end", iid=f, values=(name, headings.get(name, "")))
        n = len(self.book.files)
        self.status.set("%d file%s." % (n, "" if n == 1 else "s") if n else
                        "Add the manuscript's .docx files to begin.")

    def _changed(self):
        self.dirty = True
        self.report = None

    def _add(self, paths, at=None):
        files, skipped = self.book.add(paths, at)
        if skipped:
            messagebox.showinfo(TITLE, "Left out:\n\n" + "\n".join(
                "%s: %s" % (os.path.basename(p), why) for p, why in skipped))
        if files:
            self._changed()
            self._refresh_files()

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Add Word files",
                                            filetypes=[("Word documents", "*.docx")])
        if paths:
            self._add(list(paths))

    def add_folder(self):
        path = filedialog.askdirectory(title="Add all the .docx files in a folder")
        if path:
            self._add([path])

    def _dropped(self, event):
        paths = self.root.tk.splitlist(event.data)
        target = self.tree.identify_row(event.y) if hasattr(event, "y") else ""
        at = self.book.files.index(target) if target in self.book.files else None
        self._add(list(paths), at)

    def remove_files(self):
        for f in self.tree.selection():
            self.book.remove(f)
        self._changed()
        self._refresh_files()

    def move(self, step):
        sel = list(self.tree.selection())
        if not sel:
            return
        idx = [self.book.files.index(f) for f in sel]
        if step == "top":
            order = sel + [f for f in self.book.files if f not in sel]
        elif step == "bottom":
            order = [f for f in self.book.files if f not in sel] + sel
        else:
            order = list(self.book.files)
            for i in (sorted(idx) if step < 0 else sorted(idx, reverse=True)):
                j = i + step
                if 0 <= j < len(order) and order[j] not in sel:
                    order[i], order[j] = order[j], order[i]
        self.book.files = order
        self._changed()
        self._refresh_files()
        self.tree.selection_set(sel)

    def sort_files(self):
        self.book.sort_by_filename()
        self._changed()
        self._refresh_files()

    def new_book(self):
        if not self._maybe_save():
            return
        self.book, self.book_path, self.dirty, self.report = Book(), None, False, None
        self._load_book_into_forms()

    def open_book(self, path=None):
        if not self._maybe_save():
            return
        path = path or filedialog.askopenfilename(title="Open a book",
                                                  filetypes=[("Book", "*.json")])
        if not path:
            return
        try:
            self.book = Book.load(path)
        except (OSError, ValueError) as e:
            messagebox.showerror(TITLE, "Can't open %s: %s" % (path, e))
            return
        self.book_path, self.dirty, self.report = path, False, None
        if self.book.profile:
            self.profile_var.set(self.book.profile)
            self._profile_chosen()
        else:
            self._load_profile_into_forms()
        self._load_book_into_forms()
        self.settings["last_book"] = path

    def save_book(self, as_new=False):
        self._forms_to_book()
        path = self.book_path
        if as_new or not path:
            path = filedialog.asksaveasfilename(title="Save the book", defaultextension=".json",
                                                initialfile="Book.json",
                                                filetypes=[("Book", "*.json")])
            if not path:
                return False
        self.book.save(path)
        self.book_path, self.dirty = path, False
        self.settings["last_book"] = path
        self.status.set("Book saved: %s" % path)
        return True

    def _maybe_save(self):
        if not self.dirty or not self.book.files:
            return True
        answer = messagebox.askyesnocancel(TITLE, "Save the changes to this book first?")
        if answer is None:
            return False
        return self.save_book() if answer else True

    # ---- running heads ----

    def _refresh_heads(self):
        self.heads.delete(*self.heads.get_children())
        short = self.book.settings.get("short_titles") or {}
        kinds = self.book.settings.get("unit_kinds") or {}
        limit = self._head_limit()
        for title, detected in self.units:
            if self.heads.exists(title):
                continue              # two units with one title share a row
            kind = kinds.get(title, detected)
            head = short.get(title) or title
            note = "too long" if len(head) > limit and kind in ("chapter", "part", "front",
                                                                 "back") else ""
            if kind in ("display", "endorsements"):
                head, note = "(no running heads)", ""
            label = KIND_LABELS.get(kind, kind) + (" (set by you)" if title in kinds else "")
            self.heads.insert("", "end", iid=title, values=(title, label, head, note))

    def _head_limit(self):
        """Characters that fit a running head: 80% of the measure at the head's size."""
        from . import layout
        page = self.profile["page"]
        w, h = TRIMS.get(page.get("trim"), TRIMS["6x9"]) if page.get("trim") != "custom" else \
            (page.get("custom_width") or 6, page.get("custom_height") or 9)
        g = layout.geometry(w * 72, h * 72, 11, 14, 0.42, 200, page.get("margins"))
        return int(g.measure * 0.8 / (9 * 0.42 * 1.1))

    def _edit_head(self, event):
        item = self.heads.identify_row(event.y)
        if not item:
            return
        if self.heads.identify_column(event.x) == "#2":
            return self._edit_kind(item)
        current = self.heads.set(item, "head")
        new = simpledialog.askstring(TITLE, "Running head for “%s” (blank = the full "
                                            "title):" % item, initialvalue=current,
                                     parent=self.root)
        if new is None:
            return
        short = self.book.settings.setdefault("short_titles", {})
        if new.strip() and new.strip() != item:
            short[item] = new.strip()
        else:
            short.pop(item, None)
        self.dirty = True
        self._refresh_heads()

    def _edit_kind(self, title):
        """Choose what a unit is (chapter, front matter, endorsements...), over what was
        detected; saved with the book."""
        detected = dict(self.units).get(title, "chapter")
        kinds = self.book.settings.setdefault("unit_kinds", {})
        dlg = tk.Toplevel(self.root)
        dlg.title("What is \u201c%s\u201d?" % title[:40])
        dlg.transient(self.root)
        labels = [KIND_LABELS[k] for k in KINDS]
        var = tk.StringVar(value=KIND_LABELS[kinds.get(title, detected)])
        ttk.Label(dlg, text="\u201c%s\u201d is:" % title[:60]).grid(row=0, column=0, padx=8,
                                                                    pady=6, sticky="w")
        ttk.Combobox(dlg, textvariable=var, values=labels, state="readonly").grid(
            row=0, column=1, padx=8)
        ttk.Label(dlg, text="Display pages and endorsements have no folio or running heads; "
                            "endorsements go before the half-title.", wraplength=380).grid(
            row=1, column=0, columnspan=2, padx=8, sticky="w")

        def ok():
            key = [k for k in KINDS if KIND_LABELS[k] == var.get()][0]
            self.set_kind(title, key)
            dlg.destroy()
        ttk.Button(dlg, text="OK", command=ok).grid(row=2, column=1, sticky="e", padx=8, pady=8)

    def set_kind(self, title, key):
        detected = dict(self.units).get(title, "chapter")
        kinds = self.book.settings.setdefault("unit_kinds", {})
        if key == detected:
            kinds.pop(title, None)
        else:
            kinds[title] = key
        self.dirty = True
        self._refresh_heads()

    # ---- style map ----

    def _refresh_styles(self):
        self.mapping.refresh()

    def _look(self, word, idml, role):
        """As the export decides: the style map's choice, else Word's look only for a style
        kept under its own name with no book counterpart."""
        from .stylemap import norm
        sm = (self.profile.get("style_map") or {}).get("paragraph") or {}
        for k, v in sm.items():
            if norm(k) == norm(word) and isinstance(v, dict) and v.get("look") in LOOKS:
                return v["look"]
        return "word" if role == "body" and idml == word else "book"

    # ---- preflight and export ----

    def _run(self, work, done, what):
        """Run work() in a thread; done(result) back in the window."""
        if self.busy:
            return
        self.busy = True
        self.export_btn.state(["disabled"])
        self.progress.start(12)
        self.status.set(what)

        def target():
            try:
                result = (True, work())
            except Exception as e:      # shown to the user, with details in the report tab
                result = (False, e)
            self.results.put((lambda: self._finish(result, done)))
        threading.Thread(target=target, daemon=True).start()

    def _poll(self):
        """Run what worker threads hand back (Tk may only be touched from this thread)."""
        try:
            while True:
                self.results.get_nowait()()
        except queue.Empty:
            pass
        self._poll_id = self.root.after(50, self._poll)

    def _finish(self, result, done):
        self.busy = False
        self.export_btn.state(["!disabled"])
        self.progress.stop()
        ok, value = result
        if ok:
            done(value)
        else:
            msg = str(value) if isinstance(value, (ExportError, profiles.ProfileError)) else \
                "Something went wrong: %s" % value
            self.status.set(msg)
            self._show(msg + ("" if isinstance(value, ExportError) else "\n\n" + "".join(
                traceback.format_exception(type(value), value, value.__traceback__))))
            messagebox.showerror(TITLE, msg)

    def _show(self, text):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.tabs.select(len(self.tabs.tabs()) - 1)

    def run_preflight(self):
        if not self.book.files:
            messagebox.showinfo(TITLE, "Add the manuscript's .docx files first.")
            return
        self._forms_to_profile()
        files, prof = list(self.book.files), copy.deepcopy(self.profile)
        from .preflight import preflight, render_text

        def done(rep):
            self._preflighted(rep)
            self._show(render_text(rep))
            self.status.set("Preflight done: %d warning%s." % (
                len(rep.warnings), "" if len(rep.warnings) == 1 else "s"))
        settings = copy.deepcopy(self.book.settings)
        self._run(lambda: preflight(files, prof, settings=settings), done,
                  "Reading the manuscript...")

    def mapping_changed(self, n):
        """After the mapping changed: read the manuscript again with it (the outline depends
        on it); the Style Map tab shows the result."""
        self.report = None
        self.status.set("%d style%s mapped by you. Save the profile to keep the mapping." % (
            n, "" if n == 1 else "s") if n else "Back to the automatic mapping.")
        self._need_report(lambda: self.tabs.select(self.styles_tab))

    def _preflighted(self, rep):
        self.report = rep
        # The first time a set of files is read, show the mapping to check (after the
        # report, which is shown first).
        files = tuple(self.book.files)
        if getattr(self, "_mapped_files", None) != files and rep.paragraph_styles:
            self._mapped_files = files
            self.root.after(100, lambda: self.tabs.select(self.styles_tab)
                            if self.report is rep else None)
        # (title, kind as detected): the book settings' choices are applied when shown.
        self.units = [(u.title, kind_key(u)) for u in rep.outline.units] if rep.outline else []
        self._refresh_files()
        self._refresh_heads()
        self._refresh_styles()
        self._margins_later()

    def _need_report(self, then):
        """Run preflight first if there's no report for the current files."""
        if self.report is not None:
            return then()
        if not self.book.files:
            messagebox.showinfo(TITLE, "Add the manuscript's .docx files first.")
            return
        self._forms_to_profile()
        files, prof = list(self.book.files), copy.deepcopy(self.profile)
        from .preflight import preflight

        def done(rep):
            self._preflighted(rep)
            then()
        settings = copy.deepcopy(self.book.settings)
        self._run(lambda: preflight(files, prof, settings=settings), done,
                  "Reading the manuscript...")

    def _choose_out(self):
        path = filedialog.askdirectory(title="Where to save the export")
        if path:
            self.out_var.set(path)

    def export(self):
        if not self.book.files:
            messagebox.showinfo(TITLE, "Add the manuscript's .docx files first.")
            return
        out = self.out_var.get().strip()
        if not out or not os.path.isdir(out):
            messagebox.showinfo(TITLE, "Choose a folder to save the export in.")
            return
        self._forms_to_profile()
        self._forms_to_book()
        self.settings["out_dir"] = out
        files, prof = list(self.book.files), copy.deepcopy(self.profile)
        settings = copy.deepcopy(self.book.settings)

        def done(result):
            path, report = result
            self.last_export = os.path.dirname(path)
            self._show("Wrote %s\n\n%s" % (path, "\n".join("- " + line for line in report)))
            self.status.set("Exported: %s" % path)
            self.open_btn.pack(side="left", padx=(6, 0))
            # What the export did on its own that the user should know about.
            from .pagination import Alert
            alerts = [line for line in report if isinstance(line, Alert)]
            if alerts:
                messagebox.showinfo(TITLE, "\n\n".join(alerts), parent=self.root)
        self._run(lambda: export(files, out, prof, None, settings), done, "Exporting...")

    def open_export(self):
        if self.last_export:
            _open_path(self.last_export)

    # ---- updates ----

    def _auto_check_changed(self):
        self.settings["check_updates"] = bool(self.auto_check.get())

    def startup(self):
        """After the window shows: offer to tidy up after an update, then check for one."""
        if updates.can_install():
            self.offer_cleanup(updates.running_exe())
        if updates.due(self.settings):
            self.check_updates(manual=False)
        if self.settings.get("last_book") and os.path.exists(self.settings["last_book"]):
            self.open_book(self.settings["last_book"])

    def offer_cleanup(self, exe):
        """At the start of a new version: offer to delete older copies in its folder and to
        point shortcuts and taskbar pins that open them at this one. A copy the user chose to
        keep isn't asked about again."""
        kept = set(self.settings.get("kept_old_versions") or [])
        olds = [p for p in updates.older_copies(exe.parent, exe) if p.name not in kept]
        if not olds:
            return
        one = len(olds) == 1
        if not messagebox.askyesno(TITLE, (
                "This is %s %s. The older version%s in this folder (%s) can be deleted now, and "
                "shortcuts and taskbar pins that open %s changed to open this version. Your "
                "settings and profiles are kept.\n\nDelete the old version%s and update the "
                "shortcuts?" % (TITLE, __version__, "" if one else "s",
                                ", ".join(p.name for p in olds), "it" if one else "them",
                                "" if one else "s"))):
            self.settings["kept_old_versions"] = sorted(kept | {p.name for p in olds})
            appsettings.save(self.settings)
            return

        def work():
            n = updates.retarget_shortcuts(olds, exe)
            deleted, left = updates.delete_old(olds)
            return n, deleted, left

        def done(r):
            n, deleted, left = r
            self.status.set("Deleted %s; shortcuts changed to open this version: %d." % (
                ", ".join(p.name for p in deleted) or "nothing", n))
            if left:
                messagebox.showwarning(TITLE, "Couldn't delete %s (it may still be open). Close "
                                              "it, then delete it by hand." % ", ".join(
                                                  p.name for p in left))
        self._run(work, done, "Tidying up after the update...")

    def check_updates(self, manual=False):
        def work():
            return updates.check()

        def show(r):
            self.settings["last_update_check"] = time.time()
            appsettings.save(self.settings)
            if updates.should_offer(r, self.settings, manual):
                self._offer_update(r)
            elif manual and r["status"] != "newer":
                msg = {"current": "This is the latest version (%s)." % __version__,
                       "norelease": "No release has been published yet.",
                       "error": "Couldn't reach GitHub to check for updates. Check the "
                                "connection and try again."}.get(r["status"], "")
                messagebox.showinfo(TITLE, msg)

        def target():
            r = work()
            self.results.put(lambda: show(r))
        threading.Thread(target=target, daemon=True).start()

    def _decline(self, version):
        self.settings["declined_version"] = version
        appsettings.save(self.settings)

    def _offer_update(self, r):
        notes = (r.get("notes") or "").strip()
        msg = "Version %s is available (this is %s).\n\n%s\n\n" % (
            r["latest"], __version__, notes[:800])
        later = ("\n\n(If you say no, the check at startup won't ask about %s again; Help > Check "
                 "for updates will.)" % r["latest"])
        if not (updates.can_install() and r.get("asset")):
            if messagebox.askyesno(TITLE, msg + "Open the download page?" + later):
                webbrowser.open(r.get("url") or "https://github.com/%s/releases" % updates.REPO)
            else:
                self._decline(r["latest"])
            return
        if not messagebox.askyesno(TITLE, msg + "Download it now? It is saved beside this "
                                                "copy; this one stays until the new version "
                                                "offers to remove it." + later):
            self._decline(r["latest"])
            return

        def work():
            return updates.install(r["asset"], r["latest"])

        def done(result):
            path, fell_back = result
            note = ("The program's folder can't be written to, so the new version was saved in "
                    "Downloads:\n%s\n\n" % path) if fell_back else ""
            if messagebox.askyesno(TITLE, note + "Open the new version now? This one will close."):
                updates.launch(path)
                self.quit(force=True)
        self._run(work, done, "Downloading version %s..." % r["latest"])

    # ---- closing ----

    def about(self):
        messagebox.showinfo(TITLE, "%s %s\n\nWord manuscripts to IDML for InDesign, Affinity "
                                   "and DesignCraft.\n\nSettings and profiles: %s" % (
                                       TITLE, __version__, profiles.settings_dir()))

    def quit(self, force=False):
        if not force and not self._maybe_save():
            return
        self.settings["profile"] = self.profile_name
        self.settings["out_dir"] = self.out_var.get().strip() or None
        appsettings.save(self.settings)
        try:
            self.root.after_cancel(self._poll_id)
        except (AttributeError, tk.TclError):
            pass
        self.root.destroy()


def _open_path(path):
    if sys.platform == "win32":
        os.startfile(path)                  # noqa: S606 (opens Explorer)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def make_root():
    """(root, drag-and-drop available)."""
    try:
        from tkinterdnd2 import TkinterDnD
        return TkinterDnD.Tk(), True
    except Exception:
        return tk.Tk(), False


def main():
    root, dnd = make_root()
    try:
        ttk.Style(root).theme_use("vista" if sys.platform == "win32" else "clam")
    except tk.TclError:
        pass
    app = App(root, dnd)
    root.after(300, app.startup)
    root.mainloop()
    return 0
