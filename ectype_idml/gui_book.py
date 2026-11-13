"""The Book Details tab of the window (moved out of gui.py): the book's bibliographic details
for the title and copyright pages, filled from the manuscript, and the notice library."""

from tkinter import simpledialog, ttk
import tkinter as tk

from .frontmatter import COPYRIGHT_FIELDS, ROLE_LABELS, ROLES, creators, notice_name

# Book settings (book.settings["front"]), in the tab's sections. The contributors (creators)
# are a list of their own, edited beside the title.
TITLE_FIELDS = [("title", "Title", "text"), ("subtitle", "Subtitle", "text"),
                ("short_title", "Short title (verso head)", "text")]
PUBLICATION_FIELDS = [
    ("series", "Series", "text"), ("series_number", "Number in the series", "text"),
    ("volume", "Volume", "text"), ("volumes", "Number of volumes", "text"),
    ("edition", "Edition line", "text"), ("publisher", "Publisher", "text"),
    ("publisher_address", "Place (city or address)", "text"),
    ("year", "Copyright year", "text"),
    ("holder", "Copyright holder (blank: authors)", "text"),
    ("rights", "Rights (blank: All rights reserved.)", "text"),
    ("isbn_print", "ISBN (print)", "text"), ("isbn_ebook", "ISBN (ebook)", "text"),
    ("call_number", "Call number (blank: none)", "text"),
    ("credits", "Credits", "text"), ("printed_in", "Printed in (country)", "text"),
]
PAGE_FIELDS = [("half_title", "Half-title page", "bool"),
               ("copyright_title", "Title on the copyright page", "bool"),
               ("contents", "Contents pages", "bool"),
               ("contents_pages", "Contents pages (blank = estimated)", "text")]
FRONT_FIELDS = TITLE_FIELDS + PUBLICATION_FIELDS + PAGE_FIELDS
LABEL_ROLES = {v: k for k, v in ROLE_LABELS.items()}


class _Forms:
    """Several forms read and written as one (the tab's sections)."""

    def __init__(self, forms):
        self.forms = forms
        self.vars = {k: v for f in forms for k, v in f.vars.items()}

    def load(self, data):
        for f in self.forms:
            f.load(data)

    def save(self, data):
        for f in self.forms:
            f.save(data)


class BookTabMixin:
    """Part of gui.App: builds and reads the Book Details tab."""

    def _book_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Book Details")
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=(0, 4))
        ttk.Button(row, text="Fill from the manuscript", command=self.fill_front).pack(side="left")
        ttk.Button(row, text="Preview pages...",
                   command=self.preview_pages).pack(side="left", padx=(6, 0))
        ttk.Label(row, text="Blank fields are filled from the manuscript at export; anything "
                            "still missing appears in brackets, e.g. [ISBN].").pack(
            side="left", padx=8)
        # Where the filled values came from (which style or line), so the user sees how the
        # manuscript was read.
        self.front_sources = tk.StringVar()
        ttk.Label(tab, textvariable=self.front_sources, wraplength=900,
                  justify="left").pack(anchor="w", pady=(0, 6))
        from .gui import Form

        def fields(table):
            return [((key,), label, kind, None) for key, label, kind in table]
        cols = ttk.Frame(tab)
        cols.pack(fill="both", expand=True)
        left, right = ttk.Frame(cols), ttk.Frame(cols)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right.pack(side="left", fill="both", expand=True)
        box = ttk.LabelFrame(left, text="Title", padding=6)
        box.pack(fill="x")
        forms = [Form(box, fields(TITLE_FIELDS))]
        self._contributors_box(left)
        box = ttk.LabelFrame(right, text="Publication", padding=6)
        box.pack(fill="x")
        forms.append(Form(box, fields(PUBLICATION_FIELDS)))
        box = ttk.LabelFrame(left, text="Pages", padding=6)
        box.pack(fill="x", pady=(6, 0))
        forms.append(Form(box, fields(PAGE_FIELDS)))
        self.front_form = _Forms(forms)
        ttk.Label(tab, text="Notices on the copyright page (from the profile's library; select "
                            "any number):").pack(anchor="w", pady=(8, 2))
        self.notice_list = tk.Listbox(tab, selectmode="multiple", height=4, exportselection=False)
        self.notice_list.pack(fill="x")
        nb = ttk.Frame(tab)
        nb.pack(fill="x", pady=4)
        ttk.Button(nb, text="Add notice to library...", command=self.add_notice).pack(side="left")
        ttk.Button(nb, text="Remove from library", command=self.remove_notice).pack(side="left",
                                                                                     padx=6)

    # ---- contributors ----

    def _contributors_box(self, parent):
        """The book's contributors in order (authors, editors, translators...): the title page
        has a byline per role in this order ("Edited by...", "Translated by...")."""
        box = ttk.LabelFrame(parent, text="Contributors (in title-page order)", padding=6)
        box.pack(fill="x", pady=(6, 0))
        self.creators = []
        tree = self.creator_tree = ttk.Treeview(box, columns=("role", "name"), show="headings",
                                                height=4, selectmode="browse")
        tree.heading("role", text="Role")
        tree.heading("name", text="Name (as on the title page)")
        tree.column("role", width=110)
        tree.column("name", width=280)
        tree.grid(row=0, column=0, columnspan=4, sticky="nsew")
        tree.bind("<<TreeviewSelect>>", self._creator_picked)
        self.creator_role = tk.StringVar(value=ROLE_LABELS["author"])
        self.creator_name = tk.StringVar()
        ttk.Combobox(box, textvariable=self.creator_role, state="readonly", width=13,
                     values=[ROLE_LABELS[r] for r in ROLES]).grid(row=1, column=0, sticky="w",
                                                                   pady=(6, 0))
        ttk.Entry(box, textvariable=self.creator_name, width=30).grid(
            row=1, column=1, columnspan=3, sticky="we", padx=(6, 0), pady=(6, 0))
        btns = ttk.Frame(box)
        btns.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
        for text, cmd in (("Add", self.add_creator), ("Change", self.change_creator),
                          ("Remove", self.remove_creator), ("Move up", lambda: self.move_creator(-1)),
                          ("Move down", lambda: self.move_creator(1))):
            ttk.Button(btns, text=text, command=cmd).pack(side="left", padx=(0, 4))
        box.columnconfigure(1, weight=1)
        box.rowconfigure(0, weight=1)

    def _show_creators(self, select=None):
        tree = self.creator_tree
        tree.delete(*tree.get_children())
        for n, c in enumerate(self.creators):
            tree.insert("", "end", iid=str(n), values=(ROLE_LABELS.get(c["role"], c["role"]),
                                                       c["name"]))
        if select is not None and 0 <= select < len(self.creators):
            tree.selection_set(str(select))

    def _creator_index(self):
        sel = self.creator_tree.selection()
        return int(sel[0]) if sel else None

    def _creator_picked(self, _event=None):
        i = self._creator_index()
        if i is not None:
            c = self.creators[i]
            self.creator_role.set(ROLE_LABELS.get(c["role"], c["role"]))
            self.creator_name.set(c["name"])

    def _creator_entry(self):
        name = " ".join(self.creator_name.get().split())
        return {"role": LABEL_ROLES.get(self.creator_role.get(), "author"), "name": name} \
            if name else None

    def add_creator(self):
        c = self._creator_entry()
        if c:
            self.creators.append(c)
            self.creator_name.set("")
            self._show_creators(len(self.creators) - 1)
            self.dirty = True

    def change_creator(self):
        i, c = self._creator_index(), self._creator_entry()
        if i is not None and c:
            self.creators[i] = c
            self._show_creators(i)
            self.dirty = True

    def remove_creator(self):
        i = self._creator_index()
        if i is not None:
            del self.creators[i]
            self._show_creators(min(i, len(self.creators) - 1))
            self.dirty = True

    def move_creator(self, step):
        i = self._creator_index()
        j = None if i is None else i + step
        if j is not None and 0 <= j < len(self.creators):
            self.creators[i], self.creators[j] = self.creators[j], self.creators[i]
            self._show_creators(j)
            self.dirty = True

    # ---- the generated front pages previewed ----

    def preview_pages(self):
        """The half-title, title page and copyright page the export will make from Book
        Details, drawn at the book's trim and margins, in a window of its own; the copyright
        page beside the manuscript's (which the export replaces)."""
        self._need_report(self._show_preview)

    def _show_preview(self):
        from .frontmatter import book_info
        from .preview import front_pages
        self._forms_to_book()
        self._forms_to_profile()
        lang = self.profile["front_matter"].get("language", "en")
        info, _notes = book_info(self.report.outline, self.book.settings.get("front"), lang)
        pages = front_pages(info, self.profile, lang)
        old = list(self.report.outline.copyright_lines)
        left = (self.report.outline.details or {}).get("leftover") or []
        old_win = getattr(self, "preview_window", None)
        if old_win is not None and old_win.winfo_exists():
            old_win.destroy()
        win = self.preview_window = tk.Toplevel(self.root)
        win.title("Front pages made from Book Details")
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry("%dx%d" % (min(1000, sw - 40), min(760, sh - 80)))
        win.transient(self.root)
        bottom = ttk.Frame(win, padding=(8, 0, 8, 8))
        bottom.pack(side="bottom", fill="x")            # first, so it is never cut off
        ttk.Button(bottom, text="Close", command=win.destroy).pack(side="right")
        tabs = ttk.Notebook(win)
        tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self.preview_canvases, self.compare_texts = {}, []
        for page in pages:
            tab = ttk.Frame(tabs, padding=8)
            tabs.add(tab, text=page.name)
            canvas = tk.Canvas(tab, background="#d9d9d9", highlightthickness=0, width=440,
                               height=600)
            canvas.grid(row=1, column=0, sticky="nsew")
            ttk.Label(tab, text="In the export (fonts as installed here; a style template's "
                                "styles aren't shown)").grid(row=0, column=0, sticky="w")
            canvas.bind("<Configure>", lambda e, c=canvas, p=page: self._draw_page(c, p))
            self._draw_page(canvas, page)
            self.preview_canvases[page.name] = canvas
            tab.rowconfigure(1, weight=1)
            tab.columnconfigure(0, weight=1)
            if page.bottom:
                ttk.Label(tab, text="In the manuscript (replaced at export)").grid(
                    row=0, column=1, sticky="w", padx=(12, 0))
                text = tk.Text(tab, wrap="word", width=50, height=24)
                text.insert("1.0", "\n\n".join(old) if old else
                            "(No copyright page was found in the manuscript.)")
                text.configure(state="disabled")
                text.grid(row=1, column=1, sticky="nsew", padx=(12, 0))
                tab.columnconfigure(1, weight=1)
                self.compare_texts.append(text)
                if left:
                    ttk.Label(tab, wraplength=420, justify="left", text=(
                        "Lines of the manuscript's page that fit no field (left out): %s. Add "
                        "any that belong in Credits or as a notice." % "; ".join(
                            "\u201c%s\u201d" % x for x in left))).grid(
                        row=2, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    def _draw_page(self, canvas, page):
        """One page on the canvas, scaled to fit: the trim, the text area (dotted) and the
        lines in their sizes."""
        from . import fonts
        canvas.delete("all")
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        if cw < 100 or ch < 100:              # not shown yet: its requested size
            cw, ch = int(canvas["width"]), int(canvas["height"])
        scale = min((cw - 24) / page.width, (ch - 24) / page.height)
        x0, y0 = (cw - page.width * scale) / 2, (ch - page.height * scale) / 2
        canvas.create_rectangle(x0, y0, x0 + page.width * scale, y0 + page.height * scale,
                                fill="white", outline="#888")
        m = page.margins
        left = m["inside"] if page.recto else m["outside"]
        right = page.width - (m["outside"] if page.recto else m["inside"])
        top, foot = m["top"], page.height - m["bottom"]
        canvas.create_rectangle(x0 + left * scale, y0 + top * scale, x0 + right * scale,
                                y0 + foot * scale, outline="#c8c8e8", dash=(2, 3))
        family = (self.profile.get("fonts") or {}).get("body") or fonts.book_font() or "Times"
        y = top + page.sink
        for line in page.lines:
            y += line.space_before
            font = (family, -max(1, round(line.size * scale)),
                    "italic" if line.italic else "roman")
            x = (left + right) / 2 if line.centered else left
            item = canvas.create_text(
                x0 + x * scale, y0 + y * scale, text=line.text or " ", font=font,
                anchor="n" if line.centered else "nw", width=(right - left) * scale,
                justify="center" if line.centered else "left", tags=("text",))
            # The leading as set: wrapped lines take a line each.
            box = canvas.bbox(item)
            rows = max(1, round((box[3] - box[1]) / max(1, line.size * scale * 1.2)))
            y += rows * line.lead + line.space_after
        if page.bottom:
            canvas.move("text", 0, (foot - y) * scale)

    # ---- notices ----

    def _take_notices(self, texts):
        """Permissions found on the manuscript's copyright page: into the profile's notice
        library (by a short name: ESV, NKJV...) unless there already, and ticked for this
        book. Returns their names."""
        library = self.profile.setdefault("notices", [])
        names = []
        for text in texts:
            same = next((n for n in library if " ".join(n.get("text", "").split()) ==
                         " ".join(text.split())), None)
            if same is None:
                name, k = notice_name(text), 2
                taken = {n.get("name") for n in library}
                base = name
                while name in taken:
                    name, k = "%s (%d)" % (base, k), k + 1
                same = {"name": name, "text": text}
                library.append(same)
                self.notice_list.insert("end", name)
            i = library.index(same)
            self.notice_list.selection_set(i)
            names.append(same["name"])
        return names

    def add_notice(self):
        from .gui import TITLE
        name = simpledialog.askstring(TITLE, "Short name of the notice (e.g. ESV):",
                                      parent=self.root)
        if not name:
            return
        text = simpledialog.askstring(TITLE, "Wording of the notice, exactly as it should "
                                             "appear on the copyright page:", parent=self.root)
        if text:
            self.profile.setdefault("notices", []).append({"name": name, "text": text})
            self.notice_list.insert("end", name)
            self.status.set("Notice added. Save the profile to keep it for other books.")

    def remove_notice(self):
        for i in reversed(self.notice_list.curselection()):
            del self.profile["notices"][i]
            self.notice_list.delete(i)

    def _load_book_into_forms(self):
        front = self.book.settings.get("front") or {"half_title": True, "contents": True}
        self.front_form.load(front)
        self.creators = [dict(c) for c in creators(front)]
        self._show_creators()
        self._refresh_files()
        self._refresh_heads()

    def _forms_to_book(self):
        front = self.book.settings.setdefault("front", {})
        self.front_form.save(front)
        front["creators"] = [dict(c) for c in self.creators]
        front.pop("author", None)
        cp = front.get("contents_pages")
        try:
            front["contents_pages"] = int(cp) if cp else None
        except ValueError:
            front["contents_pages"] = None
        names = [n.get("name") for n in self.profile.get("notices") or []]
        front["notices"] = [names[i] for i in self.notice_list.curselection() if i < len(names)]
        self.book.profile = self.profile_name

    def fill_front(self):
        self._need_report(self._fill_front_now)

    def _fill_front_now(self):
        o = self.report.outline
        front = self.book.settings.setdefault("front", {})
        self.front_form.save(front)
        filled = []
        for key, value in (("title", o.title), ("subtitle", o.subtitle)):
            if value and not front.get(key):
                front[key] = value
                filled.append(key)
        details = {k: v for k, v in (getattr(o, "details", {}) or {}).items()
                   if k in COPYRIGHT_FIELDS}
        for key, value in details.items():
            if value and not front.get(key):
                front[key] = value
                filled.append(key)
        if (getattr(o, "details", {}) or {}).get("copyright_title") and \
                not front.get("copyright_title"):
            front["copyright_title"] = True          # the manuscript's page opens with it
            details["copyright_title"] = True
            filled.append("copyright_title")
        added = self._take_notices((getattr(o, "details", {}) or {}).get("notices") or [])
        found_people = creators({}, o)
        if found_people and not self.creators:
            self.creators = found_people
            self._show_creators()
            filled.append("author")
        self.front_form.load(front)
        self.dirty = True
        found = []
        for key, label, value, source in (
                ("title", "Title", o.title, o.title_source),
                ("subtitle", "Subtitle", o.subtitle, o.subtitle_source),
                ("author", "Contributors", "; ".join(
                    "%s (%s)" % (c["name"], ROLE_LABELS[c["role"]]) for c in found_people),
                 o.author_source)):
            if value:
                state = "filled in" if key in filled else "already set, kept"
                found.append("%s: \u201c%s\u201d, from %s (%s)" % (label, value, source, state))
            else:
                found.append("%s: not found in the manuscript" % label)
        labels = {key: label for key, label, _k in PUBLICATION_FIELDS + PAGE_FIELDS}
        if details:
            found.append("from the copyright page: " + ", ".join(
                "%s %s" % (labels.get(k, k).split(" (")[0].lower(),
                           "filled in" if k in filled else "already set, kept")
                for k in details))
        if added:
            found.append("notices ticked below: %s" % ", ".join(added))
        self.front_sources.set("Found in the manuscript \u2014 " + "; ".join(found) + ".")
