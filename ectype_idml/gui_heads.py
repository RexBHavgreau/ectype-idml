"""The Running Heads tab of the window (moved out of gui.py, 1.1.0): head choices, page
numbers, the running-head style, and the units of the book with their heads and kinds."""

import tkinter as tk
from tkinter import simpledialog, ttk

from .export import TRIMS
from .gui_forms import TITLE, Form
from .outline import KIND_LABELS, KINDS

HEAD_FIELDS = [
    (("running_heads", "verso"), "Verso head", "choice",
     ["book_title", "part", "chapter", "author", "custom", "none"]),
    (("running_heads", "verso_custom"), "Verso text (custom)", "text", None),
    (("running_heads", "recto"), "Recto head", "choice", ["chapter_title", "custom", "none"]),
    (("running_heads", "recto_custom"), "Recto text (custom)", "text", None),
    (("running_heads", "suppress_on_openers"), "No heads on chapter openers", "bool", None),
    (("running_heads", "suppress_on_display"), "No heads on display pages", "bool", None),
    (("running_heads", "suppress_on_blanks"), "No heads on blank pages", "bool", None),
    (("running_heads", "script_masters"),
     "Separate masters for heads with Hebrew or Greek the head font lacks", "bool", None),
]
FOLIO_FIELDS = [
    (("running_heads", "folio"), "Page numbers", "radio",
     [("foot_center", "At the foot, centered"), ("foot_outside", "At the foot, outside"),
      ("head_outside", "At the head, outside (beside the running head)")]),
    (("running_heads", "opener_folio"), "On chapter openers", "radio",
     [("drop", "At the foot"), ("none", "None")]),
    (("running_heads", "folio_size"), "Size (pt; blank = the body size)", "number", None),
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
    (("running_heads", "style", "size"), "Size (pt; blank = the body size)", "number",
     None),
    (("running_heads", "style", "tracking"), "Letter-spacing (thousandths of an em)", "int",
     None),
    (("running_heads", "style", "font"), "Font (blank = the body font)", "font", None),
]


class HeadsTabMixin:
    """The Running Heads tab of the App."""

    def _heads_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Running Heads")
        form = ttk.Frame(tab)
        form.pack(fill="x")
        self.heads_form = Form(form, HEAD_FIELDS, columns=2)
        folios = ttk.LabelFrame(tab, text="Page Numbers", padding=4)
        folios.pack(fill="x", pady=(8, 0))
        self.folio_form = Form(folios, FOLIO_FIELDS)
        ttk.Label(folios, foreground="#555", text=(
            "Display and blank pages have no page number. With page numbers at the head, "
            "an opener's goes at the foot, centered.")).grid(
            row=len(FOLIO_FIELDS), column=0, columnspan=2, sticky="w", padx=6)
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
        g = layout.geometry(w * 72, h * 72, 11, 13, 0.42, 200, page.get("margins"),
                            scheme=layout.margin_scheme(page))
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
