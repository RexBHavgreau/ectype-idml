"""Installed fonts: finding a family's file, and the average width of its characters.

The measure (characters per line) is worked out from the body font itself: the average advance
width of the manuscript's own characters, read from the font file with fontTools. Fonts are
looked for in the system and per-user font folders of the machine running the tool.
"""

import os
import sys
import threading
from pathlib import Path

FONT_EXTS = {".ttf", ".otf", ".ttc", ".otc"}
# Average character width, in ems, when the font isn't installed: a typical book serif with
# English text.
FALLBACK_WIDTH = 0.42
SAMPLE = ("The covenant formula recurs throughout the prophets with small but telling changes. "
          "Each change of wording marks a shift in the relationship the text describes, and a "
          "careful reader notices when the order of its two halves is reversed.")


def font_dirs():
    dirs = []
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs.append(Path(windir) / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    elif sys.platform == "darwin":
        dirs += [Path("/System/Library/Fonts"), Path("/Library/Fonts"),
                 Path.home() / "Library" / "Fonts"]
    else:
        dirs += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
                 Path.home() / ".local" / "share" / "fonts", Path.home() / ".fonts"]
    return [d for d in dirs if d.is_dir()]


_INDEX = None
_LOCK = threading.RLock()
_NAMES = {}                 # family (lower case) -> the family's name as the font gives it
_FACES = {}                 # (family, style) (lower case) -> the style's name as the font gives it
SCRIPT_LETTERS = {"hebrew": 0x05D0, "greek": 0x03B1}   # alef, alpha


def _names(font):
    """(family, style) names of a font: typographic names (16, 17) first, else 1, 2."""
    name = font["name"]

    def get(*ids):
        for i in ids:
            rec = name.getDebugName(i)
            if rec:
                return rec
        return None
    return get(16, 1), get(17, 2) or "Regular"


def font_index(dirs=None):
    """{family (lower case): {style (lower case): (path, font number)}} of installed fonts.
    Read once (the window reads it in the background at startup)."""
    if dirs is None:
        with _LOCK:
            if _INDEX is None:
                _read_index()
            return _INDEX
    return _read_index(dirs)


def _read_index(dirs=None):
    global _INDEX
    try:
        from fontTools.ttLib import TTCollection, TTFont
    except ImportError:
        return {}
    index = {}
    for d in dirs or font_dirs():
        for root, _subdirs, files in os.walk(d):
            for f in files:
                if os.path.splitext(f)[1].lower() not in FONT_EXTS:
                    continue
                path = os.path.join(root, f)
                try:
                    if f.lower().endswith((".ttc", ".otc")):
                        fonts = list(enumerate(TTCollection(path, lazy=True).fonts))
                    else:
                        fonts = [(0, TTFont(path, lazy=True))]
                    for n, font in fonts:
                        fam, style = _names(font)
                        if fam:
                            index.setdefault(fam.casefold(), {}).setdefault(
                                style.casefold(), (path, n))
                            _NAMES.setdefault(fam.casefold(), fam)
                            _FACES.setdefault((fam.casefold(), style.casefold()), style)
                except Exception:
                    continue
    if dirs is None:
        _INDEX = index
    return index


_SCRIPTS = None             # {script: set of families (lower case) that have its letters}


def families(script=None, index=None):
    """Installed font families, sorted, as their fonts name them; with script ("hebrew",
    "greek"), only families whose regular font has that script's letters."""
    index = index if index is not None else font_index()
    keys = list(index)
    if script:
        have = _script_families(index)[script]
        keys = [k for k in keys if k in have]
    return sorted((_NAMES.get(k, k) for k in keys), key=str.casefold)


def _script_families(index):
    """Which families have Hebrew and Greek letters: one look at each family's regular font
    (its character map), done once."""
    global _SCRIPTS
    with _LOCK:
        if _SCRIPTS is not None and index is _INDEX:
            return _SCRIPTS
        out = {s: set() for s in SCRIPT_LETTERS}
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            return out
        for key in index:
            found = find_font(key, index=index)
            if not found:
                continue
            try:
                path, number = found
                font = TTFont(path, fontNumber=number, lazy=True)
                cmap = font["cmap"]
                for script, cp in SCRIPT_LETTERS.items():
                    if any(t.isUnicode() and cp in t.cmap for t in cmap.tables):
                        out[script].add(key)
            except Exception:
                continue
        if index is _INDEX:
            _SCRIPTS = out
        return out


def has_char(found, codepoint):
    try:
        from fontTools.ttLib import TTFont
        path, number = found
        cmap = TTFont(path, fontNumber=number, lazy=True).getBestCmap() or {}
        return codepoint in cmap
    except Exception:
        return False


def regular_face(family, index=None):
    """The name of a family's upright, normal-weight face as installed: "Regular" mostly, but
    "Medium" in the Culmus Hebrew fonts (Taamey David CLM...), "Roman" or "Book" in others.
    InDesign wants the face's own name. "Regular" when the family isn't installed here."""
    key = (family or "").casefold()
    styles = (index if index is not None else font_index()).get(key)
    if not styles:
        return "Regular"
    for s in ("regular", "roman", "book", "normal", "medium", "plain"):
        if s in styles:
            return _FACES.get((key, s), s.title())
    return "Regular"


def _face_kind(name):
    """(bold, italic) of a face name: "Bold Italic" -> (True, True), "Medium" -> (False, False)."""
    n = (name or "").casefold()
    bold = any(w in n for w in ("bold", "black", "heavy"))
    italic = any(w in n for w in ("italic", "oblique", "slanted"))
    return bold, italic


def matching_face(family, face, index=None):
    """The installed face of family that matches face (bold/italic), by the family's own name
    for it ("Italic" in one font may be "Medium Oblique" in another). Returns (name, exact):
    exact False when the family has no such face and its upright one is given instead; (None,
    True) when the family isn't installed here (the face is left as it is)."""
    key = (family or "").casefold()
    styles = (index if index is not None else font_index()).get(key)
    if not styles:
        return None, True
    want = _face_kind(face)
    names = {s: _FACES.get((key, s), s.title()) for s in styles}
    if want == (False, False):
        return regular_face(family, index), True
    same = [names[s] for s in sorted(styles) if _face_kind(s) == want]
    if same:
        same.sort(key=lambda n: (n.casefold() not in ("italic", "bold", "bold italic"), len(n)))
        return same[0], True
    if want[0]:                       # bold italic missing: bold, then upright
        bold = [names[s] for s in sorted(styles) if _face_kind(s) == (True, False)]
        if bold:
            return sorted(bold, key=len)[0], False
    return regular_face(family, index), False


def find_font(family, style="Regular", index=None):
    """(path, font number) of an installed font, or None."""
    if not family:
        return None
    styles = (index if index is not None else font_index()).get(family.casefold())
    if not styles:
        return None
    for s in (style.casefold(), "regular", "roman", "book", "normal"):
        if s in styles:
            return styles[s]
    return sorted(styles.values())[0]


def average_width(found, text=None):
    """Average advance width of the characters of text (the manuscript's, or a sample), in
    ems, from the font file. Characters the font lacks count at the average of the rest."""
    from fontTools.ttLib import TTFont
    path, number = found
    font = TTFont(path, fontNumber=number, lazy=True)
    cmap = font.getBestCmap() or {}
    hmtx = font["hmtx"]
    upem = font["head"].unitsPerEm
    text = text or SAMPLE
    total, n, missing = 0, 0, 0
    for ch in text:
        if ch in "\n\t":
            continue
        glyph = cmap.get(ord(ch))
        if glyph is None:
            missing += 1
            continue
        total += hmtx[glyph][0]
        n += 1
    if not n:
        return FALLBACK_WIDTH
    return total / n / upem


def x_height(found):
    """The font's x-height in ems (OS/2 table), or None."""
    try:
        from fontTools.ttLib import TTFont
        path, number = found
        font = TTFont(path, fontNumber=number, lazy=True)
        os2 = font["OS/2"]
        xh = getattr(os2, "sxHeight", 0) if os2.version >= 2 else 0
        if not xh:
            from fontTools.pens.boundsPen import BoundsPen
            gs = font.getGlyphSet()
            name = (font.getBestCmap() or {}).get(ord("x"))
            if not name:
                return None
            pen = BoundsPen(gs)
            gs[name].draw(pen)
            xh = pen.bounds[3] if pen.bounds else 0
        return xh / font["head"].unitsPerEm if xh else None
    except Exception:
        return None


# Book fonts, in order of preference: the first installed is the body font when the profile
# sets none. Windows always has Palatino Linotype, Book Antiqua, Georgia and Cambria.
BOOK_FONTS = ["Minion Pro", "Arno Pro", "Adobe Garamond Pro", "Garamond Premier Pro",
              "Adobe Caslon Pro", "Sabon LT Std", "Sabon", "EB Garamond", "Crimson Pro",
              "Crimson Text", "Libertinus Serif", "Linux Libertine O", "Palatino Linotype",
              "Book Antiqua", "Georgia", "Cambria", "Times New Roman"]
SCRIPT_FONTS = {"hebrew": ["SBL Hebrew", "Taamey David CLM", "Ezra SIL", "Cardo",
                           "Times New Roman"],
                "greek": ["SBL Greek", "Gentium Plus", "Gentium Book Plus", "Cardo",
                          "Palatino Linotype", "Times New Roman"]}


def book_font(index=None):
    """The first installed book font (Minion Pro if none of them is installed here)."""
    for name in BOOK_FONTS:
        if find_font(name, index=index):
            return name
    return BOOK_FONTS[0]


def script_font(script, index=None):
    """The first installed font for Hebrew or Greek that has its letters (the first of the list
    if none is installed here)."""
    letters = {"hebrew": 0x05D0, "greek": 0x1F00}[script]
    for name in SCRIPT_FONTS[script]:
        found = find_font(name, index=index)
        if found and has_char(found, letters):
            return name
    return SCRIPT_FONTS[script][0]
