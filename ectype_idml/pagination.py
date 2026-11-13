"""Pagination, masters and running heads for the exporter (moved out of export.py).

PaginationMixin is part of export.Exporter: it places the book's blocks on pages (layout.plan_pages),
gives each unit its story and section (recto rules, roman/arabic numbering, section markers for
the running heads) and builds the masters: A-Body, B-Opener, C-Front with their primary text
frames and folios, D-Display, E-Blank, and a copy of A-Body per part when the verso head is the
part's title. A running head from the section marker can carry only one font: when a head has
Hebrew or Greek the running-head font lacks (or can't be checked), such a unit gets a copy of
its master (R1-Body, R2-Front...) with the head as text, which takes the Hebrew and Greek
styles, and the window says so in a pop-up (an Alert line of the report). With the profile's
running_heads.script_masters off, the report only warns.
"""


class Alert(str):
    """A report line the window also shows in a pop-up after the export (something the
    export did on its own that the user should know about)."""


def _has_script(text):
    return any(is_hebrew(c) or is_greek(c) for c in text or "")

from . import fonts, frontmatter, layout, textcase
from .docx_reader import is_greek, is_hebrew
from .layout import _half
from .idml.model import Frame, Master, Paragraph, Run, Section, Story, TOCStyle


# A unit's last page by the estimate: fuller than this may run past it, emptier than this may
# be left blank (`_fit_note`).
FULL, EMPTY = 0.8, 0.2

# Styles that carry an opener's drop (`_sinks`).
SINK_STYLES = ("Chapter Title", "Contents Title", "Book Title", "Half Title")


class PaginationMixin:
    # ---- pagination and running heads ----

    def _short(self, title):
        """A unit's running head: its short title (or title), in the profile's case."""
        return self._head_text((self.settings.get("short_titles") or {}).get(title) or title)

    def _head_text(self, text):
        """Running-head text in the case the profile sets (as typed, title or sentence)."""
        case = ((self.profile["running_heads"].get("style") or {}).get("case")) or "as_typed"
        if case not in ("title", "sentence") or not text:
            return text
        if case == "sentence" and getattr(self, "_proper", None) is None:
            self._proper = textcase.proper_nouns(
                p.text for d in self.docs for p in d.paragraphs
                if len(p.text.split()) >= 20)
            # The contributors' names too (a "Foreword by" head names one).
            for c in (getattr(self, "info", None) or {}).get("creators") or ():
                self._proper |= {w for w in c.get("name", "").split() if w[:1].isupper()}
        return textcase.apply(text, case, self.profile["front_matter"].get("language", "en"),
                              getattr(self, "_proper", None) or ())

    def _verso_heads(self, rh, info, head, part=None):
        """The verso head's runs for each kind of verso head (head: the chapter's)."""
        h = self._head_text
        return {"book_title": [Run(h(info.get("short_title") or info["title"]))],
                "author": [Run(h(info["author"]))], "chapter": head,
                "part": [Run(part)] if part else head,
                "custom": [Run(h(rh.get("verso_custom") or ""))]}

    def _head_frames(self, verso, recto):
        """Running heads above the text area: verso and recto paragraphs' runs."""
        doc, m = self.doc, self.doc.margins
        out = []
        for side, runs in (("verso", verso), ("recto", recto)):
            if runs is None:
                continue
            left = m["outside"] if side == "verso" else m["inside"]
            right = doc.width - (m["inside"] if side == "verso" else m["outside"])
            out.append(Frame(side, (m["top"] - 27, left, m["top"] - 13, right),
                             [Paragraph("Running Head", runs)], key=side[0] + "head",
                             valign="BottomAlign"))
        return out

    def _paginate(self, blocks):
        """Pages, masters, sections and running heads; returns the page count."""
        doc = self.doc
        sink = self._opener_drop()
        items = []
        for b in blocks:
            kind = b.kind
            if b.sink is None:
                b.sink = 0 if kind in ("display", "part") else sink
            spare = b.spare if b.spare is not None else \
                (0 if kind in ("display", "part") else self._spare())
            est = b.pages or self._estimate(b.paras, b.sink)
            # How full the estimate leaves the last page, for the report (texts only; set
            # page counts and display pages are as they are).
            b.est, b.fill = est, None
            if not b.pages and kind not in ("display", "part"):
                b.fill = self._estimate(b.paras, b.sink, raw=True) - (est - 1)
            items.append((kind, est, spare, b.opens))
        placed, count, masters, first_body = layout.plan_pages(
            items, self.profile.get("chapters_open", "recto"))
        doc.stories, doc.sections = [], []
        optical = self.body_size if self.profile["typography"]["optical_margins"] else None
        rh = self.profile["running_heads"]
        part = None
        part_masters = []
        script_heads = []           # (marker, part title or None, pages) for R masters
        long_heads = []
        self._sinks(blocks)
        for n, (b, pl) in enumerate(zip(blocks, placed)):
            pages = list(range(pl.start, pl.start + pl.pages))
            doc.stories.append(Story(b.paras, pages, linked=True,
                                     optical_margins=optical, valign=b.valign))
            title = b.title if not b.title.startswith("(") and b.kind != "display" else ""
            marker = self._short(title)
            if marker and self._too_long(marker):
                long_heads.append(marker)
            body = first_body is not None and n >= first_body
            start = 1 if n == 0 or n == first_body else None
            # A blank verso before a unit belongs to the section before it.
            doc.sections.append(Section(pl.start, marker=marker,
                                        numbering="Arabic" if body else "LowerRoman",
                                        start=start))
            if b.kind == "part":
                part = self._short(b.title)
                part_masters.append(part)
            elif body and part and rh.get("verso") == "part":
                name = "P%d-Body" % len(part_masters)
                for i in pages:
                    if masters.get(i) == "A-Body":
                        masters[i] = name
            if _has_script(marker) and b.kind != "part":
                script_heads.append((marker, part if body else None, pages))
        doc.page_count = max(count, 1)
        doc.page_masters = masters
        self._fit_note(blocks, placed)
        if not doc.sections:
            doc.sections = [Section(0, start=1)]
        self._masters(part_masters)
        self._script_head_masters(script_heads, masters)
        if long_heads:
            self.report.append("Running heads too long for the page: %s. Give these a short "
                               "title in the book settings." % "; ".join(
                                   '"%s"' % h for h in long_heads))
        if self.contents_depth:
            levels = [("Chapter Title", 1, "Contents 1"), ("Part Title", 1, "Contents 1")]
            if self.contents_depth == "sections":
                levels.append(("Heading A", 2, "Contents 2"))
            lang = self.profile["front_matter"].get("language", "en")
            doc.toc_styles = [TOCStyle("Contents", frontmatter.texts(lang)["contents"],
                                       "Contents Title", levels)]
        est = sum(i[1] for i in items)
        blanks = sum(1 for v in masters.values() if v == "E-Blank")
        g, m = self.geo, doc.margins
        spare = self._spare()
        self.report.append("%d pages: about %d of text, %d blank verso%s." % (
            doc.page_count, est, blanks, "" if blanks == 1 else "s"))
        if spare == 1:
            self.report.append("Each chapter ends with a spare page. Where it stays empty, delete "
                               "it together with the blank page after it, or give it the E-Blank "
                               "master, so chapters keep their sides.")
        elif spare == 2:
            self.report.append("Each chapter ends with two spare pages. Delete unused ones two at "
                               "a time, so chapters keep their sides.")
        else:
            self.report.append("No spare pages: InDesign adds pages to a chapter whose text runs "
                               "over (then check that later chapters still open on a recto); "
                               "Affinity doesn't, so in Affinity add pages to a chapter whose "
                               "text runs over, two at a time.")
        self.report.append(self._leading_note())
        self.report.append(
            "Margins (in): top %.3g, bottom %.3g, inside %.3g, outside %.3g; text %d lines of "
            "%g pt, about %d characters per line."
            % (m["top"] / 72, m["bottom"] / 72, m["inside"] / 72, m["outside"] / 72, g.lines,
               self.body_lead, round(g.cpl)))
        return doc.page_count

    def _spare(self):
        try:
            return max(0, min(2, int(self.profile["page"].get("spare_pages") or 0)))
        except (TypeError, ValueError):
            return 0

    def _too_long(self, text):
        attrs = self._resolved_attrs("Running Head")
        size = attrs.get("PointSize", self.body_size)
        return len(text) * size * self.avg_width * 1.1 > self.measure * 0.8

    def _opener_drop(self):
        """How far chapter titles (and the contents title) are lowered: the profile's
        page.opener_drop in points, else six body lines."""
        drop = (self.profile.get("page") or {}).get("opener_drop")
        return _half(drop) if drop else _half(self.body_lead * 6)

    def _fit_note(self, blocks, placed):
        """Name the units whose estimated last page is nearly full (they may run past it in
        Affinity and DesignCraft, which don't add pages; InDesign adds them itself) or nearly
        empty (the page may be left blank). The estimate can't know every program's line
        breaks, nor a font substituted on another computer."""
        from .idml.writer import page_names
        names = page_names(self.doc)
        full, empty = [], []
        for b, pl in zip(blocks, placed):
            fill = b.fill
            if fill is None or not pl.pages:
                continue
            last = names[min(pl.start + b.est - 1, len(names) - 1)]
            title = b.title if not b.title.startswith("(") else b.kind
            if fill > FULL:
                full.append("%s (to page %s)" % (title, last))
            elif fill < EMPTY and b.est > 1:
                empty.append("%s (page %s)" % (title, last))
        if full:
            self.report.append(
                "Check where these end: their last page is nearly full by the estimate, so "
                "they may run past it: %s. InDesign adds a page itself; in Affinity or "
                "DesignCraft, add a page if the text frame shows more text." % "; ".join(full))
        if empty:
            self.report.append(
                "Check these last pages: by the estimate they hold only a line or two, and may "
                "be left empty: %s. Leave an empty page in place, with the E-Blank master "
                "applied so it has no running head; deleting a single page moves every later "
                "chapter to the other side." % "; ".join(empty))

    def _sinks(self, blocks):
        """Lower each opener's first paragraph by its block's sink, in the paragraph style
        (Chapter Title, Contents Title, Book Title, Half Title), so the
        drop moves with the title if pages are added or removed, and every text frame is full
        height. InDesign ignores Space Before at the top of a frame, so the style also has an
        invisible rule above, kept in the frame, which pushes the text down (InDesign);
        Affinity ignores the rule and uses the Space Before when the style is set to apply it
        at the column top. A first paragraph in another style gets the same settings locally."""
        doc = self.doc
        claimed = {}
        for b in blocks:
            if not b.sink or not b.paras:
                continue
            p = b.paras[0]
            attrs, _f, _l = doc.resolved(p.style)
            if attrs.get("RuleAbove") and abs(attrs.get("SpaceBefore", 0) - b.sink) < 0.5:
                continue                       # its style carries this sink already
            drop = self._sink_attrs(b.sink, attrs.get("PointSize", self.body_size))
            st = doc.style(p.style)
            if st is not None and p.style in SINK_STYLES and p.style not in claimed:
                st.attrs.update(drop)
                claimed[p.style] = b.sink
                for child in doc.paragraph_styles:
                    if child.based_on == p.style and child.name not in SINK_STYLES:
                        child.attrs.setdefault("SpaceBefore", 0)
                        child.attrs["RuleAbove"] = False
            else:
                p.attrs.update(drop)
        if claimed:
            self.report.append(
                "Chapter openings are lowered by their paragraph style (%s), not by a shorter "
                "text frame, so the drop moves with the title. InDesign shows it as it is. In "
                "Affinity, set Space Before in those styles to apply \u201cOnly at column "
                "top\u201d, or the titles start at the top of the page. If pages are added or "
                "removed, apply B-Opener to the page a chapter now starts on (and A-Body to "
                "the page it left): a page keeps its master when the text moves."
                % ", ".join(sorted(claimed)))

    @staticmethod
    def _sink_attrs(sink, size):
        """Space Before (Affinity) and an invisible rule above kept in the frame (InDesign),
        both lowering the first baseline by sink (the rule's offset counts from the
        baseline, so it adds the type's ascent)."""
        return {"SpaceBefore": sink, "RuleAbove": True, "RuleAboveLineWeight": 0,
                "RuleAboveTint": 0, "RuleAboveOffset": _half(sink + size * 0.75),
                "KeepRuleAboveInFrame": True}

    def _masters(self, parts):
        """A-Body, B-Opener and C-Front carry text (each its own primary text frames, so a
        chapter threads from B into A); D-Display and E-Blank are empty. Running heads follow
        the profile: the recto head is the section marker (the chapter's short title), the
        verso head the book title, author, chapter, part or custom text; C-Front shows the
        unit's title on both sides. Parts with part verso heads get a master each (P1-Body...),
        a copy of A-Body with the part's title."""
        doc = self.doc
        rh = self.profile["running_heads"]
        info = self.info
        marker = [Run(special="section_marker")]
        verso_kind = rh.get("verso", "book_title")
        verso = self._verso_heads(rh, info, marker).get(verso_kind) if verso_kind != "part" \
            else None
        recto = [Run(self._head_text(rh.get("recto_custom") or ""))] \
            if rh.get("recto") == "custom" else marker

        frames = self._master_frames
        doc.masters = [
            Master("A", "Body", frames=frames(True, verso or marker, recto)),
            Master("B", "Opener", frames=frames(not rh.get("suppress_on_openers", True),
                                                verso or marker, recto)),
            Master("C", "Front", frames=frames(True, marker, marker)),
            Master("D", "Display", frames=[] if rh.get("suppress_on_display", True)
                   else self._head_frames(verso or marker, recto)),
            Master("E", "Blank", frames=[] if rh.get("suppress_on_blanks", True)
                   else self._head_frames(verso or marker, recto))]
        if verso_kind == "part":
            for k, title in enumerate(parts, 1):
                doc.masters.append(Master("P%d" % k, "Body",
                                          frames=frames(True, [Run(title)], recto)))

    def _master_frames(self, heads=True, verso_runs=None, recto_runs=None):
        """A text master's frames: primary text frames and folios on both sides, and the
        running heads if wanted."""
        doc, m = self.doc, self.doc.margins
        top, bottom = m["top"], doc.height - m["bottom"]
        out = []
        for side in ("verso", "recto"):
            left = m["outside"] if side == "verso" else m["inside"]
            right = doc.width - (m["inside"] if side == "verso" else m["outside"])
            out.append(Frame(side, (top, left, bottom, right), [], primary=True))
            out.append(Frame(side, (bottom + 14, left, bottom + 28, right),
                             [Paragraph("Folio", [Run(special="page_number")])],
                             key="folio"))
        if heads:
            out += self._head_frames(verso_runs, recto_runs)
        return out

    def _script_head_lack(self, heads):
        """Whether the running-head font lacks the Hebrew or Greek in these heads (or isn't
        installed here, so it couldn't be checked). Returns None when it has them, else
        (scripts, font, lack): "Hebrew", the font's name and why, for the messages."""
        font = self.doc.style("Running Head").font or self.fonts["body"]
        found = fonts.find_font(font)
        chars = {c for h in heads for c in h if is_hebrew(c) or is_greek(c)}
        missing = [c for c in chars if not (found and fonts.has_char(found, ord(c)))]
        if found and not missing:
            return None                       # the font has the letters
        scripts = " and ".join(n for n, test in (("Hebrew", is_hebrew), ("Greek", is_greek))
                               if any(test(c) for c in (missing or chars)))
        lack = ("doesn't have the %s letters" % scripts) if found else \
            ("isn't installed on this computer, so whether it has the %s letters couldn't be "
             "checked" % scripts)
        return scripts, font, lack

    def _script_head_masters(self, units, masters):
        """Units whose running head has Hebrew or Greek: a copy of their A-Body (or part's
        P-Body) or C-Front master with the head written as text instead of the section
        marker, so _generated_scripts can give the Hebrew its style."""
        if not units:
            return
        doc, rh, info = self.doc, self.profile["running_heads"], self.info
        heads = [u[0] for u in units]
        lack = self._script_head_lack(heads)
        if lack is None:
            return                            # the head font has the letters: one master
        scripts, font, why = lack
        listed = "; ".join("\u201c%s\u201d" % h for h in heads)
        if not rh.get("script_masters"):
            self.report.append(
                "Running heads with %s: %s. A running head can use only one font, and the "
                "running-head font (%s) %s, so these heads may print as empty boxes. Choose a "
                "running-head font that has them (Running Heads > Running Head Style), or "
                "turn on \u201cSeparate masters for heads with Hebrew or Greek\u201d there."
                % (scripts, listed, font, why))
            return
        verso_kind = rh.get("verso", "book_title")
        custom_recto = rh.get("recto") == "custom"
        names = []
        for k, (marker, part, pages) in enumerate(units, 1):
            head = [Run(marker)]
            recto = [Run(self._head_text(rh.get("recto_custom") or ""))] if custom_recto \
                else head
            verso = self._verso_heads(rh, info, head, part).get(verso_kind, head)
            made = {}
            for i in pages:
                base = masters.get(i)
                if base in ("A-Body",) or (base or "").startswith("P"):
                    kind, frames = "Body", (verso, recto)
                elif base == "C-Front":
                    kind, frames = "Front", (head, head)
                else:
                    continue                  # openers, display and blank pages: no heads
                if kind not in made:
                    made[kind] = Master("R%d" % k, kind,
                                        frames=self._master_frames(True, *frames))
                    doc.masters.append(made[kind])
                    if made[kind].name not in names:
                        names.append(made[kind].name)
                masters[i] = made[kind].name
        if names:
            self.report.append(Alert(
                "Running heads with %s: %s. The running-head font (%s) %s, and a running "
                "head can use only one font, so these heads would print as empty boxes. "
                "Instead, each of these chapters got a master of its own (%s) with its head "
                "written as text, so the %s is set in the %s font. To change such a head, "
                "edit it on its master. To keep one master for every chapter, choose a "
                "running-head font that has the %s letters (Running Heads > Running Head "
                "Style), or turn off \u201cSeparate masters for heads with Hebrew or "
                "Greek\u201d there." % (scripts, listed, font, why, ", ".join(names), scripts,
                                         scripts, scripts)))
