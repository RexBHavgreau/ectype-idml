"""The window, driven from code: files, forms, preflight, export, book file, profile.

Needs Tkinter and a display (on Linux, run under xvfb-run); skipped without them. The settings
folder is a temporary one, so real profiles are untouched."""

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TMP = tempfile.mkdtemp()
os.environ["APPDATA"] = os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")

from docx_builder import run_tests  # noqa: E402

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_TK = True
except Exception as e:          # no Tkinter, or no display
    HAVE_TK = False
    print("Skipped: no Tkinter or no display (%s). On Linux run: xvfb-run python "
          "tests/test_gui.py" % e)

MS = os.path.join(ROOT, "reference", "manuscript")


def _files():
    return [os.path.join(MS, f) for f in sorted(os.listdir(MS)) if f.endswith(".docx")]


def _descendants(w):
    for child in w.winfo_children():
        yield child
        yield from _descendants(child)


def _app():
    from ectype_idml import gui
    root = tk.Tk()
    root.withdraw()
    return gui.App(root, dnd=False), root


def _wait(app, root, timeout=120):
    end = time.time() + timeout
    while app.busy and time.time() < end:
        root.update()
        time.sleep(0.02)
    root.update()
    assert not app.busy, "still busy"


def test_files_and_order():
    app, root = _app()
    try:
        files = _files()
        app._add(list(reversed(files)))
        assert app.book.files == list(reversed(files))
        app.sort_files()
        assert app.book.files == files
        app.tree.selection_set(files[2])
        app.move("top")
        assert app.book.files[0] == files[2]
        app.move(1)
        assert app.book.files[1] == files[2]
        app.tree.selection_set(files[0])
        app.remove_files()
        assert files[0] not in app.book.files
    finally:
        app.quit(force=True)


def test_preflight_export_and_book_file():
    app, root = _app()
    try:
        app._add(_files())
        app.run_preflight()
        _wait(app, root)
        assert app.report is not None and app.units
        assert "PREFLIGHT" in app.text.get("1.0", "end")
        # Running heads table, with a short title.
        assert app.heads.get_children()
        # A unit's kind, changed by the user, and changed back.
        app.set_kind("Covenant and Community", "endorsements")
        assert app.book.settings["unit_kinds"] == {"Covenant and Community": "endorsements"}
        assert app.heads.set("Covenant and Community", "kind") == "endorsements (set by you)"
        assert app.heads.set("Covenant and Community", "head") == "(no running heads)"
        app.set_kind("Covenant and Community", "chapter")
        assert app.book.settings["unit_kinds"] == {}
        # The Style Map tab shows each style's look; one can be switched.
        looks = {w: lv for w, _iv, _rv, lv, _i in app.mapping.rows}
        assert looks["Epigraph"].get() == "Word's, in book terms"
        assert looks["Normal"].get() == "the book style's"
        looks["Epigraph"].set("the book style's")
        app.mapping.apply()
        _wait(app, root)
        assert app.profile["style_map"]["paragraph"]["Epigraph"]["look"] == "book"
        looks = {w: lv for w, _iv, _rv, lv, _i in app.mapping.rows}
        assert looks["Epigraph"].get() == "the book style's"
        app.book.settings["short_titles"] = {"The Formula in the Prophets": "The Formula"}
        app._refresh_heads()
        assert app.heads.set("The Formula in the Prophets", "head") == "The Formula"
        # Book details: filled from the manuscript, then edited.
        app.fill_front()
        _wait(app, root)
        var = app.front_form.vars[("isbn_print",)][0]
        var.set("978-0-000-00000-0")
        assert app.front_form.vars[("title",)][0].get() == "The Covenant Formula"
        sources = app.front_sources.get()
        assert "Title: \u201cThe Covenant Formula\u201d, from style Title in 00 Front.docx" in sources
        assert "Contributors: \u201cA. N. Author (author)\u201d, from title page text" in sources
        assert app.creators == [{"role": "author", "name": "A. N. Author"}]
        # A profile setting from the form.
        app.pvar(("page", "trim")).set("5.5x8.5")
        out = os.path.join(TMP, "out")
        os.makedirs(out)
        app.out_var.set(out)
        app.export()
        _wait(app, root)
        assert app.last_export and os.path.exists(app.last_export)
        # The Open button appears in the export row, which the tabs can't crowd out.
        assert app.open_btn.winfo_manager() == "pack"
        assert app.open_btn.master is app.export_btn.master
        report = app.text.get("1.0", "end")
        assert "Wrote" in report and "[ISBN]" not in report
        assert app.profile["page"]["trim"] == "5.5x8.5"
        # The book file keeps files, details and short titles.
        path = os.path.join(TMP, "book.json")
        app.book_path = path
        assert app.save_book()
        from ectype_idml.book import Book
        b = Book.load(path)
        assert b.files == app.book.files
        assert b.settings["front"]["isbn_print"] == "978-0-000-00000-0"
        assert b.settings["short_titles"]["The Formula in the Prophets"] == "The Formula"
    finally:
        app.quit(force=True)


def test_profile_save_and_settings():
    from ectype_idml import appsettings
    from ectype_idml import profile as profiles
    app, root = _app()
    try:
        app.pvar(("fonts", "body")).set("Arno Pro")
        app.profile_name = "Series A"
        app.save_profile()
        assert profiles.load("Series A")["fonts"]["body"] == "Arno Pro"
        place = app.folio_form.vars[("running_heads", "folio")][0]    # the Page Numbers box
        assert place.get() == "foot_center"
        place.set("head_outside")
        app.folio_form.vars[("running_heads", "opener_folio")][0].set("none")
        app.save_profile()
        saved = profiles.load("Series A")["running_heads"]
        assert (saved["folio"], saved["opener_folio"]) == ("head_outside", "none")
        app._refresh_profile_list()
        assert "Series A" in app.profile_box["values"]
    finally:
        app.quit(force=True)
    assert appsettings.load()["profile"] == "Series A"


def test_font_dropdowns():
    from ectype_idml import fonts
    app, root = _app()
    try:
        end = time.time() + 60
        while app.font_lists is None and time.time() < end:
            root.update()
            time.sleep(0.02)
        assert app.font_lists is not None, "fonts not read"
        installed = fonts.families()
        form = app._form_of(("fonts", "body"))
        boxes = {script: box for box, script in form.font_boxes}
        assert list(boxes[None]["values"]) == installed
        for script in ("hebrew", "greek"):
            assert set(app.font_lists[script]) <= set(installed)
        if installed:
            form.vars[("fonts", "body")][0].set(installed[0])
        form.vars[("fonts", "notes")][0].set("(reading the installed fonts...)")
        app._forms_to_profile()
        assert app.profile["fonts"]["body"] == (installed[0] if installed else None)
        assert app.profile["fonts"]["notes"] is None
    finally:
        app.quit(force=True)


def test_leading_note():
    app, root = _app()
    try:
        app.update_margins()
        note = app.leading_note.get()
        assert note.startswith("Suggested for 11 pt") and "standard 13" in note
        app.pvar(("body_size",)).set("10")
        app.pvar(("leading", "feel")).set("tight")
        app.update_margins()
        assert "Suggested for 10 pt" in app.leading_note.get()
        assert "(tight)" in app.leading_note.get()
        app._forms_to_profile()
        assert app.profile["body_size"] == 10 and app.profile["leading"]["feel"] == "tight"
    finally:
        app.quit(force=True)


def test_calculated_margins_shown_and_filled():
    app, root = _app()
    try:
        app.update_margins()
        form = app._form_of(("page", "margins", "inside"))
        lab, _text = form.labels[("page", "margins", "inside")]
        assert "calculated" in str(lab.cget("text"))
        note = app.margin_note.get()
        assert note.startswith("Calculated margins: top ") and "about 200 pages" in note
        assert ' pt (' in note and '")' in note                     # points with inches
        assert "picas" in note
        mlab, _t = app._form_of(("page", "measure")).labels[("page", "measure")]
        assert " picas" in str(mlab.cget("text")) and "pt (" in str(mlab.cget("text"))
        g, _pages, _found = app.calculated()
        # By default the classical canon: inside < top < outside < bottom.
        m = g.margins
        assert m["inside"] < m["top"] < m["outside"] < m["bottom"]
        app.pvar(("page", "trim")).set("5x8")
        g2, _p, _f = app.calculated()
        assert g2.measure != g.measure or g2.margins != g.margins
        form.vars[("page", "margins", "top")][0].set('1"')
        app.fill_margins()
        assert form.vars[("page", "margins", "top")][0].get() == '1"'      # kept as typed
        from ectype_idml.gui import format_points
        assert form.vars[("page", "margins", "inside")][0].get() == \
            format_points(g2.margins["inside"])
        app._forms_to_profile()
        assert app.profile["page"]["margins"]["top"] == 1                  # saved in inches
        assert abs(app.profile["page"]["margins"]["inside"] - g2.margins["inside"] / 72) < 0.01
        # A margin's arrows step 9 pt (1/8 in); typed points are saved as inches.
        form.vars[("page", "margins", "top")][0].set("54")
        app._forms_to_profile()
        assert app.profile["page"]["margins"]["top"] == 0.75
        # The footnote spacing: points, arrows step 1 pt.
        nform = app._form_of(("footnotes", "space_above"))
        assert nform.vars[("footnotes", "space_above")][0].get() == '12 pt (0.17")'

    finally:
        app.quit(force=True)


def test_update_check_at_every_start():
    """The startup check runs at every start (not once a day); a declined version isn't
    offered again at startup, but is from the Help menu."""
    from tkinter import messagebox
    from ectype_idml import updates
    asked = []
    real_check, real_ask = updates.check, messagebox.askyesno
    updates.check = lambda *a, **k: {"status": "newer", "latest": "9.9.9", "url": "u",
                                     "notes": "", "asset": None}
    messagebox.askyesno = lambda *a, **k: asked.append(a[1]) or False

    def run(app, root, manual):
        n = len(asked)
        app.check_updates(manual=manual)
        end = time.time() + 10
        while len(asked) == n and time.time() < end:
            root.update()
            time.sleep(0.02)
        root.update()
        return len(asked) > n
    try:
        app, root = _app()
        app.settings["last_update_check"] = time.time()      # checked a minute ago
        assert updates.due(app.settings)
        assert run(app, root, manual=False)                   # offered; answered No
        assert app.settings["declined_version"] == "9.9.9"
        assert "9.9.9" in asked[-1]
        assert not run(app, root, manual=False)               # not asked again at startup
        assert run(app, root, manual=True)                    # but from the Help menu
        app.quit(force=True)
    finally:
        updates.check, messagebox.askyesno = real_check, real_ask


def test_style_mapping_panel():
    """All styles in the Style Map tab after the automatic mapping (shown after the first
    preflight); the user's choices are saved in the profile and used by the export. The
    manuscript's own contents styles aren't listed."""
    from ectype_idml import gui
    app, root = _app()
    try:
        assert not app.mapping.rows                   # nothing read yet
        app._add(_files())
        app.run_preflight()
        _wait(app, root)
        end = time.time() + 5
        while app.tabs.select() != str(app.styles_tab) and time.time() < end:
            root.update()
            time.sleep(0.02)
        assert app.tabs.select() == str(app.styles_tab), "the mapping is shown after preflight"
        panel = app.mapping
        rows = {w: (iv, rv, lv) for w, iv, rv, lv, _i in panel.rows}
        assert not [w for w in rows if w.lower().startswith("toc")]
        assert rows["Epigraph"][0].get() == gui.OWN
        assert rows["Heading 1"][0].get() == "Chapter Title"
        iv, rv, lv = rows["Epigraph"]
        iv.set("Block Quote")
        panel._role_for(iv, rv)                       # a book style sets its role
        assert rv.get() == "quote"
        chars = {w: cv for w, cv, _i in panel.char_rows}
        chars["Scripture Ref"].set("Small Caps")
        panel.apply()
        _wait(app, root)
        sm = app.profile["style_map"]
        assert sm["paragraph"]["Epigraph"]["idml"] == "Block Quote"
        assert sm["paragraph"]["Epigraph"]["role"] == "quote"
        assert "Normal" not in sm["paragraph"]         # unchanged rows aren't saved
        assert sm["character"]["Scripture Ref"] == "Small Caps"
        assert app.report is not None                 # read again with the new map
        rows = {w: iv for w, iv, _rv, _lv, _i in app.mapping.rows}
        assert rows["Epigraph"].get() == "Block Quote"
        from ectype_idml.export import Exporter
        ex = Exporter(app.book.files, app.profile)
        try:
            doc = ex.build()
            styles = {p.style for st in doc.stories for p in st.paragraphs}
            # A quotation's first paragraph is Block Quote First.
            assert "Block Quote First" in styles and "Epigraph" not in styles
            runs = [r for st in doc.stories for p in st.paragraphs for r in p.runs
                    if "Lev 26:12" in r.text]
            assert runs and runs[0].style == "Small Caps"
        finally:
            ex.cleanup()
        # A change not yet applied is kept when the profile is read from the window.
        rows = {w: iv for w, iv, _rv, _lv, _i in app.mapping.rows}
        rows["Normal"].set("Block Quote")
        app._forms_to_profile()
        assert app.profile["style_map"]["paragraph"]["Normal"]["idml"] == "Block Quote"
        # Back to the automatic mapping.
        app.mapping.reset()
        _wait(app, root)
        assert "Epigraph" not in app.profile["style_map"]["paragraph"]
        assert "Normal" not in app.profile["style_map"]["paragraph"]
        assert "Scripture Ref" not in app.profile["style_map"]["character"]
    finally:
        app.quit(force=True)


def test_formatting_groups_in_style_map():
    """Headings found by formatting show in the Style Map tab; a change to one is saved with
    the book (it belongs to this manuscript), not the profile."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_outline import unstyled_book
    app, root = _app()
    try:
        app._add([unstyled_book("unstyled-gui.docx")])
        app.run_preflight()
        _wait(app, root)
        rows = {w: (iv, rv) for w, iv, rv, _lv, _i in app.mapping.rows}
        assert rows["[16 pt bold centered]"][0].get() == "Chapter Title"
        assert rows["[bold]"][0].get() == "Heading A"
        rows["[bold]"][0].set("Heading B")
        app.mapping.apply()
        _wait(app, root)
        assert app.book.settings["format_map"]["[bold]"]["idml"] == "Heading B"
        assert "[bold]" not in app.profile["style_map"]["paragraph"]
        rows = {w: iv for w, iv, _rv, _lv, _i in app.mapping.rows}
        assert rows["[bold]"].get() == "Heading B"            # read again with the choice
        app.mapping.reset()
        _wait(app, root)
        assert "[bold]" not in app.book.settings["format_map"]
    finally:
        app.quit(force=True)


def test_contributors_in_order():
    """Contributors are a list with roles, in title-page order; editors found on a copyright
    page come in as editors; old books' single author is upgraded."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_outline import front_matter_book
    from ectype_idml.book import Book
    app, root = _app()
    try:
        app._add([d.path for d in front_matter_book()])
        app.fill_front()
        _wait(app, root)
        assert app.creators == [{"role": "editor", "name": "Nicolas Ellen"},
                                {"role": "editor", "name": "Josh Stephens"},
                                {"role": "foreword", "name": "Lance Quinn"}]
        app.creator_role.set("translator")
        app.creator_name.set("Ana Traductora")
        app.add_creator()
        app.creator_tree.selection_set("3")
        app.move_creator(-1)
        app.move_creator(-1)
        assert [c["name"] for c in app.creators] == ["Nicolas Ellen", "Ana Traductora",
                                                     "Josh Stephens", "Lance Quinn"]
        # The copyright page's details fill the empty fields.
        assert app.front_form.vars[("year",)][0].get() == "2026"
        assert app.front_form.vars[("holder",)][0].get() == "A Seminary"
        assert app.front_form.vars[("isbn_print",)][0].get() == "978-1-934952-94-8"
        assert "from the copyright page: copyright year filled in" in app.front_sources.get()
        # The permission: in the notice library, ticked for this book.
        names = [n["name"] for n in app.profile["notices"]]
        assert "ESV" in names and names.index("ESV") in app.notice_list.curselection()
        # The front pages previewed; the copyright page beside the manuscript's, then closed.
        app.front_form.vars[("copyright_title",)][0].set(True)
        app.preview_pages()
        root.update()
        assert list(app.preview_canvases) == ["Half-title", "Title page", "Copyright page"]
        for _ in range(5):
            root.update()
        def texts(name):
            c = app.preview_canvases[name]
            return [c.itemcget(i, "text") for i in c.find_withtag("text")]
        old = app.compare_texts[0].get("1.0", "end")
        new = "\n".join(texts("Copyright page"))
        assert "Copyright \u00a9 2026 by A Seminary" in old and "Edited by" in old
        assert "Copyright \u00a9 2026 by A Seminary" in new and "Edited by" not in new
        assert "ISBN 978-1-934952-94-8" in new
        from ectype_idml.frontmatter import book_info
        title = book_info(app.report.outline, app.book.settings["front"])[0]["title"]
        assert texts("Copyright page")[0].startswith(title)       # the box ticked above
        assert any(t.startswith("Edited by") for t in texts("Title page"))
        app.preview_window.destroy()
        # The rights statement too.
        assert app.front_form.vars[("rights",)][0].get().startswith("All rights reserved. No")
        app._forms_to_book()
        assert app.book.settings["front"]["creators"][1] == {"role": "translator",
                                                             "name": "Ana Traductora"}
        path = os.path.join(TMP, "creators.json")
        app.book_path = path
        assert app.save_book()
        assert Book.load(path).settings["front"]["creators"] == app.creators
    finally:
        app.quit(force=True)
    # A book saved before contributors: its author becomes an author entry.
    old = os.path.join(TMP, "old-book.json")
    with open(old, "w") as f:
        f.write('{"book_version": 1, "files": [], "settings": {"front": '
                '{"author": "A. Writer and B. Writer"}}}')
    front = Book.load(old).settings["front"]
    assert front["creators"] == [{"role": "author", "name": "A. Writer"},
                                 {"role": "author", "name": "B. Writer"}]
    assert "author" not in front


def test_tabs_in_title_case_and_head_style():
    app, root = _app()
    try:
        names = [app.tabs.tab(t, "text") for t in app.tabs.tabs()]
        assert names == ["Files", "Book Details", "Running Heads", "Layout Profile", "Style Map",
                         "Report"]
        app.head_case_form.vars[("running_heads", "style", "case")][0].set("title")
        app.head_style_form.vars[("running_heads", "style", "italic")][0].set(True)
        app.head_style_form.vars[("running_heads", "style", "bold")][0].set(True)
        app._forms_to_profile()
        rs = app.profile["running_heads"]["style"]
        assert rs["case"] == "title" and rs["italic"] is True and rs["bold"] is True
        assert rs["caps"] == "small_caps"          # the default
        # All Caps and Small Caps: at most one of them.
        caps = app.head_style_form.vars[("running_heads", "style", "caps")][0]
        from tkinter import ttk
        boxes = [w for w in _descendants(app.root) if isinstance(w, ttk.Checkbutton) and
                 w.cget("text") in ("All Caps", "Small Caps")]
        by = {w.cget("text"): w for w in boxes}
        by["All Caps"].invoke()
        assert caps.get() == "all_caps"
        assert not app.root.getvar(by["Small Caps"].cget("variable"))
        by["All Caps"].invoke()
        app._forms_to_profile()
        assert app.profile["running_heads"]["style"]["caps"] is None
    finally:
        app.quit(force=True)


def test_opener_drop_field():
    """The drop at chapter openings: points shown with inches, arrows step 6 pt, inches or
    points typed are tidied, blank = automatic."""
    app, root = _app()
    try:
        form = app._form_of(("page", "opener_drop"))
        var = form.vars[("page", "opener_drop")][0]
        box = next(w for w in _descendants(app.root) if w.winfo_class() == "TSpinbox" and
                   str(w.cget("textvariable")) == str(var))
        assert var.get() == ""                         # automatic
        box.event_generate("<<Increment>>")
        assert var.get() == app_auto(app)               # the arrows start from the automatic
        var.set("72")
        box.event_generate("<<Increment>>")
        assert var.get() == '78 pt (1.08")'
        box.event_generate("<<Decrement>>")
        box.event_generate("<<Decrement>>")
        assert var.get() == '66 pt (0.92")'
        var.set('1.5"')
        box.event_generate("<FocusOut>")
        assert var.get() == '108 pt (1.5")'
        app._forms_to_profile()
        assert app.profile["page"]["opener_drop"] == 108
        var.set("")
        app._forms_to_profile()
        assert app.profile["page"]["opener_drop"] is None
    finally:
        app.quit(force=True)


def app_auto(app):
    from ectype_idml.gui import format_points
    return format_points(app._auto_drop())


def test_hebrew_head_alert_after_export():
    """A chapter head with Hebrew the head font lacks gets a master of its own, and the
    window says so in a pop-up after the export."""
    from docx_builder import make_docx, para
    from ectype_idml import gui
    heb = "\u05e0\u05e9\u05c2\u05d9\u05d0"
    long = [para("Text of the chapter goes on for a while. " * 30)] * 4
    path = make_docx(os.path.join(TMP, "heb-alert.docx"),
                     [para("Book", "Title"), para(heb + " in Ezekiel", "Heading1")] + long)
    shown = []
    real = gui.messagebox.showinfo
    gui.messagebox.showinfo = lambda title, message, **kw: shown.append(message)
    app, root = _app()
    try:
        app._add([path])
        app.head_style_form.vars[("running_heads", "style", "font")][0].set("No Such Font")
        out = os.path.join(TMP, "heb-out")
        os.makedirs(out, exist_ok=True)
        app.out_var.set(out)
        app.export()
        _wait(app, root)
        assert len(shown) == 1 and "R1-Body" in shown[0] and heb in shown[0]
    finally:
        gui.messagebox.showinfo = real
        app.quit(force=True)


def test_cleanup_after_update():
    """The new version offers to delete older copies and retarget shortcuts; declined copies
    aren't asked about again."""
    from pathlib import Path
    from tkinter import messagebox
    from ectype_idml import __version__, updates
    folder = Path(tempfile.mkdtemp())
    me = folder / updates.exe_name(__version__)
    old = folder / updates.exe_name("0.2.0")
    for p in (me, old):
        p.write_bytes(b"x")
    answers, asked, retargeted = [], [], []
    real_ask, real_retarget = messagebox.askyesno, updates.retarget_shortcuts
    messagebox.askyesno = lambda *a, **k: asked.append(a[1]) or answers.pop(0)
    updates.retarget_shortcuts = lambda olds, new, **k: retargeted.append((olds, new)) or 1
    try:
        app, root = _app()
        answers.append(False)
        app.offer_cleanup(me)                              # No: kept, not asked again
        assert old.exists() and app.settings["kept_old_versions"] == [old.name]
        assert "shortcuts" in asked[-1] and old.name in asked[-1]
        n = len(asked)
        app.offer_cleanup(me)
        assert len(asked) == n
        app.settings["kept_old_versions"] = []
        answers.append(True)
        app.offer_cleanup(me)                              # Yes: retargeted and deleted
        end = time.time() + 20
        while app.busy and time.time() < end:
            root.update()
            time.sleep(0.02)
        root.update()
        assert not old.exists() and me.exists()
        assert retargeted == [([old], me)]
        assert "shortcuts changed to open this version: 1" in app.status.get()
        app.quit(force=True)
    finally:
        messagebox.askyesno, updates.retarget_shortcuts = real_ask, real_retarget


def test_leading_preview_and_margin_schemes():
    """The leading preview pops up under its button, draws the sample at the size and
    leading the forms give, tries a feel, and closes; margin schemes: the canon by default, a
    scheme of one's own saved in the profile and used for the margins, then deleted."""
    from ectype_idml import layout
    app, root = _app()
    try:
        root.deiconify()
        root.update()
        app.pvar(("leading", "feel")).set("standard")
        app.preview_leading()
        root.update()
        assert app.leading_popup is not None and app.leading_lines > 4
        assert "pt on 13 pt leading" in app.leading_caption.get()
        app._try_feel("open")
        assert app.pvar(("leading", "feel")).get() == "open"
        assert "pt on 14 pt leading" in app.leading_caption.get()
        # A panel inside the window, visible, under its button.
        panel = app.leading_popup
        assert panel.winfo_toplevel() is root and panel.winfo_ismapped()
        assert panel.winfo_rooty() > app.leading_button.winfo_rooty()
        # A click inside it keeps it; a click elsewhere closes it.
        inner = app.leading_canvas
        app._leading_click(type("E", (), {"widget": inner})())
        assert app.leading_popup is panel
        app._leading_click(type("E", (), {"widget": app.leading_button})())
        assert app.leading_popup is None
        app.preview_leading()
        root.update()
        app.close_leading_preview()
        assert app.leading_popup is None

        assert app.scheme_var.get() == layout.MARGIN_SCHEMES["canon"]["name"]
        assert app.save_scheme({"name": "Wide", "inside": "1", "top": "1", "outside": "3",
                                "bottom": "2"}) is None
        assert app.profile["page"]["margin_scheme"] == "Wide"
        assert app.scheme_var.get() == "Wide (1:1:3:2)"
        g, _pages, _found = app.calculated()
        assert g.margins["outside"] > 2 * g.margins["inside"] - 1
        assert "above 0" in app.save_scheme({"name": "Bad", "inside": "0", "top": "1",
                                             "outside": "1", "bottom": "1"})
        assert "built-in" in app.save_scheme({"name": "canon", "inside": "1", "top": "1",
                                              "outside": "1", "bottom": "1"})
        app.delete_scheme()
        assert app.profile["page"]["margin_schemes"] == []
        assert app.profile["page"]["margin_scheme"] == "canon"
        dlg = app._scheme_dialog(None)
        dlg.destroy()
    finally:
        app.quit(force=True)


if __name__ == "__main__":
    if not HAVE_TK:
        sys.exit(0)
    run_tests(globals())
