"""Style map: Word style -> IDML style and the role it plays in the book.

Styles are matched by name, so one mapping covers every file of a book. Word writes its
built-in style names in English in the file ("heading 1", "footnote text") whatever the
language of Word, so the defaults below work for any manuscript.

Lookup order: the profile's own map, then the defaults for Word's built-ins, then the style
the unknown style is based on (a custom "Chapter Head" based on Heading 1 is a chapter title),
then body text. The last two are reported as warnings.
"""

from dataclasses import dataclass

# Roles. The outline uses part/chapter/book_title/subtitle/author; "toc" paragraphs are
# replaced by the layout program's own contents; "skip" never reaches the book.
ROLES = ("body", "part", "chapter", "heading", "book_title", "subtitle", "author", "quote",
         "verse", "list", "note", "caption", "toc", "toc_title", "skip")

# Word's built-in paragraph styles (normalized name -> IDML style, role, heading level).
PARAGRAPH_DEFAULTS = {
    "normal": ("Body", "body"),
    "body text": ("Body", "body"),
    "body text 2": ("Body", "body"),
    "body text 3": ("Body", "body"),
    "body text first indent": ("Body", "body"),
    "body text first indent 2": ("Body", "body"),
    "body text indent": ("Body", "body"),
    "plain text": ("Body", "body"),
    "no spacing": ("Body", "body"),
    "normal (web)": ("Body", "body"),
    "normal indent": ("Body", "body"),
    "title": ("Book Title", "book_title"),
    "author": ("Author", "author"),     # not built in, but the usual name
    "autor": ("Author", "author"),
    "subtitle": ("Book Subtitle", "subtitle"),
    "heading 1": ("Chapter Title", "chapter"),
    "heading 2": ("Heading A", "heading", 1),
    "heading 3": ("Heading B", "heading", 2),
    "heading 4": ("Heading C", "heading", 3),
    "heading 5": ("Heading C", "heading", 3),
    "heading 6": ("Heading C", "heading", 3),
    "heading 7": ("Heading C", "heading", 3),
    "heading 8": ("Heading C", "heading", 3),
    "heading 9": ("Heading C", "heading", 3),
    "quote": ("Block Quote", "quote"),
    "intense quote": ("Block Quote", "quote"),
    "block text": ("Block Quote", "quote"),
    "footnote text": ("Footnote", "note"),
    "endnote text": ("Footnote", "note"),
    "caption": ("Caption", "caption"),
    "table of figures": ("Body", "body"),
    "list paragraph": ("List", "list"),
    "list": ("List", "list"),
    "list bullet": ("List Bullet", "list"),
    "list bullet 2": ("List Bullet", "list"),
    "list bullet 3": ("List Bullet", "list"),
    "list number": ("List Number", "list"),
    "list number 2": ("List Number", "list"),
    "list number 3": ("List Number", "list"),
    "list continue": ("List", "list"),
    "bibliography": ("Bibliography", "body"),
    "toc heading": ("Contents Title", "toc_title"),
    "header": (None, "skip"),
    "footer": (None, "skip"),
}
PARAGRAPH_DEFAULTS.update({"toc %d" % i: ("Contents %d" % min(i, 3), "toc") for i in range(1, 10)})

# Word's built-in character styles (normalized name -> IDML character style, or None for none).
CHARACTER_DEFAULTS = {
    "default paragraph font": None,
    "emphasis": "Italic",
    "subtle emphasis": "Italic",
    "intense emphasis": "Bold Italic",
    "strong": "Bold",
    "book title": "Italic",
    "footnote reference": "Footnote Reference",
    "endnote reference": "Footnote Reference",
    "hyperlink": "Hyperlink",
    "followedhyperlink": "Hyperlink",
    "subtle reference": "Small Caps",
    "intense reference": "Small Caps",
    "placeholder text": None,
    "page number": None,
}

# How Word shows its built-in names (they are lower case in the file).
_DISPLAY = {"normal": "Normal", "toc heading": "TOC Heading", "followedhyperlink": "FollowedHyperlink",
            "normal (web)": "Normal (Web)"}


def norm(name):
    return " ".join((name or "").split()).casefold()


def display_name(name):
    """The name as Word shows it ("heading 1" -> "Heading 1")."""
    key = norm(name)
    if key in _DISPLAY:
        return _DISPLAY[key]
    if key in PARAGRAPH_DEFAULTS or key in CHARACTER_DEFAULTS:
        if key.startswith("toc "):
            return "TOC " + key[4:]
        return " ".join(w[:1].upper() + w[1:] for w in key.split(" "))
    return name


@dataclass
class Mapping:
    word: str             # Word style name (as Word shows it)
    idml: str             # IDML style name, or None (no style / not carried over)
    role: str
    level: int = 0        # heading level for role "heading" (1 = first level below chapter)
    source: str = "default"   # profile, default, based on <name>, outline level n, linked, own,
                              # fallback, formatting (a heading found by its look), book
    warning: bool = False
    feats: tuple = ()         # run features a formatting heading's look is made of (dropped)


def _entry(value):
    """A profile map entry: {"idml": ..., "role": ..., "level": ...} or just an IDML name."""
    if value is None:
        return None, None, 0            # mapped to nothing (no character style)
    if isinstance(value, str):
        return value, None, 0
    return value.get("idml"), value.get("role"), int(value.get("level") or 0)


class StyleMap:
    def __init__(self, paragraph=None, character=None, formats=None):
        """paragraph / character: the profile's maps {Word style name: entry}; formats: the
        book's map for headings found by formatting {"[14 pt bold centered]": entry}."""
        self.paragraph = {norm(k): v for k, v in (paragraph or {}).items()}
        self.character = {norm(k): v for k, v in (character or {}).items()}
        self.formats = dict(formats or {})

    @classmethod
    def from_profile(cls, profile, settings=None):
        sm = profile.get("style_map", {}) if profile else {}
        return cls(sm.get("paragraph"), sm.get("character"),
                   (settings or {}).get("format_map"))

    def prepare(self, docs):
        """Find the headings set by formatting across the book's files (formatheads.plan),
        once for this set of files."""
        from .formatheads import plan
        self._plan = plan(docs, lambda d, p: self.paragraph_style(d, d.para_style(p)).role)
        self._planned = {id(d) for d in docs}
        self._docs = list(docs)

    def _plan_for(self, doc):
        if id(doc) not in getattr(self, "_planned", ()) or doc not in self._docs:
            self.prepare([doc])
        return self._plan

    @property
    def book_title_line(self):
        """A first line that opens several files: the book's title (or None)."""
        return getattr(self, "_plan", None) and self._plan.book_title

    def format_groups(self, doc):
        """Headings found by formatting in doc: (the groups with members there, {paragraph
        index: group})."""
        pl = self._plan_for(doc)
        by_para = pl.by_doc.get(id(doc), {})
        groups = [g for g in pl.groups if g.members(doc)]
        return groups, by_para

    def repeated_title(self, doc, p):
        """The book's title repeated at the top of a file, before the file's own title."""
        return p.index in self._plan_for(doc).repeats.get(id(doc), ())

    def paragraph_mapping(self, doc, p):
        """Mapping for one paragraph: its style's, unless it is a heading found by formatting
        (then the group's, or what the book's map says for the group)."""
        if getattr(p, "where", "body") == "body":
            from .formatheads import feats_of
            if self.repeated_title(doc, p):
                return Mapping("[book title repeated in a file]", None, "skip", 0,
                               "formatting", False)
            g = self.format_groups(doc)[1].get(p.index)
            if g is not None:
                feats = feats_of(p) if p.look else ()
                if g.name in self.formats:
                    idml, role, level = _entry(self.formats[g.name])
                    role = role or g.role
                    if role == "heading" and not level:
                        level = g.level
                    return Mapping(g.name, idml, role, level, "book", False, feats)
                return Mapping(g.name, g.idml, g.role, g.level, "formatting", True, feats)
        return self.paragraph_style(doc, doc.para_style(p))

    def paragraph_style(self, doc, style_id):
        """Mapping for a paragraph style of a DocxFile."""
        st = doc.styles.get(style_id)
        name = st.name if st else (style_id or "Normal")
        word = display_name(name)
        chain = doc.style_chain(style_id) if st else []
        for i, sid in enumerate(chain or [None]):
            key = norm(doc.styles[sid].name) if sid else norm(name)
            if key in self.paragraph:
                idml, role, level = _entry(self.paragraph[key])
                role = role or _default_role(key) or "body"
                return self._found(word, idml, role, level, "profile", i, doc, sid)
            if key in PARAGRAPH_DEFAULTS:
                d = PARAGRAPH_DEFAULTS[key]
                return self._found(word, d[0], d[1], d[2] if len(d) > 2 else 0, "default", i, doc, sid)
        # Not known by name: a custom style with an outline level is a heading.
        lvl = doc.style_outline_level(style_id) if st else None
        if lvl is not None:
            if lvl == 0:
                return Mapping(word, "Chapter Title", "chapter", 0, "outline level 1", True)
            return Mapping(word, "Heading " + "ABC"[min(lvl, 3) - 1], "heading", min(lvl, 3),
                           "outline level %d" % (lvl + 1), True)
        return Mapping(word, "Body", "body", 0, "fallback", True)

    def _found(self, word, idml, role, level, source, depth, doc, sid):
        if depth == 0:
            return Mapping(word, idml, role, level, source)
        # Inherited from a parent: a custom style keeps its own name in IDML, except headings
        # and roles the outline relies on, which keep the parent's role.
        parent = display_name(doc.styles[sid].name)
        return Mapping(word, word if role in ("body", "quote", "list", "verse", "caption") else idml,
                       role, level, "based on " + parent, True)

    def character_style(self, doc, style_id):
        st = doc.styles.get(style_id)
        name = st.name if st else style_id
        word = display_name(name)
        if st and st.linked and doc.styles.get(st.linked, None) and \
                doc.styles[st.linked].type == "paragraph":
            # "Heading 1 Char" and the like: Word's half of a linked style, not a real
            # character style.
            return Mapping(word, None, "skip", 0, "linked")
        key = norm(name)
        if key in self.character:
            idml, _role, _lvl = _entry(self.character[key])
            return Mapping(word, idml, "char", 0, "profile")
        if key in CHARACTER_DEFAULTS:
            return Mapping(word, CHARACTER_DEFAULTS[key], "char", 0, "default")
        # A custom character style is kept under its own name, with its own settings.
        return Mapping(word, word, "char", 0, "own")


def _default_role(key):
    d = PARAGRAPH_DEFAULTS.get(key)
    return d[1] if d else None
